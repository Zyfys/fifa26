"""Тесты разбора ответа football-data.org и маппинга названий команд."""

from __future__ import annotations

from src.data.teams_en import ru_name
from src.services.football_api import parse_matches


def test_ru_name_mapping():
    assert ru_name("Brazil") == "Бразилия"
    assert ru_name("United States") == "США"
    assert ru_name("USA") == "США"
    assert ru_name("Korea Republic") == "Южная Корея"
    assert ru_name("Türkiye") == "Турция"
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
