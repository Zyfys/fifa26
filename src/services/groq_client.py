"""Клиент Groq (OpenAI-совместимый) — извлекает результаты матчей из текста в JSON.

Groq НЕ источник истины (он не знает счета) — он лишь структурирует текст из Tavily.
Имена команд просим брать строго из переданного списка фикстур, чтобы упростить
последующее сопоставление. При ошибке возвращает пустой список.
"""

from __future__ import annotations

import json
import logging

import aiohttp

from src.services.result_matching import ParsedResult

logger = logging.getLogger(__name__)

_URL = "https://api.groq.com/openai/v1/chat/completions"
_TIMEOUT = aiohttp.ClientTimeout(total=40)

_SYSTEM = (
    "Ты извлекаешь футбольные результаты из текста. Возвращай СТРОГО JSON-объект "
    '{"results": [{"home": str, "away": str, "home_score": int, "away_score": int}]}. '
    "Названия команд бери ТОЛЬКО из списка матчей, который дам. Включай матч только "
    "если в тексте явно есть его финальный счёт. Ничего не выдумывай: нет счёта — "
    "не включай. Без пояснений, только JSON."
)


def _build_user_prompt(text: str, fixtures: list[tuple[int, str, str]]) -> str:
    lines = [f"{home} — {away}" for _n, home, away in fixtures]
    return (
        "Список матчей (используй ровно эти названия команд):\n"
        + "\n".join(lines)
        + "\n\nТекст с результатами:\n"
        + text
    )


async def extract_results(
    text: str,
    fixtures: list[tuple[int, str, str]],
    *,
    api_key: str,
    model: str,
) -> list[ParsedResult]:
    if not text.strip() or not fixtures:
        return []
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _build_user_prompt(text, fixtures)},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.post(_URL, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                data = await resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except Exception:  # noqa: BLE001 — LLM-путь опционален, есть ручной ввод
        logger.exception("Groq extraction failed")
        return []

    return _coerce(parsed)


def _coerce(parsed: object) -> list[ParsedResult]:
    """Аккуратно достать список результатов из ответа модели."""
    items = parsed.get("results") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        return []
    out: list[ParsedResult] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            out.append(
                ParsedResult(
                    home=str(it["home"]).strip(),
                    away=str(it["away"]).strip(),
                    home_score=int(it["home_score"]),
                    away_score=int(it["away_score"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out
