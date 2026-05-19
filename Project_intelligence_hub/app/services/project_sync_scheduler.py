import asyncio
import logging

from app.core.config import settings
from app.services.project_chat_engine import sync_project_knowledge


logger = logging.getLogger(__name__)


def _configured_project_ids() -> list[str]:
    return [
        project_id.strip()
        for project_id in settings.PROJECT_SYNC_PROJECT_IDS.split(",")
        if project_id.strip()
    ]


async def _sync_global_project_knowledge() -> None:
    if not settings.PROJECT_SYNC_GLOBAL_AUTORUN:
        return

    logger.info("Starting global project knowledge auto-sync.")
    result = await sync_project_knowledge()
    logger.info("Global project knowledge auto-sync completed: %s", result)


async def _sync_single_project_knowledge(project_id: str) -> None:
    logger.info("Starting project knowledge auto-sync for project_id=%s.", project_id)
    result = await sync_project_knowledge(project_id=project_id)
    logger.info(
        "Project knowledge auto-sync completed for project_id=%s: %s",
        project_id,
        result,
    )


async def _run_project_sync_cycle() -> None:
    try:
        await _sync_global_project_knowledge()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Global project knowledge auto-sync failed.")

    for project_id in _configured_project_ids():
        try:
            await _sync_single_project_knowledge(project_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Project knowledge auto-sync failed for project_id=%s.",
                project_id,
            )


async def run_project_sync_scheduler() -> None:
    interval_seconds = max(0, settings.PROJECT_SYNC_INTERVAL_SECONDS)

    while True:
        try:
            await _run_project_sync_cycle()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Project knowledge auto-sync failed.")

        if interval_seconds <= 0:
            return

        await asyncio.sleep(interval_seconds)
