"""Тесты чистой логики сопоставления распознанных результатов с расписанием."""

from __future__ import annotations

from src.services.result_matching import ParsedResult, match_results_to_fixtures

FIXTURES = [
    (1, "Бразилия", "Сербия"),
    (2, "Аргентина", "Мексика"),
]


def test_exact_pair_matches():
    parsed = [ParsedResult("Бразилия", "Сербия", 2, 1)]
    matched, unmatched = match_results_to_fixtures(parsed, FIXTURES)
    assert unmatched == []
    assert len(matched) == 1
    m = matched[0]
    assert (m.match_number, m.home, m.away, m.home_score, m.away_score) == (
        1,
        "Бразилия",
        "Сербия",
        2,
        1,
    )


def test_reverse_pair_swaps_score():
    # В отчёте команды в обратном порядке — счёт должен лечь под расписание.
    parsed = [ParsedResult("Мексика", "Аргентина", 3, 1)]
    matched, unmatched = match_results_to_fixtures(parsed, FIXTURES)
    assert unmatched == []
    m = matched[0]
    # Фикстура: Аргентина (дома) — Мексика (в гостях); счёт переворачивается.
    assert (m.match_number, m.home, m.away, m.home_score, m.away_score) == (
        2,
        "Аргентина",
        "Мексика",
        1,
        3,
    )


def test_unknown_pair_unmatched():
    parsed = [ParsedResult("Гана", "Дания", 1, 0)]
    matched, unmatched = match_results_to_fixtures(parsed, FIXTURES)
    assert matched == []
    assert len(unmatched) == 1
    assert unmatched[0].reason == "пара не найдена в расписании"


def test_invalid_score_unmatched():
    parsed = [ParsedResult("Бразилия", "Сербия", 99, 0)]
    matched, unmatched = match_results_to_fixtures(parsed, FIXTURES)
    assert matched == []
    assert unmatched[0].reason == "счёт вне диапазона"


def test_duplicate_unmatched():
    parsed = [
        ParsedResult("Бразилия", "Сербия", 2, 1),
        ParsedResult("Сербия", "Бразилия", 0, 0),  # тот же матч, обратный порядок
    ]
    matched, unmatched = match_results_to_fixtures(parsed, FIXTURES)
    assert len(matched) == 1
    assert len(unmatched) == 1 and unmatched[0].reason == "дубль"


def test_case_and_whitespace_insensitive():
    parsed = [ParsedResult("  бразилия ", "СЕРБИЯ", 1, 0)]
    matched, _ = match_results_to_fixtures(parsed, FIXTURES)
    assert matched and matched[0].match_number == 1


def test_matched_sorted_by_match_number():
    parsed = [
        ParsedResult("Аргентина", "Мексика", 1, 1),
        ParsedResult("Бразилия", "Сербия", 2, 0),
    ]
    matched, _ = match_results_to_fixtures(parsed, FIXTURES)
    assert [m.match_number for m in matched] == [1, 2]
