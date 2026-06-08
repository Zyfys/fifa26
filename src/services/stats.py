"""Админ-статистика: агрегаты по пользователям и их прогнозам.

Чистый сервис (только чтение БД), чтобы хэндлер оставался тонким и тестировался
отдельно. «Завершённым» считаем прогноз, доведённый до чемпиона (финал сетит
победителя матча №104), а не по полю User.progress — оно не обновляется по ходу.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import repo
from src.models import BracketPrediction, GroupPrediction, Team, User
from src.services.playoff import FINAL_MATCH

GROUP_MATCHES_TOTAL = repo.GROUP_MATCHES_TOTAL


@dataclass
class UserStat:
    id: int
    telegram_id: int
    username: str | None
    created_at: object  # datetime | None — форматируется на стороне хэндлера
    group_done: int
    completed: bool
    champion: str | None


@dataclass
class BotStats:
    total_users: int
    completed: int
    users: list[UserStat] = field(default_factory=list)


async def collect_stats(session: AsyncSession, *, limit: int | None = None) -> BotStats:
    """Сводка: всего пользователей, сколько завершили, и список (свежие сверху)."""
    total = await session.scalar(select(func.count()).select_from(User)) or 0
    completed = (
        await session.scalar(
            select(func.count())
            .select_from(BracketPrediction)
            .where(
                BracketPrediction.match_number == FINAL_MATCH,
                BracketPrediction.winner_team_id.isnot(None),
            )
        )
        or 0
    )

    group_done = (
        select(
            GroupPrediction.user_id.label("user_id"),
            func.count().label("cnt"),
        )
        .group_by(GroupPrediction.user_id)
        .subquery()
    )
    final = (
        select(
            BracketPrediction.user_id.label("user_id"),
            BracketPrediction.winner_team_id.label("champ_id"),
        )
        .where(BracketPrediction.match_number == FINAL_MATCH)
        .subquery()
    )

    stmt = (
        select(
            User.id,
            User.telegram_id,
            User.username,
            User.created_at,
            func.coalesce(group_done.c.cnt, 0),
            final.c.champ_id,
            Team.name,
        )
        .outerjoin(group_done, group_done.c.user_id == User.id)
        .outerjoin(final, final.c.user_id == User.id)
        .outerjoin(Team, Team.id == final.c.champ_id)
        .order_by(User.created_at.desc(), User.id.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    rows = await session.execute(stmt)
    users = [
        UserStat(
            id=r[0],
            telegram_id=r[1],
            username=r[2],
            created_at=r[3],
            group_done=int(r[4] or 0),
            completed=r[5] is not None,
            champion=r[6],
        )
        for r in rows
    ]
    return BotStats(total_users=total, completed=completed, users=users)
