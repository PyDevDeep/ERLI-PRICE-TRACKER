import argparse
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import settings
from src.integrations.ai_router import AIRouter
from src.integrations.anthropic_client import AnthropicClient
from src.integrations.openai_client import OpenAIClient
from src.integrations.serper_client import SerperClient
from src.integrations.telegram_client import TelegramClient
from src.models.base import async_session_maker
from src.services.alerter import send_price_alert
from src.services.parser import parse_erli_data_smart
from src.services.price_monitor import compare_price, store_history
from src.services.product_repo import get_or_create_product


async def main(url: str) -> None:
    """Scrape a single product URL and send a price alert if the price changed."""
    print(f"[*] Initializing scraping for URL: {url}")

    openai_client = OpenAIClient(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL,
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
    )
    anthropic_client = AnthropicClient(
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.ANTHROPIC_MODEL,
        timeout=settings.ANTHROPIC_TIMEOUT_SECONDS,
    )
    ai_router = AIRouter(openai_client, anthropic_client, settings)

    serper = SerperClient()
    telegram = TelegramClient()

    try:
        print("[*] Sending request to Serper API...")
        raw_data = await serper.scrape_url(url)

        print("[*] Parsing data...")
        parsed = await parse_erli_data_smart(raw_data, ai_router)

        print("\n--- Parsing result ---")
        for k, v in parsed.items():
            print(f"  {k}: {v}")
        print("--------------------------\n")

        if not parsed.get("price_min"):
            print("[!] WARNING: Price not found. History may be incomplete.")

        print("[*] Saving to database...")
        async with async_session_maker() as session:
            product = await get_or_create_product(
                session=session, url=url, name=parsed.get("name") or "Manual Scrape Product"
            )

            await store_history(
                session=session,
                product_id=product.id,
                price_min=parsed.get("price_min"),
                price_max=parsed.get("price_max"),
                rating=parsed.get("rating"),
            )

            price_change = await compare_price(session, product.id)
            await session.commit()

            if price_change:
                print(f"[+] Price change detected: {price_change.delta_percent}%")
                print("[*] Sending Telegram notification...")
                await send_price_alert(
                    telegram_client=telegram,
                    product_name=price_change.product,
                    old_price=price_change.old_price,
                    new_price=price_change.new_price,
                    delta_percent=price_change.delta_percent,
                    url=product.url,
                )
                print("[+] Notification sent.")
            else:
                print("[-] No price change detected (or this is the first record).")

        print("[+] Completed successfully.")
        sys.exit(0)

    except Exception as e:
        print(f"[X] CRITICAL ERROR: {e}")
        sys.exit(1)
    finally:
        await ai_router.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manual scraping of an ERLI.pl product")
    parser.add_argument("--url", required=True, help="Product URL on erli.pl")
    args = parser.parse_args()

    asyncio.run(main(args.url))
