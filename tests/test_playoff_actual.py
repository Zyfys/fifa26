"""Тесты сопоставления сыгранных матчей плей-офф из API (чистая логика).

Ключ — по стадии + каждой команде отдельно: фактический матч находится по одному
достоверно известному участнику, даже если соперник в слоте «3?» был предсказан неверно.
"""

from __future__ import annotations

from src.services.football_api import FinishedMatch
from src.services.playoff_actual import _index_api_by_team_stage


def test_index_maps_winner_by_each_team():
    name_to_id = {"Бразилия": 1, "Япония": 2}
    api = [FinishedMatch("Brazil", "Japan", 2, 0, "HOME", "LAST_32")]
    idx = _index_api_by_team_stage(api, name_to_id)
    assert idx[("LAST_32", 1)] == {"opp": 2, "my": 2, "opp_score": 0, "winner": 1}
    assert idx[("LAST_32", 2)] == {"opp": 1, "my": 0, "opp_score": 2, "winner": 1}


def test_index_penalty_away_winner():
    name_to_id = {"Испания": 5, "Марокко": 7}
    api = [FinishedMatch("Spain", "Morocco", 1, 1, "AWAY", "LAST_32")]
    idx = _index_api_by_team_stage(api, name_to_id)
    assert idx[("LAST_32", 5)]["winner"] == 7  # прошло Марокко
    assert idx[("LAST_32", 7)]["winner"] == 7


def test_index_skips_group_stage():
    name_to_id = {"Бразилия": 1, "Япония": 2}
    api = [FinishedMatch("Brazil", "Japan", 2, 0, "HOME", "GROUP_STAGE")]
    assert _index_api_by_team_stage(api, name_to_id) == {}


def test_index_skips_unmappable_names():
    name_to_id = {"Бразилия": 1}
    api = [FinishedMatch("Atlantis", "Brazil", 3, 0, "HOME", "LAST_32")]  # Atlantis не маппится
    assert _index_api_by_team_stage(api, name_to_id) == {}
