from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.parser import parse_erli_data_smart


def _make_ai_router(content: str = "{}") -> MagicMock:
    response = MagicMock()
    response.content = content
    response.provider = "openai"
    response.latency_ms = 100
    router = MagicMock()
    router.complete = AsyncMock(return_value=response)
    return router


@pytest.fixture
def serper_sample_valid() -> dict[str, Any]:
    return {
        "text": "Some text without price",
        "jsonld": {
            "name": "iPhone 17 Pro 256GB Cosmic Orange Dual eSIM",
            "aggregateRating": {"ratingValue": 5.916666666666667},
            "offers": {"price": 4899.99},
        },
    }


@pytest.fixture
def serper_sample_no_jsonld() -> dict[str, Any]:
    return {"text": "Cena: 4899.99 zł iPhone 17 Pro", "jsonld": {}}


@pytest.mark.asyncio
async def test_parse_jsonld_primary(serper_sample_valid: dict[str, Any]) -> None:
    ai_router = _make_ai_router()
    result = await parse_erli_data_smart(serper_sample_valid, ai_router)

    assert result["name"] == "iPhone 17 Pro 256GB Cosmic Orange Dual eSIM"
    assert result["price_min"] == Decimal("4899.99")
    assert result["price_max"] == Decimal("4899.99")
    assert result["rating"] == Decimal("5.92")
    # JSON-LD знайдено — LLM не повинен викликатись
    ai_router.complete.assert_not_called()


@pytest.mark.asyncio
async def test_parse_llm_fallback(serper_sample_no_jsonld: dict[str, Any]) -> None:
    llm_json = (
        '{"price_min": 4899.99, "price_max": 4899.99, "name": "iPhone 17 Pro", "rating": null}'
    )
    ai_router = _make_ai_router(llm_json)
    result = await parse_erli_data_smart(serper_sample_no_jsonld, ai_router)

    assert result["price_min"] == Decimal("4899.99")
    assert result["price_max"] == Decimal("4899.99")
    assert result["name"] == "iPhone 17 Pro"
    ai_router.complete.assert_called_once()


@pytest.mark.asyncio
async def test_parse_empty_data() -> None:
    ai_router = _make_ai_router()
    result = await parse_erli_data_smart({}, ai_router)

    assert result["name"] is None
    assert result["price_min"] is None
    assert result["rating"] is None
    # Немає тексту — LLM не викликається
    ai_router.complete.assert_not_called()


@pytest.mark.asyncio
async def test_parse_llm_invalid_json() -> None:
    ai_router = _make_ai_router("not a json at all")
    result = await parse_erli_data_smart({"text": "some text", "jsonld": {}}, ai_router)

    assert result["price_min"] is None
