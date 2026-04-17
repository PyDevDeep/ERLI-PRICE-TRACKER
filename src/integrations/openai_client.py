import httpx
import structlog

logger = structlog.get_logger(__name__)


class OpenAIError(Exception):
    """Виняток для помилок взаємодії з OpenAI API."""

    pass


class OpenAIClient:
    def __init__(self, api_key: str, model: str, timeout: int) -> None:
        self.model = model
        self.client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout),
        )

    async def complete(self, messages: list[dict[str, str]], max_tokens: int = 1000) -> str:
        """Виконує запит до /chat/completions."""
        logger.info("openai_request_start", model=self.model, max_tokens=max_tokens)

        try:
            response = await self.client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            usage = data.get("usage", {})
            logger.info("openai_request_success", usage=usage)

            return content

        except httpx.HTTPStatusError as e:
            logger.error("openai_http_error", status=e.response.status_code, body=e.response.text)
            raise OpenAIError(
                f"OpenAI HTTP error {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            logger.error("openai_network_error", error=str(e))
            raise OpenAIError(f"OpenAI network error: {e}") from e

    async def close(self) -> None:
        """Graceful shutdown клієнта."""
        await self.client.aclose()
