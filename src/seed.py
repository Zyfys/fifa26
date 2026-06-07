"""Заполнение справочных данных ЧМ-2026 в БД.

Запуск (после применения миграций):
    python -m src.seed

Идемпотентность: если группы уже есть — выходим, чтобы не плодить дубликаты.
Загрузка игроков выполняется из JSON-файлов в src/data/players/ (если присутствуют).
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from src.data.players_loader import load_players
from src.data.wc2026 import BRACKET, GROUPS, iter_group_matches
from src.db.session import async_session
from src.models import BracketSlot, Group, GroupMatch, Team


async def seed() -> None:
    async with async_session() as session:
        existing = await session.scalar(select(Group).limit(1))
        if existing is not None:
            print("Данные уже загружены — пропускаю сид справочников.")
        else:
            await _seed_reference(session)
            await session.commit()
            print("Справочники ЧМ-2026 загружены: 12 групп, 48 команд, 72 матча, сетка 73–104.")

        # Игроки — отдельно, чтобы можно было дозагружать по мере наполнения данных.
        added = await load_players(session)
        await session.commit()
        if added:
            print(f"Загружено игроков: {added}.")
        else:
            print("Данные игроков не найдены (src/data/players/*.json) — пропускаю.")


async def _seed_reference(session) -> None:
    # Группы и команды.
    team_by_name: dict[str, Team] = {}
    for letter, team_names in GROUPS.items():
        group = Group(letter=letter)
        session.add(group)
        await session.flush()  # получить group.id
        for name in team_names:
            team = Team(name=name, group_id=group.id)
            session.add(team)
            team_by_name[name] = team
    await session.flush()  # получить team.id

    # Расписание групповых матчей.
    group_id_by_letter = {
        letter: team_by_name[GROUPS[letter][0]].group_id for letter in GROUPS
    }
    for letter, match_number, home_pos, away_pos in iter_group_matches():
        home = team_by_name[GROUPS[letter][home_pos - 1]]
        away = team_by_name[GROUPS[letter][away_pos - 1]]
        session.add(
            GroupMatch(
                group_id=group_id_by_letter[letter],
                match_number=match_number,
                home_team_id=home.id,
                away_team_id=away.id,
            )
        )

    # Статическая структура сетки плей-офф.
    for stage, match_number, home_source, away_source in BRACKET:
        session.add(
            BracketSlot(
                match_number=match_number,
                stage=stage,
                home_source=home_source,
                away_source=away_source,
            )
        )


if __name__ == "__main__":
    asyncio.run(seed())
