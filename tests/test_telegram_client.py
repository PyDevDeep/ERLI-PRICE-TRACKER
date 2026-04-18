"""
Tests for src/integrations/telegram_client.py and src/services/alerter.py.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from src.integrations.telegram_client import TelegramClient
from src.services.alerter import format_alert_message, send_price_alert


def _make_retry_after(seconds: int) -> TelegramRetryAfter:
    exc = TelegramRetryAfter.__new__(TelegramRetryAfter)
    object.__setattr__(exc, "retry_after", seconds)
    return exc


def _make_api_error(message: str = "error") -> TelegramAPIError:
    from aiogram.methods import SendMessage

    return TelegramAPIError(method=SendMessage(chat_id=1, text="x"), message=message)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_bot() -> MagicMock:
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    bot.session = MagicMock()
    bot.session.close = AsyncMock()
    return bot


@pytest.fixture
def telegram_client(mock_bot: MagicMock) -> TelegramClient:
    return TelegramClient(bot=mock_bot, chat_id="123456")


@pytest.fixture
def mock_telegram_client() -> AsyncMock:
    client = MagicMock(spec=TelegramClient)
    client.send_alert = AsyncMock(return_value=True)
    return client


# ---------------------------------------------------------------------------
# TelegramClient.send_alert — happy path
# ---------------------------------------------------------------------------


class TestTelegramClientSendAlert:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_success_returns_true(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        result = await telegram_client.send_alert("Test message")

        assert result is True
        mock_bot.send_message.assert_awaited_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_passes_correct_chat_id(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        await telegram_client.send_alert("msg")

        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == "123456"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_passes_message_text(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        await telegram_client.send_alert("<b>Alert!</b>")

        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert call_kwargs["text"] == "<b>Alert!</b>"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_disables_web_preview(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        await telegram_client.send_alert("msg")

        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert call_kwargs.get("disable_web_page_preview") is True

    # ---------------------------------------------------------------------------
    # RetryAfter handling
    # ---------------------------------------------------------------------------

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_retry_after_float_sleeps_and_returns_false(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        """TelegramRetryAfter with float retry_after → sleeps and retries, returns False."""
        mock_bot.send_message.side_effect = _make_retry_after(5)

        with patch(
            "src.integrations.telegram_client.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            result = await telegram_client.send_alert("msg")

        assert result is False
        rate_limit_sleeps = [c for c in mock_sleep.await_args_list if c.args == (5.0,)]
        assert len(rate_limit_sleeps) == 3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_retry_after_int_converts_to_float_for_sleep(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        """TelegramRetryAfter.retry_after (int) is cast to float for asyncio.sleep."""
        mock_bot.send_message.side_effect = _make_retry_after(42)

        with patch(
            "src.integrations.telegram_client.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            result = await telegram_client.send_alert("msg")

        assert result is False
        rate_limit_sleeps = [c for c in mock_sleep.await_args_list if c.args == (42.0,)]
        assert len(rate_limit_sleeps) == 3

    # ---------------------------------------------------------------------------
    # TelegramAPIError handling
    # ---------------------------------------------------------------------------

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_api_error_returns_false_after_retries(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        """Persistent TelegramAPIError exhausts retries and returns False."""
        mock_bot.send_message.side_effect = _make_api_error("network fail")

        with patch("src.integrations.telegram_client.asyncio.sleep", new_callable=AsyncMock):
            result = await telegram_client.send_alert("msg")

        assert result is False
        assert mock_bot.send_message.await_count == 3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_succeeds_after_transient_error(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        """Recovers and returns True if one attempt fails but next succeeds."""
        mock_bot.send_message.side_effect = [_make_api_error("temp"), MagicMock()]

        with patch("src.integrations.telegram_client.asyncio.sleep", new_callable=AsyncMock):
            result = await telegram_client.send_alert("msg")

        assert result is True
        assert mock_bot.send_message.await_count == 2


# ---------------------------------------------------------------------------
# format_alert_message — pure function
# ---------------------------------------------------------------------------


class TestFormatAlertMessage:
    @pytest.mark.unit
    def test_format_price_drop_english(self) -> None:
        with patch("src.services.alerter.settings") as mock_settings:
            mock_settings.ALERT_LANGUAGE = "en"
            result = format_alert_message(
                product_name="Widget",
                old_price=Decimal("200.00"),
                new_price=Decimal("160.00"),
                delta_percent=-20.0,
                url="https://erli.pl/produkt/widget",
            )

        assert "Price Alert" in result
        assert "Widget" in result
        assert "200" in result
        assert "160" in result
        assert "20.0%" in result
        assert "erli.pl/produkt/widget" in result
        assert "⬇️" in result

    @pytest.mark.unit
    def test_format_price_rise_english(self) -> None:
        with patch("src.services.alerter.settings") as mock_settings:
            mock_settings.ALERT_LANGUAGE = "en"
            result = format_alert_message(
                product_name="Gadget",
                old_price=Decimal("100.00"),
                new_price=Decimal("120.00"),
                delta_percent=20.0,
                url="https://erli.pl/produkt/gadget",
            )

        assert "⬆️" in result
        assert "⬇️" not in result

    @pytest.mark.unit
    def test_format_price_drop_ukrainian(self) -> None:
        with patch("src.services.alerter.settings") as mock_settings:
            mock_settings.ALERT_LANGUAGE = "uk"
            result = format_alert_message(
                product_name="Товар",
                old_price=Decimal("500.00"),
                new_price=Decimal("400.00"),
                delta_percent=-20.0,
                url="https://erli.pl/produkt/tovar",
            )

        assert "Зміна ціни" in result
        assert "Товар" in result
        assert "⬇️" in result

    @pytest.mark.unit
    def test_format_unknown_language_falls_back_to_english(self) -> None:
        with patch("src.services.alerter.settings") as mock_settings:
            mock_settings.ALERT_LANGUAGE = "fr"
            result = format_alert_message(
                product_name="Produit",
                old_price=Decimal("100.00"),
                new_price=Decimal("80.00"),
                delta_percent=-20.0,
                url="https://erli.pl/produkt/produit",
            )

        assert "Price Alert" in result

    @pytest.mark.unit
    def test_format_delta_rounded_to_two_decimal_places(self) -> None:
        with patch("src.services.alerter.settings") as mock_settings:
            mock_settings.ALERT_LANGUAGE = "en"
            result = format_alert_message(
                product_name="Item",
                old_price=Decimal("100.00"),
                new_price=Decimal("85.00"),
                delta_percent=-15.123456,
                url="https://erli.pl/produkt/item",
            )

        assert "15.12%" in result

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "old_price,new_price,delta_percent,expected_arrow",
        [
            (Decimal("100"), Decimal("80"), -20.0, "⬇️"),
            (Decimal("100"), Decimal("120"), 20.0, "⬆️"),
        ],
    )
    def test_format_price_direction_routing(
        self,
        old_price: Decimal,
        new_price: Decimal,
        delta_percent: float,
        expected_arrow: str,
    ) -> None:
        with patch("src.services.alerter.settings") as mock_settings:
            mock_settings.ALERT_LANGUAGE = "en"
            result = format_alert_message(
                product_name="X",
                old_price=old_price,
                new_price=new_price,
                delta_percent=delta_percent,
                url="https://erli.pl/produkt/x",
            )

        assert expected_arrow in result

    @pytest.mark.unit
    def test_format_output_has_three_lines(self) -> None:
        with patch("src.services.alerter.settings") as mock_settings:
            mock_settings.ALERT_LANGUAGE = "en"
            result = format_alert_message(
                product_name="Item",
                old_price=Decimal("100"),
                new_price=Decimal("90"),
                delta_percent=-10.0,
                url="https://erli.pl/produkt/item",
            )

        assert result.count("\n") == 2


# ---------------------------------------------------------------------------
# send_price_alert — async orchestrator
# ---------------------------------------------------------------------------


class TestSendPriceAlert:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_price_alert_returns_true_on_success(
        self, mock_telegram_client: AsyncMock
    ) -> None:
        with patch("src.services.alerter.settings") as mock_settings:
            mock_settings.ALERT_LANGUAGE = "en"
            result = await send_price_alert(
                telegram_client=mock_telegram_client,
                product_name="Widget",
                old_price=Decimal("100.00"),
                new_price=Decimal("80.00"),
                delta_percent=-20.0,
                url="https://erli.pl/produkt/widget",
            )

        assert result is True
        mock_telegram_client.send_alert.assert_awaited_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_price_alert_passes_formatted_message(
        self, mock_telegram_client: AsyncMock
    ) -> None:
        with patch("src.services.alerter.settings") as mock_settings:
            mock_settings.ALERT_LANGUAGE = "en"
            await send_price_alert(
                telegram_client=mock_telegram_client,
                product_name="Gadget",
                old_price=Decimal("200.00"),
                new_price=Decimal("180.00"),
                delta_percent=-10.0,
                url="https://erli.pl/produkt/gadget",
            )

        sent_message: str = mock_telegram_client.send_alert.call_args.args[0]
        assert "Gadget" in sent_message
        assert "200" in sent_message

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_price_alert_returns_false_on_exception(
        self, mock_telegram_client: AsyncMock
    ) -> None:
        mock_telegram_client.send_alert.side_effect = _make_api_error("boom")

        with patch("src.services.alerter.settings") as mock_settings:
            mock_settings.ALERT_LANGUAGE = "en"
            result = await send_price_alert(
                telegram_client=mock_telegram_client,
                product_name="BrokenItem",
                old_price=Decimal("100.00"),
                new_price=Decimal("50.00"),
                delta_percent=-50.0,
                url="https://erli.pl/produkt/broken",
            )

        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_price_alert_returns_false_on_generic_exception(
        self, mock_telegram_client: AsyncMock
    ) -> None:
        mock_telegram_client.send_alert.side_effect = RuntimeError("unexpected")

        with patch("src.services.alerter.settings") as mock_settings:
            mock_settings.ALERT_LANGUAGE = "en"
            result = await send_price_alert(
                telegram_client=mock_telegram_client,
                product_name="Item",
                old_price=Decimal("100.00"),
                new_price=Decimal("90.00"),
                delta_percent=-10.0,
                url="https://erli.pl/produkt/item",
            )

        assert result is False
