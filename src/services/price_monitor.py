from decimal import Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.price_history import PriceHistory

logger = structlog.get_logger(__name__)


async def store_history(
    session: AsyncSession,
    product_id: int,
    price_min: Decimal | None,
    price_max: Decimal | None,
    rating: Decimal | None,
) -> PriceHistory:
    """
    Зберігає новий запис історії цін.
    Управління транзакцією (commit) лежить на викликаючому коді (orchestrator/handler).
    """
    history = PriceHistory(
        product_id=product_id,
        price_min=price_min,
        price_max=price_max,
        rating=rating,
    )

    session.add(history)
    await session.flush()  # Отримуємо ID без комміту транзакції

    logger.info(
        "price_history_stored",
        product_id=product_id,
        price_min=str(price_min) if price_min else None,
        history_id=history.id,
    )

    return history
