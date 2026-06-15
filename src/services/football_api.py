"""Клиент football-data.org — реальные результаты матчей ЧМ (competition WC).

Free tier: 10 запросов/мин, авторизация заголовком X-Auth-Token. Возвращает
сыгранные матчи со счётом; названия команд — английские (маппинг в data/teams_en).
HTTP отделён от разбора (parse_matches) для тестируемости.
"""

from __future__ import annotations

import logging

import aiohttp

logger = logging.getLogger(__name__)

_URL = "https://api.football-data.org/v4/competitions/WC/matches?status=FINISHED"
_TIMEOUT = aiohttp.ClientTimeout(total=30)


def parse_matches(data: dict) -> list[tuple[str, str, int, int]]:
    """Из ответа API → список (home_en, away_en, home_score, away_score) сыгранных матчей."""
    out: list[tuple[str, str, int, int]] = []
    for m in data.get("matches", []) or []:
        full = (m.get("score") or {}).get("fullTime") or {}
        home_score, away_score = full.get("home"), full.get("away")
        home = (m.get("homeTeam") or {}).get("name")
        away = (m.get("awayTeam") or {}).get("name")
        if home_score is None or away_score is None or not home or not away:
            continue
        out.append((home, away, int(home_score), int(away_score)))
    return out


async def fetch_finished_results(*, token: str) -> list[tuple[str, str, int, int]]:
    """Сыгранные матчи ЧМ с реальным счётом. При ошибке — пустой список."""
    headers = {"X-Auth-Token": token}
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(_URL, headers=headers) as resp:
                resp.raise_for_status()
                data = await resp.json()
    except Exception:  # noqa: BLE001 — источник опционален, не валим бота
        logger.exception("football-data.org request failed")
        return []
    return parse_matches(data)
