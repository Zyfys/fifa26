"""Расчёт турнирной таблицы группы.

Чистая логика без БД — легко тестируется. Тай-брейки по регламенту ЧМ-2026
(см. docs/tournament-format.md), в доступном для прогноза объёме:
очки → разница мячей → забитые → личные встречи → имя (детерминированный фолбэк).
Дисциплина (fair-play) и рейтинг FIFA в прогнозе недоступны, поэтому опущены.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MatchResult:
    """Сыгранный матч с результатом."""

    home_id: int
    away_id: int
    home_score: int
    away_score: int


@dataclass
class StandingRow:
    """Строка таблицы для одной команды."""

    team_id: int
    team_name: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    gf: int = 0  # забито
    ga: int = 0  # пропущено

    @property
    def gd(self) -> int:
        return self.gf - self.ga

    @property
    def points(self) -> int:
        return self.won * 3 + self.drawn


# Сколько лучших третьих мест выходит в плей-офф (Round of 32).
THIRD_PLACES_QUALIFY = 8


def rank_third_places(
    thirds: list[tuple[str, StandingRow]],
) -> list[tuple[str, StandingRow]]:
    """Ранжировать команды, занявшие 3-и места (буква группы, строка таблицы).

    Критерии: очки → разница мячей → забитые → имя (детерминированный фолбэк).
    Личных встреч между ними нет (разные группы). Первые THIRD_PLACES_QUALIFY проходят.
    """
    return sorted(
        thirds,
        key=lambda t: (-t[1].points, -t[1].gd, -t[1].gf, t[1].team_name),
    )


def _apply(row: StandingRow, gf: int, ga: int) -> None:
    row.played += 1
    row.gf += gf
    row.ga += ga
    if gf > ga:
        row.won += 1
    elif gf < ga:
        row.lost += 1
    else:
        row.drawn += 1


def _build_rows(
    teams: list[tuple[int, str]], results: list[MatchResult]
) -> dict[int, StandingRow]:
    rows = {tid: StandingRow(team_id=tid, team_name=name) for tid, name in teams}
    for m in results:
        if m.home_id not in rows or m.away_id not in rows:
            continue
        _apply(rows[m.home_id], m.home_score, m.away_score)
        _apply(rows[m.away_id], m.away_score, m.home_score)
    return rows


def _head_to_head_key(team_id: int, tied_ids: set[int], results: list[MatchResult]):
    """Мини-таблица только по матчам между равными командами."""
    sub = [
        m
        for m in results
        if m.home_id in tied_ids and m.away_id in tied_ids
    ]
    row = StandingRow(team_id=team_id, team_name="")
    for m in sub:
        if m.home_id == team_id:
            _apply(row, m.home_score, m.away_score)
        elif m.away_id == team_id:
            _apply(row, m.away_score, m.home_score)
    return (row.points, row.gd, row.gf)


def compute_standings(
    teams: list[tuple[int, str]], results: list[MatchResult]
) -> list[StandingRow]:
    """Вернуть отсортированную таблицу группы (1-е место первым)."""
    rows = _build_rows(teams, results)
    ordered = sorted(
        rows.values(),
        key=lambda r: (-r.points, -r.gd, -r.gf, r.team_name),
    )

    # Разрешаем равенство (очки/разница/голы) личными встречами.
    result: list[StandingRow] = []
    i = 0
    while i < len(ordered):
        j = i + 1
        while (
            j < len(ordered)
            and (ordered[j].points, ordered[j].gd, ordered[j].gf)
            == (ordered[i].points, ordered[i].gd, ordered[i].gf)
        ):
            j += 1
        group = ordered[i:j]
        if len(group) > 1:
            tied_ids = {r.team_id for r in group}
            group.sort(
                key=lambda r: (
                    tuple(-x for x in _head_to_head_key(r.team_id, tied_ids, results)),
                    r.team_name,
                )
            )
        result.extend(group)
        i = j
    return result
