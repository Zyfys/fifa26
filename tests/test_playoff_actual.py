"""Тесты сопоставления сыгранных матчей из API к парам сетки (чистая логика)."""

from __future__ import annotations

from src.services.football_api import FinishedMatch
from src.services.playoff_actual import _index_api_by_pair


def test_index_api_by_pair_maps_winner():
    name_to_id = {"Бразилия": 1, "Япония": 2}
    api = [FinishedMatch("Brazil", "Japan", 2, 0, "HOME")]
    idx = _index_api_by_pair(api, name_to_id)
    rec = idx[frozenset((1, 2))]
    assert rec["winner"] == 1
    assert rec["score"] == {1: 2, 2: 0}


def test_index_api_by_pair_penalty_away_winner():
    name_to_id = {"Испания": 5, "Марокко": 7}
    api = [FinishedMatch("Spain", "Morocco", 1, 1, "AWAY")]
    idx = _index_api_by_pair(api, name_to_id)
    assert idx[frozenset((5, 7))]["winner"] == 7  # прошло Марокко


def test_index_api_by_pair_skips_unmappable_names():
    name_to_id = {"Бразилия": 1}
    api = [FinishedMatch("Atlantis", "Brazil", 3, 0, "HOME")]  # Atlantis не маппится
    assert _index_api_by_pair(api, name_to_id) == {}
