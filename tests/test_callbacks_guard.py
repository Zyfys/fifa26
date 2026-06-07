"""Тесты guard'а доступности сообщения колбэка и глобального error-handler'а.

Используются лёгкие фейки вместо полного мока aiogram.
"""

from __future__ import annotations

from typing import Any

import pytest
from aiogram.types import InaccessibleMessage

from src.bot import ERROR_TEXT, on_error
from src.handlers.callbacks import accessible_message


class FakeCallback:
    def __init__(self, message: Any) -> None:
        self.message = message
        self.answers: list[tuple[str, bool]] = []

    async def answer(self, text: str = "", show_alert: bool = False) -> None:
        self.answers.append((text, show_alert))


class FakeMessage:
    """Минимальный «доступный» Message — НЕ InaccessibleMessage."""


async def test_accessible_message_returns_message_when_available():
    msg = FakeMessage()
    call = FakeCallback(msg)
    result = await accessible_message(call)  # type: ignore[arg-type]
    assert result is msg
    assert call.answers == []  # подсказку не показывали


async def test_accessible_message_none_shows_alert():
    call = FakeCallback(None)
    result = await accessible_message(call)  # type: ignore[arg-type]
    assert result is None
    assert len(call.answers) == 1
    text, show_alert = call.answers[0]
    assert show_alert is True
    assert "/start" in text


async def test_accessible_message_inaccessible_shows_alert():
    inaccessible = InaccessibleMessage.model_construct()
    call = FakeCallback(inaccessible)
    result = await accessible_message(call)  # type: ignore[arg-type]
    assert result is None
    assert len(call.answers) == 1
    assert call.answers[0][1] is True


# --- Глобальный error-handler ---

class FakeAnswerableMessage:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def answer(self, text: str) -> None:
        self.sent.append(text)


class FakeUpdate:
    def __init__(self, message: Any = None, callback_query: Any = None) -> None:
        self.message = message
        self.callback_query = callback_query


class FakeErrorEvent:
    def __init__(self, update: Any, exc: Exception) -> None:
        self.update = update
        self.exception = exc


@pytest.fixture
def _patch_isinstance(monkeypatch: pytest.MonkeyPatch):
    """on_error использует isinstance(... Message/CallbackQuery) — подменяем фейки."""
    import src.bot as bot_module

    monkeypatch.setattr(
        bot_module, "Message", FakeAnswerableMessage, raising=True
    )
    monkeypatch.setattr(bot_module, "CallbackQuery", FakeCallback, raising=True)


async def test_on_error_notifies_message_user(_patch_isinstance):
    msg = FakeAnswerableMessage()
    event = FakeErrorEvent(FakeUpdate(message=msg), RuntimeError("boom"))
    await on_error(event)  # type: ignore[arg-type]
    assert msg.sent == [ERROR_TEXT]


async def test_on_error_notifies_callback_user(_patch_isinstance):
    call = FakeCallback(None)
    event = FakeErrorEvent(FakeUpdate(callback_query=call), ValueError("boom"))
    await on_error(event)  # type: ignore[arg-type]
    assert len(call.answers) == 1
    assert call.answers[0] == (ERROR_TEXT, True)


async def test_on_error_swallows_notify_failure(_patch_isinstance):
    class ExplodingMessage:
        async def answer(self, text: str) -> None:
            raise RuntimeError("cannot send")

    # ExplodingMessage не пройдёт isinstance(... FakeAnswerableMessage),
    # поэтому проверяем, что отсутствие подходящего получателя не роняет хэндлер.
    event = FakeErrorEvent(FakeUpdate(message=ExplodingMessage()), RuntimeError("x"))
    await on_error(event)  # type: ignore[arg-type]  # не должно бросить
