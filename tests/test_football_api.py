"""Тесты разбора ответа football-data.org и маппинга названий команд."""

from __future__ import annotations

from src.data.teams_en import ru_name
from src.services.football_api import parse_finished, parse_matches


def test_ru_name_mapping():
    assert ru_name("Brazil") == "Бразилия"
    assert ru_name("United States") == "США"
    assert ru_name("USA") == "США"
    assert ru_name("Korea Republic") == "Южная Корея"
    assert ru_name("Türkiye") == "Турция"
    assert ru_name("Cape Verde Islands") == "Кабо-Верде"
    assert ru_name("  czech republic ") == "Чехия"  # регистр/пробелы не важны
    assert ru_name("Atlantis") is None


def test_parse_matches_takes_finished_with_score():
    data = {
        "matches": [
            {
                "homeTeam": {"name": "Brazil"},
                "awayTeam": {"name": "Morocco"},
                "score": {"fullTime": {"home": 2, "away": 1}},
            },
            # без счёта (не сыгран) — пропускается
            {
                "homeTeam": {"name": "Spain"},
                "awayTeam": {"name": "Uruguay"},
                "score": {"fullTime": {"home": None, "away": None}},
            },
        ]
    }
    assert parse_matches(data) == [("Brazil", "Morocco", 2, 1)]


def test_parse_matches_empty():
    assert parse_matches({}) == []


def test_parse_finished_winner_from_penalties():
    """Ничья в осн. время, но score.winner (серия пенальти) задаёт прошедшего."""
    data = {
        "matches": [
            {
                "homeTeam": {"name": "Spain"},
                "awayTeam": {"name": "Morocco"},
                "score": {"winner": "AWAY_TEAM", "fullTime": {"home": 1, "away": 1}},
            }
        ]
    }
    [m] = parse_finished(data)
    assert (m.home_en, m.away_en, m.home_score, m.away_score) == ("Spain", "Morocco", 1, 1)
    assert m.winner == "AWAY"  # прошло Марокко по пенальти


def test_parse_finished_winner_fallback_by_score():
    """Если score.winner не пришёл — победитель определяется по счёту."""
    data = {
        "matches": [
            {
                "homeTeam": {"name": "Brazil"},
                "awayTeam": {"name": "Japan"},
                "score": {"fullTime": {"home": 2, "away": 0}},
            }
        ]
    }
    [m] = parse_finished(data)
    assert m.winner == "HOME"


def test_parse_finished_group_draw_has_no_winner():
    data = {
        "matches": [
            {
                "homeTeam": {"name": "France"},
                "awayTeam": {"name": "England"},
                "score": {"winner": "DRAW", "fullTime": {"home": 1, "away": 1}},
            }
        ]
    }
    [m] = parse_finished(data)
    assert m.winner is None
