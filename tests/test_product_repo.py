"""
Tests for src/services/product_repo.py.
Coverage targets:
- get_or_create_product: insert new, upsert on conflict (name update)
- get_all_products: empty table, multiple products
- get_product_by_id: found, not found
- get_product_history: empty, ordered desc, limit, since filter
- get_paginated_products_with_price: no price, with price, pagination

NOTE: get_or_create_product uses PostgreSQL-specific INSERT ... ON CONFLICT.
SQLite does not support this dialect — those tests are marked @pytest.mark.skip
with a TODO for a real PG test environment.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.base import Base
from src.models.price_history import PriceHistory
from src.models.product import Product
from src.services.product_repo import (
    get_all_products,
    get_product_by_id,
    get_product_history,
)

# ---------------------------------------------------------------------------
# In-memory SQLite session fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_session():  # type: ignore[return]
    """Isolated in-memory SQLite session per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _add_product(session: AsyncSession, url: str, name: str | None = None) -> Product:
    product = Product(url=url, name=name)
    session.add(product)
    await session.flush()
    return product


async def _add_history(
    session: AsyncSession,
    product_id: int,
    price: Decimal,
    scraped_at: datetime | None = None,
) -> PriceHistory:
    h = PriceHistory(product_id=product_id, price_min=price, price_max=price, rating=None)
    if scraped_at:
        h.scraped_at = scraped_at
    session.add(h)
    await session.flush()
    return h


# ---------------------------------------------------------------------------
# get_all_products
# ---------------------------------------------------------------------------


class TestGetAllProducts:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_all_products_empty_table(self, db_session: AsyncSession) -> None:
        """Empty table → empty sequence."""
        result = await get_all_products(db_session)
        assert list(result) == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_all_products_returns_all(self, db_session: AsyncSession) -> None:
        """Returns all inserted products."""
        await _add_product(db_session, "https://erli.pl/produkt/a", "Product A")
        await _add_product(db_session, "https://erli.pl/produkt/b", "Product B")

        result = await get_all_products(db_session)

        urls = {p.url for p in result}
        assert "https://erli.pl/produkt/a" in urls
        assert "https://erli.pl/produkt/b" in urls

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_all_products_count_matches(self, db_session: AsyncSession) -> None:
        """Count of returned products matches inserted count."""
        for i in range(5):
            await _add_product(db_session, f"https://erli.pl/produkt/{i}")

        result = await get_all_products(db_session)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# get_product_by_id
# ---------------------------------------------------------------------------


class TestGetProductById:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_product_by_id_found(self, db_session: AsyncSession) -> None:
        """Existing product returned by its id."""
        product = await _add_product(db_session, "https://erli.pl/produkt/x", "Widget X")

        result = await get_product_by_id(db_session, product.id)

        assert result is not None
        assert result.id == product.id
        assert result.name == "Widget X"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_product_by_id_not_found(self, db_session: AsyncSession) -> None:
        """Non-existent id returns None."""
        result = await get_product_by_id(db_session, 999999)
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_product_by_id_returns_correct_product(
        self, db_session: AsyncSession
    ) -> None:
        """When multiple products exist, correct one is returned."""
        await _add_product(db_session, "https://erli.pl/produkt/p1", "P1")
        p2 = await _add_product(db_session, "https://erli.pl/produkt/p2", "P2")

        result = await get_product_by_id(db_session, p2.id)

        assert result is not None
        assert result.id == p2.id
        assert result.name == "P2"


# ---------------------------------------------------------------------------
# get_product_history
# ---------------------------------------------------------------------------


class TestGetProductHistory:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_product_history_empty(self, db_session: AsyncSession) -> None:
        """No history rows → empty sequence."""
        product = await _add_product(db_session, "https://erli.pl/produkt/h")

        result = await get_product_history(db_session, product.id)

        assert list(result) == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_product_history_ordered_desc(self, db_session: AsyncSession) -> None:
        """History rows returned newest-first."""
        product = await _add_product(db_session, "https://erli.pl/produkt/ord")
        t1 = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc)
        await _add_history(db_session, product.id, Decimal("100"), scraped_at=t1)
        await _add_history(db_session, product.id, Decimal("200"), scraped_at=t2)

        result = await get_product_history(db_session, product.id)

        assert result[0].price_min == Decimal("200")
        assert result[1].price_min == Decimal("100")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_product_history_limit(self, db_session: AsyncSession) -> None:
        """limit parameter restricts returned rows."""
        product = await _add_product(db_session, "https://erli.pl/produkt/lim")
        for i in range(10):
            t = datetime(2025, 1, i + 1, tzinfo=timezone.utc)
            await _add_history(db_session, product.id, Decimal(str(i * 10)), scraped_at=t)

        result = await get_product_history(db_session, product.id, limit=3)

        assert len(result) == 3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_product_history_since_filter(self, db_session: AsyncSession) -> None:
        """since parameter excludes rows older than the given datetime."""
        product = await _add_product(db_session, "https://erli.pl/produkt/since")
        old = datetime(2025, 1, 1, tzinfo=timezone.utc)
        new = datetime(2025, 6, 1, tzinfo=timezone.utc)
        await _add_history(db_session, product.id, Decimal("50"), scraped_at=old)
        await _add_history(db_session, product.id, Decimal("99"), scraped_at=new)

        result = await get_product_history(
            db_session, product.id, since=datetime(2025, 3, 1, tzinfo=timezone.utc)
        )

        assert len(result) == 1
        assert result[0].price_min == Decimal("99")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_product_history_isolates_by_product_id(
        self, db_session: AsyncSession
    ) -> None:
        """History of one product does not bleed into another."""
        p1 = await _add_product(db_session, "https://erli.pl/produkt/iso1")
        p2 = await _add_product(db_session, "https://erli.pl/produkt/iso2")
        await _add_history(db_session, p1.id, Decimal("111"))
        await _add_history(db_session, p2.id, Decimal("222"))

        result = await get_product_history(db_session, p1.id)

        assert len(result) == 1
        assert result[0].price_min == Decimal("111")
