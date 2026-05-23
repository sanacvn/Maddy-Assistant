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
class PendingReminder:
    event_key: str
    task_name: str
    sent_at: datetime
    fallback_at: datetime
    chat_id: int | None


class ContextualReminderService:
    def __init__(self, settings: Settings, tools: ToolRegistry) -> None:
        self.settings = settings
        self.tools = tools
        self._application: Application | None = None
        self._task: asyncio.Task[None] | None = None
        self._sent_event_keys: dict[str, datetime] = {}
        self._pending_reminders: dict[str, PendingReminder] = {}
        self._known_telegram_chat_id = settings.reminder_telegram_chat_id
        self._timezone = ZoneInfo(settings.timezone)

    async def start(self, application: Application) -> None:
        if self._task or not self.settings.reminder_enabled:
            return

        self._application = application
        self._task = asyncio.create_task(self._run_loop(), name="contextual-reminder-loop")
        logger.info("Contextual reminder loop started")

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
        logger.info("Contextual reminder loop stopped")

    def register_user_activity(self, chat_id: int) -> None:
        if self.settings.reminder_telegram_chat_id is None:
            self._known_telegram_chat_id = chat_id
        for event_key, pending in list(self._pending_reminders.items()):
            if pending.chat_id == chat_id:
                logger.info(
                    "Reminder acknowledged chat_id=%s event_key=%s",
                    chat_id,
                    event_key,
                )
                self._pending_reminders.pop(event_key, None)

    async def _run_loop(self) -> None:
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Reminder loop tick failed")
            await asyncio.sleep(self.settings.reminder_poll_seconds)

    async def _tick(self) -> None:
        now = datetime.now(self._timezone)
        await self._send_due_reminders(now)
        await self._trigger_fallbacks(now)
        self._prune_sent_events(now)

    async def _send_due_reminders(self, now: datetime) -> None:
        if not self.settings.google_service_account_file:
            return

        window_start = now - timedelta(seconds=self.settings.reminder_poll_seconds + 10)
        window_end = now + timedelta(seconds=50)
        result = await self.tools.calendar_list_events(
            start_iso=window_start.isoformat(),
            end_iso=window_end.isoformat(),
        )
        if result.get("error"):
            logger.warning("Reminder calendar scan failed: %s", result["error"])
            return

        for event in result.get("events", []):
            start_at = self._parse_event_datetime(event.get("start"))
            if not start_at:
                continue
            if start_at < window_start or start_at > window_end:
                continue

            event_key = f"{event.get('id')}:{event.get('start')}"
            if event_key in self._sent_event_keys:
                continue

            message = await self._build_message(event, now)
            delivery = await self._deliver_primary(message)
            if not delivery["ok"]:
                logger.warning(
                    "Reminder delivery skipped event_key=%s error=%s",
                    event_key,
                    delivery["error"],
                )
                continue

            self._sent_event_keys[event_key] = now
            self._pending_reminders[event_key] = PendingReminder(
                event_key=event_key,
                task_name=event.get("summary") or "task kamu",
                sent_at=now,
                fallback_at=now
                + timedelta(minutes=self.settings.reminder_response_timeout_minutes),
                chat_id=delivery.get("chat_id"),
            )
            logger.info("Reminder sent event_key=%s", event_key)

    async def _trigger_fallbacks(self, now: datetime) -> None:
        for event_key, pending in list(self._pending_reminders.items()):
            if now < pending.fallback_at:
                continue

            try:
                await self._trigger_alarm_webhook(pending)
            except Exception:
                logger.exception("Alarm webhook failed event_key=%s", event_key)

            try:
                await self._deliver_primary("Hei, belum ada respons nih. Alarm aktif ya!")
            except Exception:
                logger.exception("Fallback message delivery failed event_key=%s", event_key)

            self._pending_reminders.pop(event_key, None)
            logger.info("Reminder fallback triggered event_key=%s", event_key)

    def _prune_sent_events(self, now: datetime) -> None:
        expiry = now - timedelta(days=2)
        for event_key, sent_at in list(self._sent_event_keys.items()):
            if sent_at < expiry:
                self._sent_event_keys.pop(event_key, None)

    async def _build_message(self, event: dict[str, Any], now: datetime) -> str:
        task_name = event.get("summary") or "task kamu"
        description = event.get("description") or ""
        desc_context, desc_target = self._extract_context_and_target(description)

        notion_context = {}
        if self.settings.notion_api_key:
            try:
                notion_context = await self.tools.notion_extract_task_context(task_name)
            except Exception:
                logger.exception("Failed to load Notion context for task=%s", task_name)

        context = (
            desc_context
            or notion_context.get("context")
            or self._fallback_context(task_name, notion_context.get("page_title"))
        )
        target = (
            desc_target
            or notion_context.get("target")
            or self._fallback_target(task_name, notion_context.get("page_title"))
        )

        current_time = now.strftime("%H:%M")
        return (
            f"Udah jam {current_time} nih. Waktunya {task_name}. "
            f"{self._ensure_sentence(context)} Target sekarang: {self._ensure_phrase(target)}."
        )

    async def _deliver_primary(self, message: str) -> dict[str, Any]:
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
            await self._post_webhook(
                self.settings.whatsapp_webhook_url,
                {
                    "channel": "whatsapp",
                    "message": message,
                    "sent_at": datetime.now(self._timezone).isoformat(),
                },
            )
            return {"ok": True, "chat_id": None}

        return {"ok": False, "error": f"Unsupported reminder channel: {channel}"}

    async def _trigger_alarm_webhook(self, pending: PendingReminder) -> None:
        if not self.settings.alarm_webhook_url:
            return

        await self._post_webhook(
            self.settings.alarm_webhook_url,
            {
                "event": "reminder_no_response",
                "task_name": pending.task_name,
                "event_key": pending.event_key,
                "sent_at": pending.sent_at.isoformat(),
                "triggered_at": datetime.now(self._timezone).isoformat(),
            },
        )

    @staticmethod
    async def _post_webhook(url: str, payload: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

    @staticmethod
    def _extract_context_and_target(text: str) -> tuple[str | None, str | None]:
        context = None
        target = None
        lines = [line.strip(" -\t") for line in text.splitlines() if line.strip()]
        for line in lines:
            lowered = line.lower()
            normalized = ContextualReminderService._strip_label(line)
            if not context and any(
                token in lowered for token in ("konteks", "context", "terakhir", "last update")
            ):
                context = normalized
                continue
            if not target and any(
                token in lowered for token in ("target", "malam ini", "tonight", "next step")
            ):
                target = normalized
                continue

        if not context and lines:
            context = ContextualReminderService._strip_label(lines[0])
        if not target and len(lines) > 1:
            target = ContextualReminderService._strip_label(lines[1])
        return context, target

    @staticmethod
    def _strip_label(text: str) -> str:
        cleaned = text.strip()
        for label in (
            "konteks terakhir:",
            "konteks:",
            "context:",
            "last update:",
            "target sekarang:",
            "target malam ini:",
            "target:",
            "tonight:",
            "next step:",
        ):
            if cleaned.lower().startswith(label):
                return cleaned[len(label):].strip()
        return cleaned

    @staticmethod
    def _fallback_context(task_name: str, page_title: str | None) -> str:
        if page_title and page_title.lower() != task_name.lower():
            return f"Catatan terakhir nyambung ke {page_title}"
        return f"Fokus terakhir masih di progres {task_name}"

    @staticmethod
    def _fallback_target(task_name: str, page_title: str | None) -> str:
        reference = page_title or task_name
        return f"beresin next progress yang paling konkret buat {reference} malam ini"

    @staticmethod
    def _ensure_sentence(text: str) -> str:
        cleaned = text.strip()
        if cleaned.endswith((".", "!", "?")):
            return cleaned
        return f"{cleaned}."

    @staticmethod
    def _ensure_phrase(text: str) -> str:
        return text.strip().rstrip(".!?")

    def _parse_event_datetime(self, value: str | None) -> datetime | None:
        if not value or "T" not in value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=self._timezone)
        return parsed.astimezone(self._timezone)
