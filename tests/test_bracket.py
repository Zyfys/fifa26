"""Тесты логики сетки плей-офф (чистая логика)."""

from __future__ import annotations

import itertools

import pytest

from src.services.bracket import (
    THIRD_SLOT_ALLOWED,
    THIRD_SLOTS,
    assign_thirds,
    source_match_number,
)

ALL_GROUPS = list("ABCDEFGHIJKL")


def test_assign_thirds_valid_for_a_combination():
    qualified = set("ABCDEFGH")
    assignment = assign_thirds(qualified)
    # Все 8 слотов заполнены.
    assert set(assignment) == set(THIRD_SLOTS)
    # Каждой группе — ровно один слот, и все группы использованы.
    assert sorted(assignment.values()) == sorted(qualified)
    # Назначение уважает разрешённые группы слота.
    for slot, group in assignment.items():
        assert group in THIRD_SLOT_ALLOWED[slot]


def test_assign_thirds_perfect_matching_exists_for_all_combinations():
    # Для любой из C(12,8)=495 комбинаций должно находиться валидное назначение.
    count = 0
    for combo in itertools.combinations(ALL_GROUPS, 8):
        qualified = set(combo)
        assignment = assign_thirds(qualified)
        assert sorted(assignment.values()) == sorted(qualified), combo
        for slot, group in assignment.items():
            assert group in THIRD_SLOT_ALLOWED[slot], (combo, slot, group)
        count += 1
    assert count == 495


def test_assign_thirds_wrong_size_raises():
    with pytest.raises(ValueError):
        assign_thirds(set("ABC"))


def test_source_match_number():
    assert source_match_number("W74") == 74
    assert source_match_number("L101") == 101
