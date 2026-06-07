"""Unit-тесты парсера и валидации введённого счёта (без БД)."""

from __future__ import annotations

import pytest

from src.services.scores import (
    MAX_SCORE,
    SCORE_FORMAT_ERROR,
    SCORE_TOO_BIG_ERROR,
    parse_score,
    score_error_message,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2:1", (2, 1)),
        ("4-4", (4, 4)),
        ("0:0", (0, 0)),
        ("3 2", (3, 2)),
        ("  10:0  ", (10, 0)),
        ("30:30", (30, 30)),  # граница включительно
    ],
)
def test_parse_score_valid(text: str, expected: tuple[int, int]):
    assert parse_score(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        None,
        "abc",
        "2",
        "2:",
        ":1",
        "1:2:3",
        "-1:2",
        "2.5:1",
        "💥",
    ],
)
def test_parse_score_invalid_format(text: str | None):
    assert parse_score(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "31:0",
        "0:31",
        f"{MAX_SCORE + 1}:1",
        "99:99",
    ],
)
def test_parse_score_too_big(text: str):
    assert parse_score(text) is None


def test_score_error_message_format():
    assert score_error_message("abc") == SCORE_FORMAT_ERROR
    assert score_error_message(None) == SCORE_FORMAT_ERROR


def test_score_error_message_too_big():
    # Формат верный, но превышен предел — другое сообщение.
    assert score_error_message("99:99") == SCORE_TOO_BIG_ERROR
    assert score_error_message(f"{MAX_SCORE + 1}:0") == SCORE_TOO_BIG_ERROR


def test_max_score_boundary():
    assert parse_score(f"{MAX_SCORE}:0") == (MAX_SCORE, 0)
    assert parse_score(f"{MAX_SCORE + 1}:0") is None
