import argparse
import asyncio
import csv
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.base import async_session_maker
from src.services.product_repo import get_or_create_product


async def main(file_path: str) -> None:
    if not os.path.exists(file_path):
        print(f"[X] Файл не знайдено: {file_path}")
        sys.exit(1)

    print(f"[*] Читання файлу {file_path}...")

    inserted = 0
    async with async_session_maker() as session:
        with open(file_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            if not reader.fieldnames or "url" not in reader.fieldnames:
                print("[X] CSV файл повинен містити колонку 'url'")
                sys.exit(1)

            for row in reader:
                url = row["url"].strip()
                name = row.get("name", "").strip() or None

                if not url:
                    continue

                await get_or_create_product(session, url=url, name=name)
                inserted += 1

        print("[*] Виконання commit...")
        await session.commit()

    print(f"[+] Успішно додано/оновлено {inserted} продуктів.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Імпорт продуктів з CSV")
    parser.add_argument("--file", required=True, help="Шлях до CSV файлу (колонки: url, name)")
    args = parser.parse_args()

    asyncio.run(main(args.file))
