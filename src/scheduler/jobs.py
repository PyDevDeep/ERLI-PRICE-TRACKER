from typing import Optional

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from src.config.settings import settings

logger = structlog.get_logger(__name__)


class AppScheduler(AsyncIOScheduler):
    ai_router: Optional[object] = None


scheduler = AppScheduler()


@scheduler.scheduled_job("interval", hours=settings.SCRAPE_INTERVAL_HOURS)  # type: ignore[misc]
async def scrape_all_products() -> None:
    """Головне завдання для періодичного скрапінгу."""
    logger.info("scheduler_job_started", job="scrape_all_products")

    if not scheduler.ai_router:
        logger.error("scheduler_missing_dependency", dependency="ai_router")
        return

    logger.info("scheduler_job_finished", job="scrape_all_products")
