"""Тесты авто-сводки плей-офф: засчёт прохода в раунд по всей сетке (не по слоту)."""

from __future__ import annotations

from types import SimpleNamespace

from src.services.playoff_actual import ActualMatch
from src.services.playoff_digest import (
    _completed_stages,
    _new_decided,
    _user_reach,
    build_playoff_update,
)


def _pred(home=None, away=None, winner=None):
    return SimpleNamespace(home_team_id=home, away_team_id=away, winner_team_id=winner)


# id: 1 Бразилия, 2 Япония, 3 Франция, 5 Канада
TMAP = {1: "Бразилия", 2: "Япония", 3: "Франция", 5: "Канада"}


def test_user_reach_counts_team_from_any_slot():
    # Канаду (5) игрок ведёт в R16 в матче 91 как гостя — слот не важен.
    preds = {91: _pred(home=2, away=5)}
    reach_r16 = _user_reach(preds, "R32")  # победитель R32 выходит в 1/8 (R16)
    assert 5 in reach_r16  # Канада засчитана, хотя в другом слоте


def test_user_reach_champion_from_final_winner():
    preds = {104: _pred(home=1, away=3, winner=1)}
    assert _user_reach(preds, "FINAL") == {1}  # чемпион = победитель матча 104


def test_build_update_credits_advance_from_any_slot():
    # Реально Канада (5) прошла в 1/8 из матча 73; игрок вёл её в 1/8 в другом слоте.
    actual = {73: ActualMatch(73, "R32", home_id=8, away_id=5, winner_id=5)}
    preds = {91: _pred(home=2, away=5)}  # Канада в его R16 (матч 91)
    text = build_playoff_update([73], actual, preds, TMAP, completed=set())
    assert "Канада → <b>1/8 финала</b> — ✅ угадал!" in text
    assert "Угадал проходов: <b>1/1</b>" in text


def test_build_update_not_guessed_when_team_absent_deeper():
    # Канада прошла в 1/8, но игрок не вёл её дальше группового этапа.
    actual = {73: ActualMatch(73, "R32", home_id=8, away_id=5, winner_id=5)}
    preds = {}  # в R16 у игрока Канады нет
    text = build_playoff_update([73], actual, preds, TMAP, completed=set())
    assert "❌ у тебя дальше не проходила" in text
    assert "Угадал проходов: <b>0/1</b>" in text


def _decided(num, stage, winner=1):
    return ActualMatch(num, stage, home_id=1, away_id=2, winner_id=winner)


def _undecided(num, stage):
    return ActualMatch(num, stage, home_id=1, away_id=2)


def test_new_decided_only_decided_matches():
    actual = {73: _decided(73, "R32"), 74: _undecided(74, "R32"), 89: _decided(89, "R16")}
    assert _new_decided(actual, undigested={73, 74, 89}) == [73, 89]


def test_completed_stage_partial_not_complete():
    actual = {73: _decided(73, "R32")}
    for n in range(74, 89):
        actual[n] = _undecided(n, "R32")
    assert _completed_stages(actual, {"R32"}) == set()
