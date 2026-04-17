import asyncio
import os
import sys
from decimal import Decimal

# Додаємо корінь проекту до PYTHONPATH для коректних імпортів при запуску скрипта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations.telegram_client import TelegramClient
from src.services.alerter import send_price_alert


async def main() -> None:
    print("Ініціалізація Telegram клієнта...")
    client = TelegramClient()

    # Імітація падіння ціни (price_drop)
    product_name = "Sony PlayStation 5 (Тестове сповіщення)"
    old_price = Decimal("2500.00")
    new_price = Decimal("2350.50")
    delta_percent = -5.98
    url = "https://erli.pl/produkt/ps5-test"

    print(f"Надсилання тестового повідомлення для: {product_name}...")

    success = await send_price_alert(
        telegram_client=client,
        product_name=product_name,
        old_price=old_price,
        new_price=new_price,
        delta_percent=delta_percent,
        url=url,
    )

    if success:
        print("✅ Сповіщення успішно надіслано! Перевір свій Telegram чат.")
    else:
        print(
            "❌ Помилка надсилання. Перевір термінал на наявність помилок та валідність токенів у .env."
        )


if __name__ == "__main__":
    asyncio.run(main())
