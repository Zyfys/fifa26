"""Тесты сервиса расчёта таблиц групп (чистая логика, без БД)."""

from __future__ import annotations

from src.services.standings import (
    MatchResult,
    StandingRow,
    compute_standings,
    rank_third_places,
)

# Команды одной группы (id, name).
TEAMS = [(1, "Алжир"), (2, "Бразилия"), (3, "Гана"), (4, "Дания")]


def _names(rows: list[StandingRow]) -> list[str]:
    return [r.team_name for r in rows]


def test_points_and_basic_stats():
    # 1 побеждает 2 (2:0), 3 и 4 играют вничью (1:1).
    results = [
        MatchResult(1, 2, 2, 0),
        MatchResult(3, 4, 1, 1),
    ]
    rows = compute_standings(TEAMS, results)
    by_id = {r.team_id: r for r in rows}
    assert by_id[1].points == 3
    assert by_id[1].won == 1 and by_id[1].gf == 2 and by_id[1].ga == 0 and by_id[1].gd == 2
    assert by_id[2].points == 0 and by_id[2].lost == 1
    assert by_id[3].points == 1 and by_id[3].drawn == 1
    assert by_id[4].points == 1


def test_full_round_robin_ordering_by_points():
    # Команда 1 выигрывает всё, 4 проигрывает всё.
    results = [
        MatchResult(1, 2, 1, 0),
        MatchResult(1, 3, 1, 0),
        MatchResult(1, 4, 1, 0),
        MatchResult(2, 3, 1, 0),
        MatchResult(2, 4, 1, 0),
        MatchResult(3, 4, 1, 0),
    ]
    rows = compute_standings(TEAMS, results)
    assert [r.team_id for r in rows] == [1, 2, 3, 4]
    assert rows[0].points == 9
    assert rows[3].points == 0


def test_goal_difference_breaks_tie():
    # 1 и 2 по 3 очка, но у 2 лучше разница мячей.
    results = [
        MatchResult(1, 3, 1, 0),  # 1: +1
        MatchResult(2, 4, 5, 0),  # 2: +5
        MatchResult(1, 2, 0, 0),  # ничья между ними
        MatchResult(3, 4, 0, 0),
    ]
    rows = compute_standings(TEAMS, results)
    # У 1 и 2 по 4 очка (победа+ничья), у 2 разница лучше → 2 первый.
    assert rows[0].team_id == 2
    assert rows[1].team_id == 1


def test_head_to_head_breaks_equal_points_and_gd():
    # Две команды с равными очками/разницей/голами — решает личная встреча.
    teams = [(1, "А"), (2, "Б")]
    results = [
        MatchResult(1, 2, 2, 1),  # очная встреча: 1 побеждает
    ]
    rows = compute_standings(teams, results)
    assert rows[0].team_id == 1


def test_deterministic_alphabetical_fallback():
    # Полностью идентичные показатели (нет матчей) → сортировка по имени.
    rows = compute_standings(TEAMS, [])
    assert _names(rows) == ["Алжир", "Бразилия", "Гана", "Дания"]


def test_rank_third_places_orders_by_points_then_gd():
    thirds = [
        ("A", StandingRow(1, "A3", played=3, won=1, gf=2, ga=2)),  # 3 очка, РМ 0
        ("B", StandingRow(2, "B3", played=3, won=2, gf=5, ga=1)),  # 6 очков
        ("C", StandingRow(3, "C3", played=3, won=1, gf=4, ga=1)),  # 3 очка, РМ +3
    ]
    ranked = rank_third_places(thirds)
    assert [letter for letter, _ in ranked] == ["B", "C", "A"]
