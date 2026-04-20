import httpx
import structlog

logger = structlog.get_logger(__name__)


class OpenAIError(Exception):
    """Raised when an OpenAI API request fails."""

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
        """Send a /chat/completions request and return the text content."""
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
        """Close the underlying HTTP client."""
        await self.client.aclose()
