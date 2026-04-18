import asyncio
from datetime import timedelta

import structlog
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import settings

logger = structlog.get_logger(__name__)


class TelegramClient:
    def __init__(self) -> None:
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.chat_id = settings.TELEGRAM_CHAT_ID

    @retry(
        retry=retry_if_exception_type((TelegramError,)),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def send_alert(self, message: str) -> bool:
        logger.info("telegram_send_start", chat_id=self.chat_id)

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                # Вимикаємо прев'ю посилань, щоб сповіщення були компактними
                disable_web_page_preview=True,
            )
            logger.info("telegram_send_success", chat_id=self.chat_id)
            return True

        except RetryAfter as e:
            logger.warning("telegram_rate_limit", retry_after=e.retry_after)
            delay = (
                e.retry_after.total_seconds()
                if isinstance(e.retry_after, timedelta)
                else float(e.retry_after)
            )
            await asyncio.sleep(delay)
            raise
        except TelegramError as e:
            logger.error("telegram_send_error", error=str(e))
            raise
