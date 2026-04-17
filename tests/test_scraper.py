import pytest

from src.integrations.serper_client import SerperAPIError, SerperClient


@pytest.mark.integration
async def test_serper_live_request():
    """
    Перевіряє реальний запит до Serper.dev Scraping API.
    Тест впаде, якщо SERPER_API_KEY недійсний або відсутній в .env.
    """
    client = SerperClient()
    test_url = "https://erli.pl/kategoria?phrase=ps+5"

    try:
        html_text = await client.scrape_url(test_url)

        # Перевіряємо базові критерії успішного скрапінгу
        assert isinstance(html_text, str)
        assert len(html_text) > 0

        # Перевіряємо наявність польського тексту або валюти "zł",
        # що підтверджує успішне завантаження саме erli.pl
        assert "zł" in html_text.lower() or "erli" in html_text.lower()

    except SerperAPIError as e:
        pytest.fail(f"API Error during integration test: {e}")
