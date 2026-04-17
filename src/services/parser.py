import re
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import structlog

logger = structlog.get_logger(__name__)


def parse_erli_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Парсить дані товару з відповіді Serper.
    Пріоритет 1: jsonld (Schema.org) - структуровані дані.
    Пріоритет 2: Regex fallback по полю text.
    """
    result: dict[str, Any] = {
        "name": None,
        "price_min": None,
        "price_max": None,
        "rating": None,
    }

    # 1. Спроба витягти з JSON-LD
    jsonld: dict[str, Any] = data.get("jsonld") or {}
    if jsonld:
        result["name"] = jsonld.get("name")

        rating: dict[str, Any] = jsonld.get("aggregateRating") or {}
        if "ratingValue" in rating:
            try:
                result["rating"] = Decimal(str(rating["ratingValue"])).quantize(Decimal("0.01"))
            except InvalidOperation:
                pass

        offers_raw: Any = jsonld.get("offers")
        offers: dict[str, Any] = (
            cast(dict[str, Any], offers_raw) if isinstance(offers_raw, dict) else {}
        )
        if "price" in offers:
            try:
                price = Decimal(str(offers["price"])).quantize(Decimal("0.01"))
                result["price_min"] = price
                result["price_max"] = price
            except InvalidOperation:
                pass

    # 2. Fallback: Regex по text, якщо ціна досі не знайдена
    if result["price_min"] is None and "text" in data:
        text: str = str(data["text"])
        # Патерн: числа з пробілами, кома, 2 цифри, zł. Напр: "4 749,00 zł" або "4749,00 zł"
        price_pattern = r"([\d\s]+,\d{2})\s*z[łl]"
        matches: list[str] = re.findall(price_pattern, text.lower())

        if matches:
            prices: list[Decimal] = []
            for match in matches:
                # Очищення: видалення пробілів, заміна коми на крапку
                clean_val = re.sub(r"\s+", "", match).replace(",", ".")
                try:
                    prices.append(Decimal(clean_val).quantize(Decimal("0.01")))
                except InvalidOperation:
                    continue

            if prices:
                result["price_min"] = min(prices)
                result["price_max"] = max(prices)

                logger.info("parser_regex_fallback_used", min=str(result["price_min"]))

    if not result["price_min"]:
        metadata: dict[str, Any] = data.get("metadata") or {}
        logger.warning("parser_failed_to_extract_price", url=metadata.get("og:url"))

    return result
