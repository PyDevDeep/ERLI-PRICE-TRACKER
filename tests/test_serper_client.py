"""
Tests for src/integrations/serper_client.py — SerperClient.scrape_url.

Coverage targets:
- Happy path: successful POST returns parsed dict
- HTTP 4xx non-retryable errors → SerperAPIError (400, 401, 403, 404)
- HTTP 5xx retryable errors → re-raise httpx.HTTPStatusError after 3 attempts
- Network errors (RequestError) → SerperAPIError
- Correct headers and payload forwarded to httpx
"""

from collections.abc import Mapping
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.exceptions import SerperAPIError
from src.integrations.serper_client import SerperClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> SerperClient:
    """SerperClient with a fixed API key, not reading from settings."""
    with patch("src.integrations.serper_client.settings") as mock_settings:
        mock_settings.SERPER_API_KEY = "test-api-key"
        return SerperClient()


def _make_response(
    status_code: int, json_data: Mapping[str, object] | None = None, text: str = ""
) -> MagicMock:
    """Build a mock httpx.Response with the given status code and body."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestSerperClientScrapeUrl:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scrape_url_success_returns_dict(self, client: SerperClient) -> None:
        """Successful POST returns parsed JSON as dict."""
        payload = {"text": "product text", "jsonld": {"name": "Widget"}}
        mock_resp = _make_response(200, json_data=payload)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_http

            result = await client.scrape_url("https://erli.pl/produkt/widget")

        assert result == payload

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scrape_url_posts_correct_json_body(self, client: SerperClient) -> None:
        """URL is forwarded in the request body as {'url': ...}."""
        mock_resp = _make_response(200, json_data={})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_http

            await client.scrape_url("https://erli.pl/produkt/test")

        call_kwargs = mock_http.post.call_args.kwargs
        assert call_kwargs["json"] == {"url": "https://erli.pl/produkt/test"}

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scrape_url_sends_api_key_header(self, client: SerperClient) -> None:
        """X-API-KEY header is sent with every request."""
        mock_resp = _make_response(200, json_data={})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_http

            await client.scrape_url("https://erli.pl/produkt/test")

        call_kwargs = mock_http.post.call_args.kwargs
        assert call_kwargs["headers"]["X-API-KEY"] == "test-api-key"

    # ---------------------------------------------------------------------------
    # Non-retryable HTTP errors → SerperAPIError
    # ---------------------------------------------------------------------------

    @pytest.mark.unit
    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code", [400, 401, 403, 404])
    async def test_scrape_url_non_retryable_status_raises_serper_error(
        self, client: SerperClient, status_code: int
    ) -> None:
        """HTTP 4xx (400/401/403/404) → SerperAPIError without retry."""
        mock_resp = _make_response(status_code, text="error body")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_http

            with pytest.raises(SerperAPIError) as exc_info:
                await client.scrape_url("https://erli.pl/produkt/bad")

        assert exc_info.value.status_code == status_code
        assert exc_info.value.url == "https://erli.pl/produkt/bad"

    # ---------------------------------------------------------------------------
    # Retryable HTTP errors → re-raise after 3 attempts
    # ---------------------------------------------------------------------------

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scrape_url_server_error_retries_and_reraises(self, client: SerperClient) -> None:
        """HTTP 500 is retried 3 times by tenacity before re-raising."""
        mock_resp = _make_response(500, text="server error")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_http

            with pytest.raises(httpx.HTTPStatusError):
                await client.scrape_url("https://erli.pl/produkt/fail")

        assert mock_http.post.await_count == 3

    # ---------------------------------------------------------------------------
    # Network errors → SerperAPIError
    # ---------------------------------------------------------------------------

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scrape_url_network_error_raises_serper_error(self, client: SerperClient) -> None:
        """httpx.RequestError (timeout, connection reset) → SerperAPIError."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused", request=MagicMock())
            )
            mock_client_cls.return_value = mock_http

            with pytest.raises(SerperAPIError) as exc_info:
                await client.scrape_url("https://erli.pl/produkt/unreachable")

        assert exc_info.value.status_code is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scrape_url_network_error_includes_url(self, client: SerperClient) -> None:
        """SerperAPIError caused by a network failure contains the correct url."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(
                side_effect=httpx.TimeoutException("timeout", request=MagicMock())
            )
            mock_client_cls.return_value = mock_http

            with pytest.raises(SerperAPIError) as exc_info:
                await client.scrape_url("https://erli.pl/produkt/slow")

        assert exc_info.value.url == "https://erli.pl/produkt/slow"
