import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import structlog

from src.config.settings import Settings
from src.integrations.anthropic_client import AnthropicClient, AnthropicError
from src.integrations.openai_client import OpenAIClient, OpenAIError

logger = structlog.get_logger(__name__)


@dataclass
class AIResponse:
    content: str
    provider: str
    latency_ms: int


class AIRouterError(Exception):
    """Виняток, коли обидва провайдери відмовили."""

    def __init__(self, message: str, primary_error: Exception, fallback_error: Exception) -> None:
        super().__init__(message)
        self.primary_error = primary_error
        self.fallback_error = fallback_error


class AIRouter:
    def __init__(
        self, openai: OpenAIClient, anthropic: AnthropicClient, settings: Settings
    ) -> None:
        self.openai = openai
        self.anthropic = anthropic

        # Налаштування Circuit Breaker
        self.threshold = settings.AI_ROUTER_CIRCUIT_BREAKER_THRESHOLD
        self.reset_seconds = settings.AI_ROUTER_CIRCUIT_BREAKER_RESET_SECONDS

        # Стан Circuit Breaker
        self._failure_count: int = 0
        self._circuit_opened_at: datetime | None = None

    def _is_circuit_open(self) -> bool:
        if self._failure_count >= self.threshold and self._circuit_opened_at:
            # Перевіряємо, чи минув час блокування
            elapsed = datetime.now(timezone.utc) - self._circuit_opened_at
            if elapsed > timedelta(seconds=self.reset_seconds):
                logger.info(
                    "ai_router_circuit_half_open", msg="Reset timeout passed, trying primary"
                )
                return False
            return True
        return False

    def _record_success(self) -> None:
        if self._failure_count > 0:
            logger.info("ai_router_circuit_closed", msg="Primary provider recovered")
        self._failure_count = 0
        self._circuit_opened_at = None

    def _record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self.threshold and not self._circuit_opened_at:
            self._circuit_opened_at = datetime.now(timezone.utc)
            logger.error("ai_router_circuit_open", failure_count=self._failure_count)

    async def complete(self, messages: list[dict[str, str]], max_tokens: int = 1000) -> AIResponse:
        start_time = time.perf_counter()
        primary_error = None

        if not self._is_circuit_open():
            try:
                content = await self.openai.complete(messages, max_tokens)
                self._record_success()
                latency = int((time.perf_counter() - start_time) * 1000)
                return AIResponse(content=content, provider="openai", latency_ms=latency)
            except OpenAIError as e:
                primary_error = e
                self._record_failure()
                logger.warning("ai_router_primary_failed", error=str(e))
        else:
            logger.warning("ai_router_skipping_primary", reason="circuit_breaker_open")
            primary_error = Exception("Circuit breaker is OPEN")

        # Fallback на Anthropic
        try:
            content = await self.anthropic.complete(messages, max_tokens)
            latency = int((time.perf_counter() - start_time) * 1000)
            return AIResponse(content=content, provider="anthropic", latency_ms=latency)
        except AnthropicError as e:
            logger.error("ai_router_fallback_failed", error=str(e))
            raise AIRouterError(
                "Both primary and fallback AI providers failed.",
                primary_error=primary_error,
                fallback_error=e,
            ) from e

    async def close(self) -> None:
        """Закриває з'єднання обох клієнтів."""
        await self.openai.close()
        await self.anthropic.close()
