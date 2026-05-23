from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from telegram.ext import Application

from .config import Settings
from .tools import ToolRegistry


logger = logging.getLogger(__name__)


@dataclass
class TaskNagState:
    task_key: str
    source: str
    task_id: str
    task_name: str
    deadline_at: datetime
    reminder_count: int = 0
    waiting_for_response: bool = False
    response_due_at: datetime | None = None
    snooze_until: datetime | None = None
    chat_id: int | None = None
    local_completed: bool = False
    last_message_at: datetime | None = None


class DynamicNaggingService:
    def __init__(self, settings: Settings, tools: ToolRegistry) -> None:
        self.settings = settings
        self.tools = tools
        self._application: Application | None = None
        self._task: asyncio.Task[None] | None = None
        self._states: dict[str, TaskNagState] = {}
        self._pending_task_by_chat: dict[int, str] = {}
        self._latest_tasks: dict[str, dict[str, Any]] = {}
        self._next_provider_scan_at: datetime | None = None
        self._known_telegram_chat_id = settings.reminder_telegram_chat_id
        self._timezone = ZoneInfo(settings.timezone)

    async def start(self, application: Application) -> None:
        if self._task or not self.settings.dynamic_nagging_enabled:
            return

        self._application = application
        self._task = asyncio.create_task(self._run_loop(), name="dynamic-nagging-loop")
        logger.info("Dynamic nagging loop started")

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
        logger.info("Dynamic nagging loop stopped")

    def register_chat(self, chat_id: int) -> None:
        if self.settings.reminder_telegram_chat_id is None:
            self._known_telegram_chat_id = chat_id

    async def maybe_handle_user_reply(self, chat_id: int, text: str) -> str | None:
        if not self.settings.dynamic_nagging_enabled:
            return None

        task_key = self._pending_task_by_chat.get(chat_id)
        if not task_key:
            return None

        state = self._states.get(task_key)
        if not state:
            self._pending_task_by_chat.pop(chat_id, None)
            return None

        reply_kind = self._classify_reply(text)
        if not reply_kind:
            return None

        now = datetime.now(self._timezone)
        state.waiting_for_response = False
        state.response_due_at = None
        self._pending_task_by_chat.pop(chat_id, None)

        if reply_kind == "done":
            state.local_completed = True
            return f"Oke, gue anggap {state.task_name} udah kelar. Gue stop nagging buat task ini."

        if reply_kind == "snooze":
            state.snooze_until = now + timedelta(minutes=30)
            return (
                f"Siap. Gue ingetin lagi 30 menit lagi buat {state.task_name}, "
                f"selama deadlinenya masih relevan."
            )

        state.snooze_until = self._working_snooze_until(now, state.deadline_at)
        return (
            f"Gas. Gue anggap {state.task_name} lagi kamu kerjain sekarang. "
            f"Gue tahan reminder dulu, nanti gue cek lagi kalau masih mepet."
        )

    async def _run_loop(self) -> None:
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Dynamic nagging tick failed")
            await asyncio.sleep(60)

    async def _tick(self) -> None:
        now = datetime.now(self._timezone)
        if self._next_provider_scan_at is None or now >= self._next_provider_scan_at:
            tasks = await self.tools.list_urgent_tasks(
                now=now,
                window_hours=self.settings.dynamic_nagging_deadline_window_hours,
            )
            self._latest_tasks = {task["task_key"]: task for task in tasks}
            self._next_provider_scan_at = now + timedelta(
                minutes=self.settings.dynamic_nagging_poll_minutes
            )
        await self._handle_no_response_fallbacks(now)
        self._expire_reply_windows(now)
        await self._send_due_nags(now)
        self._prune_states(now)

    async def _handle_no_response_fallbacks(self, now: datetime) -> None:
        for task_key, state in list(self._states.items()):
            if not state.waiting_for_response or not state.response_due_at:
                continue
            if now < state.response_due_at:
                continue

            if state.reminder_count < self.settings.dynamic_nagging_max_reminders:
                message = self._build_urgent_message(state, now)
                try:
                    delivery = await self._deliver_message(message)
                except Exception:
                    logger.exception("Dynamic nagging fallback delivery failed task_key=%s", task_key)
                    delivery = {"ok": False}
                if delivery.get("ok"):
                    state.reminder_count += 1
                    state.last_message_at = now

            try:
                await self._trigger_alarm_webhook(
                    {
                        "event": "dynamic_nagging_no_response",
                        "task_name": state.task_name,
                        "task_key": state.task_key,
                        "deadline_at": state.deadline_at.isoformat(),
                        "triggered_at": now.isoformat(),
                    }
                )
            except Exception:
                logger.exception("Dynamic nagging alarm failed task_key=%s", state.task_key)

            state.waiting_for_response = False
            state.response_due_at = None
            state.snooze_until = now + timedelta(minutes=30)

    async def _send_due_nags(self, now: datetime) -> None:
        tasks = sorted(self._latest_tasks.values(), key=lambda item: item["deadline_at"])

        if any(state.waiting_for_response for state in self._states.values()):
            return

        for task in tasks:
            task_key = task["task_key"]
            state = self._states.get(task_key)
            if not state:
                state = TaskNagState(
                    task_key=task_key,
                    source=task["source"],
                    task_id=task["task_id"],
                    task_name=task["task_name"],
                    deadline_at=task["deadline_at"],
                )
                self._states[task_key] = state

            state.task_name = task["task_name"]
            state.deadline_at = task["deadline_at"]

            if state.local_completed:
                continue
            if state.reminder_count >= self.settings.dynamic_nagging_max_reminders:
                continue
            if state.waiting_for_response:
                continue
            if state.snooze_until and now < state.snooze_until:
                continue

            message = self._build_initial_message(state)
            delivery = await self._deliver_message(message)
            if not delivery["ok"]:
                logger.warning(
                    "Dynamic nagging delivery skipped task_key=%s error=%s",
                    task_key,
                    delivery["error"],
                )
                continue

            state.reminder_count += 1
            state.waiting_for_response = True
            state.response_due_at = now + timedelta(
                minutes=self.settings.dynamic_nagging_response_timeout_minutes
            )
            state.chat_id = delivery.get("chat_id")
            state.last_message_at = now
            if state.chat_id is not None:
                self._pending_task_by_chat[state.chat_id] = task_key
            logger.info("Dynamic nagging sent task_key=%s", task_key)
            break

    def _prune_states(self, now: datetime) -> None:
        expiry = now - timedelta(days=1)
        for task_key, state in list(self._states.items()):
            if state.deadline_at < expiry:
                self._states.pop(task_key, None)
                if (
                    state.chat_id is not None
                    and self._pending_task_by_chat.get(state.chat_id) == task_key
                ):
                    self._pending_task_by_chat.pop(state.chat_id, None)

    def _expire_reply_windows(self, now: datetime) -> None:
        for task_key, state in self._states.items():
            if state.waiting_for_response:
                continue
            if not state.snooze_until or now < state.snooze_until:
                continue
            if (
                state.chat_id is not None
                and self._pending_task_by_chat.get(state.chat_id) == task_key
            ):
                self._pending_task_by_chat.pop(state.chat_id, None)

    def _build_initial_message(self, state: TaskNagState) -> str:
        deadline_text = state.deadline_at.strftime("%H:%M")
        return (
            f"Kamu ada deadline {state.task_name} jam {deadline_text} nanti. "
            "Belum ada progres yang tercatat. Mau dikerjakan sekarang, atau aku ingetin lagi 30 menit lagi?"
        )

    def _build_urgent_message(self, state: TaskNagState, now: datetime) -> str:
        remaining = state.deadline_at - now
        urgency = self._format_remaining_time(remaining)
        return (
            f"Belum ada respons buat {state.task_name}. "
            f"Deadline-nya {urgency}. Jawab aja: kerjain sekarang, ingetin 30 menit lagi, atau udah selesai."
        )

    async def _deliver_message(self, message: str) -> dict[str, Any]:
        channel = self.settings.reminder_delivery_channel
        if channel == "telegram":
            chat_id = self._known_telegram_chat_id
            if not chat_id or not self._application:
                return {"ok": False, "error": "Telegram target chat is not configured."}
            await self._application.bot.send_message(chat_id=chat_id, text=message)
            return {"ok": True, "chat_id": chat_id}

        if channel == "whatsapp":
            if not self.settings.whatsapp_webhook_url:
                return {"ok": False, "error": "WHATSAPP_WEBHOOK_URL is not configured."}
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    self.settings.whatsapp_webhook_url,
                    json={
                        "channel": "whatsapp",
                        "message": message,
                        "sent_at": datetime.now(self._timezone).isoformat(),
                    },
                )
                response.raise_for_status()
            return {"ok": True, "chat_id": None}

        return {"ok": False, "error": f"Unsupported nagging channel: {channel}"}

    async def _trigger_alarm_webhook(self, payload: dict[str, Any]) -> None:
        if not self.settings.alarm_webhook_url:
            return

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(self.settings.alarm_webhook_url, json=payload)
            response.raise_for_status()

    @staticmethod
    def _classify_reply(text: str) -> str | None:
        lowered = text.lower().strip()
        if any(token in lowered for token in ("udah selesai", "sudah selesai", "kelar", "beres", "done")):
            return "done"
        if (
            "30" in lowered
            or "setengah jam" in lowered
            or "nanti aja" in lowered
            or "ingetin lagi" in lowered
            or "ingatkan lagi" in lowered
        ):
            return "snooze"
        if lowered in {"ya", "y", "yes", "ayo", "gas"}:
            return "work_now"
        if any(
            token in lowered
            for token in ("kerjain sekarang", "dikerjain sekarang", "lanjut sekarang", "kerjain aja")
        ):
            return "work_now"
        return None

    @staticmethod
    def _working_snooze_until(now: datetime, deadline_at: datetime) -> datetime:
        target = min(
            now + timedelta(minutes=60),
            deadline_at - timedelta(minutes=20),
        )
        if target <= now:
            return now + timedelta(minutes=15)
        return target

    @staticmethod
    def _format_remaining_time(delta: timedelta) -> str:
        total_minutes = int(delta.total_seconds() // 60)
        if total_minutes < 0:
            return f"udah lewat {-total_minutes} menit"
        if total_minutes < 60:
            return f"tinggal {total_minutes} menit lagi"
        hours, minutes = divmod(total_minutes, 60)
        if minutes == 0:
            return f"tinggal {hours} jam lagi"
        return f"tinggal {hours} jam {minutes} menit lagi"
