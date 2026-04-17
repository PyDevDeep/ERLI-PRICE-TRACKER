from __future__ import annotations

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import settings
from src.exceptions import SerperAPIError

logger = structlog.get_logger(__name__)


class SerperClient:
    def __init__(self) -> None:
        self.base_url = "https://scrape.serper.dev"
        self.headers: dict[str, str] = {
            "X-API-KEY": settings.SERPER_API_KEY,
            "Content-Type": "application/json",
        }
        # Таймаут згідно з Roadmap (1.5s latency + margin)
        self.timeout = httpx.Timeout(30.0)

    @retry(  # type: ignore[misc]
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def scrape_url(self, url: str) -> dict[str, object]:
        logger.info("serper_request_start", url=url)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"url": url},
                )
                response.raise_for_status()

                data = response.json()
                logger.info("serper_request_success", url=url)
                return data

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                logger.warning("serper_http_error", url=url, status=status)

                if status in (400, 401, 403, 404):
                    raise SerperAPIError(
                        url=url, status_code=status, message=e.response.text
                    ) from e

                raise
            except httpx.RequestError as e:
                logger.warning("serper_network_error", url=url, error=str(e))
                raise SerperAPIError(url=url, status_code=None, message=str(e)) from e
