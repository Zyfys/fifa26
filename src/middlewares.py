"""Middlewares бота."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from src.db.session import async_session

# Минимальный интервал между апдейтами одного пользователя (сек). Более частые —
# дропаются, не доходя до хэндлеров и БД. Защита от спама/флуда на общем VPS.
THROTTLE_INTERVAL = 0.5


def _user_id(event: TelegramObject) -> int | None:
    """Достать id пользователя из апдейта (для outer-middleware на dp.update)."""
    if not isinstance(event, Update):
        return None
    obj = (
        event.message
        or event.callback_query
        or event.edited_message
        or event.inline_query
        or event.my_chat_member
    )
    user = getattr(obj, "from_user", None)
    return user.id if user else None


class ThrottlingMiddleware(BaseMiddleware):
    """Транспортный анти-флуд: дропает слишком частые апдейты одного пользователя.

    In-memory, без внешних зависимостей. Регистрируется ПЕРЕД DbSessionMiddleware,
    чтобы отсекать флуд до открытия сессии БД. При рестарте бота счётчики обнуляются —
    для анти-флуда это приемлемо.
    """

    def __init__(self, interval: float = THROTTLE_INTERVAL) -> None:
        self.interval = interval
        self._last_seen: dict[int, float] = {}

    def is_throttled(self, user_id: int, now: float) -> bool:
        """Зафиксировать апдейт и решить, дропать ли его (слишком частый)."""
        last = self._last_seen.get(user_id)
        self._last_seen[user_id] = now
        return last is not None and now - last < self.interval

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = _user_id(event)
        if user_id is not None and self.is_throttled(user_id, time.monotonic()):
            # Слишком часто — гасим апдейт. У callback убираем «часики».
            if isinstance(event, Update) and event.callback_query:
                await event.callback_query.answer()
            return None
        return await handler(event, data)


class DbSessionMiddleware(BaseMiddleware):
    """Открывает async-сессию БД на время обработки апдейта и кладёт её в data['session']."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session() as session:
            data["session"] = session
            return await handler(event, data)
