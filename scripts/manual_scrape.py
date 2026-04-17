import argparse
import asyncio
import os
import sys

# Додаємо корінь проекту до PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations.serper_client import SerperClient
from src.integrations.telegram_client import TelegramClient
from src.models.base import async_session_maker
from src.services.alerter import send_price_alert
from src.services.parser import parse_erli_data
from src.services.price_monitor import compare_price, store_history
from src.services.product_repo import get_or_create_product


async def main(url: str) -> None:
    print(f"[*] Ініціалізація скрапінгу для URL: {url}")

    serper = SerperClient()
    telegram = TelegramClient()

    try:
        # 1. Scrape
        print("[*] Виконання запиту до Serper API...")
        raw_data = await serper.scrape_url(url)

        # 2. Parse
        print("[*] Парсинг даних...")
        parsed = parse_erli_data(raw_data)

        print("\n--- Результат парсингу ---")
        for k, v in parsed.items():
            print(f"  {k}: {v}")
        print("--------------------------\n")

        if not parsed.get("price_min"):
            print("[!] УВАГА: Ціну не знайдено. Збереження історії може бути неповним.")

        # 3. DB Operations
        print("[*] Збереження в базу даних...")
        async with async_session_maker() as session:
            # Гарантуємо наявність продукту в БД перед записом історії
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

            # 4. Compare & Alert
            price_change = await compare_price(session, product.id)
            await session.commit()

            if price_change:
                print(f"[+] Виявлено зміну ціни: {price_change.delta_percent}%")
                print("[*] Відправка Telegram сповіщення...")
                await send_price_alert(
                    telegram_client=telegram,
                    product_name=price_change.product,
                    old_price=price_change.old_price,
                    new_price=price_change.new_price,
                    delta_percent=price_change.delta_percent,
                    url=product.url,
                )
                print("[+] Сповіщення відправлено.")
            else:
                print("[-] Змін ціни не виявлено (або це перший запис).")

        print("[+] Успішно завершено.")
        sys.exit(0)

    except Exception as e:
        print(f"[X] КРИТИЧНА ПОМИЛКА: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ручний скрапінг товару ERLI.pl")
    parser.add_argument("--url", required=True, help="URL товару на erli.pl")
    args = parser.parse_args()

    asyncio.run(main(args.url))
