"""Сопоставление распознанных результатов с расписанием (чистая логика, без БД/сети).

Барьер против мусора из веба и галлюцинаций LLM: принимаем результат, только если
пара команд точно совпала с реальной фикстурой, а счёт валиден. Всё остальное —
в «не распознал» (для ручного ввода). Порядок команд в отчёте может быть любым:
если совпала обратная пара, счёт переворачиваем под расписание (хозяева/гости).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.services.scores import MAX_SCORE


@dataclass(frozen=True)
class ParsedResult:
    """Сырой результат, извлечённый из текста (имена — как пришли)."""

    home: str
    away: str
    home_score: int
    away_score: int


@dataclass(frozen=True)
class MatchedResult:
    """Результат, привязанный к матчу расписания (счёт уже под хозяев/гостей фикстуры)."""

    match_number: int
    home: str
    away: str
    home_score: int
    away_score: int


@dataclass(frozen=True)
class UnmatchedResult:
    parsed: ParsedResult
    reason: str


def _norm(name: str) -> str:
    return " ".join((name or "").split()).casefold()


def _valid_score(value: int) -> bool:
    return isinstance(value, int) and 0 <= value <= MAX_SCORE


def match_results_to_fixtures(
    parsed: list[ParsedResult],
    fixtures: list[tuple[int, str, str]],
) -> tuple[list[MatchedResult], list[UnmatchedResult]]:
    """Сопоставить распознанные результаты с расписанием `(match_number, home, away)`.

    Возвращает (привязанные, непривязанные). Привязанные — без дублей по match_number,
    отсортированы по номеру матча.
    """
    # (нормализованная пара хозяева,гости) -> (match_number, нужно ли менять счёт местами)
    lookup: dict[tuple[str, str], tuple[int, bool]] = {}
    for number, home, away in fixtures:
        lookup[(_norm(home), _norm(away))] = (number, False)
        lookup.setdefault((_norm(away), _norm(home)), (number, True))

    matched: dict[int, MatchedResult] = {}
    unmatched: list[UnmatchedResult] = []
    fixture_names = {num: (home, away) for num, home, away in fixtures}

    for pr in parsed:
        if not _valid_score(pr.home_score) or not _valid_score(pr.away_score):
            unmatched.append(UnmatchedResult(pr, "счёт вне диапазона"))
            continue
        key = (_norm(pr.home), _norm(pr.away))
        hit = lookup.get(key)
        if hit is None:
            unmatched.append(UnmatchedResult(pr, "пара не найдена в расписании"))
            continue
        number, swap = hit
        if number in matched:
            unmatched.append(UnmatchedResult(pr, "дубль"))
            continue
        home_name, away_name = fixture_names[number]
        hs, as_ = (pr.away_score, pr.home_score) if swap else (pr.home_score, pr.away_score)
        matched[number] = MatchedResult(
            match_number=number,
            home=home_name,
            away=away_name,
            home_score=hs,
            away_score=as_,
        )

    ordered = [matched[n] for n in sorted(matched)]
    return ordered, unmatched
