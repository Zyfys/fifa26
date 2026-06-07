"""Тесты анти-флуда: доменный кулдаун (3 попытки → пауза) и throttling."""

from __future__ import annotations

from src.middlewares import ThrottlingMiddleware
from src.services import antiflood

# --- Доменный кулдаун ввода ---

def test_cooldown_remaining_inactive():
    assert antiflood.cooldown_remaining({}, now=100.0) is None
    # просроченный кулдаун — больше не активен
    assert antiflood.cooldown_remaining({"cooldown_until": 50.0}, now=100.0) is None


def test_cooldown_remaining_active_rounds_up():
    rem = antiflood.cooldown_remaining({"cooldown_until": 110.4}, now=100.0)
    assert rem == 11  # math.ceil(10.4)


def test_bad_attempts_warn_then_cooldown():
    data: dict = {}
    now = 100.0

    attempt, cooled, fields = antiflood.note_bad_attempt(data, now)
    assert (attempt, cooled) == (1, False)
    assert fields == {"bad_attempts": 1, "cooldown_until": None}

    attempt, cooled, fields = antiflood.note_bad_attempt(fields, now)
    assert (attempt, cooled) == (2, False)
    assert fields["bad_attempts"] == 2

    attempt, cooled, fields = antiflood.note_bad_attempt(fields, now)
    assert (attempt, cooled) == (3, True)
    assert fields["bad_attempts"] == 0
    assert fields["cooldown_until"] == now + antiflood.COOLDOWN_SECONDS


def test_reset_fields_clears_state():
    fields = antiflood.reset_fields()
    assert fields == {"bad_attempts": 0, "cooldown_until": None}
    assert antiflood.cooldown_remaining(fields, now=999.0) is None


def test_cooldown_then_remaining_consistent():
    _, cooled, fields = antiflood.note_bad_attempt({"bad_attempts": 2}, now=200.0)
    assert cooled is True
    assert antiflood.cooldown_remaining(fields, now=200.0) == int(antiflood.COOLDOWN_SECONDS)
    assert antiflood.cooldown_remaining(fields, now=200.0 + antiflood.COOLDOWN_SECONDS) is None


# --- Транспортный throttling ---

def test_throttling_first_update_passes():
    mw = ThrottlingMiddleware(interval=0.5)
    assert mw.is_throttled(user_id=1, now=10.0) is False


def test_throttling_rapid_update_dropped():
    mw = ThrottlingMiddleware(interval=0.5)
    mw.is_throttled(1, now=10.0)
    assert mw.is_throttled(1, now=10.2) is True  # 0.2 c < 0.5 c


def test_throttling_spaced_update_passes():
    mw = ThrottlingMiddleware(interval=0.5)
    mw.is_throttled(1, now=10.0)
    assert mw.is_throttled(1, now=10.6) is False  # 0.6 c >= 0.5 c


def test_throttling_per_user_independent():
    mw = ThrottlingMiddleware(interval=0.5)
    mw.is_throttled(1, now=10.0)
    assert mw.is_throttled(2, now=10.1) is False  # другой пользователь не задет
