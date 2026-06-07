"""Утилиты для безопасной работы с callback_query.

В aiogram `call.message` может быть None или InaccessibleMessage (старое
сообщение, к которому Telegram не даёт доступа на редактирование/ответ).
"""

from __future__ import annotations

import time

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message

from src.services import antiflood

_STALE_TEXT = "Сообщение устарело, начните заново: /start"


async def accessible_message(call: CallbackQuery) -> Message | None:
    """Вернуть доступное сообщение колбэка или None.

    Если сообщение недоступно (None / InaccessibleMessage) — показать
    пользователю всплывающую подсказку и вернуть None, чтобы хэндлер вышел.
    """
    msg = call.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        await call.answer(_STALE_TEXT, show_alert=True)
        return None
    return msg


async def guard_text_input(
    message: Message,
    state: FSMContext,
    *,
    valid: bool,
    error_message: str,
) -> bool:
    """Анти-флуд для текстового ввода: «3 попытки → пауза».

    Возвращает True, если ввод валиден и хэндлер может продолжать.
    Иначе сам отвечает пользователю (предупреждение с номером попытки,
    сообщение о кулдауне или «подожди N сек») и возвращает False.
    Состояние счётчика/кулдауна хранится в FSM-данных.
    """
    data = await state.get_data()
    now = time.monotonic()

    remaining = antiflood.cooldown_remaining(data, now)
    if remaining is not None:
        await message.answer(antiflood.cooldown_wait_message(remaining))
        return False

    if valid:
        await state.update_data(**antiflood.reset_fields())
        return True

    attempt, cooled, fields = antiflood.note_bad_attempt(data, now)
    await state.update_data(**fields)
    if cooled:
        await message.answer(antiflood.COOLDOWN_MESSAGE)
    else:
        await message.answer(
            f"{error_message} Попытка {attempt}/{antiflood.MAX_BAD_ATTEMPTS}."
        )
    return False
