from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from src.config.lexicon import LEXICON
from src.config.settings import settings
from src.models.base import async_session_maker
from src.services.product_repo import get_or_create_product

_lex: dict[str, str] = LEXICON.get(settings.ALERT_LANGUAGE, LEXICON["en"])

router = Router(name="products_router")


class AddProduct(StatesGroup):
    waiting_for_url = State()


def get_cancel_kb() -> ReplyKeyboardMarkup:
    """Клавіатура для скасування дії."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=_lex["btn_cancel"])]], resize_keyboard=True
    )


@router.message(Command(commands=["cancel"]), StateFilter(AddProduct))
@router.message(F.text == _lex["btn_cancel"], StateFilter(AddProduct))
async def cmd_cancel(message: Message, state: FSMContext):
    """Вихід з FSM."""
    await state.clear()
    await message.answer(text=_lex["cancel"], reply_markup=ReplyKeyboardRemove())


@router.message(Command(commands=["add"]), StateFilter(None))
async def cmd_add(message: Message, state: FSMContext):
    """Початок сценарію додавання."""
    await state.set_state(AddProduct.waiting_for_url)
    await message.answer(text=_lex["ask_url"], reply_markup=get_cancel_kb())


@router.message(StateFilter(AddProduct.waiting_for_url))
async def process_url(message: Message, state: FSMContext):
    """Обробка та валідація посилання."""
    url = message.text.strip() if message.text else ""

    if not url.startswith("https://erli.pl/produkt/"):
        await message.answer(text=_lex["invalid_url"])
        return

    async with async_session_maker() as session:
        await get_or_create_product(session, url=url)
        await session.commit()

    await state.clear()
    await message.answer(text=_lex["added_success"], reply_markup=ReplyKeyboardRemove())
