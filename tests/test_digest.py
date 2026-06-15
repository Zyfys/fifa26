"""Тесты утренней сводки: классификация статуса, рендер, repo-хелперы (SQLite)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db import repo
from src.db.base import Base
from src.models import Group, GroupMatch, GroupPrediction, Team
from src.services.accuracy import Accuracy
from src.services.digest import _status, build_user_digest


def test_status():
    assert _status((2, 1), (2, 1)) == "😎"  # точный счёт
    assert _status((2, 0), (1, 0)) == "✅"  # угадан исход
    assert _status((1, 1), (2, 0)) == "☹️"  # мимо
    assert _status(None, (1, 0)) == "▫️"  # не прогнозировал


def test_build_user_digest():
    results = [
        (1, "Мексика", "ЮАР", 2, 1),
        (2, "Канада", "Босния и Герцеговина", 2, 0),
    ]
    pred_map = {1: (2, 1)}  # m1 угадан точно, m2 без прогноза
    text = build_user_digest(results, pred_map, Accuracy(played=1, outcomes=1, exacts=1))
    assert "😎🇲🇽 Мексика — ЮАР 🇿🇦 2:1 · 2:1" in text
    assert "▫️🇨🇦 Канада — Босния и Герцеговина 🇧🇦 — · 2:0" in text
    assert "🎯 Точность: исходы 1/1 (100%), точные 1/1 (100%)" in text


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
    teams = [Team(name=n, group_id=g.id) for n in ("Мексика", "ЮАР", "Южная Корея", "Чехия")]
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


async def test_undigested_and_mark(session: AsyncSession):
    await _setup_group(session)
    await repo.upsert_actual_result(session, 1, 2, 1)
    await repo.upsert_actual_result(session, 2, 0, 0)
    await session.commit()

    undig = await repo.get_undigested_results(session)
    assert [r[0] for r in undig] == [1, 2]
    assert undig[0] == (1, "Мексика", "ЮАР", 2, 1)

    await repo.mark_results_digested(session, [1])
    await session.commit()
    assert [r[0] for r in await repo.get_undigested_results(session)] == [2]

    # Исправление результата сбрасывает digested → снова попадёт в сводку.
    await repo.upsert_actual_result(session, 1, 3, 0)
    await session.commit()
    assert {r[0] for r in await repo.get_undigested_results(session)} == {1, 2}


async def test_user_pred_by_match(session: AsyncSession):
    await _setup_group(session)
    user = await repo.get_or_create_user(session, telegram_id=1, username="t")
    session.add(
        GroupPrediction(
            user_id=user.id, group_match_id=await _mid(session, 1), home_score=2, away_score=1
        )
    )
    await session.commit()
    assert await repo.get_user_pred_by_match(session, user.id) == {1: (2, 1)}


async def test_users_with_predictions(session: AsyncSession):
    await _setup_group(session)
    u1 = await repo.get_or_create_user(session, telegram_id=1, username="has")
    await repo.get_or_create_user(session, telegram_id=2, username="none")
    session.add(
        GroupPrediction(
            user_id=u1.id, group_match_id=await _mid(session, 1), home_score=1, away_score=0
        )
    )
    await session.commit()
    users = await repo.get_users_with_group_predictions(session)
    assert [u.id for u in users] == [u1.id]


async def test_clear_actual_results(session: AsyncSession):
    await _setup_group(session)
    await repo.upsert_actual_result(session, 1, 1, 0)
    await repo.upsert_actual_result(session, 2, 2, 2)
    await session.commit()
    assert await repo.count_actual_results(session) == 2

    deleted = await repo.clear_actual_results(session)
    await session.commit()
    assert deleted == 2
    assert await repo.count_actual_results(session) == 0
