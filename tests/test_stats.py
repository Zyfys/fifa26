"""Тест сервиса админ-статистики на async-SQLite."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db import repo
from src.db.base import Base
from src.models import BracketPrediction, Group, GroupMatch, GroupPrediction, Team
from src.services.playoff import FINAL_MATCH
from src.services.stats import collect_stats


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _setup_minimal(s: AsyncSession) -> tuple[int, int]:
    """Группа с одним матчем + команда-чемпион. Возвращает (match_id, champ_team_id)."""
    g = Group(letter="A")
    s.add(g)
    await s.flush()
    home = Team(name="Германия", group_id=g.id)
    away = Team(name="Бразилия", group_id=g.id)
    s.add_all([home, away])
    await s.flush()
    m = GroupMatch(group_id=g.id, match_number=1, home_team_id=home.id, away_team_id=away.id)
    s.add(m)
    await s.flush()
    return m.id, home.id


async def test_collect_stats_completed_and_partial(session: AsyncSession):
    match_id, champ_id = await _setup_minimal(session)

    # Пользователь 1 — завершил (есть победитель финала = чемпион).
    u1 = await repo.get_or_create_user(session, telegram_id=111, username="winner")
    await session.flush()
    session.add(
        BracketPrediction(
            user_id=u1.id,
            match_number=FINAL_MATCH,
            home_team_id=champ_id,
            away_team_id=champ_id,
            winner_team_id=champ_id,
        )
    )

    # Пользователь 2 — частичный (только один групповой прогноз, финал не дошёл).
    u2 = await repo.get_or_create_user(session, telegram_id=222, username=None)
    await session.flush()
    session.add(
        GroupPrediction(user_id=u2.id, group_match_id=match_id, home_score=1, away_score=0)
    )
    await session.commit()

    stats = await collect_stats(session)

    assert stats.total_users == 2
    assert stats.completed == 1

    by_id = {u.id: u for u in stats.users}
    assert by_id[u1.id].completed is True
    assert by_id[u1.id].champion == "Германия"
    assert by_id[u2.id].completed is False
    assert by_id[u2.id].champion is None
    assert by_id[u2.id].group_done == 1
    # username отсутствует → None (хэндлер покажет idNNN)
    assert by_id[u2.id].username is None


async def test_collect_stats_empty(session: AsyncSession):
    stats = await collect_stats(session)
    assert stats.total_users == 0
    assert stats.completed == 0
    assert stats.users == []


async def test_collect_stats_limit(session: AsyncSession):
    await _setup_minimal(session)
    for i in range(5):
        await repo.get_or_create_user(session, telegram_id=1000 + i, username=f"u{i}")
        await session.flush()
    await session.commit()

    stats = await collect_stats(session, limit=2)
    assert stats.total_users == 5
    assert len(stats.users) == 2  # список ограничен, total — полный
