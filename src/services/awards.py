"""Последовательность шагов Фазы 4: индивидуальные награды и символическая сборная.

Чистые определения (без БД): какие награды и слоты сборной заполняются, в каком
порядке, с какими фильтрами игроков.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

# Молодой игрок: 2005 г.р. и младше (21 год или меньше на ЧМ-2026).
YOUNG_BORN_AFTER = datetime.date(2005, 1, 1)

POSITION_LABEL: dict[str, str] = {
    "GK": "вратарь",
    "DF": "защитник",
    "MF": "полузащитник",
    "FW": "нападающий",
}

# Схема символической сборной 4-3-3: (позиция, количество слотов).
FORMATION: list[tuple[str, int]] = [("GK", 1), ("DF", 4), ("MF", 3), ("FW", 3)]

# Порядок и подписи наград (для сводки и PDF): (award_type, подпись, вид).
AWARD_DISPLAY: list[tuple[str, str, str]] = [
    ("BEST_PLAYER", "Золотой мяч (лучший игрок)", "player"),
    ("TOP_SCORER", "Золотая бутса (бомбардир)", "player_goals"),
    ("YOUNG_PLAYER", "Лучший молодой игрок", "player"),
    ("BEST_GOALKEEPER", "Золотая перчатка (вратарь)", "player"),
    ("BREAKTHROUGH", "Открытие турнира", "player"),
    ("SURPRISE_TEAM", "Сборная-сенсация", "team"),
    ("DISAPPOINTMENT_TEAM", "Команда-разочарование", "team"),
]


@dataclass(frozen=True)
class Step:
    """Один шаг прохождения Фазы 4."""

    id: str
    title: str
    kind: str  # 'team' | 'player' | 'player_goals' | 'tot'
    award_type: str | None = None
    position: str | None = None  # фильтр позиции игрока / позиция в сборной
    young: bool = False
    tot_slot: int | None = None  # номер слота в линии сборной


def build_steps() -> list[Step]:
    """Полный упорядоченный список шагов: сначала награды, затем сборная 4-3-3."""
    steps: list[Step] = [
        Step("best_player", "⭐ Золотой мяч — лучший игрок турнира", "player",
             award_type="BEST_PLAYER"),
        Step("top_scorer", "⚽ Золотая бутса — лучший бомбардир", "player_goals",
             award_type="TOP_SCORER"),
        Step("young_player", "🌟 Лучший молодой игрок", "player",
             award_type="YOUNG_PLAYER", young=True),
        Step("best_gk", "🧤 Золотая перчатка — лучший вратарь", "player",
             award_type="BEST_GOALKEEPER", position="GK"),
        Step("breakthrough", "🚀 Открытие турнира", "player",
             award_type="BREAKTHROUGH"),
        Step("surprise_team", "🔥 Сборная-сенсация", "team",
             award_type="SURPRISE_TEAM"),
        Step("disappointment_team", "📉 Команда-разочарование", "team",
             award_type="DISAPPOINTMENT_TEAM"),
    ]
    for pos, count in FORMATION:
        for slot in range(1, count + 1):
            steps.append(
                Step(
                    id=f"tot_{pos}_{slot}",
                    title=f"👕 Символическая сборная · {POSITION_LABEL[pos]} {slot}",
                    kind="tot",
                    position=pos,
                    tot_slot=slot,
                )
            )
    return steps


def steps_by_id() -> dict[str, Step]:
    return {s.id: s for s in build_steps()}
