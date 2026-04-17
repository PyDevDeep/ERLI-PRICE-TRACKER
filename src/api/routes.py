from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import ProductCreate, ProductResponse
from src.models.base import get_db_session
from src.services.product_repo import get_or_create_product

router = APIRouter(prefix="/products", tags=["Products"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def add_product(request: ProductCreate, session: DbSession):
    """Додає новий продукт для відстеження або оновлює існуючий."""
    try:
        # Перетворюємо об'єкт HttpUrl назад у рядок для збереження в БД
        url_str = str(request.url)
        product = await get_or_create_product(session, url=url_str, name=request.name)

        await session.commit()
        return product
    except Exception as e:
        await session.rollback()
        # В ідеалі тут має бути кастомний обробник помилок (Phase 5),
        # але поки повертаємо стандартний 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {str(e)}"
        ) from e
