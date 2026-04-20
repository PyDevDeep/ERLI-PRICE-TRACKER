import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from src.config.settings import settings
from src.integrations.serper_client import SerperClient
from src.integrations.telegram_client import TelegramClient
from src.models.base import async_session_maker
from src.services.alerter import send_price_alert
from src.services.parser import parse_erli_data_smart
from src.services.price_monitor import compare_price, store_history
from src.services.product_repo import get_all_products, get_product_history

if TYPE_CHECKING:
    from src.integrations.ai_router import AIRouter

logger = structlog.get_logger(__name__)


class _AppScheduler(AsyncIOScheduler):
    ai_router: "AIRouter | None" = None


scheduler = _AppScheduler()


@scheduler.scheduled_job("interval", hours=settings.SCRAPE_INTERVAL_HOURS)  # type: ignore[misc]
async def scrape_all_products() -> None:
    """Головне завдання для періодичного скрапінгу."""
    logger.info("scheduler_job_started", job="scrape_all_products")

    ai_router = scheduler.ai_router
    if not ai_router:
        logger.error("scheduler_missing_dependency", dependency="ai_router")
        return

    serper_client = SerperClient()
    telegram_client = TelegramClient()

    async with async_session_maker() as session:
        products = await get_all_products(session)
        total = len(products)

    if total == 0:
        logger.info("scheduler_no_products_found")
        return

    for i, product in enumerate(products, 1):
        logger.info(
            "scraping_product",
            current=i,
            total=total,
            product_id=product.id,
            url=product.url,
        )

        try:
            raw_data = await serper_client.scrape_url(product.url)
            parsed = await parse_erli_data_smart(raw_data, ai_router)

            async with async_session_maker() as session:
                await store_history(
                    session=session,
                    product_id=product.id,
                    price_min=parsed.get("price_min"),
                    price_max=parsed.get("price_max"),
                    rating=parsed.get("rating"),
                )
                price_change = await compare_price(session, product.id)
                await session.commit()

            if price_change:
                logger.info(
                    "price_change_detected",
                    product_id=product.id,
                    delta=price_change.delta_percent,
                )
                await send_price_alert(
                    telegram_client=telegram_client,
                    product_name=price_change.product,
                    old_price=price_change.old_price,
                    new_price=price_change.new_price,
                    delta_percent=price_change.delta_percent,
                    url=product.url,
                )

        except Exception as e:
            logger.error("scraping_product_failed", product_id=product.id, error=str(e))

        await asyncio.sleep(1)

    logger.info("scheduler_job_finished", job="scrape_all_products")


@scheduler.scheduled_job("cron", day_of_week="sun", hour=10, timezone="Europe/Kyiv")  # type: ignore[misc]
async def generate_weekly_insights() -> None:
    """Генерація щотижневого AI-зведення для користувача."""
    logger.info("scheduler_job_started", job="generate_weekly_insights")

    ai_router = scheduler.ai_router
    if not ai_router:
        logger.error("scheduler_missing_dependency", dependency="ai_router")
        return

    telegram_client = TelegramClient()
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    async with async_session_maker() as session:
        products = await get_all_products(session)
        if not products:
            return

        market_data: list[str] = []
        for p in products:
            history = await get_product_history(session, p.id, limit=20, since=one_week_ago)
            if not history:
                continue

            latest = history[0].price_min
            oldest = history[-1].price_min

            if latest and oldest:
                delta = float((latest - oldest) / oldest) * 100
                market_data.append(
                    f"Product: {p.name} | Price last week: {oldest} zl | Current price: {latest} zl | Change: {delta:.1f}%"
                )

    if not market_data:
        logger.info("insights_no_data")
        return

    context_str = "\n".join(market_data)
    prompt = f"""You are a financial assistant. Analyze the user's product price changes over the past week and write a short, engaging summary (up to 3-4 paragraphs).
Style: friendly, concise. Language: Ukrainian.
Highlight the key points: what got cheaper (recommend buying), what got more expensive. Don't list every product mechanically — draw conclusions about trends.

Raw data:
{context_str}"""

    try:
        response = await ai_router.complete([{"role": "user", "content": prompt}], max_tokens=400)
        report = f"📊 <b>Your weekly price insights:</b>\n\n{response.content}"
        await telegram_client.send_alert(report)
        logger.info("weekly_insights_sent")
    except Exception as e:
        logger.error("weekly_insights_failed", error=str(e))
