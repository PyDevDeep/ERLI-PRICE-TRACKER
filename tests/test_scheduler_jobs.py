"""
Tests for src/scheduler/jobs.py — scrape_all_products, generate_weekly_insights.

Coverage targets:
- scrape_all_products: missing ai_router early exit, no products early exit,
  happy path (scrape → store → compare → alert), scrape exception swallowed per-product,
  no alert when price_change is None
- generate_weekly_insights: missing ai_router early exit, no products early exit,
  no market data early exit, happy path sends report, AI exception swallowed

Strategy: patch all external dependencies (session_maker, service functions,
TelegramClient, SerperClient, AIRouter) so no real I/O occurs.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.scheduler.jobs import generate_weekly_insights, scrape_all_products
from src.services.price_monitor import PriceChange

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_product(
    product_id: int = 1, url: str = "https://erli.pl/produkt/p", name: str = "P"
) -> MagicMock:
    p = MagicMock()
    p.id = product_id
    p.url = url
    p.name = name
    return p


def _make_price_change(
    product: str = "P",
    old_price: Decimal = Decimal("100"),
    new_price: Decimal = Decimal("120"),
    delta: float = 20.0,
) -> PriceChange:
    return PriceChange(
        product=product, old_price=old_price, new_price=new_price, delta_percent=delta
    )


def _session_ctx(session: MagicMock) -> MagicMock:
    """Returns an async context manager mock that yields session."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# scrape_all_products
# ---------------------------------------------------------------------------


