from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from src.config.lexicon import LEXICON

router = Router(name="common_router")

_L = LEXICON["uk"]


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обробник команди /start"""
    await message.answer(text=_L["start"])


@router.message(Command(commands=["help"]))
async def cmd_help(message: Message):
    """Обробник команди /help"""
    await message.answer(text=_L["help"], parse_mode="HTML")
