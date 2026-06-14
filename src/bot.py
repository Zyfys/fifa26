"""Точка входа бота: диспетчер, middlewares, роутеры, polling."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    CallbackQuery,
    ErrorEvent,
    Message,
)

from src.config import settings
from src.handlers import build_root_router
from src.handlers.results import digest_loop, ingest_loop
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


# Команды в меню бота (синяя кнопка «/»).
PUBLIC_COMMANDS = [
    BotCommand(command="start", description="Начать / продолжить прогноз"),
    BotCommand(command="my", description="Мои прогнозы"),
    BotCommand(command="score", description="Моя точность"),
    BotCommand(command="top", description="Рейтинг точности"),
    BotCommand(command="reset", description="Сбросить прогноз"),
]
ADMIN_COMMANDS = PUBLIC_COMMANDS + [
    BotCommand(command="results", description="Внести результаты (админ)"),
    BotCommand(command="stats", description="Статистика (админ)"),
]


async def setup_commands(bot: Bot) -> None:
    """Зарегистрировать команды в меню: общие — всем, админские — в чатах админов."""
    await bot.set_my_commands(PUBLIC_COMMANDS, scope=BotCommandScopeDefault())
    for admin_id in settings.admin_id_set:
        try:
            await bot.set_my_commands(
                ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id)
            )
        except TelegramAPIError:
            logging.warning("Не задал команды для админа %s", admin_id)


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
    await setup_commands(bot)
    logging.info("Бот запущен, начинаю polling.")
    tasks = [
        asyncio.create_task(ingest_loop(bot)),  # вечером: автозапись результатов
        asyncio.create_task(digest_loop(bot)),  # утром: сводка игрокам
    ]
    try:
        await dp.start_polling(bot)
    finally:
        for task in tasks:
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
