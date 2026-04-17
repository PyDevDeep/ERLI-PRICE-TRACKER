from datetime import datetime

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
