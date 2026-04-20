"""
Tests for src/api/routes.py — FastAPI endpoints via httpx AsyncClient.

Coverage targets:
- POST /products: 201 created, duplicate URL upsert, DB error → 500
- GET /products: empty list, list with data
- GET /products/{id}/history: empty history, history with records

Strategy: override FastAPI dependency get_db_session with an in-memory SQLite session.
get_or_create_product uses PostgreSQL INSERT ON CONFLICT — for SQLite compatibility
we mock that function directly to avoid dialect errors.
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.base import Base
from src.models.price_history import PriceHistory
from src.models.product import Product

# App + DB session override
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI test client with real in-memory DB session."""
    from fastapi import FastAPI

    from src.api.routes import router
    from src.models.base import get_db_session

    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# POST /products
# ---------------------------------------------------------------------------


class TestAddProduct:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_add_product_returns_201(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Valid URL → 201 Created with product fields."""
        mock_product = MagicMock(spec=Product)
        mock_product.id = 1
        mock_product.url = "https://erli.pl/produkt/test"
        mock_product.name = "Test Product"
        mock_product.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        with patch(
            "src.api.routes.get_or_create_product",
            new_callable=AsyncMock,
            return_value=mock_product,
        ):
            resp = await api_client.post(
                "/products",
                json={"url": "https://erli.pl/produkt/test", "name": "Test Product"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == "https://erli.pl/produkt/test"
        assert data["name"] == "Test Product"
        assert "id" in data

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_add_product_without_name(self, api_client: AsyncClient) -> None:
        """URL without name → 201, name=null in response."""
        mock_product = MagicMock(spec=Product)
        mock_product.id = 2
        mock_product.url = "https://erli.pl/produkt/noname"
        mock_product.name = None
        mock_product.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        with patch(
            "src.api.routes.get_or_create_product",
            new_callable=AsyncMock,
            return_value=mock_product,
        ):
            resp = await api_client.post(
                "/products",
                json={"url": "https://erli.pl/produkt/noname"},
            )

        assert resp.status_code == 201
        assert resp.json()["name"] is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_add_product_invalid_url_returns_422(self, api_client: AsyncClient) -> None:
        """Non-URL string → FastAPI validation → 422."""
        resp = await api_client.post(
            "/products",
            json={"url": "not-a-url"},
        )
        assert resp.status_code == 422

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_add_product_db_error_raises_database_error(
        self, api_client: AsyncClient
    ) -> None:
        """DB error in get_or_create_product → route raises DatabaseError (unhandled → 500 in prod).

        FastAPI returns 500 only when an exception handler is registered.
        Here we verify the route re-raises DatabaseError, which is the correct behavior.
        """
        from src.exceptions import DatabaseError as DBError

        with patch(
            "src.api.routes.get_or_create_product",
            new_callable=AsyncMock,
            side_effect=Exception("db constraint"),
        ):
            with pytest.raises(DBError) as exc_info:
                # Call the route function directly to inspect the raised exception
                from src.api.routes import add_product
                from src.api.schemas import ProductCreate

                req = ProductCreate.model_validate({"url": "https://erli.pl/produkt/dberror"})
                mock_session = AsyncMock()
                mock_session.commit = AsyncMock()
                mock_session.rollback = AsyncMock()
                await add_product(req, mock_session)

        assert exc_info.value.operation == "add_product"
        assert "db constraint" in exc_info.value.details


# ---------------------------------------------------------------------------
# GET /products
# ---------------------------------------------------------------------------


class TestListProducts:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_products_empty(self, api_client: AsyncClient) -> None:
        """No products → empty list."""
        with patch(
            "src.api.routes.get_paginated_products_with_price",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await api_client.get("/products")

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_products_returns_data(self, api_client: AsyncClient) -> None:
        """Returns list of products with latest_price."""
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        rows = [
            {
                "id": 1,
                "url": "https://erli.pl/produkt/a",
                "name": "A",
                "created_at": now,
                "latest_price": Decimal("99.99"),
            },
            {
                "id": 2,
                "url": "https://erli.pl/produkt/b",
                "name": "B",
                "created_at": now,
                "latest_price": None,
            },
        ]
        with patch(
            "src.api.routes.get_paginated_products_with_price",
            new_callable=AsyncMock,
            return_value=rows,
        ):
            resp = await api_client.get("/products")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "A"
        assert data[1]["latest_price"] is None


# ---------------------------------------------------------------------------
# GET /products/{id}/history
# ---------------------------------------------------------------------------


class TestGetHistory:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_history_empty(self, api_client: AsyncClient) -> None:
        """No history rows → empty list."""
        with patch(
            "src.api.routes.get_product_history",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await api_client.get("/products/1/history")

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_history_returns_records(self, api_client: AsyncClient) -> None:
        """History rows serialized correctly."""
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)
        h = MagicMock(spec=PriceHistory)
        h.id = 10
        h.product_id = 1
        h.price_min = Decimal("150.00")
        h.price_max = Decimal("160.00")
        h.rating = Decimal("4.50")
        h.scraped_at = now

        with patch(
            "src.api.routes.get_product_history",
            new_callable=AsyncMock,
            return_value=[h],
        ):
            resp = await api_client.get("/products/1/history")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["price_min"] == "150.00"
        assert data[0]["product_id"] == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_history_passes_limit_param(self, api_client: AsyncClient) -> None:
        """limit query param forwarded to get_product_history."""
        with patch(
            "src.api.routes.get_product_history",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_history:
            await api_client.get("/products/5/history?limit=10")

        call_kwargs = mock_history.call_args.kwargs
        assert call_kwargs["limit"] == 10
        assert call_kwargs["product_id"] == 5
