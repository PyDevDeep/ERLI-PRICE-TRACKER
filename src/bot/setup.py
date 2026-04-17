from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from src.bot.handlers import common, products
from src.config.settings import settings


def create_bot() -> Bot:
    """Ініціалізує та повертає інстанс бота."""
    return Bot(token=settings.TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))


def create_dispatcher() -> Dispatcher:
    """Ініціалізує диспетчер та підключає всі роутери."""
    dp = Dispatcher()

    # Підключення роутерів
    dp.include_router(products.router)
    dp.include_router(common.router)

    return dp
