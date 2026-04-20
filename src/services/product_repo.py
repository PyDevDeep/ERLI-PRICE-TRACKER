from datetime import datetime
from typing import Sequence, TypedDict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.price_history import PriceHistory
from src.models.product import Product


async def get_or_create_product(
    session: AsyncSession, url: str, name: str | None = None
) -> Product:
    """Insert a new product or update its name if a row with the same URL already exists."""
    stmt = insert(Product).values(url=url, name=name)
    stmt = stmt.on_conflict_do_update(
        index_elements=["url"], set_={"name": stmt.excluded.name}
    ).returning(Product)

    result = await session.execute(stmt)
    return result.scalar_one()


async def get_all_products(session: AsyncSession) -> Sequence[Product]:
    """Return all products for the scraping queue."""
    stmt = select(Product)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_product_by_id(session: AsyncSession, product_id: int) -> Product | None:
    """Return the product with the given ID, or None if not found."""
    stmt = select(Product).where(Product.id == product_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


class ProductRow(TypedDict):
    id: int
    url: str
    name: str | None
    created_at: datetime
    latest_price: float | None


async def get_paginated_products_with_price(
    session: AsyncSession, offset: int = 0, limit: int = 100
) -> list[ProductRow]:
    """Return paginated products each with their latest price using PostgreSQL DISTINCT ON."""
    stmt = (
        select(Product, PriceHistory.price_min.label("latest_price"))
        .outerjoin(PriceHistory, Product.id == PriceHistory.product_id)
        .distinct(Product.id)
        .order_by(Product.id, PriceHistory.scraped_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [
        {
            "id": row[0].id,
            "url": row[0].url,
            "name": row[0].name,
            "created_at": row[0].created_at,
            "latest_price": row[1],
        }
        for row in rows
    ]


async def get_product_history(
    session: AsyncSession, product_id: int, limit: int = 100, since: datetime | None = None
) -> Sequence[PriceHistory]:
    """Return price history for a product, ordered newest first."""
    stmt = select(PriceHistory).where(PriceHistory.product_id == product_id)

    if since:
        stmt = stmt.where(PriceHistory.scraped_at >= since)

    stmt = stmt.order_by(PriceHistory.scraped_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()