class TestScrapeAllProducts:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_exits_early_when_ai_router_missing(self) -> None:
        """No ai_router on scheduler → returns without touching any service."""
        from src.scheduler.jobs import scheduler

        original = scheduler.ai_router
        scheduler.ai_router = None
        try:
            with patch("src.scheduler.jobs.async_session_maker") as mock_sm:
                await scrape_all_products()
                mock_sm.assert_not_called()
        finally:
            scheduler.ai_router = original

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_exits_early_when_no_products(self) -> None:
        """Empty products list → no SerperClient calls."""
        from src.scheduler.jobs import scheduler

        ai_router = AsyncMock()
        scheduler.ai_router = ai_router

        session = AsyncMock()
        session.commit = AsyncMock()

        # scrape_all_products opens TWO session contexts: one for get_all_products,
        # one per-product (not reached here). Use side_effect to return ctx each call.
        ctx = _session_ctx(session)

        try:
            with (
                patch("src.scheduler.jobs.async_session_maker", return_value=ctx),
                patch(
                    "src.scheduler.jobs.get_all_products", new_callable=AsyncMock, return_value=[]
                ),
                patch("src.scheduler.jobs.SerperClient") as mock_serper_cls,
            ):
                await scrape_all_products()

            # SerperClient is instantiated before the empty-check, but scrape_url is never called
            mock_serper_cls.assert_called_once()
            mock_serper_cls.return_value.scrape_url.assert_not_called()
        finally:
            scheduler.ai_router = None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_happy_path_stores_and_alerts(self) -> None:
        """Full pipeline: scrape → parse → store → compare → send alert."""
        from src.scheduler.jobs import scheduler

        ai_router = AsyncMock()
        scheduler.ai_router = ai_router

        product = _make_product()
        session = AsyncMock()
        session.commit = AsyncMock()

        price_change = _make_price_change()

        try:
            with (
                patch("src.scheduler.jobs.async_session_maker", return_value=_session_ctx(session)),
                patch("src.scheduler.jobs.get_all_products", return_value=[product]),
                patch("src.scheduler.jobs.SerperClient") as mock_serper_cls,
                patch("src.scheduler.jobs.TelegramClient") as mock_tg_cls,
                patch(
                    "src.scheduler.jobs.parse_erli_data_smart",
                    new_callable=AsyncMock,
                    return_value={
                        "price_min": Decimal("120"),
                        "price_max": Decimal("120"),
                        "rating": None,
                    },
                ),
                patch("src.scheduler.jobs.store_history", new_callable=AsyncMock),
                patch(
                    "src.scheduler.jobs.compare_price",
                    new_callable=AsyncMock,
                    return_value=price_change,
                ),
                patch("src.scheduler.jobs.send_price_alert", new_callable=AsyncMock) as mock_alert,
                patch("asyncio.sleep", new_callable=AsyncMock),
            ):
                mock_serper = AsyncMock()
                mock_serper.scrape_url = AsyncMock(return_value={"text": "", "jsonld": {}})
                mock_serper_cls.return_value = mock_serper

                mock_tg = MagicMock()
                mock_tg_cls.return_value = mock_tg

                await scrape_all_products()

            mock_alert.assert_awaited_once()
            call_kwargs = mock_alert.call_args.kwargs
            assert call_kwargs["product_name"] == "P"
            assert call_kwargs["new_price"] == Decimal("120")
        finally:
            scheduler.ai_router = None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_alert_when_price_unchanged(self) -> None:
        """compare_price returns None → send_price_alert not called."""
        from src.scheduler.jobs import scheduler

        ai_router = AsyncMock()
        scheduler.ai_router = ai_router
        product = _make_product()
        session = AsyncMock()
        session.commit = AsyncMock()

        try:
            with (
                patch("src.scheduler.jobs.async_session_maker", return_value=_session_ctx(session)),
                patch("src.scheduler.jobs.get_all_products", return_value=[product]),
                patch("src.scheduler.jobs.SerperClient") as mock_serper_cls,
                patch("src.scheduler.jobs.TelegramClient"),
                patch(
                    "src.scheduler.jobs.parse_erli_data_smart",
                    new_callable=AsyncMock,
                    return_value={
                        "price_min": Decimal("100"),
                        "price_max": Decimal("100"),
                        "rating": None,
                    },
                ),
                patch("src.scheduler.jobs.store_history", new_callable=AsyncMock),
                patch(
                    "src.scheduler.jobs.compare_price", new_callable=AsyncMock, return_value=None
                ),
                patch("src.scheduler.jobs.send_price_alert", new_callable=AsyncMock) as mock_alert,
                patch("asyncio.sleep", new_callable=AsyncMock),
            ):
                mock_serper = AsyncMock()
                mock_serper.scrape_url = AsyncMock(return_value={})
                mock_serper_cls.return_value = mock_serper

                await scrape_all_products()

            mock_alert.assert_not_awaited()
        finally:
            scheduler.ai_router = None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_product_scrape_exception_swallowed_continues(self) -> None:
        """Exception during one product's scrape is logged and loop continues."""
        from src.scheduler.jobs import scheduler

        ai_router = AsyncMock()
        scheduler.ai_router = ai_router
        p1 = _make_product(1, "https://erli.pl/produkt/p1", "P1")
        p2 = _make_product(2, "https://erli.pl/produkt/p2", "P2")
        session = AsyncMock()
        session.commit = AsyncMock()

        try:
            with (
                patch("src.scheduler.jobs.async_session_maker", return_value=_session_ctx(session)),
                patch("src.scheduler.jobs.get_all_products", return_value=[p1, p2]),
                patch("src.scheduler.jobs.SerperClient") as mock_serper_cls,
                patch("src.scheduler.jobs.TelegramClient"),
                patch(
                    "src.scheduler.jobs.parse_erli_data_smart",
                    new_callable=AsyncMock,
                    return_value={"price_min": None, "price_max": None, "rating": None},
                ),
                patch("src.scheduler.jobs.store_history", new_callable=AsyncMock),
                patch(
                    "src.scheduler.jobs.compare_price", new_callable=AsyncMock, return_value=None
                ),
                patch("src.scheduler.jobs.send_price_alert", new_callable=AsyncMock),
                patch("asyncio.sleep", new_callable=AsyncMock),
            ):
                mock_serper = AsyncMock()
                mock_serper.scrape_url = AsyncMock(
                    side_effect=[RuntimeError("scrape failed"), {"text": "", "jsonld": {}}]
                )
                mock_serper_cls.return_value = mock_serper

                await scrape_all_products()

            assert mock_serper.scrape_url.await_count == 2
        finally:
            scheduler.ai_router = None


# ---------------------------------------------------------------------------
# generate_weekly_insights
# ---------------------------------------------------------------------------


