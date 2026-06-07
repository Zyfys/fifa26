"""Интеграция: построение сетки плей-офф и продвижение до финала (async SQLite)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.data.wc2026 import GROUP_PAIRINGS, GROUPS, iter_group_matches
from src.db import repo
from src.db.base import Base
from src.models import Group, GroupMatch, GroupPrediction, Team, User
from src.services import playoff


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _setup_full_tournament(s: AsyncSession) -> int:
    """12 групп, 48 команд, 72 матча + прогноз пользователя на все матчи.

    Внутри группы выигрывает команда с меньшим номером позиции (детерминированно).
    Возвращает user_id.
    """
    team_ids: dict[tuple[str, int], int] = {}  # (буква, позиция 1..4) -> team_id
    for letter in GROUPS:
        g = Group(letter=letter)
        s.add(g)
        await s.flush()
        for pos in range(1, 5):
            t = Team(name=f"{letter}{pos}", group_id=g.id)
            s.add(t)
            await s.flush()
            team_ids[(letter, pos)] = t.id

    group_id_by_letter = {}
    for g in await repo.get_all_groups(s):
        group_id_by_letter[g.letter] = g.id

    for letter, match_number, home_pos, away_pos in iter_group_matches():
        s.add(
            GroupMatch(
                group_id=group_id_by_letter[letter],
                match_number=match_number,
                home_team_id=team_ids[(letter, home_pos)],
                away_team_id=team_ids[(letter, away_pos)],
            )
        )
    await s.flush()

    user = User(telegram_id=1, username="t")
    s.add(user)
    await s.flush()

    # Прогноз: в каждой паре побеждает команда с меньшей позицией (хозяин здесь всегда меньше).
    assert all(h < a for h, a in GROUP_PAIRINGS)
    for gm in (await s.scalars(select(GroupMatch))).all():
        s.add(
            GroupPrediction(
                user_id=user.id, group_match_id=gm.id, home_score=1, away_score=0
            )
        )
    await s.commit()
    return user.id


async def test_bracket_resolves_and_completes(session: AsyncSession):
    user_id = await _setup_full_tournament(session)

    # Строим сетку: R32 должно полностью определиться.
    await playoff.resolve_bracket(session, user_id)
    await session.commit()

    preds = await repo.get_bracket_preds(session, user_id)
    r32 = [n for n in preds if 73 <= n <= 88]
    assert len(r32) == 16
    for n in r32:
        assert preds[n].home_team_id is not None
        assert preds[n].away_team_id is not None

    # Прогоняем всю сетку: победитель — всегда хозяин.
    steps = 0
    while (m := await repo.get_next_bracket_match(session, user_id)) is not None:
        await repo.set_bracket_result(
            session, user_id, m.match_number, 1, 0, m.home_team_id
        )
        await session.commit()
        await playoff.resolve_bracket(session, user_id)
        await session.commit()
        steps += 1
        assert steps <= 40  # страховка от зацикливания

    # Все 32 матча сетки сыграны, чемпион определён.
    preds = await repo.get_bracket_preds(session, user_id)
    assert len(preds) == 32
    assert all(p.winner_team_id is not None for p in preds.values())
    champion = await playoff.get_champion_id(session, user_id)
    assert champion is not None
