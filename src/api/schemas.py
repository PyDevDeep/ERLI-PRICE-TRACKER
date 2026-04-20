from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, HttpUrl


class ProductCreate(BaseModel):
    """Request schema for adding a new product."""

    url: HttpUrl
    name: str | None = None


class ProductResponse(BaseModel):
    """Response schema for a product."""

    id: int
    url: str
    name: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PriceHistoryResponse(BaseModel):
    """Response schema for a price history record."""

    id: int
    product_id: int
    price_min: Decimal | None
    price_max: Decimal | None
    rating: Decimal | None
    scraped_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductWithPriceResponse(ProductResponse):
    """Product response extended with its latest price."""

    latest_price: Decimal | None
