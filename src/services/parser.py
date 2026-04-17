import json
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import structlog

from src.integrations.ai_router import AIRouter

logger = structlog.get_logger(__name__)

LLM_EXTRACTOR_PROMPT = """
Ти екстрактор даних з e-commerce сторінок. Твоє завдання — знайти ціну та назву товару.
Поверни ТІЛЬКИ валідний JSON без жодного markdown-форматування (без блоків ```json).
Формат: {"price_min": float | null, "price_max": float | null, "name": str | null, "rating": float | null}
Якщо даних немає, поверни null для відповідних полів.
"""


async def parse_erli_data_smart(data: dict[str, Any], ai_router: AIRouter) -> dict[str, Any]:
    """
    Парсить дані. Пріоритет 1: jsonld (Schema.org). Пріоритет 2: LLM аналіз тексту сторінки.
    """
    result: dict[str, Any] = {
        "name": None,
        "price_min": None,
        "price_max": None,
        "rating": None,
    }

    # --- Пріоритет 1: Швидкий парсинг JSON-LD ---
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

    if result["price_min"] is not None:
        logger.info("parser_jsonld_success")
        return result

    # --- Пріоритет 2: LLM Fallback (замість Regex) ---
    text: str = str(data.get("text", ""))
    if not text:
        logger.warning("parser_failed_no_text")
        return result

    truncated_text = text[:4000]

    messages = [
        {"role": "system", "content": LLM_EXTRACTOR_PROMPT},
        {"role": "user", "content": f"Текст сторінки: {truncated_text}"},
    ]

    ai_response = None
    try:
        ai_response = await ai_router.complete(messages, max_tokens=150)

        clean_json = ai_response.content.strip().strip("`").removeprefix("json").strip()
        llm_data = json.loads(clean_json)

        if llm_data.get("price_min"):
            result["price_min"] = Decimal(str(llm_data["price_min"])).quantize(Decimal("0.01"))
            result["price_max"] = Decimal(
                str(llm_data.get("price_max") or llm_data["price_min"])
            ).quantize(Decimal("0.01"))
        if llm_data.get("name") and not result["name"]:
            result["name"] = llm_data["name"]

        logger.info(
            "parser_llm_fallback_used",
            provider=ai_response.provider,
            latency=ai_response.latency_ms,
        )

    except json.JSONDecodeError as e:
        raw = ai_response.content if ai_response else "<no response>"
        logger.error("parser_llm_invalid_json", error=str(e), raw_response=raw)
    except Exception as e:
        logger.error("parser_llm_failed", error=str(e))

    return result
