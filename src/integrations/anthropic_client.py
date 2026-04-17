import httpx
import structlog

logger = structlog.get_logger(__name__)

Message = dict[str, str]


class AnthropicError(Exception):
    """Виняток для помилок взаємодії з Anthropic API."""

    pass


class AnthropicClient:
    def __init__(self, api_key: str, model: str, timeout: int) -> None:
        self.model = model
        self.client = httpx.AsyncClient(
            base_url="https://api.anthropic.com/v1",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=httpx.Timeout(timeout),
        )

    async def complete(self, messages: list[Message], max_tokens: int = 1000) -> str:
        """
        Виконує запит до /messages.
        Конвертує формат OpenAI (system role) у формат Anthropic.
        """
        logger.info("anthropic_request_start", model=self.model, max_tokens=max_tokens)

        system_prompt = ""
        anthropic_messages: list[Message] = []

        # Конверсія формату згідно зі специфікацією
        for msg in messages:
            if msg["role"] == "system":
                # Конкатенуємо системні повідомлення, якщо їх декілька
                system_prompt += msg["content"] + "\n"
            else:
                anthropic_messages.append({"role": msg["role"], "content": msg["content"]})

        payload: dict[str, str | int | list[Message]] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
        }

        if system_prompt:
            payload["system"] = system_prompt.strip()

        try:
            response = await self.client.post("/messages", json=payload)
            response.raise_for_status()

            data = response.json()
            content = data["content"][0]["text"]

            usage = data.get("usage", {})
            logger.info("anthropic_request_success", usage=usage)

            return content

        except httpx.HTTPStatusError as e:
            logger.error(
                "anthropic_http_error", status=e.response.status_code, body=e.response.text
            )
            raise AnthropicError(
                f"Anthropic HTTP error {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            logger.error("anthropic_network_error", error=str(e))
            raise AnthropicError(f"Anthropic network error: {e}") from e

    async def close(self) -> None:
        """Graceful shutdown клієнта."""
        await self.client.aclose()
