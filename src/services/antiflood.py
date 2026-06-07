"""Доменный анти-флуд для текстового ввода: 3 попытки → пауза (кулдаун).

Чистая логика поверх словаря FSM-данных, без aiogram — легко тестируется.
Состояние хранится в FSM (`state.update_data(...)`): счётчик `bad_attempts`
и метка `cooldown_until` (значение time.monotonic(), переданное хэндлером).
"""

from __future__ import annotations

import math

MAX_BAD_ATTEMPTS = 3
COOLDOWN_SECONDS = 30.0


def cooldown_remaining(data: dict, now: float) -> int | None:
    """Сколько секунд осталось до конца кулдауна (вверх до целого), либо None.

    None — кулдаун не активен, ввод можно принимать.
    """
    until = data.get("cooldown_until")
    if until is not None and until > now:
        return math.ceil(until - now)
    return None


def note_bad_attempt(data: dict, now: float) -> tuple[int, bool, dict]:
    """Учесть невалидный ввод.

    Возвращает (номер_попытки, кулдаун_включён, поля_для_update).
    На MAX_BAD_ATTEMPTS-й попытке включается кулдаун и счётчик сбрасывается.
    """
    bad = int(data.get("bad_attempts", 0)) + 1
    if bad >= MAX_BAD_ATTEMPTS:
        return bad, True, {"bad_attempts": 0, "cooldown_until": now + COOLDOWN_SECONDS}
    return bad, False, {"bad_attempts": bad, "cooldown_until": None}


def reset_fields() -> dict:
    """Поля FSM для сброса анти-флуда после валидного ввода."""
    return {"bad_attempts": 0, "cooldown_until": None}


COOLDOWN_MESSAGE = (
    "⏳ Слишком много неверных попыток. Подожди немного "
    "или нажми кнопку счёта."
)


def cooldown_wait_message(remaining: int) -> str:
    return f"⏳ Подожди ещё {remaining} сек или нажми кнопку счёта."
