from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram.ext import Application

from .config import Settings
from .tools import ToolRegistry


logger = logging.getLogger(__name__)


class MorningBriefingService:
    def __init__(self, settings: Settings, tools: ToolRegistry) -> None:
        self.settings = settings
        self.tools = tools
        self._application: Application | None = None
        self._task: asyncio.Task[None] | None = None
        self._last_sent_date: datetime.date | None = None
        self._known_telegram_chat_id = settings.reminder_telegram_chat_id
        self._timezone = ZoneInfo(settings.timezone)

    async def start(self, application: Application) -> None:
        if self._task or not self.settings.morning_briefing_enabled:
            return

        self._application = application
        self._task = asyncio.create_task(self._run_loop(), name="morning-briefing-loop")
        logger.info("Morning briefing loop started")

    async def stop(self) -> None:
        if not self._task:
            return

        task = self._task
        self._task = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info("Morning briefing loop stopped")

    def register_chat(self, chat_id: int) -> None:
        if self.settings.reminder_telegram_chat_id is None:
            self._known_telegram_chat_id = chat_id

    async def _run_loop(self) -> None:
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Morning briefing tick failed")
            await asyncio.sleep(30)

    async def _tick(self) -> None:
        now = datetime.now(self._timezone)
        if self._last_sent_date == now.date():
            return
        if now.hour != self.settings.morning_briefing_hour:
            return
        if now.minute != self.settings.morning_briefing_minute:
            return

        message = await self._build_briefing(now)
        if not message:
            return

        await self._deliver(message)
        self._last_sent_date = now.date()
        logger.info("Morning briefing sent date=%s", self._last_sent_date)

    async def _build_briefing(self, now: datetime) -> str:
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        calendar_result = await self.tools.calendar_list_events(
            start_iso=start_of_day.isoformat(),
            end_iso=end_of_day.isoformat(),
        )
        events = calendar_result.get("events", []) if not calendar_result.get("error") else []

        tasks = await self.tools.list_urgent_tasks(
            now=start_of_day,
            deadline_before=end_of_day,
        )
        tasks_due_today = [
            task
            for task in tasks
            if task["deadline_at"].date() == now.date()
        ]
        tasks_due_today.sort(key=lambda item: item["deadline_at"])

        note = await self._personal_note(events, tasks_due_today)
        density = self._density_text(len(events), len(tasks_due_today))
        schedule_line = self._schedule_line(events)
        tasks_line = self._tasks_line(tasks_due_today)

        lines = [
            f"Pagi! {self.settings.morning_briefing_personal_greeting}. Hari ini {density}.",
            schedule_line,
            tasks_line,
        ]
        if note:
            lines.append(note)

        return "\n".join(lines[:5])

    async def _personal_note(self, events: list[dict], tasks: list[dict]) -> str | None:
        focus_name = None
        if tasks:
            focus_name = tasks[0]["task_name"]
        elif events:
            focus_name = events[0].get("summary")

        if focus_name and self.settings.notion_api_key:
            try:
                context = await self.tools.notion_extract_task_context(focus_name)
            except Exception:
                logger.exception("Morning briefing failed to load notion context")
                context = {}
            context_text = context.get("context")
            if context_text:
                return f"Catatan: {self._truncate(context_text, 90)}"

        if tasks and not events:
            return "Catatan: Hari ini lebih enak dipush dari task dulu, slot waktunya masih longgar."
        if events and not tasks:
            return "Catatan: Agenda dominan, jadi jaga transisi antar jam biar nggak keburu capek duluan."
        if events and tasks:
            return "Catatan: Ada agenda dan deadline bareng, jadi paling aman beresin prioritas utama sebelum siang."
        return "Catatan: Hari ini kelihatan ringan, bagus buat nyicil hal yang sempat ketahan."

    async def _deliver(self, message: str) -> None:
        if not self._application or not self._known_telegram_chat_id:
            raise ValueError("Telegram target chat is not configured for morning briefing.")
        await self._application.bot.send_message(
            chat_id=self._known_telegram_chat_id,
            text=message,
        )

    @staticmethod
    def _density_text(event_count: int, task_count: int) -> str:
        total = event_count + task_count
        if total == 0:
            return "kelihatan cukup ringan"
        if total <= 2:
            return "masih cukup santai"
        if total <= 5:
            return "lumayan keisi"
        return "bakal padat"

    def _schedule_line(self, events: list[dict]) -> str:
        if not events:
            return "Jadwal hari ini: belum ada event yang nyangkut."

        chunks = []
        for event in events[:3]:
            start_text = self._event_start_text(event.get("start"))
            summary = event.get("summary") or "Tanpa judul"
            chunks.append(f"{start_text} {summary}")
        suffix = " +" if len(events) > 3 else ""
        return f"Jadwal: {' | '.join(chunks)}{suffix}"

    @staticmethod
    def _tasks_line(tasks: list[dict]) -> str:
        if not tasks:
            return "Prioritas tugas hari ini: belum ada yang due hari ini."

        items = [task["task_name"] for task in tasks[:3]]
        suffix = " +" if len(tasks) > 3 else ""
        return f"Prioritas tugas hari ini: {', '.join(items)}{suffix}"

    def _event_start_text(self, value: str | None) -> str:
        if not value or "T" not in value:
            return "All-day"
        parsed = self.tools._parse_datetime(value)
        if not parsed:
            return "??:??"
        return parsed.strftime("%H:%M")

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 3].rstrip() + "..."
