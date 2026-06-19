import pytest

from src.integrations.serper_client import SerperAPIError, SerperClient


@pytest.mark.integration
async def test_serper_live_request():
    """Verify a real request to the Serper.dev Scraping API; fails if SERPER_API_KEY is invalid or missing."""
    client = SerperClient()
    test_url = "https://erli.pl/kategoria?phrase=ps+5"

    try:
        data = await client.scrape_url(test_url)
        assert isinstance(data, dict)
        text = str(data.get("text", ""))
        assert len(text) > 0
        assert "zł" in text.lower() or "erli" in text.lower()

    except SerperAPIError as e:
        pytest.fail(f"API Error during integration test: {e}")
