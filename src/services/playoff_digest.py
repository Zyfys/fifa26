"""Авто-сводка плей-офф: после полностью сыгранной стадии рассылает игрокам
обновление сетки и сравнение с их прогнозом.

Что показываем по стадии:
  • кто реально прошёл дальше (✅ если игрок угадал прошедшего);
  • кто прошёл ВМЕСТО тех, на кого ставил игрок;
  • счётчики: угаданных прошедших и совпавших пар стадии.

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


def build_stage_digest(
    stage: str,
    stage_nums: list[int],
    actual: dict[int, ActualMatch],
    user_preds: dict,
    tmap: dict[int, str],
) -> str:
    """Текст сводки по одной сыгранной стадии плей-офф для одного игрока."""
    name = bracket.STAGE_NAMES.get(stage, stage)
    advanced: list[str] = []  # угадал прошедшего
    instead: list[str] = []  # прошёл не тот, кого ждал
    correct = 0
    pair_hits = 0

    for num in stage_nums:
        am = actual[num]
        pred = user_preds.get(num)
        u_win = pred.winner_team_id if pred else None

        if (
            pred is not None
            and None not in (am.home_id, am.away_id)
            and {pred.home_team_id, pred.away_team_id} == {am.home_id, am.away_id}
        ):
            pair_hits += 1

        if u_win is not None and u_win == am.winner_id:
            correct += 1
            advanced.append(f"✅ {_lbl(tmap, am.winner_id)}")
        else:
            instead.append(f"🔄 прошёл {_lbl(tmap, am.winner_id)} — ты ждал {_lbl(tmap, u_win)}")

    n = len(stage_nums)
    lines = [
        f"⚽️ <b>{name} — сыграно!</b>",
        "Сетка обновилась — сравниваю с твоим прогнозом.",
        "",
        "🟢 <b>Прошедших дальше угадал:</b>",
    ]
    lines += advanced or ["— ни одного 😬"]
    if instead:
        lines += ["", "<b>Прошли вместо твоих:</b>", *instead]
    lines += [
        "",
        f"📊 Угадал прошедших: <b>{correct}/{n}</b> · совпавших пар: <b>{pair_hits}/{n}</b>",
    ]
    return "\n".join(lines)


def _announceable_stages(actual: dict[int, ActualMatch], undigested: set[int]) -> list[str]:
    """Стадии, полностью сыгранные и с неразосланными матчами (в порядке сетки)."""
    out: list[str] = []
    for stage in bracket.STAGE_ORDER:
        nums = STAGE_MATCHES.get(stage, [])
        if not nums:
            continue
        all_decided = all(actual.get(num) and actual[num].decided for num in nums)
        has_new = any(num in undigested for num in nums)
        if all_decided and has_new:
            out.append(stage)
    return out


async def send_playoff_digests(bot: Bot, session: AsyncSession) -> int:
    """Разослать сводки по новым полностью сыгранным стадиям плей-офф.

    Возвращает число отправленных сообщений (0, если нечего слать).
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
    stages = _announceable_stages(actual, undigested)
    if not stages:
        return 0

    tmap = await repo.get_teams_map(session)
    users = await repo.get_users_with_group_predictions(session)
    sent = 0
    for stage in stages:
        nums = STAGE_MATCHES[stage]
        for user in users:
            preds = await repo.get_bracket_preds(session, user.id)
            text = build_stage_digest(stage, nums, actual, preds, tmap)
            try:
                await bot.send_message(user.telegram_id, text)
                sent += 1
            except TelegramAPIError:
                logger.warning("Не доставил сводку сетки user=%s", user.telegram_id)
            await asyncio.sleep(_SEND_PAUSE)
        await repo.mark_results_digested(session, nums)
        logger.info("Сводка плей-офф разослана: стадия %s", stage)

    await session.commit()
    return sent
