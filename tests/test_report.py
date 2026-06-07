"""Тесты PDF-отчёта: рендер и сбор данных."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.base import Base
from src.models import Group, GroupMatch, GroupPrediction, Team, User
from src.pdf.report import render
from src.services.report_data import (
    BracketMatch,
    GroupTable,
    ReportData,
    ThirdRow,
    build_report_data,
)
from src.services.standings import StandingRow


def test_render_produces_valid_pdf():
    rows = [
        StandingRow(1, "Бразилия", played=3, won=3, gf=6, ga=1),
        StandingRow(2, "Швейцария", played=3, won=2, gf=4, ga=2),
        StandingRow(3, "Камерун", played=3, won=1, gf=2, ga=3),
        StandingRow(4, "Сербия", played=3, won=0, gf=1, ga=7),
    ]
    data = ReportData(
        username="tester",
        created="06.06.2026",
        groups=[GroupTable("A", rows)],
        thirds=[ThirdRow("A", rows[2], qualified=True)],
        rounds=[("Финал", [BracketMatch("Бразилия", "Франция", 2, 1, "Бразилия")])],
        champion="Бразилия",
        runner_up="Франция",
        third_place="Аргентина",
        awards=[("Золотой мяч", "Винисиус"), ("Золотая бутса", "Мбаппе (7 голов)")],
        tot=[("Вратарь", ["Алисон"]), ("Защитник", ["Маркиньос"])],
    )
    pdf = render(data)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1500


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_build_report_data_with_one_group(session: AsyncSession):
    g = Group(letter="A")
    session.add(g)
    await session.flush()
    teams = [Team(name=n, group_id=g.id) for n in ("Алжир", "Бразилия", "Гана", "Дания")]
    session.add_all(teams)
    await session.flush()
    ids = [t.id for t in teams]
    pairs = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    user = User(telegram_id=5, username="neo")
    session.add(user)
    await session.flush()
    for i, (h, a) in enumerate(pairs, start=1):
        gm = GroupMatch(
            group_id=g.id, match_number=i, home_team_id=ids[h], away_team_id=ids[a]
        )
        session.add(gm)
        await session.flush()
        session.add(
            GroupPrediction(
                user_id=user.id, group_match_id=gm.id, home_score=1, away_score=0
            )
        )
    await session.commit()

    data = await build_report_data(session, user.id)
    assert data.username == "neo"
    assert len(data.groups) == 1
    assert len(data.groups[0].rows) == 4
    # PDF тоже должен собраться.
    assert render(data)[:4] == b"%PDF"
