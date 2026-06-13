"""Логика сетки плей-офф (чистая, без БД).

- Назначение 8 лучших третьих мест по слотам Round of 32 (с учётом разрешённых групп).
- Разбор кодов источников участников ("1A", "2B", "3?", "W74", "L101").
- Человекочитаемые названия стадий.

Точная официальная таблица FIFA (495 комбинаций) заменена корректным по правилам
сопоставлением: каждому слоту достаётся третье место из разрешённого набора групп,
все 8 распределяются без повторов. См. docs/tournament-format.md и LESSONS.md.
"""

from __future__ import annotations

from src.data.wc2026 import BRACKET

STAGE_NAMES: dict[str, str] = {
    "R32": "1/16 финала",
    "R16": "1/8 финала",
    "QF": "Четвертьфинал",
    "SF": "Полуфинал",
    "THIRD": "Матч за 3-е место",
    "FINAL": "Финал",
}

# Порядок стадий от 1/16 до финала и привязка номера матча сетки к стадии.
STAGE_ORDER: list[str] = ["R32", "R16", "QF", "SF", "THIRD", "FINAL"]
STAGE_BY_NUM: dict[int, str] = {num: stage for stage, num, _h, _a in BRACKET}

# Слоты R32, куда попадают третьи места, и разрешённые группы для каждого
# (по сетке из docs/tournament-format.md).
THIRD_SLOT_ALLOWED: dict[int, frozenset[str]] = {
    74: frozenset("ABCDF"),
    77: frozenset("CDFGH"),
    79: frozenset("CEFHI"),
    80: frozenset("EHIJK"),
    81: frozenset("BEFIJ"),
    82: frozenset("AEHIJ"),
    85: frozenset("EFGIJ"),
    87: frozenset("DEIJL"),
}

# Фиксированный порядок слотов для детерминированного назначения.
THIRD_SLOTS: list[int] = sorted(THIRD_SLOT_ALLOWED)


def assign_thirds(qualified_groups: set[str]) -> dict[int, str]:
    """Сопоставить 8 групп-обладателей лучших третьих мест слотам R32.

    Возвращает {номер_матча_слота: буква_группы}. Каждый слот получает группу
    из своего разрешённого набора, все группы используются ровно один раз
    (поиск идеального паросочетания с возвратом).
    """
    if len(qualified_groups) != len(THIRD_SLOTS):
        raise ValueError(
            f"Ожидается {len(THIRD_SLOTS)} групп, получено {len(qualified_groups)}"
        )

    result: dict[int, str] = {}
    used: set[str] = set()

    def backtrack(i: int) -> bool:
        if i == len(THIRD_SLOTS):
            return True
        slot = THIRD_SLOTS[i]
        for group in sorted(THIRD_SLOT_ALLOWED[slot] & qualified_groups):
            if group not in used:
                used.add(group)
                result[slot] = group
                if backtrack(i + 1):
                    return True
                used.discard(group)
                del result[slot]
        return False

    if backtrack(0):
        return dict(result)

    # Фолбэк (теоретически недостижим при корректных наборах FIFA):
    # раскидать оставшиеся группы по слотам без учёта ограничений.
    leftover = sorted(qualified_groups)
    return {slot: leftover[i] for i, slot in enumerate(THIRD_SLOTS)}


def is_group_source(code: str) -> bool:
    """Код вида "1A"/"2B" (место в группе)."""
    return len(code) == 2 and code[0] in ("1", "2") and code[1].isalpha()


def is_third_source(code: str) -> bool:
    return code == "3?"


def is_winner_source(code: str) -> bool:
    return code.startswith("W")


def is_loser_source(code: str) -> bool:
    return code.startswith("L")


def source_match_number(code: str) -> int:
    """Номер матча из кода "W74"/"L101"."""
    return int(code[1:])
