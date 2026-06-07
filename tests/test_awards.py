"""Тесты Фазы 4: шаги наград, фильтры игроков, CRUD (async SQLite)."""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db import repo
from src.db.base import Base
from src.handlers.awards import _first_incomplete_step
from src.models import Group, Player, Team, User
from src.services.awards import YOUNG_BORN_AFTER, build_steps


def test_build_steps_counts():
    steps = build_steps()
    assert len(steps) == 18  # 7 наград + 11 игроков сборной (1+4+3+3)
    tot = [s for s in steps if s.kind == "tot"]
    assert len(tot) == 11
    assert sum(1 for s in tot if s.position == "DF") == 4


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _setup(s: AsyncSession) -> tuple[int, dict[str, int]]:
    g = Group(letter="A")
    s.add(g)
    await s.flush()
    team = Team(name="Команда", group_id=g.id)
    s.add(team)
    await s.flush()
    players = {
        "gk_old": Player(name="Вратарь Старый", position="GK",
                         birth_date=datetime.date(1990, 1, 1), team_id=team.id),
        "gk_young": Player(name="Вратарь Юный", position="GK",
                           birth_date=datetime.date(2006, 1, 1), team_id=team.id),
        "df_young": Player(name="Защитник Юный", position="DF",
                           birth_date=datetime.date(2005, 6, 1), team_id=team.id),
        "fw_old": Player(name="Форвард Старый", position="FW",
                         birth_date=datetime.date(1992, 1, 1), team_id=team.id),
    }
    s.add_all(list(players.values()))
    await s.flush()
    user = User(telegram_id=1, username="t")
    s.add(user)
    await s.flush()
    await s.commit()
    return team.id, {k: v.id for k, v in players.items()}


async def test_player_filters(session: AsyncSession):
    team_id, ids = await _setup(session)

    gks = await repo.list_players(session, team_id, position="GK")
    assert {pid for pid, _ in gks} == {ids["gk_old"], ids["gk_young"]}

    young = await repo.list_players(session, team_id, born_after=YOUNG_BORN_AFTER)
    assert {pid for pid, _ in young} == {ids["gk_young"], ids["df_young"]}

    young_gk = await repo.list_players(
        session, team_id, position="GK", born_after=YOUNG_BORN_AFTER
    )
    assert {pid for pid, _ in young_gk} == {ids["gk_young"]}


async def test_award_and_tot_crud(session: AsyncSession):
    _team_id, ids = await _setup(session)
    user = await repo.get_or_create_user(session, 1, "t")

    await repo.upsert_award(session, user.id, "BEST_PLAYER", player_id=ids["fw_old"])
    await repo.upsert_award(session, user.id, "TOP_SCORER",
                            player_id=ids["fw_old"], int_value=8)
    await session.commit()
    awards = await repo.get_awards_map(session, user.id)
    assert awards["TOP_SCORER"].int_value == 8

    await repo.upsert_tot_pick(session, user.id, "GK", 1, ids["gk_young"])
    await session.commit()
    assert await repo.get_tot_slots(session, user.id) == {("GK", 1)}
    assert await repo.get_tot_player_ids(session, user.id) == {ids["gk_young"]}


async def test_first_incomplete_step_progression(session: AsyncSession):
    _team_id, ids = await _setup(session)
    user = await repo.get_or_create_user(session, 1, "t")

    step = await _first_incomplete_step(session, user.id)
    assert step.id == "best_player"

    await repo.upsert_award(session, user.id, "BEST_PLAYER", player_id=ids["fw_old"])
    await session.commit()
    step = await _first_incomplete_step(session, user.id)
    assert step.id == "top_scorer"
