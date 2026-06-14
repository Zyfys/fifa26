"""Тесты точности прогнозов и фактических результатов (async-SQLite)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db import repo
from src.db.base import Base
from src.models import Group, GroupMatch, GroupPrediction, Team
from src.services.accuracy import (
    compute_leaderboard,
    compute_user_accuracy,
    outcome,
)


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


PAIRS = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]


async def _setup_group(s: AsyncSession) -> None:
    g = Group(letter="A")
    s.add(g)
    await s.flush()
    teams = [Team(name=n, group_id=g.id) for n in ("Бразилия", "Сербия", "Гана", "Дания")]
    s.add_all(teams)
    await s.flush()
    ids = [t.id for t in teams]
    for i, (h, a) in enumerate(PAIRS, start=1):
        s.add(
            GroupMatch(
                group_id=g.id, match_number=i, home_team_id=ids[h], away_team_id=ids[a]
            )
        )
    await s.commit()


async def _mid(s: AsyncSession, number: int) -> int:
    m = await s.scalar(select(GroupMatch).where(GroupMatch.match_number == number))
    return m.id


def test_outcome():
    assert outcome(2, 1) == 1
    assert outcome(1, 1) == 0
    assert outcome(0, 2) == -1


async def test_compute_user_accuracy(session: AsyncSession):
    await _setup_group(session)
    user = await repo.get_or_create_user(session, telegram_id=1, username="t")
    await session.commit()

    preds = {1: (2, 1), 2: (1, 0), 3: (0, 0)}
    for number, (h, a) in preds.items():
        session.add(
            GroupPrediction(
                user_id=user.id,
                group_match_id=await _mid(session, number),
                home_score=h,
                away_score=a,
            )
        )
    # m1 3:1 (исход да, точн нет), m2 0:3 (нет/нет), m3 0:0 (да/да).
    await repo.upsert_actual_result(session, 1, 3, 1)
    await repo.upsert_actual_result(session, 2, 0, 3)
    await repo.upsert_actual_result(session, 3, 0, 0)
    await session.commit()

    acc = await compute_user_accuracy(session, user.id)
    assert acc.played == 3
    assert acc.outcomes == 2
    assert acc.exacts == 1
    assert acc.outcome_pct == 67
    assert acc.exact_pct == 33


async def test_accuracy_empty_when_no_actuals(session: AsyncSession):
    await _setup_group(session)
    user = await repo.get_or_create_user(session, telegram_id=2, username="x")
    session.add(
        GroupPrediction(
            user_id=user.id,
            group_match_id=await _mid(session, 1),
            home_score=1,
            away_score=0,
        )
    )
    await session.commit()
    acc = await compute_user_accuracy(session, user.id)
    assert acc.played == 0 and acc.outcomes == 0 and acc.exacts == 0
    assert acc.outcome_pct == 0


async def test_leaderboard_order(session: AsyncSession):
    await _setup_group(session)
    u1 = await repo.get_or_create_user(session, telegram_id=1, username="good")
    u2 = await repo.get_or_create_user(session, telegram_id=2, username="bad")
    await session.commit()

    mid1 = await _mid(session, 1)
    session.add(
        GroupPrediction(user_id=u1.id, group_match_id=mid1, home_score=2, away_score=1)
    )
    session.add(
        GroupPrediction(user_id=u2.id, group_match_id=mid1, home_score=0, away_score=0)
    )
    await repo.upsert_actual_result(session, 1, 2, 1)
    await session.commit()

    board = await compute_leaderboard(session)
    assert [r.user_id for r in board] == [u1.id, u2.id]
    assert board[0].accuracy.exacts == 1 and board[1].accuracy.exacts == 0


async def test_upsert_actual_overwrite_and_unfilled(session: AsyncSession):
    await _setup_group(session)
    await repo.upsert_actual_result(session, 1, 1, 0)
    await session.commit()
    assert await repo.count_actual_results(session) == 1

    await repo.upsert_actual_result(session, 1, 2, 2)  # перезапись того же матча
    await session.commit()
    assert await repo.count_actual_results(session) == 1
    assert (await repo.get_actual_results(session))[1] == (2, 2)

    unfilled = await repo.get_unfilled_group_matches(session)
    assert [m.match_number for m in unfilled] == [2, 3, 4, 5, 6]

    fixtures = await repo.list_group_fixtures(session)
    assert len(fixtures) == 6
    assert fixtures[0][0] == 1  # (match_number, home, away)
