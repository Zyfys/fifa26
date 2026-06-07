"""Фоллбэк: мягкая обработка любого текста, не пойманного другими хэндлерами.

Включается ПОСЛЕДНИМ роутером — ловит мусорный ввод вне ожидаемых состояний
(например текст в шагах, где нужен выбор кнопкой) без обращения к БД.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

router = Router()


@router.message()
async def on_unexpected(message: Message) -> None:
    await message.answer("Не понял 🤔 Используй кнопки ниже или начни заново: /start")
