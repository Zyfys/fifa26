"""Тесты авто-сводки плей-офф: инкрементальный рендер и группировка новых матчей."""

from __future__ import annotations

from types import SimpleNamespace

from src.services.playoff_actual import ActualMatch
from src.services.playoff_digest import (
    _completed_stages,
    _new_by_stage,
    build_playoff_update,
)


def _pred(home, away, winner):
    return SimpleNamespace(home_team_id=home, away_team_id=away, winner_team_id=winner)


# id команд: 1 Бразилия, 2 Япония, 3 Франция, 4 Германия
TMAP = {1: "Бразилия", 2: "Япония", 3: "Франция", 4: "Германия"}


def test_build_update_guessed_and_instead():
    actual = {
        73: ActualMatch(73, "R32", home_id=1, away_id=2, winner_id=1),  # прошла Бразилия
        74: ActualMatch(74, "R32", home_id=3, away_id=4, winner_id=3),  # прошла Франция
    }
    preds = {
        73: _pred(1, 2, 1),  # угадал Бразилию ✅
        74: _pred(3, 4, 4),  # ждал Германию — прошла Франция 🔄
    }
    text = build_playoff_update({"R32": [73, 74]}, actual, preds, TMAP, completed=set())

    assert "обновление сетки" in text
    assert "Бразилия прошёл дальше — угадал!" in text
    assert "прошёл" in text and "Франция" in text and "ты ждал" in text and "Германия" in text
    assert "угадал прошедших: <b>1/2</b>" in text


def test_build_update_marks_completed_stage():
    actual = {103: ActualMatch(103, "THIRD", home_id=1, away_id=2, winner_id=2)}
    preds = {103: _pred(1, 2, 2)}
    text = build_playoff_update({"THIRD": [103]}, actual, preds, TMAP, completed={"THIRD"})
    assert "🏁" in text  # стадия сыграна полностью


def _decided(num, stage):
    return ActualMatch(num, stage, home_id=1, away_id=2, winner_id=1)


def _undecided(num, stage):
    return ActualMatch(num, stage, home_id=1, away_id=2)


def test_new_by_stage_groups_only_decided_new():
    actual = {
        73: _decided(73, "R32"),
        74: _undecided(74, "R32"),  # не сыгран — игнор
        89: _decided(89, "R16"),
    }
    # 74 в undigested не попадёт (он не decided); проверяем группировку 73 и 89.
    grouped = _new_by_stage(actual, undigested={73, 74, 89})
    assert grouped == {"R32": [73], "R16": [89]}


def test_completed_stages_partial_not_complete():
    # R32: только один матч сыгран — стадия не завершена.
    actual = {73: _decided(73, "R32")}
    for n in range(74, 89):
        actual[n] = _undecided(n, "R32")
    assert _completed_stages(actual, ["R32"]) == set()
