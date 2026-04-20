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
    """Manage application startup and shutdown: AI router, scheduler, and bot polling."""
    logger.info("app_starting")

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

    scheduler.ai_router = ai_router

    scheduler.start()
    logger.info("scheduler_started", interval_hours=settings.SCRAPE_INTERVAL_HOURS)

    bot = create_bot()
    dp = create_dispatcher()
    dp["ai_router"] = ai_router

    def _bot_crashed(task: "asyncio.Task[None]") -> None:
        if not task.cancelled() and task.exception():
            logger.error("bot_polling_crashed", error=str(task.exception()))

    logger.info("bot_starting")
    # Run bot polling as a background task so it does not block FastAPI
    bot_task: asyncio.Task[None] = asyncio.create_task(dp.start_polling(bot))  # type: ignore[misc]
    bot_task.add_done_callback(_bot_crashed)

    yield

    logger.info("app_shutting_down")

    await dp.stop_polling()
    bot_task.cancel()
    await bot.session.close()
    logger.info("bot_stopped")

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
    """Handle custom application exceptions and return a structured JSON 400 response."""
    return JSONResponse(
        status_code=400,
        content={"error": exc.__class__.__name__, "message": exc.message},
    )


@app.get("/health")
@app.head("/health")
async def health_check() -> dict[str, object]:
    return {"status": "ok", "scheduler_running": scheduler.running}  # type: ignore[no-untyped-call]
