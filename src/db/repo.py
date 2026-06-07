"""Репозиторий: операции доступа к данным для хэндлеров и сервисов."""

from __future__ import annotations

import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models import (
    AwardPrediction,
    BracketPrediction,
    Group,
    GroupMatch,
    GroupPrediction,
    Player,
    Team,
    TeamOfTournamentPick,
    User,
)
from src.services.standings import MatchResult

GROUP_MATCHES_TOTAL = 72


async def get_or_create_user(
    session: AsyncSession, telegram_id: int, username: str | None
) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.flush()
    elif username and user.username != username:
        user.username = username
    return user


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def reset_user_predictions(session: AsyncSession, user_id: int) -> None:
    """Удалить все прогнозы пользователя (группы, сетка, награды, сборная)."""
    for model in (
        GroupPrediction,
        BracketPrediction,
        AwardPrediction,
        TeamOfTournamentPick,
    ):
        await session.execute(delete(model).where(model.user_id == user_id))


async def count_group_predictions(session: AsyncSession, user_id: int) -> int:
    return await session.scalar(
        select(func.count()).select_from(GroupPrediction).where(
            GroupPrediction.user_id == user_id
        )
    ) or 0


async def get_next_group_match(
    session: AsyncSession, user_id: int
) -> GroupMatch | None:
    """Первый групповой матч без прогноза пользователя (по номеру)."""
    answered = select(GroupPrediction.group_match_id).where(
        GroupPrediction.user_id == user_id
    )
    stmt = (
        select(GroupMatch)
        .where(GroupMatch.id.notin_(answered))
        .order_by(GroupMatch.match_number)
        .limit(1)
        .options(
            joinedload(GroupMatch.home_team),
            joinedload(GroupMatch.away_team),
            joinedload(GroupMatch.group),
        )
    )
    return await session.scalar(stmt)


async def get_group_match(session: AsyncSession, match_id: int) -> GroupMatch | None:
    stmt = (
        select(GroupMatch)
        .where(GroupMatch.id == match_id)
        .options(
            joinedload(GroupMatch.home_team),
            joinedload(GroupMatch.away_team),
            joinedload(GroupMatch.group),
        )
    )
    return await session.scalar(stmt)


async def get_prev_group_match(
    session: AsyncSession, match_number: int
) -> GroupMatch | None:
    """Предыдущий по номеру групповой матч (для редактирования)."""
    stmt = (
        select(GroupMatch)
        .where(GroupMatch.match_number < match_number)
        .order_by(GroupMatch.match_number.desc())
        .limit(1)
        .options(
            joinedload(GroupMatch.home_team),
            joinedload(GroupMatch.away_team),
            joinedload(GroupMatch.group),
        )
    )
    return await session.scalar(stmt)


async def upsert_group_prediction(
    session: AsyncSession,
    user_id: int,
    group_match_id: int,
    home_score: int,
    away_score: int,
) -> None:
    existing = await session.scalar(
        select(GroupPrediction).where(
            GroupPrediction.user_id == user_id,
            GroupPrediction.group_match_id == group_match_id,
        )
    )
    if existing is None:
        session.add(
            GroupPrediction(
                user_id=user_id,
                group_match_id=group_match_id,
                home_score=home_score,
                away_score=away_score,
            )
        )
    else:
        existing.home_score = home_score
        existing.away_score = away_score


async def is_group_complete(
    session: AsyncSession, group_id: int, user_id: int
) -> bool:
    """Все ли матчи группы заполнены прогнозом пользователя."""
    total = await session.scalar(
        select(func.count()).select_from(GroupMatch).where(
            GroupMatch.group_id == group_id
        )
    )
    answered = await session.scalar(
        select(func.count())
        .select_from(GroupPrediction)
        .join(GroupMatch, GroupMatch.id == GroupPrediction.group_match_id)
        .where(GroupMatch.group_id == group_id, GroupPrediction.user_id == user_id)
    )
    return total is not None and total > 0 and answered == total


async def get_all_groups(session: AsyncSession) -> list[Group]:
    return list(
        await session.scalars(select(Group).order_by(Group.letter))
    )


async def get_group_teams(
    session: AsyncSession, group_id: int
) -> list[tuple[int, str]]:
    rows = await session.execute(
        select(Team.id, Team.name).where(Team.group_id == group_id).order_by(Team.name)
    )
    return [(r.id, r.name) for r in rows]


async def get_teams_map(session: AsyncSession) -> dict[int, str]:
    """id → название команды (для отрисовки сетки)."""
    rows = await session.execute(select(Team.id, Team.name))
    return {r.id: r.name for r in rows}


async def list_teams(session: AsyncSession) -> list[tuple[int, str]]:
    """Все команды (id, name) по алфавиту."""
    rows = await session.execute(select(Team.id, Team.name).order_by(Team.name))
    return [(r.id, r.name) for r in rows]


async def list_players(
    session: AsyncSession,
    team_id: int,
    *,
    position: str | None = None,
    born_after: datetime.date | None = None,
) -> list[tuple[int, str]]:
    """Игроки команды (id, name) с опциональными фильтрами позиции и возраста."""
    stmt = select(Player.id, Player.name).where(Player.team_id == team_id)
    if position is not None:
        stmt = stmt.where(Player.position == position)
    if born_after is not None:
        stmt = stmt.where(Player.birth_date.isnot(None), Player.birth_date >= born_after)
    stmt = stmt.order_by(Player.name)
    rows = await session.execute(stmt)
    return [(r.id, r.name) for r in rows]


async def get_player_name(session: AsyncSession, player_id: int) -> str | None:
    return await session.scalar(select(Player.name).where(Player.id == player_id))


