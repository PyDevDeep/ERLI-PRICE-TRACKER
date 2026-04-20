from decimal import Decimal

import structlog

from src.config.lexicon import ALERTS
from src.config.settings import settings
from src.integrations.telegram_client import TelegramClient

logger = structlog.get_logger(__name__)


def format_alert_message(
    product_name: str,
    old_price: Decimal,
    new_price: Decimal,
    delta_percent: float,
    url: str,
) -> str:
    """Генерує локалізоване повідомлення про зміну ціни."""
    lang = settings.ALERT_LANGUAGE
    lexicon = ALERTS.get(lang, ALERTS["en"])

    title = lexicon["title"].format(product_name=product_name)

    abs_delta = round(abs(delta_percent), 2)

    if new_price < old_price:
        price_line = lexicon["price_drop"].format(
            old_price=old_price, new_price=new_price, delta_percent=abs_delta
        )
    else:
        price_line = lexicon["price_rise"].format(
            old_price=old_price, new_price=new_price, delta_percent=abs_delta
        )

    link = lexicon["link"].format(url=url)

    return f"{title}\n{price_line}\n{link}"


async def send_price_alert(
    telegram_client: TelegramClient,
    product_name: str,
    old_price: Decimal,
    new_price: Decimal,
    delta_percent: float,
    url: str,
) -> bool:
    """Format and send a price change alert; return True on success."""
    message = format_alert_message(
        product_name=product_name,
        old_price=old_price,
        new_price=new_price,
        delta_percent=delta_percent,
        url=url,
    )

    try:
        await telegram_client.send_alert(message)
        return True
    except Exception as e:
        logger.error("alerter_failed_to_send", product=product_name, error=str(e))
        return False
