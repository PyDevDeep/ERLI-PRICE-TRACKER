import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.routes import router as api_router
from src.bot.setup import create_bot, create_dispatcher
from src.config.settings import settings
from src.exceptions import BaseAppError
from src.integrations.ai_router import AIRouter
from src.integrations.anthropic_client import AnthropicClient
from src.integrations.openai_client import OpenAIClient
from src.scheduler.jobs import (
    scheduler,  # type: ignore[import-untyped]  # apscheduler==3.11.2 lacks py.typed
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Управління життєвим циклом додатку."""
    logger.info("app_starting")

    # 1-3. Ініціалізація AI Router та його під-клієнтів
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

    # 4. Inject ai_router у планувальник
    scheduler.ai_router = ai_router

    # 5. Запуск APScheduler
    scheduler.start()
    logger.info("scheduler_started", interval_hours=settings.SCRAPE_INTERVAL_HOURS)

    # 6. Ініціалізація та запуск Telegram Бота
    bot = create_bot()
    dp = create_dispatcher()

    logger.info("bot_starting")
    # Запускаємо polling бота у фоновому таску, щоб не блокувати FastAPI
    bot_task: asyncio.Task[None] = asyncio.create_task(dp.start_polling(bot))  # type: ignore[misc]

    yield  # Додаток працює

    # --- Shutdown sequence ---
    logger.info("app_shutting_down")

    # Безпечна зупинка бота
    await dp.stop_polling()
    bot_task.cancel()
    await bot.session.close()
    logger.info("bot_stopped")

    # Зупинка планувальника та клієнтів
    scheduler.shutdown()
    await ai_router.close()

    logger.info("app_shutdown_complete")


app = FastAPI(
    title="ERLI.PL Price Tracker",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)


@app.exception_handler(BaseAppError)
async def app_error_handler(request: Request, exc: BaseAppError):
    """Глобальний обробник кастомних винятків для API."""
    return JSONResponse(
        status_code=400,  # Загальний код клієнтської помилки
        content={"error": exc.__class__.__name__, "message": exc.message},
    )


@app.get("/health")
@app.head("/health")
async def health_check() -> dict[str, object]:
    return {"status": "ok", "scheduler_running": scheduler.running}  # type: ignore[no-untyped-call]
