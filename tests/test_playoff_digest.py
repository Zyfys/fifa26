"""Тесты авто-сводки плей-офф: засчёт прохода в раунд по всей сетке (не по слоту)."""

from __future__ import annotations

from types import SimpleNamespace

from src.services.playoff_actual import ActualMatch
from src.services.playoff_digest import (
    _completed_stages,
    _new_decided,
    _user_depth_label,
    _user_pick_label,
    _user_reach,
    build_playoff_update,
)


def _pred(home=None, away=None, winner=None, hs=None, as_=None):
    return SimpleNamespace(
        home_team_id=home,
        away_team_id=away,
        winner_team_id=winner,
        home_score=hs,
        away_score=as_,
    )


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


def test_user_depth_label_shows_how_far_user_took_team():
    # Канаду (5) игрок довёл до финала (участник матча 104) — но не чемпион.
    assert _user_depth_label({104: _pred(home=5, away=1, winner=1)}, 5) == "ты вёл её до финала"
    # Чемпион.
    champ_preds = {104: _pred(home=5, away=1, winner=5)}
    assert _user_depth_label(champ_preds, 5) == "ты ставил её в чемпионы 🏆"
    # Нет в плей-офф прогноза.
    assert _user_depth_label({}, 5) == "у тебя она не выходила из группы"


def test_user_pick_label_decisive_score_no_winner_note():
    # Решающий счёт — победитель ясен из счёта, «→» не нужен.
    preds = {73: _pred(home=2, away=3, winner=2, hs=2, as_=1)}
    label = _user_pick_label(preds, 73, TMAP)
    assert "Ты ставил:" in label and "Япония" in label and "2:1" in label and "Франция" in label
    assert "→" not in label
    # Нет прогноза на матч.
    assert _user_pick_label({}, 73, TMAP) == "🎟 Ты не делал прогноз на этот матч"


def test_user_pick_label_draw_shows_who_advances():
    # Ничья — нужно показать, кого игрок пускал дальше (пенальти).
    preds = {73: _pred(home=2, away=3, winner=3, hs=1, as_=1)}
    label = _user_pick_label(preds, 73, TMAP)
    assert "1:1" in label and "→" in label and "Франция" in label


def test_build_update_pick_then_fact_then_verdict():
    # Реально Канада (5) прошла в 1/8 из матча 73; игрок вёл её в 1/8 в другом слоте.
    actual = {73: ActualMatch(73, "R32", home_id=8, away_id=5, winner_id=5)}
    preds = {73: _pred(home=2, away=3, winner=2, hs=1, as_=0), 91: _pred(home=2, away=5)}
    text = build_playoff_update([73], actual, preds, TMAP, completed=set())
    # Порядок: ставка -> факт -> вердикт.
    i_pick = text.index("Ты ставил:")
    i_fact = text.index("По факту:")
    i_verdict = text.index("✅ угадал!")
    assert i_pick < i_fact < i_verdict
    assert "Канада прошла в 1/8 финала" in text
    assert "ты вёл её до 1/8 финала" in text
    assert "Угадал проходов: <b>1/1</b>" in text


def test_build_update_not_guessed_shows_user_prediction():
    # Канада прошла в 1/8, но игрок не вёл её дальше группового этапа.
    actual = {73: ActualMatch(73, "R32", home_id=8, away_id=5, winner_id=5)}
    preds = {}  # в плей-офф у игрока Канады нет
    text = build_playoff_update([73], actual, preds, TMAP, completed=set())
    assert "❌ у тебя она не выходила из группы" in text
    assert "🎟 Ты не делал прогноз на этот матч" in text
    assert "По факту:" in text and "Канада прошла в 1/8 финала" in text
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
