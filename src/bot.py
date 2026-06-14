"""Точка входа бота: диспетчер, middlewares, роутеры, polling."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, ErrorEvent, Message

from src.config import settings
from src.handlers import build_root_router
from src.handlers.results import autofetch_loop
from src.middlewares import DbSessionMiddleware, ThrottlingMiddleware

ERROR_TEXT = "⚠️ Что-то пошло не так. Попробуйте /start."


async def on_error(event: ErrorEvent) -> None:
    """Глобальный обработчик: логирует исключение и не даёт боту упасть."""
    logging.exception("Необработанное исключение в хэндлере: %s", event.exception)

    # Пытаемся дружелюбно ответить пользователю, если есть куда.
    update = event.update
    try:
        if isinstance(update.message, Message):
            await update.message.answer(ERROR_TEXT)
        elif isinstance(update.callback_query, CallbackQuery):
            await update.callback_query.answer(ERROR_TEXT, show_alert=True)
    except Exception:  # noqa: BLE001 — уведомление не должно ронять обработчик ошибок.
        logging.exception("Не удалось уведомить пользователя об ошибке.")


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    # Throttling — ПЕРЕД сессией БД: флуд отсекается до открытия соединения.
    dp.update.outer_middleware(ThrottlingMiddleware())
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.include_router(build_root_router())
    dp.errors.register(on_error)
    return dp


async def main() -> None:
    logging.basicConfig(level=settings.log_level)
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()
    logging.info("Бот запущен, начинаю polling.")
    fetch_task = asyncio.create_task(autofetch_loop(bot, dp))
    try:
        await dp.start_polling(bot)
    finally:
        fetch_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await fetch_task


if __name__ == "__main__":
    asyncio.run(main())
