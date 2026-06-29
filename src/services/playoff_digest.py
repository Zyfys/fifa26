"""Авто-сводка плей-офф: ежедневно (в 11:00) рассылает игрокам обновление сетки
по СВЕЖИМ сыгранным матчам — инкрементально, не дожидаясь конца стадии.

Что показываем по каждому новому матчу:
  • кто реально прошёл дальше (✅ если игрок угадал прошедшего);
  • кто прошёл ВМЕСТО того, на кого ставил игрок (🔄);
  • счётчик угаданных прошедших по новым матчам; пометка 🏁 — стадия завершена.

Журнал «уже разослано» — флаг digested у ActualResult (матчи 73..104), как и в
групповой сводке. Реальная сетка пересчитывается из API при каждом запуске.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.data.flags import team_flag
from src.data.wc2026 import BRACKET
from src.db import repo
from src.services import bracket
from src.services.football_api import fetch_finished_detailed
from src.services.playoff_actual import ActualMatch, resolve_actual_bracket

logger = logging.getLogger(__name__)

_SEND_PAUSE = 0.05

# Стадия -> номера её матчей (в порядке сетки).
STAGE_MATCHES: dict[str, list[int]] = {}
for _stage, _num, _h, _a in BRACKET:
    STAGE_MATCHES.setdefault(_stage, []).append(_num)


def _lbl(tmap: dict[int, str], tid: int | None) -> str:
    if tid is None:
        return "—"
    name = tmap.get(tid, "?")
    return f"{team_flag(name)} {name}"


def build_playoff_update(
    new_by_stage: dict[str, list[int]],
    actual: dict[int, ActualMatch],
    user_preds: dict,
    tmap: dict[int, str],
    completed: set[str],
) -> str:
    """Текст сводки по свежим сыгранным матчам плей-офф (инкрементально) для игрока.

    new_by_stage — новые (ещё не разосланные) сыгранные матчи по стадиям;
    completed — стадии, сыгранные теперь полностью (для пометки 🏁).
    """
    lines = [
        "⚽️ <b>Плей-офф — обновление сетки!</b>",
        "Свежие результаты против твоего прогноза.",
        "",
    ]
    correct = total = 0
    for stage in bracket.STAGE_ORDER:
        nums = new_by_stage.get(stage)
        if not nums:
            continue
        suffix = " — сыграна полностью! 🏁" if stage in completed else ""
        lines.append(f"<b>{bracket.STAGE_NAMES.get(stage, stage)}{suffix}</b>")
        for num in nums:
            am = actual[num]
            pred = user_preds.get(num)
            u_win = pred.winner_team_id if pred else None
            total += 1
            if u_win is not None and u_win == am.winner_id:
                correct += 1
                lines.append(f"✅ {_lbl(tmap, am.winner_id)} прошёл дальше — угадал!")
            else:
                lines.append(f"🔄 прошёл {_lbl(tmap, am.winner_id)} — ты ждал {_lbl(tmap, u_win)}")
        lines.append("")

    lines.append(f"📊 По новым матчам угадал прошедших: <b>{correct}/{total}</b>")
    return "\n".join(lines)


def _new_by_stage(actual: dict[int, ActualMatch], undigested: set[int]) -> dict[str, list[int]]:
    """Новые сыгранные матчи плей-офф, сгруппированные по стадии (в порядке сетки)."""
    out: dict[str, list[int]] = {}
    for num in sorted(undigested):
        am = actual.get(num)
        if am and am.decided:
            out.setdefault(am.stage, []).append(num)
    return out


def _completed_stages(actual: dict[int, ActualMatch], stages: list[str]) -> set[str]:
    """Из заданных стадий — те, что теперь сыграны полностью."""
    return {
        st for st in stages if all(actual.get(n) and actual[n].decided for n in STAGE_MATCHES[st])
    }


async def send_playoff_digests(bot: Bot, session: AsyncSession) -> int:
    """Разослать сводку по новым сыгранным матчам плей-офф (инкрементально).

    Возвращает число отправленных сообщений (0, если новых матчей нет).
    """
    if not settings.football_data_token:
        return 0
    api = await fetch_finished_detailed(token=settings.football_data_token)
    actual = await resolve_actual_bracket(session, api)
    if not actual:
        return 0

    # Журнал: записываем счёт новых/изменившихся сыгранных матчей плей-офф.
    stored = await repo.get_actual_results(session)
    wrote = False
    for num, am in actual.items():
        if not am.decided or am.home_score is None or am.away_score is None:
            continue
        if stored.get(num) != (am.home_score, am.away_score):
            await repo.upsert_actual_result(session, num, am.home_score, am.away_score)
            wrote = True
    if wrote:
        await session.commit()

    undigested = set(await repo.get_undigested_playoff_results(session))
    new_by_stage = _new_by_stage(actual, undigested)
    if not new_by_stage:
        return 0
    completed = _completed_stages(actual, list(new_by_stage))
    new_nums = [num for nums in new_by_stage.values() for num in nums]

    tmap = await repo.get_teams_map(session)
    users = await repo.get_users_with_group_predictions(session)
    sent = 0
    for user in users:
        preds = await repo.get_bracket_preds(session, user.id)
        text = build_playoff_update(new_by_stage, actual, preds, tmap, completed)
        try:
            await bot.send_message(user.telegram_id, text)
            sent += 1
        except TelegramAPIError:
            logger.warning("Не доставил сводку сетки user=%s", user.telegram_id)
        await asyncio.sleep(_SEND_PAUSE)

    await repo.mark_results_digested(session, new_nums)
    await session.commit()
    logger.info("Сводка плей-офф разослана: %s матчей, %s сообщений", len(new_nums), sent)
    return sent
