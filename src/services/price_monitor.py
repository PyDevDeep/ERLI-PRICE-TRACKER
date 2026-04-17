from decimal import Decimal
from typing import NamedTuple

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.models.price_history import PriceHistory
from src.models.product import Product

logger = structlog.get_logger(__name__)


class PriceChange(NamedTuple):
    product: str
    old_price: Decimal
    new_price: Decimal
    delta_percent: float


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


async def compare_price(session: AsyncSession, product_id: int) -> PriceChange | None:
    """
    Порівнює дві останні ціни продукту.
    Повертає PriceChange, якщо різниця перевищує threshold, інакше None.
    """
    stmt = (
        select(PriceHistory, Product.name)
        .join(Product, Product.id == PriceHistory.product_id)
        .where(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.scraped_at.desc())
        .limit(2)
    )

    result = await session.execute(stmt)
    rows = result.all()

    if len(rows) < 2:
        return None

    new_history, product_name = rows[0]
    old_history, _ = rows[1]

    new_price = new_history.price_min
    old_price = old_history.price_min

    # Захист від ділення на нуль або відсутності ціни
    if not new_price or not old_price or old_price == 0:
        return None

    delta = (new_price - old_price) / old_price * Decimal("100")
    delta_percent = float(delta)

    if abs(delta_percent) >= settings.PRICE_CHANGE_THRESHOLD_PERCENT:
        return PriceChange(
            product=product_name or "Unknown Product",
            old_price=old_price,
            new_price=new_price,
            delta_percent=delta_percent,
        )

    return None
