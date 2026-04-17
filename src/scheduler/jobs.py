import asyncio
from typing import TYPE_CHECKING

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from src.config.settings import settings
from src.integrations.serper_client import SerperClient
from src.models.base import async_session_maker
from src.services.parser import parse_erli_data
from src.services.price_monitor import store_history
from src.services.product_repo import get_all_products

if TYPE_CHECKING:
    from src.integrations.ai_router import AIRouter

logger = structlog.get_logger(__name__)


class _AppScheduler(AsyncIOScheduler):
    ai_router: "AIRouter | None" = None


scheduler = _AppScheduler()
_scrape_semaphore = asyncio.Semaphore(1)


@scheduler.scheduled_job("interval", hours=settings.SCRAPE_INTERVAL_HOURS)  # type: ignore[misc]
async def scrape_all_products() -> None:
    """Головне завдання для періодичного скрапінгу."""
    logger.info("scheduler_job_started", job="scrape_all_products")

    ai_router = scheduler.ai_router
    if not ai_router:
        logger.error("scheduler_missing_dependency", dependency="ai_router")
        return

    serper_client = SerperClient()

    async with async_session_maker() as session:
        products = await get_all_products(session)
        total = len(products)

        if total == 0:
            logger.info("scheduler_no_products_found")
            return

        for i, product in enumerate(products, 1):
            async with _scrape_semaphore:
                logger.info(
                    "scraping_product",
                    current=i,
                    total=total,
                    product_id=product.id,
                    url=product.url,
                )

                try:
                    raw_data = await serper_client.scrape_url(product.url)
                    parsed = parse_erli_data(raw_data)

                    await store_history(
                        session=session,
                        product_id=product.id,
                        price_min=parsed.get("price_min"),
                        price_max=parsed.get("price_max"),
                        rating=parsed.get("rating"),
                    )
                    await session.commit()
                except Exception as e:
                    logger.error("scraping_product_failed", product_id=product.id, error=str(e))
                    await session.rollback()

                # Жорсткий троттлінг 1 сек згідно з лімітами Serper
                await asyncio.sleep(1)

    logger.info("scheduler_job_finished", job="scrape_all_products")
