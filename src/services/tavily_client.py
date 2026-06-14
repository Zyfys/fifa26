"""Клиент Tavily (веб-поиск) — достаёт текст с результатами матчей за день.

Только сетевой вызов; извлечение структуры — в groq_client, сопоставление — в
result_matching. При любой ошибке возвращает пустую строку (источник недоступен).
"""

from __future__ import annotations

import datetime
import logging

import aiohttp

logger = logging.getLogger(__name__)

_URL = "https://api.tavily.com/search"
_TIMEOUT = aiohttp.ClientTimeout(total=30)


async def search_results(
    day: datetime.date, *, api_key: str, max_results: int = 6
) -> str:
    """Найти в вебе результаты матчей ЧМ-2026 за указанный день.

    Возвращает текст (синтез-ответ Tavily + сниппеты) для последующего извлечения.
    """
    query = (
        "результаты сыгранных матчей чемпионата мира по футболу 2026 "
        f"за {day:%d.%m.%Y}: команды и счёт"
    )
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "topic": "news",
        "days": 2,
        "max_results": max_results,
    }
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.post(_URL, json=payload) as resp:
                resp.raise_for_status()
                data = await resp.json()
    except Exception:  # noqa: BLE001 — источник опционален, не валим бота
        logger.exception("Tavily search failed")
        return ""

    parts: list[str] = []
    answer = data.get("answer")
    if answer:
        parts.append(str(answer))
    for item in data.get("results", []) or []:
        content = item.get("content")
        if content:
            parts.append(str(content))
    return "\n\n".join(parts)
