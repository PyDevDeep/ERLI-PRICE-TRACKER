from typing import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product


async def get_or_create_product(
    session: AsyncSession, url: str, name: str | None = None
) -> Product:
    """
    Upsert логіка: вставляє новий продукт або оновлює ім'я існуючого за URL.
    Повертає об'єкт Product.
    """
    stmt = insert(Product).values(url=url, name=name)
    stmt = stmt.on_conflict_do_update(
        index_elements=["url"], set_={"name": stmt.excluded.name}
    ).returning(Product)

    result = await session.execute(stmt)
    return result.scalar_one()


async def get_all_products(session: AsyncSession) -> Sequence[Product]:
    """Повертає всі продукти для черги скрапінгу."""
    stmt = select(Product)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_product_by_id(session: AsyncSession, product_id: int) -> Product | None:
    """Отримує продукт за ID."""
    stmt = select(Product).where(Product.id == product_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
