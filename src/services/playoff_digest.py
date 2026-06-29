"""Авто-сводка плей-офф: ежедневно (в 11:00) рассылает игрокам обновление сетки
по СВЕЖИМ сыгранным матчам — инкрементально, не дожидаясь конца стадии.

Что показываем по каждому новому матчу:
  • какая команда в какой раунд вышла (напр. «Канада → 1/8 финала»);
  • ✅ если игрок ВЁЛ эту команду в этот раунд по своей сетке — с ЛЮБОГО места
    (сравнение по факту попадания в раунд, не по конкретному слоту), иначе ❌;
  • счётчик угаданных проходов; пометка 🏁 — стадия завершена полностью.

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

# Стадия выигранного матча -> раунд, в который выходит его победитель (для текста).
_REACHED_LABEL: dict[str, str] = {
    "R32": "1/8 финала",
    "R16": "1/4 финала",
    "QF": "1/2 финала",
    "SF": "финал",
    "FINAL": "🏆 чемпион",
    "THIRD": "🥉 3-е место",
}
# Стадия -> следующая стадия: по её участникам судим «команда дошла до раунда».
_NEXT_STAGE: dict[str, str] = {"R32": "R16", "R16": "QF", "QF": "SF", "SF": "FINAL"}


def _lbl(tmap: dict[int, str], tid: int | None) -> str:
    if tid is None:
        return "—"
    name = tmap.get(tid, "?")
    return f"{team_flag(name)} {name}"


def _user_reach(user_preds: dict, stage: str) -> set[int]:
    """Команды, которые игрок предсказал в раунд, куда выходит победитель `stage`.

    Сравнение по факту попадания команды в раунд (с ЛЮБОГО места сетки), а не по
    конкретному слоту: если игрок довёл команду до этого раунда где угодно — засчитано.
    """
    nxt = _NEXT_STAGE.get(stage)
    if nxt is not None:  # участники матчей следующей стадии в прогнозе игрока
        return {
            t
            for num in STAGE_MATCHES[nxt]
            if (p := user_preds.get(num)) is not None
            for t in (p.home_team_id, p.away_team_id)
            if t is not None
        }
    # Финал -> чемпион, матч за 3-е -> бронза: победитель соответствующего матча.
    src = 104 if stage == "FINAL" else 103
    p = user_preds.get(src)
    return {p.winner_team_id} if p and p.winner_team_id is not None else set()


# Докуда игрок довёл команду в прогнозе (от глубокой стадии к мелкой).
_DEPTH_LABEL: list[tuple[str, str]] = [
    ("FINAL", "ты вёл её до финала"),
    ("SF", "ты вёл её до 1/2 финала"),
    ("QF", "ты вёл её до 1/4 финала"),
    ("R16", "ты вёл её до 1/8 финала"),
    ("R32", "ты вёл её до 1/16 финала"),
]


def _user_depth_label(user_preds: dict, team_id: int) -> str:
    """Докуда игрок довёл команду в своём прогнозе — для строки «что ты ставил»."""
    champ = user_preds.get(104)
    if champ is not None and champ.winner_team_id == team_id:
        return "ты ставил её в чемпионы 🏆"
    for stage, text in _DEPTH_LABEL:
        teams = {
            t
            for num in STAGE_MATCHES[stage]
            if (p := user_preds.get(num)) is not None
            for t in (p.home_team_id, p.away_team_id)
            if t is not None
        }
        if team_id in teams:
            return text
    return "у тебя она не выходила из группы"


def _user_pick_label(user_preds: dict, num: int, tmap: dict[int, str]) -> str:
    """Прогноз игрока на этот же матч сетки (пара, счёт, кто проходит) — «что ставил»."""
    p = user_preds.get(num)
    if p is None or p.home_team_id is None or p.away_team_id is None:
        return "🎟 ты не делал прогноз на этот матч"
    home, away, win = (
        _lbl(tmap, p.home_team_id),
        _lbl(tmap, p.away_team_id),
        _lbl(tmap, p.winner_team_id),
    )
    score = (
        f" {p.home_score}:{p.away_score}"
        if p.home_score is not None and p.away_score is not None
        else " —"
    )
    return f"🎟 ты ставил: {home}{score} {away} → прошёл {win}"


def build_playoff_update(
    new_nums: list[int],
    actual: dict[int, ActualMatch],
    user_preds: dict,
    tmap: dict[int, str],
    completed: set[str],
) -> str:
    """Сводка по свежим матчам плей-офф: какая команда в какой раунд вышла и угадал
    ли это игрок — по всей сетке, с любого места (не по конкретному слоту)."""
    lines = [
        "⚽️ <b>Плей-офф — кто прошёл дальше!</b>",
        "Засчитываю, если ты вёл команду в этот раунд с любого места сетки.",
        "",
    ]
    correct = 0
    for num in new_nums:
        am = actual[num]
        label = _REACHED_LABEL.get(am.stage, am.stage)
        guessed = am.winner_id in _user_reach(user_preds, am.stage)
        correct += guessed
        depth = _user_depth_label(user_preds, am.winner_id)
        verdict = f"✅ угадал! ({depth})" if guessed else f"❌ {depth}"
        lines.append(f"{_lbl(tmap, am.winner_id)} → <b>{label}</b>")
        lines.append(f"   {verdict}")
        lines.append(f"   {_user_pick_label(user_preds, num, tmap)}")
        lines.append("")

    lines.append(f"📊 Угадал проходов: <b>{correct}/{len(new_nums)}</b>")
    if completed:
        done = ", ".join(
            bracket.STAGE_NAMES.get(s, s) for s in bracket.STAGE_ORDER if s in completed
        )
        lines += ["", f"🏁 Стадия сыграна полностью: {done}"]
    return "\n".join(lines)


def _new_decided(actual: dict[int, ActualMatch], undigested: set[int]) -> list[int]:
    """Новые (неразосланные) и уже сыгранные матчи плей-офф — по номеру."""
    return sorted(n for n in undigested if (am := actual.get(n)) and am.decided)


def _completed_stages(actual: dict[int, ActualMatch], stages: set[str]) -> set[str]:
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
    new_nums = _new_decided(actual, undigested)
    if not new_nums:
        return 0
    completed = _completed_stages(actual, {actual[n].stage for n in new_nums})

    tmap = await repo.get_teams_map(session)
    users = await repo.get_users_with_group_predictions(session)
    sent = 0
    for user in users:
        preds = await repo.get_bracket_preds(session, user.id)
        text = build_playoff_update(new_nums, actual, preds, tmap, completed)
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
