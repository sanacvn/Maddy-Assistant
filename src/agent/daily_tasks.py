from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .config import Settings
from .tools import ToolRegistry


logger = logging.getLogger(__name__)


class DailyTaskService:
    def __init__(self, settings: Settings, tools: ToolRegistry) -> None:
        self.settings = settings
        self.tools = tools
        self._task: asyncio.Task[None] | None = None
        self._last_ensured_date: date | None = None
        self._timezone = ZoneInfo(settings.timezone)

    # async def start(self) -> None:
    #     # if (
    #     #     self._task
    #     #     or not self.settings.daily_task_list_enabled
    #     #     or not self.settings.daily_task_templates
    #     # ):
    #     #     return

    #     await self._ensure_for_today()
    #     self._task = asyncio.create_task(self._run_loop(), name="daily-task-loop")
    #     logger.info("Daily task loop started")

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
        logger.info("Daily task loop stopped")

    async def _run_loop(self) -> None:
        while True:
            try:
                await self._ensure_for_today()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Daily task tick failed")
            await asyncio.sleep(300)

    async def _ensure_for_today(self) -> None:
        now = datetime.now(self._timezone)
        if self._last_ensured_date == now.date():
            return

        created = await self.tools.ensure_daily_tasks(now)
        self._last_ensured_date = now.date()
        if created:
            logger.info(
                "Daily tasks ensured date=%s created=%s",
                now.date().isoformat(),
                ", ".join(item["task_name"] for item in created),
            )
