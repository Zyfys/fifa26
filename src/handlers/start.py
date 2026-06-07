"""Приветствие и старт прогноза."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import repo
from src.handlers.callbacks import accessible_message
from src.handlers.group_stage import send_next_match
from src.keyboards.common import reset_confirm_keyboard, start_keyboard

router = Router()

WELCOME = (
    "⚽ <b>Добро пожаловать в прогноз Чемпионата мира 2026!</b>\n\n"
    "Сделай свой прогноз всего турнира: от группового этапа до финала.\n"
    "После завершения ты получишь персональный PDF с результатами."
)


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    user = await repo.get_or_create_user(
        session, message.from_user.id, message.from_user.username
    )
    await session.commit()
    done = await repo.count_group_predictions(session, user.id)
    has_progress = 0 < done < repo.GROUP_MATCHES_TOTAL
    await message.answer(WELCOME, reply_markup=start_keyboard(has_progress=has_progress))


@router.callback_query(F.data == "begin")
async def on_begin(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    user = await repo.get_or_create_user(
        session, call.from_user.id, call.from_user.username
    )
    await call.answer()
    await send_next_match(msg, state, session, user.id)


@router.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    await message.answer(
        "⚠️ Сбросить весь прогноз и начать заново? Это удалит группы, сетку, "
        "награды и сборную.",
        reply_markup=reset_confirm_keyboard(),
    )


@router.callback_query(F.data == "reset_yes")
async def on_reset_yes(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    user = await repo.get_or_create_user(
        session, call.from_user.id, call.from_user.username
    )
    await repo.reset_user_predictions(session, user.id)
    await session.commit()
    await state.clear()
    await call.answer("Прогноз сброшен")
    await msg.edit_text("🗑 Прогноз сброшен. Отправь /start, чтобы начать заново.")


@router.callback_query(F.data == "reset_no")
async def on_reset_no(call: CallbackQuery) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    await call.answer()
    await msg.edit_text("Отменено — прогноз цел.")
