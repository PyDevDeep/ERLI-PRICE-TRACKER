"""
Tests for src/integrations/telegram_client.py and src/services/alerter.py.

Coverage targets:
- TelegramClient.send_alert: happy path, TelegramError retry, RetryAfter with
  timedelta vs float, exhausted retries (reraise), generic exception propagation
- format_alert_message: price drop / rise, uk / en languages, unknown language fallback,
  delta rounding, boundary (old == new routed correctly)
- send_price_alert: delegates to telegram_client, returns True/False on exception
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import RetryAfter, TelegramError

from src.integrations.telegram_client import TelegramClient
from src.services.alerter import format_alert_message, send_price_alert

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_bot() -> MagicMock:
    """python-telegram-bot Bot mock with async send_message."""
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    return bot


@pytest.fixture
def telegram_client(mock_bot: MagicMock) -> TelegramClient:
    """TelegramClient with injected mock Bot and fixed chat_id."""
    return TelegramClient(bot=mock_bot, chat_id="123456")


@pytest.fixture
def mock_telegram_client() -> AsyncMock:
    """Standalone mock for send_price_alert tests."""
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
        """Successful send_message call returns True."""
        result = await telegram_client.send_alert("Test message")

        assert result is True
        mock_bot.send_message.assert_awaited_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_passes_correct_chat_id(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        """chat_id from settings is forwarded to send_message."""
        await telegram_client.send_alert("msg")

        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == "123456"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_passes_message_text(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        """Message text is forwarded verbatim to send_message."""
        await telegram_client.send_alert("<b>Alert!</b>")

        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert call_kwargs["text"] == "<b>Alert!</b>"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_disables_web_preview(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        """disable_web_page_preview=True must always be set."""
        await telegram_client.send_alert("msg")

        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert call_kwargs.get("disable_web_page_preview") is True

    # ---------------------------------------------------------------------------
    # RetryAfter handling
    # ---------------------------------------------------------------------------

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_retry_after_float_sleeps_and_reraises(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        """RetryAfter with float retry_after → asyncio.sleep(float) called each retry attempt."""
        retry_err = RetryAfter(retry_after=5)
        mock_bot.send_message.side_effect = retry_err

        with (
            patch(
                "src.integrations.telegram_client.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep,
            pytest.raises(TelegramError),
        ):
            await telegram_client.send_alert("msg")

        # tenacity also calls asyncio.sleep for wait_exponential — filter by our arg
        rate_limit_sleeps = [c for c in mock_sleep.await_args_list if c.args == (5.0,)]
        assert len(rate_limit_sleeps) == 3, (
            f"Expected 3 RetryAfter sleeps with 5.0s, got: {mock_sleep.await_args_list}"
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_retry_after_timedelta_sleeps_total_seconds(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        """RetryAfter.retry_after as timedelta → sleep receives total_seconds() value.

        RetryAfter.retry_after is a read-only property, so we test the isinstance branch
        by enabling PTB's timedelta mode via environment variable.
        """
        # PTB_TIMEDELTA=true makes retry_after return timedelta instead of float
        import os

        os.environ["PTB_TIMEDELTA"] = "true"
        try:
            retry_err = RetryAfter(retry_after=42)
            # With PTB_TIMEDELTA=true, retry_after is a timedelta(seconds=42)
            assert isinstance(retry_err.retry_after, timedelta), (
                "Expected timedelta with PTB_TIMEDELTA=true — check PTB version"
            )
            mock_bot.send_message.side_effect = retry_err

            with (
                patch(
                    "src.integrations.telegram_client.asyncio.sleep", new_callable=AsyncMock
                ) as mock_sleep,
                pytest.raises(TelegramError),
            ):
                await telegram_client.send_alert("msg")

            # tenacity also calls asyncio.sleep for wait_exponential — filter by our arg
            rate_limit_sleeps = [c for c in mock_sleep.await_args_list if c.args == (42.0,)]
            assert len(rate_limit_sleeps) == 3, (
                f"Expected 3 RetryAfter sleeps with 42.0s, got: {mock_sleep.await_args_list}"
            )
        finally:
            os.environ.pop("PTB_TIMEDELTA", None)

    # ---------------------------------------------------------------------------
    # TelegramError propagation
    # ---------------------------------------------------------------------------

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_telegram_error_reraises(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        """Generic TelegramError is re-raised after being logged."""
        mock_bot.send_message.side_effect = TelegramError("network fail")

        with pytest.raises(TelegramError, match="network fail"):
            await telegram_client.send_alert("msg")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_alert_exhausted_retries_reraises(
        self, telegram_client: TelegramClient, mock_bot: MagicMock
    ) -> None:
        """After 3 tenacity attempts (stop_after_attempt=3) the error is re-raised."""
        mock_bot.send_message.side_effect = TelegramError("persistent error")

        with pytest.raises(TelegramError):
            await telegram_client.send_alert("msg")

        # tenacity викликає send_message тричі перед reraise
        assert mock_bot.send_message.await_count == 3


# ---------------------------------------------------------------------------
# format_alert_message — pure function
# ---------------------------------------------------------------------------


class TestFormatAlertMessage:
    @pytest.mark.unit
    def test_format_price_drop_english(self) -> None:
        """Price drop with lang=en uses en lexicon and correct format."""
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
        # price_drop шаблон містить ⬇️
        assert "⬇️" in result

    @pytest.mark.unit
    def test_format_price_rise_english(self) -> None:
        """Price rise with lang=en triggers price_rise template with ⬆️."""
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
        """Price drop with lang=uk uses uk lexicon."""
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
        """Unknown language code falls back to 'en' lexicon."""
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
        """abs_delta is rounded to 2 decimal places in the output."""
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
        """new_price < old_price → drop template; new_price >= old_price → rise template."""
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
        """Output is exactly 3 lines: title, price_line, link."""
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
        """Returns True when telegram_client.send_alert succeeds."""
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
        """The message passed to send_alert is the output of format_alert_message."""
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
        """Returns False (and logs) when send_alert raises any exception."""
        mock_telegram_client.send_alert.side_effect = TelegramError("boom")

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
        """Non-Telegram exceptions (e.g. network error) also return False."""
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
