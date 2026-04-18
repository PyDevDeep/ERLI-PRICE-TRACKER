"""
Tests for src/services/price_monitor.py — compare_price, store_history.

Coverage targets:
- compare_price: no history, single record, price increase, price decrease,
  below threshold, zero/null price guards
- store_history: record creation, flush without commit
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.base import Base
from src.models.price_history import PriceHistory
from src.models.product import Product
from src.services.price_monitor import PriceChange, compare_price, store_history

# ---------------------------------------------------------------------------
# In-memory SQLite fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_session():
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


async def _seed_product(session: AsyncSession, name: str = "Test Product") -> Product:
    """Insert a product and return it with its DB-assigned id."""
    product = Product(url=f"https://example.com/{name}", name=name)
    session.add(product)
    await session.flush()
    return product


async def _seed_history(
    session: AsyncSession,
    product_id: int,
    price: Decimal,
    scraped_at: datetime | None = None,
) -> PriceHistory:
    """Insert a PriceHistory row with optional explicit scraped_at."""
    history = PriceHistory(
        product_id=product_id,
        price_min=price,
        price_max=price,
        rating=None,
    )
    if scraped_at is not None:
        history.scraped_at = scraped_at
    session.add(history)
    await session.flush()
    return history


# ---------------------------------------------------------------------------
# compare_price — acceptance criteria from Task 5.1.2
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compare_no_history(db_session: AsyncSession) -> None:
    """No price records at all → None."""
    product = await _seed_product(db_session)

    result = await compare_price(db_session, product.id)

    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compare_single_record(db_session: AsyncSession) -> None:
    """Only one history row — cannot compute delta → None."""
    product = await _seed_product(db_session)
    await _seed_history(db_session, product.id, Decimal("100.00"))

    result = await compare_price(db_session, product.id)

    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compare_price_increase(db_session: AsyncSession) -> None:
    """Price rose above threshold → PriceChange returned."""
    product = await _seed_product(db_session)
    t1 = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    await _seed_history(db_session, product.id, Decimal("100.00"), scraped_at=t1)
    await _seed_history(db_session, product.id, Decimal("120.00"), scraped_at=t2)

    result = await compare_price(db_session, product.id)

    assert isinstance(result, PriceChange)
    assert result.old_price == Decimal("100.00")
    assert result.new_price == Decimal("120.00")
    assert abs(result.delta_percent - 20.0) < 0.01
    assert result.product == "Test Product"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compare_price_decrease(db_session: AsyncSession) -> None:
    """Price dropped below threshold (absolute) → PriceChange returned."""
    product = await _seed_product(db_session)
    t1 = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    await _seed_history(db_session, product.id, Decimal("200.00"), scraped_at=t1)
    await _seed_history(db_session, product.id, Decimal("160.00"), scraped_at=t2)

    result = await compare_price(db_session, product.id)

    assert isinstance(result, PriceChange)
    assert result.delta_percent < 0
    assert abs(result.delta_percent - (-20.0)) < 0.01


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compare_below_threshold(db_session: AsyncSession) -> None:
    """Price change smaller than PRICE_CHANGE_THRESHOLD_PERCENT (5%) → None."""
    product = await _seed_product(db_session)
    t1 = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    await _seed_history(db_session, product.id, Decimal("100.00"), scraped_at=t1)
    # 2% change — below default threshold of 5%
    await _seed_history(db_session, product.id, Decimal("102.00"), scraped_at=t2)

    result = await compare_price(db_session, product.id)

    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compare_exact_threshold_triggers(db_session: AsyncSession) -> None:
    """Change exactly equal to threshold (>= check) → PriceChange returned."""
    product = await _seed_product(db_session)
    t1 = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    await _seed_history(db_session, product.id, Decimal("100.00"), scraped_at=t1)
    await _seed_history(db_session, product.id, Decimal("105.00"), scraped_at=t2)

    result = await compare_price(db_session, product.id)

    assert isinstance(result, PriceChange)
    assert abs(result.delta_percent - 5.0) < 0.01


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compare_new_price_none_returns_none(db_session: AsyncSession) -> None:
    """new_price=None (scrape failed) → division guard returns None."""
    product = await _seed_product(db_session)
    t1 = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    await _seed_history(db_session, product.id, Decimal("100.00"), scraped_at=t1)

    # second record with no price
    history = PriceHistory(product_id=product.id, price_min=None, price_max=None, rating=None)
    history.scraped_at = t2
    db_session.add(history)
    await db_session.flush()

    result = await compare_price(db_session, product.id)

    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compare_old_price_none_returns_none(db_session: AsyncSession) -> None:
    """old_price=None → division guard returns None."""
    product = await _seed_product(db_session)
    t1 = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    history_old = PriceHistory(product_id=product.id, price_min=None, price_max=None, rating=None)
    history_old.scraped_at = t1
    db_session.add(history_old)
    await db_session.flush()

    await _seed_history(db_session, product.id, Decimal("100.00"), scraped_at=t2)

    result = await compare_price(db_session, product.id)

    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compare_product_name_unknown_fallback(db_session: AsyncSession) -> None:
    """Product with name=None → PriceChange.product is 'Unknown Product'."""
    product = Product(url="https://example.com/noname", name=None)
    db_session.add(product)
    await db_session.flush()

    t1 = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    await _seed_history(db_session, product.id, Decimal("100.00"), scraped_at=t1)
    await _seed_history(db_session, product.id, Decimal("120.00"), scraped_at=t2)

    result = await compare_price(db_session, product.id)

    assert isinstance(result, PriceChange)
    assert result.product == "Unknown Product"


# ---------------------------------------------------------------------------
# store_history
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_store_history_creates_record(db_session: AsyncSession) -> None:
    """store_history flushes a PriceHistory row and returns it with an id."""
    product = await _seed_product(db_session)

    history = await store_history(
        db_session,
        product_id=product.id,
        price_min=Decimal("99.99"),
        price_max=Decimal("109.99"),
        rating=Decimal("4.50"),
    )

    assert history.id is not None
    assert history.price_min == Decimal("99.99")
    assert history.price_max == Decimal("109.99")
    assert history.rating == Decimal("4.50")
    assert history.product_id == product.id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_store_history_accepts_none_fields(db_session: AsyncSession) -> None:
    """store_history works when all optional fields are None."""
    product = await _seed_product(db_session)

    history = await store_history(
        db_session,
        product_id=product.id,
        price_min=None,
        price_max=None,
        rating=None,
    )

    assert history.id is not None
    assert history.price_min is None
    assert history.rating is None
