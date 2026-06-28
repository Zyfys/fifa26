"""Тесты авто-сводки плей-офф: рендер по стадии и выбор готовых стадий."""

from __future__ import annotations

from types import SimpleNamespace

from src.services.playoff_actual import ActualMatch
from src.services.playoff_digest import _announceable_stages, build_stage_digest


def _pred(home, away, winner):
    return SimpleNamespace(home_team_id=home, away_team_id=away, winner_team_id=winner)


# id команд: 1 Бразилия, 2 Япония, 3 Франция, 4 Германия
TMAP = {1: "Бразилия", 2: "Япония", 3: "Франция", 4: "Германия"}


def test_build_stage_digest_correct_and_instead():
    # Реальная стадия из двух матчей.
    actual = {
        89: ActualMatch(89, "R16", home_id=1, away_id=2, winner_id=1,
                        loser_id=2, home_score=2, away_score=0),
        90: ActualMatch(90, "R16", home_id=3, away_id=4, winner_id=3,
                        loser_id=4, home_score=1, away_score=0),
    }
    preds = {
        89: _pred(1, 2, 1),  # пара угадана, прошедший угадан (Бразилия) ✅
        90: _pred(3, 4, 4),  # пара угадана, но ждал Германию — прошла Франция 🔄
    }
    text = build_stage_digest("R16", [89, 90], actual, preds, TMAP)

    assert "1/8 финала — сыграно" in text
    assert "Бразилия" in text  # угаданный прошедший
    assert "прошёл" in text and "Франция" in text and "ты ждал" in text
    assert "Угадал прошедших: <b>1/2</b>" in text
    assert "совпавших пар: <b>2/2</b>" in text  # обе пары совпали по составу


def test_build_stage_digest_none_guessed():
    actual = {
        89: ActualMatch(89, "R16", home_id=1, away_id=2, winner_id=1),
    }
    preds = {89: _pred(3, 4, 3)}  # совсем мимо: ни пара, ни прошедший
    text = build_stage_digest("R16", [89], actual, preds, TMAP)
    assert "ни одного" in text
    assert "Угадал прошедших: <b>0/1</b>" in text
    assert "совпавших пар: <b>0/1</b>" in text


def _decided(num, stage):
    return ActualMatch(num, stage, home_id=1, away_id=2, winner_id=1)


def _undecided(num, stage):
    return ActualMatch(num, stage, home_id=1, away_id=2)


def test_announceable_stage_fully_decided_and_new():
    # THIRD — одна игра 103, сыграна и не разослана.
    actual = {103: _decided(103, "THIRD")}
    assert _announceable_stages(actual, undigested={103}) == ["THIRD"]


def test_not_announceable_when_partial():
    # R32: 16 матчей, сыгран только один — стадия не готова.
    actual = {73: _decided(73, "R32")}
    for n in range(74, 89):
        actual[n] = _undecided(n, "R32")
    assert _announceable_stages(actual, undigested={73}) == []


def test_not_announceable_when_already_digested():
    actual = {104: _decided(104, "FINAL")}
    assert _announceable_stages(actual, undigested=set()) == []
