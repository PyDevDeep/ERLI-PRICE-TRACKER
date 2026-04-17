from decimal import Decimal
from typing import Any

import pytest

from src.services.parser import parse_erli_data


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
def serper_sample_regex_fallback() -> dict[str, Any]:
    return {"text": "Kup teraz za 4 749,00 zł! Stara cena to 4 899,99 zł.", "jsonld": {}}


def test_parse_jsonld_primary(serper_sample_valid: dict[str, Any]) -> None:
    result = parse_erli_data(serper_sample_valid)

    assert result["name"] == "iPhone 17 Pro 256GB Cosmic Orange Dual eSIM"
    assert result["price_min"] == Decimal("4899.99")
    assert result["price_max"] == Decimal("4899.99")
    assert result["rating"] == Decimal("5.92")  # Перевірка округлення


def test_parse_regex_fallback(serper_sample_regex_fallback: dict[str, Any]) -> None:
    result = parse_erli_data(serper_sample_regex_fallback)

    assert result["price_min"] == Decimal("4749.00")
    assert result["price_max"] == Decimal("4899.99")


def test_parse_empty_data() -> None:
    result = parse_erli_data({})

    assert result["name"] is None
    assert result["price_min"] is None
    assert result["rating"] is None
