from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(dotenv_path: str = ".env") -> None:
    path = Path(dotenv_path)
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def parse_json_list(raw_value: str | None) -> list[dict[str, str]]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    cleaned: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        normalized = {
            str(key): str(value)
            for key, value in item.items()
            if value is not None
        }
        if normalized.get("after") and normalized.get("message"):
            cleaned.append(normalized)
    return cleaned


@dataclass
class Settings:
    telegram_bot_token: str
    gemini_api_key: str
    gemini_model: str
    notion_api_key: str | None
    notion_version: str
    notion_parent_page_id: str | None
    google_calendar_id: str
    google_service_account_file: str | None
    timezone: str
    playwright_headless: bool
    reminder_enabled: bool
    reminder_delivery_channel: str
    reminder_telegram_chat_id: int | None
    whatsapp_webhook_url: str | None
    alarm_webhook_url: str | None
    reminder_poll_seconds: int
    reminder_response_timeout_minutes: int
    dynamic_nagging_enabled: bool
    dynamic_nagging_source: str
    dynamic_nagging_poll_minutes: int
    dynamic_nagging_deadline_window_hours: int
    dynamic_nagging_response_timeout_minutes: int
    dynamic_nagging_max_reminders: int
    notion_task_database_id: str | None
    notion_task_title_property: str
    notion_task_status_property: str
    notion_task_deadline_property: str
    notion_task_progress_property: str
    notion_task_done_values: tuple[str, ...]
    todoist_api_token: str | None
    google_tasks_service_account_file: str | None
    google_tasks_impersonate_user: str | None
    google_tasks_tasklist_id: str | None
    natural_language_input_enabled: bool
    calendar_default_event_duration_minutes: int
    morning_briefing_enabled: bool
    morning_briefing_hour: int
    morning_briefing_minute: int
    morning_briefing_personal_greeting: str
    chain_reminders_enabled: bool
    chain_reminder_poll_seconds: int
    chain_reminder_delay_min_minutes: int
    chain_reminder_delay_max_minutes: int
    chain_reminder_rules: list[dict[str, str]]

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        reminder_chat_id = os.getenv("REMINDER_TELEGRAM_CHAT_ID")
        notion_done_values = tuple(
            value.strip().lower()
            for value in os.getenv(
                "NOTION_TASK_DONE_VALUES",
                "done,selesai,completed,complete",
            ).split(",")
            if value.strip()
        )
        chain_rules = parse_json_list(os.getenv("CHAIN_REMINDER_RULES"))
        return cls(
            telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            gemini_api_key=os.environ["GEMINI_API_KEY"],
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
            notion_api_key=os.getenv("NOTION_API_KEY"),
            notion_version=os.getenv("NOTION_VERSION", "2022-06-28"),
            notion_parent_page_id=os.getenv("NOTION_PARENT_PAGE_ID"),
            google_calendar_id=os.getenv("GOOGLE_CALENDAR_ID", "your_calendar@gmail.com"),
            google_service_account_file=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
            timezone=os.getenv("TIMEZONE", "Asia/Jakarta"),
            playwright_headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true",
            reminder_enabled=os.getenv("REMINDER_ENABLED", "false").lower() == "true",
            reminder_delivery_channel=os.getenv("REMINDER_DELIVERY_CHANNEL", "telegram").lower(),
            reminder_telegram_chat_id=int(reminder_chat_id) if reminder_chat_id else None,
            whatsapp_webhook_url=os.getenv("WHATSAPP_WEBHOOK_URL"),
            alarm_webhook_url=os.getenv("ALARM_WEBHOOK_URL"),
            reminder_poll_seconds=max(15, int(os.getenv("REMINDER_POLL_SECONDS", "30"))),
            reminder_response_timeout_minutes=max(
                1,
                int(os.getenv("REMINDER_RESPONSE_TIMEOUT_MINUTES", "10")),
            ),
            dynamic_nagging_enabled=os.getenv("DYNAMIC_NAGGING_ENABLED", "false").lower()
            == "true",
            dynamic_nagging_source=os.getenv("DYNAMIC_NAGGING_SOURCE", "auto").lower(),
            dynamic_nagging_poll_minutes=max(
                30,
                int(os.getenv("DYNAMIC_NAGGING_POLL_MINUTES", "60")),
            ),
            dynamic_nagging_deadline_window_hours=max(
                1,
                int(os.getenv("DYNAMIC_NAGGING_DEADLINE_WINDOW_HOURS", "3")),
            ),
            dynamic_nagging_response_timeout_minutes=max(
                1,
                int(os.getenv("DYNAMIC_NAGGING_RESPONSE_TIMEOUT_MINUTES", "10")),
            ),
            dynamic_nagging_max_reminders=max(
                1,
                int(os.getenv("DYNAMIC_NAGGING_MAX_REMINDERS", "3")),
            ),
            notion_task_database_id=os.getenv("NOTION_TASK_DATABASE_ID"),
            notion_task_title_property=os.getenv("NOTION_TASK_TITLE_PROPERTY", "Name"),
            notion_task_status_property=os.getenv("NOTION_TASK_STATUS_PROPERTY", "Status"),
            notion_task_deadline_property=os.getenv("NOTION_TASK_DEADLINE_PROPERTY", "Deadline"),
            notion_task_progress_property=os.getenv("NOTION_TASK_PROGRESS_PROPERTY", "Progress"),
            notion_task_done_values=notion_done_values,
            todoist_api_token=os.getenv("TODOIST_API_TOKEN"),
            google_tasks_service_account_file=os.getenv("GOOGLE_TASKS_SERVICE_ACCOUNT_FILE"),
            google_tasks_impersonate_user=os.getenv("GOOGLE_TASKS_IMPERSONATE_USER"),
            google_tasks_tasklist_id=os.getenv("GOOGLE_TASKS_TASKLIST_ID"),
            natural_language_input_enabled=os.getenv("NATURAL_LANGUAGE_INPUT_ENABLED", "true")
            .lower()
            == "true",
            calendar_default_event_duration_minutes=max(
                5,
                int(os.getenv("CALENDAR_DEFAULT_EVENT_DURATION_MINUTES", "30")),
            ),
            morning_briefing_enabled=os.getenv("MORNING_BRIEFING_ENABLED", "false").lower()
            == "true",
            morning_briefing_hour=min(
                23,
                max(0, int(os.getenv("MORNING_BRIEFING_HOUR", "6"))),
            ),
            morning_briefing_minute=min(
                59,
                max(0, int(os.getenv("MORNING_BRIEFING_MINUTE", "0"))),
            ),
            morning_briefing_personal_greeting=os.getenv(
                "MORNING_BRIEFING_PERSONAL_GREETING",
                "semoga pagimu enak",
            ),
            chain_reminders_enabled=os.getenv("CHAIN_REMINDERS_ENABLED", "false").lower()
            == "true",
            chain_reminder_poll_seconds=max(
                30,
                int(os.getenv("CHAIN_REMINDER_POLL_SECONDS", "60")),
            ),
            chain_reminder_delay_min_minutes=max(
                0,
                int(os.getenv("CHAIN_REMINDER_DELAY_MIN_MINUTES", "2")),
            ),
            chain_reminder_delay_max_minutes=max(
                1,
                int(os.getenv("CHAIN_REMINDER_DELAY_MAX_MINUTES", "5")),
            ),
            chain_reminder_rules=chain_rules,
        )
