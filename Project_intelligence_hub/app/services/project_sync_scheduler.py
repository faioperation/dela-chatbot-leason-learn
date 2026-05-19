import asyncio
import logging

from app.core.config import settings
from app.services.project_chat_engine import sync_project_knowledge


logger = logging.getLogger(__name__)


async def run_project_sync_scheduler() -> None:
    interval_seconds = max(0, settings.PROJECT_SYNC_INTERVAL_SECONDS)

    while True:
        try:
            logger.info("Starting project knowledge auto-sync.")
            result = await sync_project_knowledge()
            logger.info("Project knowledge auto-sync completed: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Project knowledge auto-sync failed.")

        if interval_seconds <= 0:
            return

        await asyncio.sleep(interval_seconds)
