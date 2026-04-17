from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src.config.settings import Settings
from src.integrations.ai_router import AIRouter, AIRouterError
from src.integrations.anthropic_client import AnthropicError
from src.integrations.openai_client import OpenAIError


@pytest.fixture
def mock_settings() -> Settings:
    # Заповнюємо обов'язкові поля dummy-даними для валідації
    settings = Settings(
        SERPER_API_KEY="test",
        TELEGRAM_BOT_TOKEN="test",
        TELEGRAM_CHAT_ID="test",
        DATABASE_URL="test",
        OPENAI_API_KEY="test",
        ANTHROPIC_API_KEY="test",
    )
    # Форсуємо параметри Circuit Breaker для тестів
    settings.AI_ROUTER_CIRCUIT_BREAKER_THRESHOLD = 3
    settings.AI_ROUTER_CIRCUIT_BREAKER_RESET_SECONDS = 60
    return settings


@pytest.fixture
def mock_openai() -> AsyncMock:
    mock = AsyncMock()
    mock.complete.return_value = "openai response"
    return mock


@pytest.fixture
def mock_anthropic() -> AsyncMock:
    mock = AsyncMock()
    mock.complete.return_value = "anthropic response"
    return mock


@pytest.fixture
def router(mock_openai: AsyncMock, mock_anthropic: AsyncMock, mock_settings: Settings) -> AIRouter:
    return AIRouter(mock_openai, mock_anthropic, mock_settings)


@pytest.mark.asyncio
async def test_primary_success(
    router: AIRouter, mock_openai: AsyncMock, mock_anthropic: AsyncMock
) -> None:
    response = await router.complete([{"role": "user", "content": "test"}])
    assert response.provider == "openai"
    assert response.content == "openai response"
    mock_openai.complete.assert_called_once()
    mock_anthropic.complete.assert_not_called()


@pytest.mark.asyncio
async def test_primary_failure_fallback_success(
    router: AIRouter, mock_openai: AsyncMock, mock_anthropic: AsyncMock
) -> None:
    mock_openai.complete.side_effect = OpenAIError("HTTP 500")
    response = await router.complete([{"role": "user", "content": "test"}])
    assert response.provider == "anthropic"
    assert response.content == "anthropic response"
    mock_openai.complete.assert_called_once()
    mock_anthropic.complete.assert_called_once()


@pytest.mark.asyncio
async def test_both_fail(
    router: AIRouter, mock_openai: AsyncMock, mock_anthropic: AsyncMock
) -> None:
    mock_openai.complete.side_effect = OpenAIError("Fail")
    mock_anthropic.complete.side_effect = AnthropicError("Fail")

    with pytest.raises(AIRouterError) as exc_info:
        await router.complete([{"role": "user", "content": "test"}])

    assert isinstance(exc_info.value.primary_error, OpenAIError)
    assert isinstance(exc_info.value.fallback_error, AnthropicError)


@pytest.mark.asyncio
async def test_circuit_breaker_opens_and_skips_primary(
    router: AIRouter, mock_openai: AsyncMock, mock_anthropic: AsyncMock
) -> None:
    mock_openai.complete.side_effect = OpenAIError("Fail")

    # Провалюємо запити до досягнення ліміту (3)
    for _ in range(3):
        await router.complete([{"role": "user", "content": "test"}])

    assert router._is_circuit_open() is True

    # Наступний (4-й) виклик має ігнорувати OpenAI
    mock_openai.reset_mock()
    await router.complete([{"role": "user", "content": "test"}])
    mock_openai.complete.assert_not_called()
    assert mock_anthropic.complete.call_count == 4


@pytest.mark.asyncio
async def test_circuit_breaker_resets_after_timeout(
    router: AIRouter, mock_openai: AsyncMock, mock_anthropic: AsyncMock
) -> None:
    mock_openai.complete.side_effect = OpenAIError("Fail")

    for _ in range(3):
        await router.complete([{"role": "user", "content": "test"}])

    assert router._is_circuit_open() is True

    # Емулюємо проходження часу (61 секунда)
    router._circuit_opened_at = datetime.now(timezone.utc) - timedelta(seconds=61)
    # Емулюємо відновлення OpenAI
    mock_openai.complete.side_effect = None

    response = await router.complete([{"role": "user", "content": "test"}])

    assert response.provider == "openai"
    assert router._is_circuit_open() is False
    assert router._failure_count == 0


@pytest.mark.asyncio
async def test_success_resets_failure_count(
    router: AIRouter, mock_openai: AsyncMock, mock_anthropic: AsyncMock
) -> None:
    mock_openai.complete.side_effect = OpenAIError("Fail")

    # 2 провали (менше ліміту)
    await router.complete([{"role": "user", "content": "test"}])
    await router.complete([{"role": "user", "content": "test"}])
    assert router._failure_count == 2

    # 1 успіх
    mock_openai.complete.side_effect = None
    await router.complete([{"role": "user", "content": "test"}])
    assert router._failure_count == 0
