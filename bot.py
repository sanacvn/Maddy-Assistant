from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo
from langchain_core.messages import AIMessage, HumanMessage
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from agent import agent_executor
from obsidian_rag import index_vault
from src.agent.config import Settings
from src.agent.chain import ChainReminderService
from src.agent.morning import MorningBriefingService
from src.agent.nagging import DynamicNaggingService
from src.agent.nl_input import NaturalLanguageInputService
from src.agent.reminder import ContextualReminderService
from src.agent.tools import ToolRegistry


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)
chat_histories: dict[int, list] = {}


def note_user_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reminder_service: ContextualReminderService | None = context.application.bot_data.get(
        "reminder_service"
    )
    if reminder_service and update.effective_chat:
        reminder_service.register_user_activity(update.effective_chat.id)

    nagging_service: DynamicNaggingService | None = context.application.bot_data.get(
        "nagging_service"
    )
    if nagging_service and update.effective_chat:
        nagging_service.register_chat(update.effective_chat.id)

    morning_service: MorningBriefingService | None = context.application.bot_data.get(
        "morning_service"
    )
    if morning_service and update.effective_chat:
        morning_service.register_chat(update.effective_chat.id)

    chain_service: ChainReminderService | None = context.application.bot_data.get(
        "chain_service"
    )
    if chain_service and update.effective_chat:
        chain_service.register_chat(update.effective_chat.id)


def _trim_history(history: list, max_messages: int = 20) -> None:
    if len(history) > max_messages:
        del history[:-max_messages]


def _extract_text(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, dict):
        for key in ("text", "content", "output", "answer", "result"):
            extracted = _extract_text(value.get(key))
            if extracted:
                return extracted
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            extracted = _extract_text(item)
            if extracted:
                return extracted
    return None


def _extract_reply(result: object) -> str:
    if isinstance(result, dict):
        extracted = _extract_text(
            result.get("output")
            or result.get("text")
            or result.get("content")
            or result.get("output_text")
        )
        if extracted:
            return extracted
        return str(result)
    if isinstance(result, str):
        return result
    extracted = _extract_text(result)
    if extracted:
        return extracted
    return str(result)


def _primary_paragraph(text: str) -> str:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not paragraphs:
        return text.strip()
    return paragraphs[0]


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _format_datetime_for_reply(value: datetime | None) -> str:
    if not value:
        return "unknown time"
    if value.hour == 0 and value.minute == 0 and value.second == 0:
        return value.strftime("%Y-%m-%d")
    return value.strftime("%Y-%m-%d %H:%M")


def _extract_doc_checklist_tasks(content: str) -> tuple[list[str], list[str]]:
    today: list[str] = []
    future: list[str] = []
    current_heading = ""

    today_markers = ("today", "hari ini", "urgent", "now")
    future_markers = ("long", "jangka", "project", "goal", "reminder", "later")

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#"):
            current_heading = line.lstrip("#").strip().lower()
            continue

        if line.endswith(":") and len(line) < 80:
            current_heading = line[:-1].strip().lower()
            continue

        cleaned = line
        if cleaned.startswith("- "):
            cleaned = cleaned[2:].strip()

        if not cleaned.startswith("[ ]") and not cleaned.startswith("[x]"):
            continue

        is_done = cleaned.startswith("[x]")
        task_text = cleaned[3:].strip()
        if not task_text:
            continue

        formatted = f"[{'x' if is_done else ' '}] {task_text}"
        heading = current_heading
        if any(marker in heading for marker in future_markers):
            future.append(formatted)
        elif any(marker in heading for marker in today_markers):
            today.append(formatted)
        else:
            today.append(formatted)

    return today, future


def _format_task_section(title: str, items: list[str]) -> str:
    lines = [title]
    lines.extend(items)
    return "\n".join(lines)


