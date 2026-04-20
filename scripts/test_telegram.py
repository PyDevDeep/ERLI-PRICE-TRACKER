import asyncio
import os
import sys
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations.telegram_client import TelegramClient
from src.services.alerter import send_price_alert


async def main() -> None:
    """Send a test price drop alert via Telegram."""
    print("Initializing Telegram client...")
    client = TelegramClient()

    product_name = "Sony PlayStation 5 (Test notification)"
    old_price = Decimal("2500.00")
    new_price = Decimal("2350.50")
    delta_percent = -5.98
    url = "https://erli.pl/produkt/ps5-test"

    print(f"Sending test message for: {product_name}...")

    success = await send_price_alert(
        telegram_client=client,
        product_name=product_name,
        old_price=old_price,
        new_price=new_price,
        delta_percent=delta_percent,
        url=url,
    )

    if success:
        print("✅ Notification sent successfully! Check your Telegram chat.")
    else:
        print("❌ Send failed. Check the terminal for errors and verify tokens in .env.")


if __name__ == "__main__":
    asyncio.run(main())
