"""Парсинг и валидация введённого пользователем счёта матча.

Единая логика для группового этапа и плей-офф — формат «2:1» / «4-4» и предел.
"""

from __future__ import annotations

import re

SCORE_RE = re.compile(r"^\s*(\d{1,2})\s*[:\-\s]\s*(\d{1,2})\s*$")
MAX_SCORE = 30

# Сообщения об ошибках ввода (на русском, с HTML-разметкой для подсказки формата).
SCORE_FORMAT_ERROR = "Не понял счёт. Введите в формате <code>2:1</code>."
SCORE_TOO_BIG_ERROR = "Слишком большой счёт, например <code>2:1</code>."


def parse_score(text: str | None) -> tuple[int, int] | None:
    """Разобрать счёт из текста.

    Возвращает кортеж (home, away) при корректном вводе либо None,
    если формат не распознан или счёт превышает MAX_SCORE.
    """
    m = SCORE_RE.match(text or "")
    if not m:
        return None
    home, away = int(m.group(1)), int(m.group(2))
    if home > MAX_SCORE or away > MAX_SCORE:
        return None
    return home, away


def score_error_message(text: str | None) -> str:
    """Подобрать сообщение об ошибке для невалидного ввода счёта."""
    if not SCORE_RE.match(text or ""):
        return SCORE_FORMAT_ERROR
    return SCORE_TOO_BIG_ERROR
