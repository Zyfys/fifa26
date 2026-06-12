"""Сбор всех данных прогноза пользователя в структуру для PDF-отчёта."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.wc2026 import BRACKET
from src.db import repo
from src.services.awards import AWARD_DISPLAY, FORMATION, POSITION_LABEL
from src.services.bracket import STAGE_NAMES
from src.services.playoff import FINAL_MATCH
from src.services.standings import (
    THIRD_PLACES_QUALIFY,
    StandingRow,
    compute_standings,
    rank_third_places,
)

STAGE_ORDER = ["R32", "R16", "QF", "SF", "THIRD", "FINAL"]
_STAGE_BY_NUM = {num: stage for stage, num, _h, _a in BRACKET}


@dataclass
class GroupTable:
    letter: str
    rows: list[StandingRow]


@dataclass
class ThirdRow:
    letter: str
    row: StandingRow
    qualified: bool


@dataclass
class BracketMatch:
    home: str
    away: str
    home_score: int | None
    away_score: int | None
    winner: str | None


@dataclass
class ReportData:
    username: str
    created: str
    groups: list[GroupTable] = field(default_factory=list)
    thirds: list[ThirdRow] = field(default_factory=list)
    rounds: list[tuple[str, list[BracketMatch]]] = field(default_factory=list)
    bracket: dict[int, BracketMatch] = field(default_factory=dict)
    champion: str = "—"
    runner_up: str = "—"
    third_place: str = "—"
    awards: list[tuple[str, str]] = field(default_factory=list)
    tot: list[tuple[str, list[str]]] = field(default_factory=list)


async def build_report_data(session: AsyncSession, user_id: int) -> ReportData:
    user = await repo.get_user(session, user_id)
    teams = await repo.get_teams_map(session)

    data = ReportData(
        username=(user.username or str(user.telegram_id)) if user else "user",
        created=datetime.datetime.now().strftime("%d.%m.%Y"),
    )

    # Группы + третьи места.
    groups = await repo.get_all_groups(session)
    thirds_raw: list[tuple[str, StandingRow]] = []
    for g in groups:
        g_teams = await repo.get_group_teams(session, g.id)
        results = await repo.get_group_results(session, g.id, user_id)
        rows = compute_standings(g_teams, results)
        data.groups.append(GroupTable(letter=g.letter, rows=rows))
        if len(rows) >= 3:
            thirds_raw.append((g.letter, rows[2]))

    ranked = rank_third_places(thirds_raw)
    for i, (letter, row) in enumerate(ranked):
        data.thirds.append(ThirdRow(letter=letter, row=row, qualified=i < THIRD_PLACES_QUALIFY))

    # Плей-офф по раундам.
    preds = await repo.get_bracket_preds(session, user_id)

    def name(team_id: int | None) -> str:
        return teams.get(team_id, "—") if team_id else "—"

    for stage in STAGE_ORDER:
        matches = []
        for num in sorted(n for n in preds if _STAGE_BY_NUM.get(n) == stage):
            p = preds[num]
            bm = BracketMatch(
                home=name(p.home_team_id),
                away=name(p.away_team_id),
                home_score=p.home_score,
                away_score=p.away_score,
                winner=name(p.winner_team_id) if p.winner_team_id else None,
            )
            matches.append(bm)
            data.bracket[num] = bm
        if matches:
            data.rounds.append((STAGE_NAMES[stage], matches))

    # Призёры из сетки.
    final = preds.get(FINAL_MATCH)
    third = preds.get(103)
    if final and final.winner_team_id:
        data.champion = name(final.winner_team_id)
        data.runner_up = name(
            final.away_team_id if final.home_team_id == final.winner_team_id else final.home_team_id
        )
    if third and third.winner_team_id:
        data.third_place = name(third.winner_team_id)

    # Награды.
    awards_map = await repo.get_awards_map(session, user_id)
    for award_type, label, kind in AWARD_DISPLAY:
        a = awards_map.get(award_type)
        if a is None:
            value = "—"
        elif kind == "team":
            value = name(a.team_id)
        else:
            value = await repo.get_player_name(session, a.player_id) or "—"
            if kind == "player_goals" and a.int_value is not None:
                value += f" ({a.int_value} голов)"
        data.awards.append((label, value))

    # Символическая сборная.
    picks = await repo.get_tot_picks(session, user_id)
    by_pos: dict[str, list[str]] = {pos: [] for pos, _ in FORMATION}
    for p in picks:
        nm = await repo.get_player_name(session, p.player_id) or "—"
        by_pos.setdefault(p.position, []).append(nm)
    for pos, _count in FORMATION:
        data.tot.append((POSITION_LABEL[pos].capitalize(), by_pos.get(pos, [])))

    return data
