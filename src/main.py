from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI

from src.config.settings import settings
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

    # 4. Inject ai_router у планувальник (уникаємо глобальних змінних та циклічних імпортів)
    scheduler.ai_router = ai_router

    # Запуск APScheduler
    scheduler.start()  # type: ignore[no-untyped-call]
    logger.info("scheduler_started", interval_hours=settings.SCRAPE_INTERVAL_HOURS)

    yield  # Додаток працює

    # --- Shutdown sequence ---
    logger.info("app_shutting_down")

    scheduler.shutdown()  # type: ignore[no-untyped-call]
    await ai_router.close()

    logger.info("app_shutdown_complete")


app = FastAPI(
    title="ERLI.PL Price Tracker",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict[str, object]:
    return {"status": "ok", "scheduler_running": scheduler.running}  # type: ignore[no-untyped-call]