async def _build_live_context(
    tool_registry: ToolRegistry,
    user_message: str,
) -> str:
    settings = tool_registry.settings
    now = datetime.now(ZoneInfo(settings.timezone))
    horizon = now + timedelta(days=7)

    calendar_result, urgent_tasks, docs_result = await asyncio.gather(
        tool_registry.calendar_list_events(now.isoformat(), horizon.isoformat()),
        tool_registry.list_urgent_tasks(now, deadline_before=horizon),
        tool_registry.google_docs_read(max_chars=5000),
    )

    calendar_events = []
    if isinstance(calendar_result, dict) and not calendar_result.get("error"):
        calendar_events = calendar_result.get("events", [])

    doc_today: list[str] = []
    doc_future: list[str] = []
    docs_content = ""
    if isinstance(docs_result, dict) and docs_result.get("ok"):
        docs_content = str(docs_result.get("content", ""))
        doc_today, doc_future = _extract_doc_checklist_tasks(docs_content)

    task_today: list[str] = []
    task_future: list[str] = []
    for task in urgent_tasks:
        deadline_at = task.get("deadline_at")
        if not isinstance(deadline_at, datetime):
            continue
        line = f"[ ] {task.get('task_name', 'Task')} — due: {_format_datetime_for_reply(deadline_at)}"
        if deadline_at.date() == now.date():
            task_today.append(line)
        else:
            task_future.append(line)

    event_today: list[str] = []
    event_future: list[str] = []
    for event in calendar_events:
        start_dt = _parse_iso_datetime(event.get("start"))
        summary = event.get("summary") or "Untitled event"
        line = f"- {summary} — {_format_datetime_for_reply(start_dt)}"
        if start_dt and start_dt.date() == now.date():
            event_today.append(line)
        else:
            event_future.append(line)

    sections: list[str] = [
        f"User message: {user_message}",
        f"Current time: {now.isoformat()}",
    ]

    if task_today or event_today or doc_today:
        sections.append("Today's task candidates:")
        sections.extend(task_today or ["- None from task providers"])
        sections.extend(event_today or ["- None from calendar"])
        sections.extend(doc_today or ["- None from Google Docs"])

    if task_future or event_future or doc_future:
        sections.append("Long-term task candidates and reminders:")
        sections.extend(task_future or ["- None from task providers"])
        sections.extend(event_future or ["- None from calendar"])
        sections.extend(doc_future or ["- None from Google Docs"])

    if len(sections) == 2:
        sections.append("No task data was found in the live sources.")

    return "\n".join(sections)


def _build_task_output(
    tool_registry: ToolRegistry,
    live_context: str,
) -> str:
    now = datetime.now(ZoneInfo(tool_registry.settings.timezone))
    today_label = now.strftime("%Y-%m-%d")

    today_lines: list[str] = []
    long_term_lines: list[str] = []

    for line in live_context.splitlines():
        stripped = line.strip()
        if stripped.startswith("[ ]") or stripped.startswith("[x]"):
            if "due:" in stripped:
                if today_label in stripped:
                    today_lines.append(stripped)
                else:
                    long_term_lines.append(stripped)
            else:
                today_lines.append(stripped)
        elif stripped.startswith("- "):
            if today_label in stripped:
                today_lines.append(stripped[2:].strip())
            else:
                long_term_lines.append(stripped[2:].strip())

    if not today_lines and not long_term_lines:
        return "No tasks for today 🎉"

    parts: list[str] = []
    if today_lines:
        parts.append(_format_task_section(f"📋 Today's Tasks · {today_label}", today_lines))
    if long_term_lines:
        parts.append(
            _format_task_section(
                "🎯 Long-term Tasks & Reminders",
                long_term_lines,
            )
        )
    return "\n\n".join(parts)


def _command_name(text: str) -> str | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    first_token = stripped.split(maxsplit=1)[0]
    command = first_token[1:].split("@", 1)[0].lower()
    return command or None