# --- Награды ---

async def get_awards_map(
    session: AsyncSession, user_id: int
) -> dict[str, AwardPrediction]:
    rows = await session.scalars(
        select(AwardPrediction).where(AwardPrediction.user_id == user_id)
    )
    return {a.award_type: a for a in rows}


async def upsert_award(
    session: AsyncSession,
    user_id: int,
    award_type: str,
    *,
    team_id: int | None = None,
    player_id: int | None = None,
    int_value: int | None = None,
) -> None:
    award = await session.scalar(
        select(AwardPrediction).where(
            AwardPrediction.user_id == user_id,
            AwardPrediction.award_type == award_type,
        )
    )
    if award is None:
        session.add(
            AwardPrediction(
                user_id=user_id,
                award_type=award_type,
                team_id=team_id,
                player_id=player_id,
                int_value=int_value,
            )
        )
    else:
        award.team_id = team_id
        award.player_id = player_id
        award.int_value = int_value


# --- Символическая сборная ---

async def get_tot_slots(
    session: AsyncSession, user_id: int
) -> set[tuple[str, int]]:
    rows = await session.execute(
        select(TeamOfTournamentPick.position, TeamOfTournamentPick.slot_index).where(
            TeamOfTournamentPick.user_id == user_id
        )
    )
    return {(r.position, r.slot_index) for r in rows}


async def get_tot_player_ids(session: AsyncSession, user_id: int) -> set[int]:
    rows = await session.scalars(
        select(TeamOfTournamentPick.player_id).where(
            TeamOfTournamentPick.user_id == user_id
        )
    )
    return set(rows)


async def upsert_tot_pick(
    session: AsyncSession,
    user_id: int,
    position: str,
    slot_index: int,
    player_id: int,
) -> None:
    pick = await session.scalar(
        select(TeamOfTournamentPick).where(
            TeamOfTournamentPick.user_id == user_id,
            TeamOfTournamentPick.position == position,
            TeamOfTournamentPick.slot_index == slot_index,
        )
    )
    if pick is None:
        session.add(
            TeamOfTournamentPick(
                user_id=user_id,
                position=position,
                slot_index=slot_index,
                player_id=player_id,
            )
        )
    else:
        pick.player_id = player_id


async def get_tot_picks(
    session: AsyncSession, user_id: int
) -> list[TeamOfTournamentPick]:
    rows = await session.scalars(
        select(TeamOfTournamentPick)
        .where(TeamOfTournamentPick.user_id == user_id)
        .order_by(TeamOfTournamentPick.position, TeamOfTournamentPick.slot_index)
    )
    return list(rows)


# --- Плей-офф ---

async def get_bracket_preds(
    session: AsyncSession, user_id: int
) -> dict[int, BracketPrediction]:
    rows = await session.scalars(
        select(BracketPrediction).where(BracketPrediction.user_id == user_id)
    )
    return {p.match_number: p for p in rows}


async def upsert_bracket_teams(
    session: AsyncSession,
    user_id: int,
    match_number: int,
    home_team_id: int,
    away_team_id: int,
) -> None:
    """Зафиксировать участников матча сетки (если ещё не зафиксированы)."""
    pred = await session.scalar(
        select(BracketPrediction).where(
            BracketPrediction.user_id == user_id,
            BracketPrediction.match_number == match_number,
        )
    )
    if pred is None:
        session.add(
            BracketPrediction(
                user_id=user_id,
                match_number=match_number,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
            )
        )
    elif pred.winner_team_id is None:
        pred.home_team_id = home_team_id
        pred.away_team_id = away_team_id


async def set_bracket_result(
    session: AsyncSession,
    user_id: int,
    match_number: int,
    home_score: int,
    away_score: int,
    winner_team_id: int,
) -> None:
    pred = await session.scalar(
        select(BracketPrediction).where(
            BracketPrediction.user_id == user_id,
            BracketPrediction.match_number == match_number,
        )
    )
    if pred is not None:
        pred.home_score = home_score
        pred.away_score = away_score
        pred.winner_team_id = winner_team_id


async def get_next_bracket_match(
    session: AsyncSession, user_id: int
) -> BracketPrediction | None:
    """Первый матч сетки с известными участниками, но без победителя."""
    stmt = (
        select(BracketPrediction)
        .where(
            BracketPrediction.user_id == user_id,
            BracketPrediction.home_team_id.isnot(None),
            BracketPrediction.away_team_id.isnot(None),
            BracketPrediction.winner_team_id.is_(None),
        )
        .order_by(BracketPrediction.match_number)
        .limit(1)
    )
    return await session.scalar(stmt)


async def get_bracket_pred(
    session: AsyncSession, user_id: int, match_number: int
) -> BracketPrediction | None:
    return await session.scalar(
        select(BracketPrediction).where(
            BracketPrediction.user_id == user_id,
            BracketPrediction.match_number == match_number,
        )
    )


async def get_group_results(
    session: AsyncSession, group_id: int, user_id: int
) -> list[MatchResult]:
    """Спрогнозированные результаты матчей одной группы."""
    stmt = (
        select(
            GroupMatch.home_team_id,
            GroupMatch.away_team_id,
            GroupPrediction.home_score,
            GroupPrediction.away_score,
        )
        .join(GroupPrediction, GroupPrediction.group_match_id == GroupMatch.id)
        .where(GroupMatch.group_id == group_id, GroupPrediction.user_id == user_id)
    )
    rows = await session.execute(stmt)
    return [
        MatchResult(home_id=r[0], away_id=r[1], home_score=r[2], away_score=r[3])
        for r in rows
    ]
