"""Загрузка игроков из JSON-файлов в БД.

Формат: каталог src/data/players/ с файлами «<Команда>.json», где имя файла
совпадает с русским названием команды (как в wc2026.GROUPS). Содержимое файла —
массив объектов:

    [
      {"name": "Лионель Месси", "position": "FW", "birth_date": "1987-06-24"},
      {"name": "Эмилиано Мартинес", "position": "GK", "birth_date": "1992-09-02"}
    ]

birth_date — строка ISO (YYYY-MM-DD) или null/отсутствует.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from sqlalchemy import select

from src.models import Player, Team

PLAYERS_DIR = Path(__file__).parent / "players"

VALID_POSITIONS = {"GK", "DF", "MF", "FW"}


async def load_players(session) -> int:
    """Загрузить игроков из JSON-файлов. Возвращает число добавленных записей.

    Пропускает игроков, если у команды они уже есть (идемпотентность по команде).
    """
    if not PLAYERS_DIR.exists():
        return 0

    team_by_name = {
        t.name: t for t in (await session.scalars(select(Team))).all()
    }

    added = 0
    for path in sorted(PLAYERS_DIR.glob("*.json")):
        team_name = path.stem
        team = team_by_name.get(team_name)
        if team is None:
            print(f"  ⚠️ Пропуск {path.name}: команда «{team_name}» не найдена в БД.")
            continue

        # Уже есть игроки у команды — не дублируем.
        has_players = await session.scalar(
            select(Player.id).where(Player.team_id == team.id).limit(1)
        )
        if has_players is not None:
            continue

        records = json.loads(path.read_text(encoding="utf-8"))
        for rec in records:
            position = rec["position"]
            if position not in VALID_POSITIONS:
                raise ValueError(f"{path.name}: недопустимая позиция {position!r}")
            birth = rec.get("birth_date")
            session.add(
                Player(
                    name=rec["name"],
                    position=position,
                    birth_date=datetime.date.fromisoformat(birth) if birth else None,
                    team_id=team.id,
                )
            )
            added += 1

    return added
