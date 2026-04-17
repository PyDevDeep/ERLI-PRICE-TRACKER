from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from src.config.lexicon import LEXICON

# Створюємо роутер для базових команд
router = Router(name="common_router")


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обробник команди /start"""
    await message.answer(text=LEXICON["start"])


@router.message(Command(commands=["help"]))
async def cmd_help(message: Message):
    """Обробник команди /help"""
    await message.answer(text=LEXICON["help"], parse_mode="HTML")
