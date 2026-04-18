"""
Tests for src/services/parser.py — parse_erli_data_smart.

Coverage targets:
- JSON-LD happy path (price, name, rating)
- JSON-LD partial data (missing price / malformed values)
- LLM fallback (valid JSON, invalid JSON, exception)
- Edge cases: empty input, no text, truncation at 4000 chars
- Name priority: jsonld name wins over LLM name
"""

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.parser import parse_erli_data_smart

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_ai_router(content: str = "{}") -> MagicMock:
    """AIRouter mock whose .complete() returns an AIResponse-like object."""
    response = MagicMock()
    response.content = content
    response.provider = "openai"
    response.latency_ms = 100
    router = MagicMock()
    router.complete = AsyncMock(return_value=response)
    return router


@pytest.fixture
def serper_sample_valid() -> dict[str, Any]:
    """Full JSON-LD payload: name + rating + price."""
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
    """No JSON-LD — forces LLM fallback."""
    return {"text": "Cena: 4899.99 zł iPhone 17 Pro", "jsonld": {}}


# ---------------------------------------------------------------------------
# JSON-LD path
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_jsonld_primary(serper_sample_valid: dict[str, Any]) -> None:
    """Valid JSON-LD returns all fields; LLM must not be called."""
    ai_router = _make_ai_router()
    result = await parse_erli_data_smart(serper_sample_valid, ai_router)

    assert result["name"] == "iPhone 17 Pro 256GB Cosmic Orange Dual eSIM"
    assert result["price_min"] == Decimal("4899.99")
    assert result["price_max"] == Decimal("4899.99")
    assert result["rating"] == Decimal("5.92")
    ai_router.complete.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_jsonld_no_price_falls_back_to_llm() -> None:
    """JSON-LD present but without offers.price — triggers LLM fallback."""
    data: dict[str, Any] = {
        "text": "Cena: 100 zł",
        "jsonld": {"name": "Some Product", "offers": {}},
    }
    llm_json = '{"price_min": 100.0, "price_max": 100.0, "name": "LLM Name", "rating": null}'
    ai_router = _make_ai_router(llm_json)

    result = await parse_erli_data_smart(data, ai_router)

    assert result["price_min"] == Decimal("100.00")
    # jsonld name has priority — LLM name must NOT overwrite
    assert result["name"] == "Some Product"
    ai_router.complete.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_jsonld_malformed_price_falls_back_to_llm() -> None:
    """Non-numeric price in JSON-LD offers triggers LLM fallback."""
    data: dict[str, Any] = {
        "text": "price text",
        "jsonld": {"name": "Widget", "offers": {"price": "not-a-number"}},
    }
    llm_json = '{"price_min": 55.0, "price_max": 55.0, "name": null, "rating": null}'
    ai_router = _make_ai_router(llm_json)

    result = await parse_erli_data_smart(data, ai_router)

    assert result["price_min"] == Decimal("55.00")
    assert result["name"] == "Widget"  # jsonld name still present
    ai_router.complete.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_jsonld_malformed_rating_skipped() -> None:
    """Non-numeric ratingValue is silently skipped; price still parsed."""
    data: dict[str, Any] = {
        "text": "",
        "jsonld": {
            "name": "Widget",
            "aggregateRating": {"ratingValue": "bad-rating"},
            "offers": {"price": 99.0},
        },
    }
    ai_router = _make_ai_router()

    result = await parse_erli_data_smart(data, ai_router)

    assert result["rating"] is None
    assert result["price_min"] == Decimal("99.00")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_jsonld_no_rating_field() -> None:
    """Missing aggregateRating leaves rating as None."""
    data: dict[str, Any] = {
        "text": "",
        "jsonld": {"name": "Widget", "offers": {"price": 10.0}},
    }
    ai_router = _make_ai_router()

    result = await parse_erli_data_smart(data, ai_router)

    assert result["rating"] is None


