"""Утренняя сводка пользователю: его прогноз vs реальный счёт по сыгранным матчам.

Формат строки:  <статус><флаг> Хозяева — Гости <флаг> твой_счёт · реальный_счёт
Статусы:  😎 точный счёт · ✅ угадал исход · ☹️ мимо · ▫️ не прогнозировал.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.flags import team_flag
from src.db import repo
from src.services.accuracy import Accuracy, compute_user_accuracy, outcome

logger = logging.getLogger(__name__)

_SEND_PAUSE = 0.05  # пауза между сообщениями (дружелюбно к лимитам Telegram)
_LEGEND = "😎 точный счёт · ✅ угадал исход · ☹️ мимо"


def _status(pred: tuple[int, int] | None, actual: tuple[int, int]) -> str:
    if pred is None:
        return "▫️"
    if pred == actual:
        return "😎"
    if outcome(*pred) == outcome(*actual):
        return "✅"
    return "☹️"


def build_user_digest(
    results: list[tuple[int, str, str, int, int]],
    pred_map: dict[int, tuple[int, int]],
    accuracy: Accuracy,
) -> str:
    """Собрать текст сводки для одного пользователя."""
    lines = ["☀️ <b>Итоги сыгранных матчей</b>", "<i>твой прогноз · реальный счёт</i>", ""]
    for number, home, away, ah, aa in results:
        pred = pred_map.get(number)
        pred_str = f"{pred[0]}:{pred[1]}" if pred else "—"
        lines.append(
            f"{_status(pred, (ah, aa))}{team_flag(home)} {home} — "
            f"{away} {team_flag(away)} {pred_str} · {ah}:{aa}"
        )
    lines.append("")
    if accuracy.played:
        lines.append(
            f"🎯 Точность: исходы {accuracy.outcomes}/{accuracy.played} "
            f"({accuracy.outcome_pct}%), точные {accuracy.exacts}/{accuracy.played} "
            f"({accuracy.exact_pct}%)"
        )
    lines.append(_LEGEND)
    return "\n".join(lines)


async def send_daily_digests(bot: Bot, session: AsyncSession) -> int:
    """Разослать сводку всем игрокам по новым (неразосланным) результатам.

    Возвращает число успешно отправленных сообщений. Помечает результаты
    как разосланные только после прохода (чтобы повтор не задвоил рассылку).
    """
    results = await repo.get_undigested_results(session)
    if not results:
        return 0
    users = await repo.get_users_with_group_predictions(session)
    sent = 0
    for user in users:
        pred_map = await repo.get_user_pred_by_match(session, user.id)
        accuracy = await compute_user_accuracy(session, user.id)
        text = build_user_digest(results, pred_map, accuracy)
        try:
            await bot.send_message(user.telegram_id, text)
            sent += 1
        except TelegramAPIError:
            logger.warning("Не доставил сводку user=%s", user.telegram_id)
        await asyncio.sleep(_SEND_PAUSE)

    await repo.mark_results_digested(session, [r[0] for r in results])
    await session.commit()
    return sent
