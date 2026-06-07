"""Интеграционный тест потока группового этапа на async-SQLite."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db import repo
from src.db.base import Base
from src.handlers.group_stage import render_all_tables
from src.models import Group, GroupMatch, Team


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _setup_one_group(s: AsyncSession) -> None:
    g = Group(letter="A")
    s.add(g)
    await s.flush()
    teams = [Team(name=n, group_id=g.id) for n in ("Алжир", "Бразилия", "Гана", "Дания")]
    s.add_all(teams)
    await s.flush()
    ids = [t.id for t in teams]
    pairs = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    for i, (h, a) in enumerate(pairs, start=1):
        s.add(
            GroupMatch(
                group_id=g.id, match_number=i, home_team_id=ids[h], away_team_id=ids[a]
            )
        )
    await s.commit()


async def test_group_flow(session: AsyncSession):
    await _setup_one_group(session)
    user = await repo.get_or_create_user(session, telegram_id=1, username="t")
    await session.commit()

    # Первый незаполненный матч — матч №1.
    first = await repo.get_next_group_match(session, user.id)
    assert first is not None and first.match_number == 1

    # Заполняем все 6 матчей (команда 1 выигрывает всё, далее по убыванию).
    scores = {1: (2, 0), 2: (2, 0), 3: (2, 0), 4: (1, 0), 5: (1, 0), 6: (1, 0)}
    while (m := await repo.get_next_group_match(session, user.id)) is not None:
        h, a = scores[m.match_number]
        await repo.upsert_group_prediction(session, user.id, m.id, h, a)
        await session.commit()

    assert await repo.count_group_predictions(session, user.id) == 6
    assert await repo.get_next_group_match(session, user.id) is None

    # Редактирование: матч 1 теперь 0:3.
    await repo.upsert_group_prediction(session, user.id, first.id, 0, 3)
    await session.commit()
    assert await repo.count_group_predictions(session, user.id) == 6  # без дублей

    text = await render_all_tables(session, user.id)
    assert "Группа A" in text
    assert "Бразилия" in text