# ---------------------------------------------------------------------------
# LLM fallback path
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_llm_fallback(serper_sample_no_jsonld: dict[str, Any]) -> None:
    """LLM is called when JSON-LD has no price; fields populated from LLM JSON."""
    llm_json = (
        '{"price_min": 4899.99, "price_max": 4899.99, "name": "iPhone 17 Pro", "rating": null}'
    )
    ai_router = _make_ai_router(llm_json)

    result = await parse_erli_data_smart(serper_sample_no_jsonld, ai_router)

    assert result["price_min"] == Decimal("4899.99")
    assert result["price_max"] == Decimal("4899.99")
    assert result["name"] == "iPhone 17 Pro"
    ai_router.complete.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_llm_fallback_price_max_defaults_to_price_min() -> None:
    """If LLM returns price_max=null, price_max is set equal to price_min."""
    llm_json = '{"price_min": 200.0, "price_max": null, "name": "Gadget", "rating": null}'
    ai_router = _make_ai_router(llm_json)

    result = await parse_erli_data_smart({"text": "some text", "jsonld": {}}, ai_router)

    assert result["price_min"] == Decimal("200.00")
    assert result["price_max"] == Decimal("200.00")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_llm_fallback_price_max_different_from_price_min() -> None:
    """LLM returns a price range — both values are stored separately."""
    llm_json = '{"price_min": 100.0, "price_max": 150.0, "name": "Range Item", "rating": null}'
    ai_router = _make_ai_router(llm_json)

    result = await parse_erli_data_smart({"text": "some text", "jsonld": {}}, ai_router)

    assert result["price_min"] == Decimal("100.00")
    assert result["price_max"] == Decimal("150.00")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_llm_no_price_in_response() -> None:
    """LLM returns JSON without price_min — result price stays None."""
    llm_json = '{"price_min": null, "price_max": null, "name": "No Price", "rating": null}'
    ai_router = _make_ai_router(llm_json)

    result = await parse_erli_data_smart({"text": "some text", "jsonld": {}}, ai_router)

    assert result["price_min"] is None
    assert result["price_max"] is None
    assert result["name"] == "No Price"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_llm_invalid_json() -> None:
    """Malformed LLM JSON response is handled gracefully — all fields stay None."""
    ai_router = _make_ai_router("not a json at all")

    result = await parse_erli_data_smart({"text": "some text", "jsonld": {}}, ai_router)

    assert result["price_min"] is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_llm_exception_returns_empty_result() -> None:
    """If AIRouter.complete() raises any exception, result is returned with None fields."""
    router = MagicMock()
    router.complete = AsyncMock(side_effect=RuntimeError("network error"))

    result = await parse_erli_data_smart({"text": "some text", "jsonld": {}}, router)

    assert result["price_min"] is None
    assert result["name"] is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_empty_data() -> None:
    """Empty dict: no text, no jsonld — LLM not called, all fields None."""
    ai_router = _make_ai_router()

    result = await parse_erli_data_smart({}, ai_router)

    assert result["name"] is None
    assert result["price_min"] is None
    assert result["rating"] is None
    ai_router.complete.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_no_text_no_jsonld_skips_llm() -> None:
    """Explicit empty text with empty jsonld — LLM not called."""
    ai_router = _make_ai_router()

    result = await parse_erli_data_smart({"text": "", "jsonld": {}}, ai_router)

    assert result["price_min"] is None
    ai_router.complete.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_text_truncated_to_4000_chars() -> None:
    """Text longer than 4000 chars is truncated before sending to LLM."""
    long_text = "x" * 8000
    llm_json = '{"price_min": 1.0, "price_max": 1.0, "name": null, "rating": null}'
    ai_router = _make_ai_router(llm_json)

    await parse_erli_data_smart({"text": long_text, "jsonld": {}}, ai_router)

    call_args = ai_router.complete.call_args
    messages: list[dict[str, str]] = call_args[0][0]
    user_message = next(m for m in messages if m["role"] == "user")
    # The actual content passed to LLM must not exceed 4000 chars of original text
    assert len(user_message["content"]) <= 4000 + 100  # +100 for prompt prefix


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_jsonld_none_value_treated_as_empty() -> None:
    """jsonld=None in input is treated same as missing jsonld."""
    data: dict[str, Any] = {"text": "some text", "jsonld": None}
    llm_json = '{"price_min": 10.0, "price_max": 10.0, "name": "Item", "rating": null}'
    ai_router = _make_ai_router(llm_json)

    result = await parse_erli_data_smart(data, ai_router)

    assert result["price_min"] == Decimal("10.00")
    ai_router.complete.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_llm_name_not_overwrite_jsonld_name() -> None:
    """jsonld.name is preserved even when LLM also returns a name."""
    data: dict[str, Any] = {
        "text": "some text",
        "jsonld": {"name": "Original Name", "offers": {}},
    }
    llm_json = '{"price_min": 50.0, "price_max": 50.0, "name": "LLM Name", "rating": null}'
    ai_router = _make_ai_router(llm_json)

    result = await parse_erli_data_smart(data, ai_router)

    assert result["name"] == "Original Name"
