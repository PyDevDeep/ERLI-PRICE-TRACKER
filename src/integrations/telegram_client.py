import asyncio

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from src.config.settings import settings

logger = structlog.get_logger(__name__)


class TelegramClient:
    def __init__(self, bot: Bot | None = None, chat_id: str | None = None) -> None:
        self._owned = bot is None
        self.bot = bot or Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID

    async def send_alert(self, message: str) -> bool:
        """Send an HTML message to the configured chat, retrying on transient errors."""
        logger.info("telegram_send_start", chat_id=self.chat_id)
        attempts = 0
        max_attempts = 3

        while attempts < max_attempts:
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                logger.info("telegram_send_success", chat_id=self.chat_id)
                return True

            except TelegramRetryAfter as e:
                logger.warning("telegram_rate_limit", retry_after=e.retry_after)
                await asyncio.sleep(float(e.retry_after))
                attempts += 1

            except TelegramAPIError as e:
                logger.error("telegram_send_error", error=str(e))
                attempts += 1
                if attempts < max_attempts:
                    await asyncio.sleep(2**attempts)

        logger.error("telegram_send_failed_all_attempts", chat_id=self.chat_id)
        return False

    async def close(self) -> None:
        """Close the bot session if it was created internally."""
        if self._owned:
            await self.bot.session.close()
