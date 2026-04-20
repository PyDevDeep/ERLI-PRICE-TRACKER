from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    PriceHistoryResponse,
    ProductCreate,
    ProductResponse,
    ProductWithPriceResponse,
)
from src.models.base import get_db_session
from src.services.product_repo import (
    get_or_create_product,
    get_paginated_products_with_price,
    get_product_history,
)

router = APIRouter(prefix="/products", tags=["Products"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def add_product(request: ProductCreate, session: DbSession):
    """Add a new tracked product or update an existing one."""
    try:
        url_str = str(request.url)
        product = await get_or_create_product(session, url=url_str, name=request.name)
        await session.commit()
        return product
    except Exception as e:
        await session.rollback()
        from src.exceptions import DatabaseError

        raise DatabaseError(operation="add_product", details=str(e)) from e


@router.get("", response_model=list[ProductWithPriceResponse])
async def list_products(session: DbSession, skip: int = 0, limit: int = 100):
    """Return all tracked products with their latest price."""
    products = await get_paginated_products_with_price(session, offset=skip, limit=limit)
    return products


@router.get("/{product_id}/history", response_model=list[PriceHistoryResponse])
async def get_history(
    product_id: int,
    session: DbSession,
    limit: int = 100,
    since: datetime | None = None,
):
    """Return price history for a specific product."""
    history = await get_product_history(session, product_id=product_id, limit=limit, since=since)
    return history
