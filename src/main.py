from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .agent.config import Settings
from .agent.chain import ChainReminderService
from .agent.daily_tasks import DailyTaskService
from .agent.gemini_agent import GeminiTelegramAgent
from .agent.morning import MorningBriefingService
from .agent.nagging import DynamicNaggingService
from .agent.nl_input import NaturalLanguageInputService
from .agent.reminder import ContextualReminderService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


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


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    note_user_activity(update, context)
    logger.info(
        "Received /start chat_id=%s user_id=%s",
        update.effective_chat.id if update.effective_chat else None,
        update.effective_user.id if update.effective_user else None,
    )
    if update.message:
        await update.message.reply_text(
            "Agent aktif. Kirim pesan biasa untuk chat, tanya kalender, baca/tulis Google Docs, cari web, atau simpan ke Notion."
        )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    note_user_activity(update, context)
    logger.info(
        "Received /reset chat_id=%s user_id=%s",
        update.effective_chat.id if update.effective_chat else None,
        update.effective_user.id if update.effective_user else None,
    )
    agent: GeminiTelegramAgent = context.application.bot_data["agent"]
    if update.effective_chat:
        agent.reset_history(update.effective_chat.id)
    if update.message:
        await update.message.reply_text("Riwayat percakapan untuk chat ini sudah direset.")


async def calendar_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    note_user_activity(update, context)
    logger.info(
        "Received /calendar_check chat_id=%s user_id=%s",
        update.effective_chat.id if update.effective_chat else None,
        update.effective_user.id if update.effective_user else None,
    )
    agent: GeminiTelegramAgent = context.application.bot_data["agent"]
    result = await agent.tools.calendar_check_setup()
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
    logger.info(
        "Received /docs_check chat_id=%s user_id=%s",
        update.effective_chat.id if update.effective_chat else None,
        update.effective_user.id if update.effective_user else None,
    )
    agent: GeminiTelegramAgent = context.application.bot_data["agent"]
    result = await agent.tools.google_docs_check_setup()
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    note_user_activity(update, context)
    logger.info(
        "Received text message chat_id=%s user_id=%s text=%r",
        update.effective_chat.id if update.effective_chat else None,
        update.effective_user.id if update.effective_user else None,
        update.message.text[:200],
    )
    agent: GeminiTelegramAgent = context.application.bot_data["agent"]
    nagging_service: DynamicNaggingService | None = context.application.bot_data.get(
        "nagging_service"
    )
    nl_input_service: NaturalLanguageInputService | None = context.application.bot_data.get(
        "nl_input_service"
    )
    user_text = update.message.text

    if nl_input_service and update.effective_chat:
        nl_reply = await nl_input_service.maybe_handle_message(
            update.effective_chat.id,
            user_text,
        )
        if nl_reply:
            await update.message.reply_text(nl_reply)
            return

    if nagging_service and update.effective_chat:
        nagging_reply = await nagging_service.maybe_handle_user_reply(
            update.effective_chat.id,
            user_text,
        )
        if nagging_reply:
            await update.message.reply_text(nagging_reply)
            return

    await update.message.chat.send_action("typing")
    try:
        reply = await agent.respond(update.effective_chat.id, user_text)
    except Exception as exc:
        if exc.__class__.__name__ == "HTTPStatusError":
            logging.exception("Upstream HTTP error")
            reply = "Request ke service model gagal. Cek `GEMINI_API_KEY`, nama model, atau coba lagi sesaat."
        else:
            logging.exception("Failed to handle message")
            reply = f"Terjadi error: {exc}"

    await update.message.reply_text(reply)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled telegram error. update=%r", update, exc_info=context.error)


async def post_init(application: Application) -> None:
    daily_task_service: DailyTaskService = application.bot_data["daily_task_service"]
    await daily_task_service.start()
    reminder_service: ContextualReminderService = application.bot_data["reminder_service"]
    await reminder_service.start(application)
    nagging_service: DynamicNaggingService = application.bot_data["nagging_service"]
    await nagging_service.start(application)
    morning_service: MorningBriefingService = application.bot_data["morning_service"]
    await morning_service.start(application)
    chain_service: ChainReminderService = application.bot_data["chain_service"]
    await chain_service.start(application)


async def post_shutdown(application: Application) -> None:
    daily_task_service: DailyTaskService = application.bot_data["daily_task_service"]
    await daily_task_service.stop()
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
    agent = GeminiTelegramAgent(settings)
    daily_task_service = DailyTaskService(settings, agent.tools)
    reminder_service = ContextualReminderService(settings, agent.tools)
    nagging_service = DynamicNaggingService(settings, agent.tools)
    nl_input_service = NaturalLanguageInputService(settings, agent.tools)
    morning_service = MorningBriefingService(settings, agent.tools)
    chain_service = ChainReminderService(settings, agent.tools)

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data["agent"] = agent
    application.bot_data["daily_task_service"] = daily_task_service
    application.bot_data["reminder_service"] = reminder_service
    application.bot_data["nagging_service"] = nagging_service
    application.bot_data["nl_input_service"] = nl_input_service
    application.bot_data["morning_service"] = morning_service
    application.bot_data["chain_service"] = chain_service

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("calendar_check", calendar_check_command))
    application.add_handler(CommandHandler("docs_check", docs_check_command))
    application.add_handler(CommandHandler("chat_id", chat_id_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(on_error)

    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
