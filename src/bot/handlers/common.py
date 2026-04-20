from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from src.config.lexicon import LEXICON
from src.config.settings import settings

router = Router(name="common_router")

_lex: dict[str, str] = LEXICON.get(settings.ALERT_LANGUAGE, LEXICON["en"])


def get_main_kb() -> ReplyKeyboardMarkup:
    """Build the main reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_lex["btn_main_add"]), KeyboardButton(text=_lex["btn_main_list"])],
            [KeyboardButton(text=_lex["btn_main_help"])],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    await message.answer(text=_lex["start"], reply_markup=get_main_kb())


@router.message(Command(commands=["help"]))
@router.message(F.text == _lex["btn_main_help"])
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    await message.answer(text=_lex["help"], parse_mode="HTML", reply_markup=get_main_kb())
