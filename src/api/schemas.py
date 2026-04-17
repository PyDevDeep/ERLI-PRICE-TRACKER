from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, HttpUrl


class ProductCreate(BaseModel):
    url: HttpUrl
    name: str | None = None


class ProductResponse(BaseModel):
    id: int
    url: str
    name: str | None
    created_at: datetime

    # Дозволяє Pydantic парсити дані напряму з SQLAlchemy моделей
    model_config = ConfigDict(from_attributes=True)


class PriceHistoryResponse(BaseModel):
    id: int
    product_id: int
    price_min: Decimal | None
    price_max: Decimal | None
    rating: Decimal | None
    scraped_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductWithPriceResponse(ProductResponse):
    latest_price: Decimal | None
