"""Тест сборки схемы БД на SQLite (без PostgreSQL/Docker)."""

from __future__ import annotations

import datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.db.base import Base
from src.models import Group, GroupMatch, Player, Team, User


def test_metadata_builds_and_basic_insert():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    # Все ожидаемые таблицы созданы.
    expected = {
        "groups",
        "teams",
        "players",
        "group_matches",
        "bracket_slots",
        "users",
        "predictions_group",
        "predictions_bracket",
        "predictions_awards",
        "predictions_tot",
    }
    assert expected <= set(Base.metadata.tables)

    with Session(engine) as s:
        g = Group(letter="A")
        s.add(g)
        s.flush()
        home = Team(name="Мексика", group_id=g.id)
        away = Team(name="ЮАР", group_id=g.id)
        s.add_all([home, away])
        s.flush()
        s.add(
            Player(
                name="Рауль Хименес",
                position="FW",
                birth_date=datetime.date(1991, 5, 5),
                team_id=home.id,
            )
        )
        s.add(
            GroupMatch(
                group_id=g.id,
                match_number=1,
                home_team_id=home.id,
                away_team_id=away.id,
            )
        )
        s.add(User(telegram_id=12345, username="tester"))
        s.commit()

        assert s.scalar(select(func.count()).select_from(Team)) == 2
        assert s.scalar(select(func.count()).select_from(Player)) == 1
        assert s.scalar(select(Player.position)) == "FW"