class TestGenerateWeeklyInsights:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_exits_early_when_ai_router_missing(self) -> None:
        """No ai_router → returns without touching session."""
        from src.scheduler.jobs import scheduler

        scheduler.ai_router = None
        with patch("src.scheduler.jobs.async_session_maker") as mock_sm:
            await generate_weekly_insights()
            mock_sm.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_exits_early_when_no_products(self) -> None:
        """No products → no AI call."""
        from src.scheduler.jobs import scheduler

        ai_router = AsyncMock()
        scheduler.ai_router = ai_router
        session = AsyncMock()

        try:
            with (
                patch("src.scheduler.jobs.async_session_maker", return_value=_session_ctx(session)),
                patch("src.scheduler.jobs.get_all_products", return_value=[]),
            ):
                await generate_weekly_insights()
                ai_router.complete.assert_not_awaited()
        finally:
            scheduler.ai_router = None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_exits_early_when_no_market_data(self) -> None:
        """Products without history → no AI call."""
        from src.scheduler.jobs import scheduler

        ai_router = AsyncMock()
        scheduler.ai_router = ai_router
        product = _make_product()
        session = AsyncMock()

        try:
            with (
                patch("src.scheduler.jobs.async_session_maker", return_value=_session_ctx(session)),
                patch("src.scheduler.jobs.get_all_products", return_value=[product]),
                patch(
                    "src.scheduler.jobs.get_product_history",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
            ):
                await generate_weekly_insights()
                ai_router.complete.assert_not_awaited()
        finally:
            scheduler.ai_router = None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_happy_path_sends_report(self) -> None:
        """Valid history → AI called → report sent via telegram."""
        from src.scheduler.jobs import scheduler

        ai_router = AsyncMock()
        ai_response = MagicMock()
        ai_response.content = "Ціни тижня: все добре."
        ai_router.complete = AsyncMock(return_value=ai_response)
        scheduler.ai_router = ai_router

        product = _make_product(name="Test Widget")
        session = AsyncMock()

        h_new = MagicMock()
        h_new.price_min = Decimal("90")
        h_old = MagicMock()
        h_old.price_min = Decimal("100")
        history = [h_new, h_old]

        try:
            with (
                patch("src.scheduler.jobs.async_session_maker", return_value=_session_ctx(session)),
                patch("src.scheduler.jobs.get_all_products", return_value=[product]),
                patch(
                    "src.scheduler.jobs.get_product_history",
                    new_callable=AsyncMock,
                    return_value=history,
                ),
                patch("src.scheduler.jobs.TelegramClient") as mock_tg_cls,
            ):
                mock_tg = MagicMock()
                mock_tg.send_alert = AsyncMock()
                mock_tg_cls.return_value = mock_tg

                await generate_weekly_insights()

            mock_tg.send_alert.assert_awaited_once()
            sent_msg: str = mock_tg.send_alert.call_args.args[0]
            assert "інсайти" in sent_msg.lower() or "цінов" in sent_msg.lower()
            assert "Ціни тижня" in sent_msg
        finally:
            scheduler.ai_router = None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_ai_exception_swallowed(self) -> None:
        """AI router exception is logged and does not propagate."""
        from src.scheduler.jobs import scheduler

        ai_router = AsyncMock()
        ai_router.complete = AsyncMock(side_effect=RuntimeError("AI down"))
        scheduler.ai_router = ai_router

        product = _make_product()
        session = AsyncMock()

        h_new = MagicMock()
        h_new.price_min = Decimal("90")
        h_old = MagicMock()
        h_old.price_min = Decimal("100")

        try:
            with (
                patch("src.scheduler.jobs.async_session_maker", return_value=_session_ctx(session)),
                patch("src.scheduler.jobs.get_all_products", return_value=[product]),
                patch(
                    "src.scheduler.jobs.get_product_history",
                    new_callable=AsyncMock,
                    return_value=[h_new, h_old],
                ),
                patch("src.scheduler.jobs.TelegramClient"),
            ):
                await generate_weekly_insights()  # не повинно кидати
        finally:
            scheduler.ai_router = None
