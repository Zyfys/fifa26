"""Оркестрация сетки плей-офф над БД.

Строит участников Round of 32 из результатов групп и продвигает победителей
по сетке (89–104) по мере того, как пользователь заполняет матчи.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.wc2026 import BRACKET
from src.db import repo
from src.models import BracketPrediction
from src.services import bracket
from src.services.standings import compute_standings, rank_third_places

# Номер финала и общее число матчей сетки.
FINAL_MATCH = 104
BRACKET_MATCHES_TOTAL = len(BRACKET)  # 32


async def get_group_positions(
    session: AsyncSession, user_id: int
) -> tuple[dict[str, int], dict[str, int], dict[str, int], set[str]]:
    """Места в группах: (1-е по группам, 2-е, 3-е, буквы 8 лучших третьих)."""
    groups = await repo.get_all_groups(session)
    first: dict[str, int] = {}
    second: dict[str, int] = {}
    third_by_group: dict[str, int] = {}
    thirds = []
    for g in groups:
        teams = await repo.get_group_teams(session, g.id)
        results = await repo.get_group_results(session, g.id, user_id)
        rows = compute_standings(teams, results)
        first[g.letter] = rows[0].team_id
        second[g.letter] = rows[1].team_id
        third_by_group[g.letter] = rows[2].team_id
        thirds.append((g.letter, rows[2]))

    ranked = rank_third_places(thirds)
    qualified = {letter for letter, _ in ranked[: len(bracket.THIRD_SLOTS)]}
    return first, second, third_by_group, qualified


def _loser_id(pred: BracketPrediction) -> int | None:
    if pred.winner_team_id is None:
        return None
    if pred.home_team_id == pred.winner_team_id:
        return pred.away_team_id
    return pred.home_team_id


async def resolve_bracket(session: AsyncSession, user_id: int) -> None:
    """Заполнить участников всех матчей сетки, которые уже можно определить."""
    first, second, third_by_group, qualified = await get_group_positions(
        session, user_id
    )
    assignment = bracket.assign_thirds(qualified)  # слот R32 -> буква группы
    preds = await repo.get_bracket_preds(session, user_id)

    def team_for(code: str, match_number: int) -> int | None:
        if bracket.is_group_source(code):
            table = first if code[0] == "1" else second
            return table.get(code[1])
        if bracket.is_third_source(code):
            group = assignment.get(match_number)
            return third_by_group.get(group) if group else None
        if bracket.is_winner_source(code):
            p = preds.get(bracket.source_match_number(code))
            return p.winner_team_id if p else None
        if bracket.is_loser_source(code):
            p = preds.get(bracket.source_match_number(code))
            return _loser_id(p) if p else None
        return None

    for _stage, num, home_src, away_src in BRACKET:
        home_id = team_for(home_src, num)
        away_id = team_for(away_src, num)
        if home_id is not None and away_id is not None:
            await repo.upsert_bracket_teams(session, user_id, num, home_id, away_id)


async def get_champion_id(session: AsyncSession, user_id: int) -> int | None:
    pred = await repo.get_bracket_pred(session, user_id, FINAL_MATCH)
    return pred.winner_team_id if pred else None
