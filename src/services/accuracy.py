"""Точность прогнозов: сравнение прогнозов групповых матчей с фактом.

Метрики на пользователя: сколько угадано исходов (П1/Х/П2) и сколько точных счетов,
от числа сыгранных (внесённых) матчей, по которым у пользователя есть прогноз.
Чистый расчёт на стороне БД — без сохранения агрегатов (всегда актуально).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import ActualResult, GroupMatch, GroupPrediction, User


def outcome(home: int, away: int) -> int:
    """Исход матча: 1 — победа хозяев, 0 — ничья, -1 — победа гостей."""
    return (home > away) - (home < away)


def _pct(part: int, whole: int) -> int:
    return round(100 * part / whole) if whole else 0


@dataclass
class Accuracy:
    played: int  # сыграно матчей с прогнозом
    outcomes: int  # угадано исходов
    exacts: int  # угадано точных счетов

    @property
    def outcome_pct(self) -> int:
        return _pct(self.outcomes, self.played)

    @property
    def exact_pct(self) -> int:
        return _pct(self.exacts, self.played)


@dataclass
class LeaderRow:
    user_id: int
    telegram_id: int
    username: str | None
    accuracy: Accuracy


# Прогноз пользователя и факт по одному матчу.
_PH = GroupPrediction.home_score
_PA = GroupPrediction.away_score
_AH = ActualResult.home_score
_AA = ActualResult.away_score

# Исход угадан, если знаки (П1/Х/П2) совпали.
_OUTCOME_OK = or_(
    and_(_PH > _PA, _AH > _AA),
    and_(_PH < _PA, _AH < _AA),
    and_(_PH == _PA, _AH == _AA),
)
# Точный счёт угадан.
_EXACT_OK = and_(_PH == _AH, _PA == _AA)

_PLAYED = func.count().label("played")
_OUTCOMES = func.sum(case((_OUTCOME_OK, 1), else_=0)).label("outcomes")
_EXACTS = func.sum(case((_EXACT_OK, 1), else_=0)).label("exacts")


def _joined(stmt):
    """Прицепить факт к прогнозам через group_matches.match_number."""
    return (
        stmt.select_from(GroupPrediction)
        .join(GroupMatch, GroupMatch.id == GroupPrediction.group_match_id)
        .join(ActualResult, ActualResult.match_number == GroupMatch.match_number)
    )


async def compute_user_accuracy(session: AsyncSession, user_id: int) -> Accuracy:
    stmt = _joined(select(_PLAYED, _OUTCOMES, _EXACTS)).where(
        GroupPrediction.user_id == user_id
    )
    row = (await session.execute(stmt)).one()
    return Accuracy(
        played=int(row.played or 0),
        outcomes=int(row.outcomes or 0),
        exacts=int(row.exacts or 0),
    )


async def compute_leaderboard(session: AsyncSession) -> list[LeaderRow]:
    """Рейтинг пользователей: по точным счетам, затем исходам, затем числу матчей."""
    stmt = (
        _joined(
            select(
                User.id,
                User.telegram_id,
                User.username,
                _PLAYED,
                _OUTCOMES,
                _EXACTS,
            )
        )
        .join(User, User.id == GroupPrediction.user_id)
        .group_by(User.id, User.telegram_id, User.username)
        .order_by(_EXACTS.desc(), _OUTCOMES.desc(), _PLAYED.desc(), User.id)
    )
    rows = await session.execute(stmt)
    return [
        LeaderRow(
            user_id=r.id,
            telegram_id=r.telegram_id,
            username=r.username,
            accuracy=Accuracy(
                played=int(r.played or 0),
                outcomes=int(r.outcomes or 0),
                exacts=int(r.exacts or 0),
            ),
        )
        for r in rows
    ]
