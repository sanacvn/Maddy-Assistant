from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram.ext import Application

from .config import Settings
from .tools import ToolRegistry


logger = logging.getLogger(__name__)


class ChainReminderService:
    def __init__(self, settings: Settings, tools: ToolRegistry) -> None:
        self.settings = settings
        self.tools = tools
        self._application: Application | None = None
        self._task: asyncio.Task[None] | None = None
        self._known_telegram_chat_id = settings.reminder_telegram_chat_id
        self._timezone = ZoneInfo(settings.timezone)
        self._sent_event_keys: dict[str, datetime] = {}

    async def start(self, application: Application) -> None:
        if (
            self._task
            or not self.settings.chain_reminders_enabled
            or not self.settings.chain_reminder_rules
        ):
            return

        self._application = application
        self._task = asyncio.create_task(self._run_loop(), name="chain-reminder-loop")
        logger.info("Chain reminder loop started")

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
        logger.info("Chain reminder loop stopped")

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
                logger.exception("Chain reminder tick failed")
            await asyncio.sleep(self.settings.chain_reminder_poll_seconds)

    async def _tick(self) -> None:
        now = datetime.now(self._timezone)
        min_delay = timedelta(minutes=self.settings.chain_reminder_delay_min_minutes)
        max_delay = timedelta(minutes=self.settings.chain_reminder_delay_max_minutes)
        if max_delay < min_delay:
            max_delay = min_delay

        window_start = now - max_delay - timedelta(seconds=15)
        window_end = now - min_delay + timedelta(seconds=15)
        if window_end <= window_start:
            return

        result = await self.tools.calendar_list_events(
            start_iso=window_start.isoformat(),
            end_iso=now.isoformat(),
        )
        if result.get("error"):
            logger.warning("Chain reminder calendar scan failed: %s", result["error"])
            return

        for event in result.get("events", []):
            end_at = self.tools._parse_datetime(event.get("end"))
            if not end_at:
                continue
            if end_at < window_start or end_at > window_end:
                continue

            event_key = f"{event.get('id')}:{event.get('end')}"
            if event_key in self._sent_event_keys:
                continue

            rule = self._match_rule(event.get("summary") or "")
            if not rule:
                continue

            message = self._build_message(event.get("summary") or "Event ini", rule)
            await self._deliver(message)
            self._sent_event_keys[event_key] = now
            logger.info("Chain reminder sent event_key=%s rule_after=%s", event_key, rule["after"])

        self._prune_sent_events(now)

    def _match_rule(self, event_name: str) -> dict[str, str] | None:
        normalized_event = self._normalize(event_name)
        for rule in self.settings.chain_reminder_rules:
            after = rule.get("after", "")
            if self._normalize(after) == normalized_event:
                return rule
        for rule in self.settings.chain_reminder_rules:
            after = rule.get("after", "")
            normalized_after = self._normalize(after)
            if normalized_after and normalized_after in normalized_event:
                return rule
        return None

    @staticmethod
    def _build_message(event_name: str, rule: dict[str, str]) -> str:
        estimate = rule.get("estimate_minutes") or rule.get("estimate") or "10"
        estimate_text = f"{estimate} menit" if estimate.isdigit() else estimate
        return (
            f"{event_name} udah beres kan? {rule['message']} "
            f"{estimate_text} aja cukup!"
        )

    async def _deliver(self, message: str) -> None:
        if not self._application or not self._known_telegram_chat_id:
            raise ValueError("Telegram target chat is not configured for chain reminders.")
        await self._application.bot.send_message(
            chat_id=self._known_telegram_chat_id,
            text=message,
        )

    def _prune_sent_events(self, now: datetime) -> None:
        expiry = now - timedelta(days=2)
        for event_key, sent_at in list(self._sent_event_keys.items()):
            if sent_at < expiry:
                self._sent_event_keys.pop(event_key, None)

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().split())
