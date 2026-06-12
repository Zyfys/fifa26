"""Тесты тай-брейков FIFA: рекурсивные личные встречи и ранжирование третьих мест."""

from __future__ import annotations

from src.services.standings import (
    THIRD_PLACES_QUALIFY,
    MatchResult,
    StandingRow,
    compute_standings,
    rank_third_places,
)


def _names(rows: list[StandingRow]) -> list[str]:
    return [r.team_name for r in rows]


def test_recursive_h2h_reapplies_to_remaining_subgroup():
    """Контрпример из регламента: цикл трёх + аутсайдер.

    Алжир 2:1 Япония, Япония 1:0 Аргентина, Аргентина 2:1 Алжир,
    Дания проигрывает всем. Все три лидера равны по общим показателям
    (6 очков, +1, 4 забитых). Мини-таблица трёх отделяет Алжир (3 забитых
    против 2), а Япония и Аргентина в ней равны. По FIFA критерии заново
    применяются к подгруппе {Япония, Аргентина}: личная встреча 1:0 ставит
    Японию выше — против алфавитного порядка.
    """
    teams = [(1, "Алжир"), (2, "Япония"), (3, "Аргентина"), (4, "Дания")]
    results = [
        MatchResult(1, 2, 2, 1),  # Алжир — Япония
        MatchResult(2, 3, 1, 0),  # Япония — Аргентина
        MatchResult(3, 1, 2, 1),  # Аргентина — Алжир
        MatchResult(1, 4, 1, 0),
        MatchResult(2, 4, 2, 1),
        MatchResult(3, 4, 2, 1),
    ]
    rows = compute_standings(teams, results)
    # Общие показатели трёх лидеров действительно равны.
    for r in rows[:3]:
        assert (r.points, r.gd, r.gf) == (6, 1, 4)
    assert _names(rows) == ["Алжир", "Япония", "Аргентина", "Дания"]


def test_circular_h2h_falls_back_to_name():
    """Идеальный цикл: личные встречи ничего не решают → фолбэк по имени."""
    teams = [(1, "Гана"), (2, "Бразилия"), (3, "Алжир"), (4, "Дания")]
    results = [
        MatchResult(1, 2, 1, 0),  # Гана — Бразилия
        MatchResult(2, 3, 1, 0),  # Бразилия — Алжир
        MatchResult(3, 1, 1, 0),  # Алжир — Гана
        MatchResult(1, 4, 1, 0),
        MatchResult(2, 4, 1, 0),
        MatchResult(3, 4, 1, 0),
    ]
    rows = compute_standings(teams, results)
    # Лидеры равны и в общей, и в мини-таблице → алфавитный порядок.
    for r in rows[:3]:
        assert (r.points, r.gd, r.gf) == (6, 1, 2)
    assert _names(rows) == ["Алжир", "Бразилия", "Гана", "Дания"]


def test_rank_third_places_boundary_8_vs_9_by_name():
    """12 третьих мест: 8-е и 9-е равны по показателям, проходит первый по имени."""

    def row(team_id: int, name: str, won: int, drawn: int, gf: int, ga: int) -> StandingRow:
        return StandingRow(
            team_id=team_id, team_name=name, played=3, won=won, drawn=drawn, gf=gf, ga=ga
        )

    thirds = [
        # 7 заведомо более сильных третьих мест (убывающие очки/показатели).
        ("A", row(1, "A3", won=2, drawn=1, gf=6, ga=1)),  # 7 очков
        ("B", row(2, "B3", won=2, drawn=0, gf=5, ga=1)),  # 6 очков, +4
        ("C", row(3, "C3", won=2, drawn=0, gf=4, ga=1)),  # 6 очков, +3
        ("D", row(4, "D3", won=1, drawn=2, gf=4, ga=1)),  # 5 очков
        ("E", row(5, "E3", won=1, drawn=1, gf=4, ga=2)),  # 4 очка, +2
        ("F", row(6, "F3", won=1, drawn=1, gf=3, ga=2)),  # 4 очка, +1
        ("G", row(7, "G3", won=1, drawn=0, gf=3, ga=1)),  # 3 очка, +2
        # Граница 8/9: одинаковые очки (3), разница (0) и забитые (2),
        # порядок решает имя команды: «Гана» < «Дания».
        ("H", row(8, "Дания", won=1, drawn=0, gf=2, ga=2)),
        ("I", row(9, "Гана", won=1, drawn=0, gf=2, ga=2)),
        # 3 заведомо более слабых.
        ("J", row(10, "J3", won=0, drawn=2, gf=1, ga=2)),  # 2 очка
        ("K", row(11, "K3", won=0, drawn=1, gf=1, ga=3)),  # 1 очко
        ("L", row(12, "L3", won=0, drawn=0, gf=0, ga=5)),  # 0 очков
    ]
    ranked = rank_third_places(thirds)
    assert len(ranked) == 12
    qualified = ranked[:THIRD_PLACES_QUALIFY]
    eliminated = ranked[THIRD_PLACES_QUALIFY:]
    # Гана (группа I) занимает 8-е место и проходит, Дания (группа H) — нет.
    assert qualified[-1][1].team_name == "Гана"
    assert qualified[-1][0] == "I"
    assert eliminated[0][1].team_name == "Дания"
    assert eliminated[0][0] == "H"
