"""Реальная сетка плей-офф из фактических результатов.

Группы (ActualResult 1..72) → места → участники Round of 32; затем по стадиям
матчим сыгранные матчи из API к парам сетки и определяем победителей
(учёт пенальти через FinishedMatch.winner), продвигаясь до финала.

Только читает БД; ничего не пишет. Результат — карта {номер_матча: ActualMatch}
со всем, что уже можно определить по имеющимся результатам.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.teams_en import ru_name
from src.data.wc2026 import BRACKET
from src.db import repo
from src.models import GroupMatch
from src.services import bracket
from src.services.football_api import FinishedMatch
from src.services.standings import MatchResult, compute_standings, rank_third_places


@dataclass
class ActualMatch:
    """Один матч реальной сетки: участники и (если сыгран) победитель/счёт."""

    match_number: int
    stage: str
    home_id: int | None
    away_id: int | None
    winner_id: int | None = None
    loser_id: int | None = None
    home_score: int | None = None
    away_score: int | None = None

    @property
    def decided(self) -> bool:
        """Матч сыгран и победитель известен."""
        return self.winner_id is not None


async def _actual_group_positions(
    session: AsyncSession,
) -> tuple[dict[str, int], dict[str, int], dict[str, int], list]:
    """Места в группах по фактическим результатам: (1-е, 2-е, 3-е, строки третьих)."""
    groups = await repo.get_all_groups(session)
    rows = (
        await session.execute(
            select(
                GroupMatch.match_number,
                GroupMatch.group_id,
                GroupMatch.home_team_id,
                GroupMatch.away_team_id,
            )
        )
    ).all()
    gid_letter = {g.id: g.letter for g in groups}
    meta = {n: (gid_letter[gid], h, a) for n, gid, h, a in rows}

    actual = await repo.get_actual_results(session)  # match_number -> (h, a)
    per_group: dict[str, list[MatchResult]] = {g.letter: [] for g in groups}
    for n, (hs, as_) in actual.items():
        if n in meta:
            letter, h, a = meta[n]
            per_group[letter].append(
                MatchResult(home_id=h, away_id=a, home_score=hs, away_score=as_)
            )

    first: dict[str, int] = {}
    second: dict[str, int] = {}
    third_by_group: dict[str, int] = {}
    thirds = []
    for g in groups:
        teams = await repo.get_group_teams(session, g.id)
        standings = compute_standings(teams, per_group[g.letter])
        if len(standings) < 3:
            continue
        first[g.letter] = standings[0].team_id
        second[g.letter] = standings[1].team_id
        third_by_group[g.letter] = standings[2].team_id
        thirds.append((g.letter, standings[2]))
    return first, second, third_by_group, thirds


def _index_api_by_pair(
    api: list[FinishedMatch], name_to_id: dict[str, int]
) -> dict[frozenset[int], dict]:
    """Сыгранные матчи → {набор_id_двух_команд: {winner, score}} (по русским названиям)."""
    out: dict[frozenset[int], dict] = {}
    for fm in api:
        hid = name_to_id.get(ru_name(fm.home_en) or "")
        aid = name_to_id.get(ru_name(fm.away_en) or "")
        if hid is None or aid is None or hid == aid:
            continue
        if fm.winner == "HOME":
            win: int | None = hid
        elif fm.winner == "AWAY":
            win = aid
        else:
            win = None
        out[frozenset((hid, aid))] = {
            "winner": win,
            "score": {hid: fm.home_score, aid: fm.away_score},
        }
    return out


async def resolve_actual_bracket(
    session: AsyncSession, api: list[FinishedMatch]
) -> dict[int, ActualMatch]:
    """Построить реальную сетку (73..104) из результатов групп и матчей плей-офф.

    Пустой dict, если групповой этап ещё не позволяет определить участников R32.
    """
    first, second, third_by_group, thirds = await _actual_group_positions(session)
    if len(first) < 12 or len(thirds) < len(bracket.THIRD_SLOTS):
        return {}

    ranked = rank_third_places(thirds)
    qualified = {letter for letter, _ in ranked[: len(bracket.THIRD_SLOTS)]}
    assignment = bracket.assign_thirds(qualified)  # слот R32 -> буква группы

    tmap = await repo.get_teams_map(session)
    name_to_id = {name: tid for tid, name in tmap.items()}
    api_by_pair = _index_api_by_pair(api, name_to_id)

    resolved: dict[int, ActualMatch] = {}

    def team_for(code: str, num: int) -> int | None:
        if bracket.is_group_source(code):
            table = first if code[0] == "1" else second
            return table.get(code[1])
        if bracket.is_third_source(code):
            g = assignment.get(num)
            return third_by_group.get(g) if g else None
        if bracket.is_winner_source(code):
            m = resolved.get(bracket.source_match_number(code))
            return m.winner_id if m else None
        if bracket.is_loser_source(code):
            m = resolved.get(bracket.source_match_number(code))
            return m.loser_id if m else None
        return None

    for stage, num, home_src, away_src in BRACKET:
        hid = team_for(home_src, num)
        aid = team_for(away_src, num)
        am = ActualMatch(match_number=num, stage=stage, home_id=hid, away_id=aid)
        if hid is not None and aid is not None:
            rec = api_by_pair.get(frozenset((hid, aid)))
            if rec and rec["winner"] is not None:
                am.winner_id = rec["winner"]
                am.loser_id = aid if rec["winner"] == hid else hid
                am.home_score = rec["score"].get(hid)
                am.away_score = rec["score"].get(aid)
        resolved[num] = am
    return resolved
