"""Тесты справочных данных ЧМ-2026 и файлов игроков (без БД)."""

from __future__ import annotations

import datetime
import json

from src.data.players_loader import PLAYERS_DIR, VALID_POSITIONS
from src.data.wc2026 import BRACKET, FAVORITES, GROUPS, iter_group_matches, team_label


def test_groups_structure():
    assert len(GROUPS) == 12
    assert list(GROUPS) == list("ABCDEFGHIJKL")
    for teams in GROUPS.values():
        assert len(teams) == 4


def test_all_teams_unique_and_48():
    all_teams = [t for teams in GROUPS.values() for t in teams]
    assert len(all_teams) == 48
    assert len(set(all_teams)) == 48


def test_group_schedule_is_full_round_robin():
    matches = iter_group_matches()
    # 12 групп * 6 матчей = 72
    assert len(matches) == 72
    numbers = [m[1] for m in matches]
    assert numbers == list(range(1, 73))
    # В каждой группе по 6 уникальных пар.
    by_group: dict[str, set[tuple[int, int]]] = {}
    for letter, _, home, away in matches:
        by_group.setdefault(letter, set()).add((home, away))
    for letter, pairs in by_group.items():
        assert len(pairs) == 6, letter


def test_bracket_structure():
    assert len(BRACKET) == 32  # матчи 73..104
    numbers = sorted(m[1] for m in BRACKET)
    assert numbers == list(range(73, 105))
    stages = {m[1]: m[0] for m in BRACKET}
    assert sum(s == "R32" for s in stages.values()) == 16
    assert sum(s == "R16" for s in stages.values()) == 8
    assert sum(s == "QF" for s in stages.values()) == 4
    assert sum(s == "SF" for s in stages.values()) == 2
    assert stages[103] == "THIRD"
    assert stages[104] == "FINAL"


def test_bracket_sources_reference_existing_matches():
    valid_numbers = {m[1] for m in BRACKET}
    group_codes = {f"{pos}{letter}" for letter in GROUPS for pos in (1, 2, 3)}
    for _stage, _num, home, away in BRACKET:
        for src in (home, away):
            if src == "3?":
                continue
            if src[0] in ("W", "L"):
                assert int(src[1:]) in valid_numbers, src
            else:
                assert src in group_codes, src


def test_favorites_cover_all_teams():
    all_teams = {t for teams in GROUPS.values() for t in teams}
    # Каждая команда есть в рейтинге, и ранги уникальны 1..48.
    assert set(FAVORITES) == all_teams
    assert sorted(FAVORITES.values()) == list(range(1, 49))


def test_team_label_formats_rank():
    assert team_label("Испания") == "Испания (1)"
    assert team_label("Неизвестная") == "Неизвестная"


def test_player_files_valid():
    files = sorted(PLAYERS_DIR.glob("*.json"))
    assert files, "нет файлов игроков"
    known_teams = {t for teams in GROUPS.values() for t in teams}
    for path in files:
        team_name = path.stem
        assert team_name in known_teams, f"неизвестная команда: {team_name}"
        records = json.loads(path.read_text(encoding="utf-8"))
        assert 18 <= len(records) <= 26, f"{team_name}: {len(records)} игроков"
        positions = [r["position"] for r in records]
        assert set(positions) <= VALID_POSITIONS, team_name
        assert "GK" in positions, f"{team_name}: нет вратаря"
        for r in records:
            assert r["name"].strip(), team_name
            if r.get("birth_date"):
                datetime.date.fromisoformat(r["birth_date"])  # не должно бросать