async def _dispatch_command(
    command: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    handlers: dict[str, Callable[[Update, ContextTypes.DEFAULT_TYPE], object]] = {
        "start": start_command,
        "reset": reset_command,
        "calendar_check": calendar_check_command,
        "docs_check": docs_check_command,
        "chat_id": chat_id_command,
        "reindex": reindex_command,
    }
    handler = handlers.get(command)
    if not handler:
        return False
    await handler(update, context)
    return True


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    note_user_activity(update, context)
    if update.message:
        await update.message.reply_text("Agent aktif. Kirim pesan untuk mulai chat.")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    note_user_activity(update, context)
    if update.effective_user:
        chat_histories.pop(update.effective_user.id, None)
    if update.message:
        await update.message.reply_text("Riwayat percakapan sudah direset.")


async def calendar_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    note_user_activity(update, context)
    tool_registry = context.application.bot_data["tool_registry"]
    result = await tool_registry.calendar_check_setup()
    if update.message:
        if result.get("ok"):
            await update.message.reply_text(
                "Calendar setup OK.\n"
                f"Calendar: {result.get('calendar_summary')} ({result.get('calendar_id')})\n"
                f"Timezone: {result.get('calendar_time_zone')}\n"
                f"Service account: {result.get('service_account_email')}"
            )
        else:
            await update.message.reply_text(
                "Calendar setup bermasalah.\n"
                f"Error: {result.get('error')}\n"
                f"Calendar ID: {result.get('calendar_id', '-')}\n"
                f"Service account: {result.get('service_account_email', '-')}"
            )


async def docs_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    note_user_activity(update, context)
    tool_registry = context.application.bot_data["tool_registry"]
    result = await tool_registry.google_docs_check_setup()
    if update.message:
        if result.get("ok"):
            await update.message.reply_text(
                "Google Docs setup OK.\n"
                f"Document: {result.get('title')} ({result.get('document_id')})\n"
                f"Words: {result.get('word_count')}\n"
                f"Service account: {result.get('service_account_email')}\n"
                f"Link: {result.get('document_url')}"
            )
        else:
            await update.message.reply_text(
                "Google Docs setup bermasalah.\n"
                f"Error: {result.get('error')}\n"
                f"Document ID: {result.get('document_id', '-')}\n"
                f"Service account: {result.get('service_account_email', '-')}"
            )


async def chat_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    note_user_activity(update, context)
    if update.message and update.effective_chat:
        await update.message.reply_text(
            f"Chat ID buat scheduler reminder: {update.effective_chat.id}"
        )


async def reindex_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    note_user_activity(update, context)
    if update.message:
        await update.message.reply_text("Mulai reindex vault Obsidian...")

    try:
        await asyncio.to_thread(index_vault)
        if update.message:
            await update.message.reply_text("Reindex vault selesai.")
    except Exception:
        logger.exception("Failed to reindex Obsidian vault")
        if update.message:
            await update.message.reply_text(
                "Maaf, reindex vault gagal. Cek konfigurasi `OBSIDIAN_VAULT_PATH` dan `OBSIDIAN_CHROMA_DB_PATH`."
            )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text or not update.effective_user:
        return

    command = _command_name(update.message.text)
    if command and await _dispatch_command(command, update, context):
        return

    note_user_activity(update, context)
    user_id = update.effective_user.id
    user_message = update.message.text
    history = chat_histories.setdefault(user_id, [])

    nl_input_service: NaturalLanguageInputService | None = context.application.bot_data.get(
        "nl_input_service"
    )
    if nl_input_service and update.effective_chat:
        nl_reply = await nl_input_service.maybe_handle_message(
            update.effective_chat.id,
            user_message,
        )
        if nl_reply:
            await update.message.reply_text(nl_reply)
            return

    nagging_service: DynamicNaggingService | None = context.application.bot_data.get(
        "nagging_service"
    )
    if nagging_service and update.effective_chat:
        nagging_reply = await nagging_service.maybe_handle_user_reply(
            update.effective_chat.id,
            user_message,
        )
        if nagging_reply:
            await update.message.reply_text(nagging_reply)
            return

    tool_registry: ToolRegistry = context.application.bot_data["tool_registry"]
    live_context = await _build_live_context(tool_registry, user_message)

    await update.message.chat.send_action("typing")
    try:
        result = await agent_executor.ainvoke(
            {
                "input": user_message,
                "chat_history": history,
                "prefetched_context": live_context,
            }
        )
        reply_text = _primary_paragraph(_extract_reply(result))
        task_output = _build_task_output(tool_registry, live_context)
        full_reply = reply_text if task_output == "No tasks for today 🎉" else f"{reply_text}\n\n{task_output}"
        history.extend([HumanMessage(content=user_message), AIMessage(content=full_reply)])
        _trim_history(history, max_messages=20)
        await update.message.reply_text(full_reply)
    except Exception:
        logger.exception("Failed to handle message user_id=%s", user_id)
        await update.message.reply_text(
            "Maaf, ada gangguan saat memproses pesan ini. Coba lagi sebentar."
        )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled telegram error. update=%r", update, exc_info=context.error)


async def post_init(application: Application) -> None:
    reminder_service: ContextualReminderService = application.bot_data["reminder_service"]
    await reminder_service.start(application)
    nagging_service: DynamicNaggingService = application.bot_data["nagging_service"]
    await nagging_service.start(application)
    morning_service: MorningBriefingService = application.bot_data["morning_service"]
    await morning_service.start(application)
    chain_service: ChainReminderService = application.bot_data["chain_service"]
    await chain_service.start(application)


async def post_shutdown(application: Application) -> None:
    reminder_service: ContextualReminderService = application.bot_data["reminder_service"]
    await reminder_service.stop()
    nagging_service: DynamicNaggingService = application.bot_data["nagging_service"]
    await nagging_service.stop()
    morning_service: MorningBriefingService = application.bot_data["morning_service"]
    await morning_service.stop()
    chain_service: ChainReminderService = application.bot_data["chain_service"]
    await chain_service.stop()


def main() -> None:
    settings = Settings.from_env()
    tool_registry = ToolRegistry(settings)
    reminder_service = ContextualReminderService(settings, tool_registry)
    nagging_service = DynamicNaggingService(settings, tool_registry)
    nl_input_service = NaturalLanguageInputService(settings, tool_registry)
    morning_service = MorningBriefingService(settings, tool_registry)
    chain_service = ChainReminderService(settings, tool_registry)

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data["tool_registry"] = tool_registry
    application.bot_data["reminder_service"] = reminder_service
    application.bot_data["nagging_service"] = nagging_service
    application.bot_data["nl_input_service"] = nl_input_service
    application.bot_data["morning_service"] = morning_service
    application.bot_data["chain_service"] = chain_service

    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    application.add_error_handler(on_error)

    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
