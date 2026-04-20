from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from aiogram import F, Router

if TYPE_CHECKING:
    from src.integrations.ai_router import AIRouter

from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from sqlalchemy import delete

from src.bot.handlers.common import get_main_kb
from src.config.lexicon import LEXICON
from src.config.settings import settings
from src.integrations.serper_client import SerperClient
from src.models.base import async_session_maker
from src.models.product import Product
from src.services.parser import parse_erli_data_smart
from src.services.price_monitor import store_history
from src.services.product_repo import (
    get_or_create_product,
    get_paginated_products_with_price,
    get_product_by_id,
    get_product_history,
)

logger = structlog.get_logger(__name__)

_lex: dict[str, str] = LEXICON.get(settings.ALERT_LANGUAGE, LEXICON["en"])

router = Router(name="products_router")


class AddProduct(StatesGroup):
    waiting_for_url = State()


def get_cancel_kb() -> ReplyKeyboardMarkup:
    """Build the cancel reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=_lex["btn_cancel"])]], resize_keyboard=True
    )


def get_product_kb(product_id: int) -> InlineKeyboardMarkup:
    """Build inline keyboard with history and delete buttons for a product."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=_lex["btn_history"], callback_data=f"hist_{product_id}"),
                InlineKeyboardButton(
                    text=_lex["btn_delete"], callback_data=f"del_conf_{product_id}"
                ),
            ]
        ]
    )


@router.message(Command(commands=["cancel"]), StateFilter(AddProduct))
@router.message(F.text == _lex["btn_cancel"], StateFilter(AddProduct))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Handle /cancel command — clear FSM state and return to main menu."""
    await state.clear()
    await message.answer(text=_lex["cancel"], reply_markup=get_main_kb())


@router.message(Command(commands=["add"]), StateFilter(None))
@router.message(F.text == _lex["btn_main_add"], StateFilter(None))
async def cmd_add(message: Message, state: FSMContext) -> None:
    """Handle /add command — prompt the user for a product URL."""
    await state.set_state(AddProduct.waiting_for_url)
    await message.answer(text=_lex["ask_url"], reply_markup=get_cancel_kb())


@router.message(StateFilter(AddProduct.waiting_for_url))
async def process_url(message: Message, state: FSMContext, ai_router: "AIRouter") -> None:
    """Validate the URL, scrape the product, and store it in the database."""
    url = message.text.strip() if message.text else ""

    if not url.startswith("https://erli.pl/produkt/"):
        await message.answer(text=_lex["invalid_url"])
        return

    status_msg = await message.answer(text=_lex["adding_in_progress"])

    try:
        serper = SerperClient()
        raw_data = await serper.scrape_url(url)
        parsed = await parse_erli_data_smart(raw_data, ai_router)

        async with async_session_maker() as session:
            product = await get_or_create_product(session, url=url, name=parsed.get("name"))
            await store_history(
                session=session,
                product_id=product.id,
                price_min=parsed.get("price_min"),
                price_max=parsed.get("price_max"),
                rating=parsed.get("rating"),
            )
            await session.commit()

        await state.clear()
        await status_msg.delete()
        await message.answer(text=_lex["added_success"], reply_markup=get_main_kb())

    except Exception:
        logger.exception("process_url_failed", url=url)
        await state.clear()
        await message.answer(
            text=_lex.get("add_failed", "❌ Не вдалося додати товар. Спробуйте пізніше."),
            reply_markup=get_main_kb(),
        )


@router.message(Command(commands=["list"]))
@router.message(F.text == _lex["btn_main_list"])
async def cmd_list(message: Message) -> None:
    """Handle /list command — show all tracked products."""
    async with async_session_maker() as session:
        products = await get_paginated_products_with_price(session)

    if not products:
        await message.answer(_lex["empty_list"])
        return

    await message.answer(_lex["list_header"], parse_mode="HTML")
    for i, p in enumerate(products, 1):
        text = _lex["list_item"].format(
            index=i,
            name=p["name"] or "—",
            price=p["latest_price"] or "---",
            url=p["url"],
        )
        await message.answer(
            text,
            reply_markup=get_product_kb(p["id"]),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


@router.callback_query(F.data.startswith("hist_"))
async def callback_history(callback: CallbackQuery) -> None:
    """Show the last 5 price history entries for a product."""
    assert callback.data is not None
    assert isinstance(callback.message, Message)
    product_id = int(callback.data.split("_")[1])
    async with async_session_maker() as session:
        product = await get_product_by_id(session, product_id)
        history = await get_product_history(session, product_id, limit=5)

    if not history:
        await callback.answer(_lex.get("no_history", "No history found."), show_alert=True)
        return

    assert product is not None
    response = _lex["history_header"].format(name=product.name or str(product_id))
    for h in history:
        response += _lex["history_item"].format(
            date=h.scraped_at.strftime("%d.%m %H:%M"),
            price=h.price_min,
        )

    await callback.message.edit_text(response, parse_mode="HTML", reply_markup=None)
    await callback.answer()


@router.callback_query(F.data.startswith("del_conf_"))
async def callback_delete_confirm(callback: CallbackQuery) -> None:
    """Show a delete confirmation prompt for a product."""
    assert callback.data is not None
    assert isinstance(callback.message, Message)
    product_id = int(callback.data.split("_")[2])
    async with async_session_maker() as session:
        product = await get_product_by_id(session, product_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_lex["btn_confirm_delete"],
                    callback_data=f"del_exec_{product_id}",
                )
            ],
            [InlineKeyboardButton(text=_lex["btn_back"], callback_data="list_refresh")],
        ]
    )
    name = product.name if product else str(product_id)
    await callback.message.edit_text(
        _lex["confirm_delete"].format(name=name), parse_mode="HTML", reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_exec_"))
async def callback_delete_execute(callback: CallbackQuery) -> None:
    """Delete a product and confirm in the chat."""
    assert callback.data is not None
    assert isinstance(callback.message, Message)
    product_id = int(callback.data.split("_")[2])
    async with async_session_maker() as session:
        await session.execute(delete(Product).where(Product.id == product_id))
        await session.commit()

    await callback.message.edit_text(_lex["deleted"], reply_markup=None)
    await callback.answer()
