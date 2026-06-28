"""Клиент football-data.org — реальные результаты матчей ЧМ (competition WC).

Free tier: 10 запросов/мин, авторизация заголовком X-Auth-Token. Возвращает
сыгранные матчи со счётом; названия команд — английские (маппинг в data/teams_en).
HTTP отделён от разбора (parse_matches) для тестируемости.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import aiohttp

logger = logging.getLogger(__name__)

_URL = "https://api.football-data.org/v4/competitions/WC/matches?status=FINISHED"
_TIMEOUT = aiohttp.ClientTimeout(total=30)


@dataclass(frozen=True)
class FinishedMatch:
    """Сыгранный матч из API с победителем (учитывает пенальти для плей-офф)."""

    home_en: str
    away_en: str
    home_score: int
    away_score: int
    # "HOME" / "AWAY" / None. Берётся из score.winner (учитывает серию пенальти),
    # с фолбэком на счёт. None — для ничьей группового этапа.
    winner: str | None


def _winner_side(score: dict, home_score: int, away_score: int) -> str | None:
    """Сторона-победитель: приоритет score.winner (учёт пенальти), иначе по счёту."""
    raw = score.get("winner")
    if raw == "HOME_TEAM":
        return "HOME"
    if raw == "AWAY_TEAM":
        return "AWAY"
    # Фолбэк (winner не пришёл): по основному счёту; ничья → None.
    if home_score > away_score:
        return "HOME"
    if away_score > home_score:
        return "AWAY"
    return None


def parse_finished(data: dict) -> list[FinishedMatch]:
    """Из ответа API → список FinishedMatch (со счётом и победителем)."""
    out: list[FinishedMatch] = []
    for m in data.get("matches", []) or []:
        score = m.get("score") or {}
        full = score.get("fullTime") or {}
        home_score, away_score = full.get("home"), full.get("away")
        home = (m.get("homeTeam") or {}).get("name")
        away = (m.get("awayTeam") or {}).get("name")
        if home_score is None or away_score is None or not home or not away:
            continue
        hs, as_ = int(home_score), int(away_score)
        out.append(FinishedMatch(home, away, hs, as_, _winner_side(score, hs, as_)))
    return out


def parse_matches(data: dict) -> list[tuple[str, str, int, int]]:
    """Из ответа API → список (home_en, away_en, home_score, away_score) сыгранных матчей."""
    return [(m.home_en, m.away_en, m.home_score, m.away_score) for m in parse_finished(data)]


async def _fetch_raw(*, token: str) -> dict | None:
    """Сырой JSON сыгранных матчей ЧМ. При ошибке — None."""
    headers = {"X-Auth-Token": token}
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(_URL, headers=headers) as resp:
                resp.raise_for_status()
                return await resp.json()
    except Exception:  # noqa: BLE001 — источник опционален, не валим бота
        logger.exception("football-data.org request failed")
        return None


async def fetch_finished_results(*, token: str) -> list[tuple[str, str, int, int]]:
    """Сыгранные матчи ЧМ с реальным счётом. При ошибке — пустой список."""
    data = await _fetch_raw(token=token)
    return parse_matches(data) if data else []


async def fetch_finished_detailed(*, token: str) -> list[FinishedMatch]:
    """Сыгранные матчи ЧМ со счётом и победителем. При ошибке — пустой список."""
    data = await _fetch_raw(token=token)
    return parse_finished(data) if data else []
