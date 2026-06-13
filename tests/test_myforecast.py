"""Тесты просмотра «Мои прогнозы»: запрос групповых прогнозов и форматтеры."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db import repo
from src.db.base import Base
from src.handlers.myforecast import (
    _format_group_predictions,
    _format_playoff_predictions,
)
from src.models import (
    BracketPrediction,
    Group,
    GroupMatch,
    GroupPrediction,
    Team,
    User,
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


async def _setup_groups(session: AsyncSession) -> int:
    """Группа A (2 матча) и группа B (1 матч) + прогнозы. Возвращает user_id.

    Сущности добавляются «не по порядку» (B раньше A, матч 2 раньше матча 1),
    чтобы проверить сортировку результата по букве группы и номеру матча.
    """
    gb = Group(letter="B")
    ga = Group(letter="A")
    session.add_all([gb, ga])
    await session.flush()
    tb = [Team(name=n, group_id=gb.id) for n in ("Перу", "Катар")]
    ta = [Team(name=n, group_id=ga.id) for n in ("Бразилия", "Сербия", "Гана")]
    session.add_all(tb + ta)
    await session.flush()
    user = User(telegram_id=1, username="t")
    session.add(user)
    await session.flush()

    gm_a2 = GroupMatch(
        group_id=ga.id, match_number=2, home_team_id=ta[0].id, away_team_id=ta[2].id
    )
    gm_a1 = GroupMatch(
        group_id=ga.id, match_number=1, home_team_id=ta[0].id, away_team_id=ta[1].id
    )
    # match_number глобально уникален (1..72), поэтому у группы B — свой номер.
    gm_b1 = GroupMatch(
        group_id=gb.id, match_number=3, home_team_id=tb[0].id, away_team_id=tb[1].id
    )
    session.add_all([gm_a2, gm_a1, gm_b1])
    await session.flush()
    session.add_all(
        [
            GroupPrediction(
                user_id=user.id, group_match_id=gm_a2.id, home_score=0, away_score=0
            ),
            GroupPrediction(
                user_id=user.id, group_match_id=gm_a1.id, home_score=2, away_score=1
            ),
            GroupPrediction(
                user_id=user.id, group_match_id=gm_b1.id, home_score=3, away_score=2
            ),
        ]
    )
    await session.commit()
    return user.id


async def test_get_group_predictions_ordered_and_named(session: AsyncSession):
    user_id = await _setup_groups(session)
    rows = await repo.get_group_predictions(session, user_id)
    # Сортировка: группа A (матч 1, затем матч 2), затем группа B.
    assert rows == [
        ("A", "Бразилия", "Сербия", 2, 1),
        ("A", "Бразилия", "Гана", 0, 0),
        ("B", "Перу", "Катар", 3, 2),
    ]


async def test_get_group_predictions_empty(session: AsyncSession):
    user = User(telegram_id=9)
    session.add(user)
    await session.flush()
    await session.commit()
    assert await repo.get_group_predictions(session, user.id) == []


async def test_format_group_predictions(session: AsyncSession):
    user_id = await _setup_groups(session)
    blocks = await _format_group_predictions(session, user_id)
    assert len(blocks) == 2  # по блоку на группу
    assert "Группа A" in blocks[0] and "<pre>" in blocks[0]
    assert "Бразилия 2:1 Сербия" in blocks[0]
    assert "Бразилия 0:0 Гана" in blocks[0]
    assert "Группа B" in blocks[1]
    assert "Перу 3:2 Катар" in blocks[1]


async def _setup_playoff(session: AsyncSession) -> int:
    g = Group(letter="A")
    session.add(g)
    await session.flush()
    teams = [Team(name=n, group_id=g.id) for n in ("Бразилия", "Сербия", "Гана", "Дания")]
    session.add_all(teams)
    await session.flush()
    b, s, gh, d = (t.id for t in teams)
    user = User(telegram_id=2, username="p")
    session.add(user)
    await session.flush()
    session.add_all(
        [
            # 1/16: ничья, прошла Бразилия по пенальти.
            BracketPrediction(
                user_id=user.id,
                match_number=73,
                home_team_id=b,
                away_team_id=s,
                home_score=1,
                away_score=1,
                winner_team_id=b,
            ),
            # 1/8: участники известны, счёт ещё не заполнен.
            BracketPrediction(
                user_id=user.id, match_number=89, home_team_id=gh, away_team_id=d
            ),
        ]
    )
    await session.commit()
    return user.id


async def test_format_playoff_predictions(session: AsyncSession):
    user_id = await _setup_playoff(session)
    blocks = await _format_playoff_predictions(session, user_id)
    assert len(blocks) == 2  # 1/16 и 1/8
    assert "1/16 финала" in blocks[0]
    assert "Бразилия 1:1 Сербия (пен. ✅ Бразилия)" in blocks[0]
    assert "1/8 финала" in blocks[1]
    assert "Гана — Дания (не заполнено)" in blocks[1]


async def test_format_playoff_empty(session: AsyncSession):
    user = User(telegram_id=7)
    session.add(user)
    await session.flush()
    await session.commit()
    assert await _format_playoff_predictions(session, user.id) == []
