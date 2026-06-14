"""Оркестрация автопоиска результатов: Tavily → Groq → сопоставление с расписанием.

Возвращает кандидатов (привязанные + непривязанные) для подтверждения админом.
Ничего не сохраняет в БД — запись делает только хэндлер после ✅ админа.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import repo
from src.services import groq_client, tavily_client
from src.services.result_matching import (
    MatchedResult,
    UnmatchedResult,
    match_results_to_fixtures,
)


@dataclass
class IngestResult:
    matched: list[MatchedResult] = field(default_factory=list)
    unmatched: list[UnmatchedResult] = field(default_factory=list)
    note: str | None = None  # пояснение, если кандидатов нет


async def fetch_candidates(
    session: AsyncSession, *, day: datetime.date | None = None
) -> IngestResult:
    if not (settings.groq_enabled and settings.tavily_enabled):
        return IngestResult(note="нет ключей Tavily/Groq — используй ручной ввод")

    day = day or datetime.date.today()
    fixtures_all = await repo.list_group_fixtures(session)
    filled = await repo.get_actual_results(session)
    unfilled = [(n, h, a) for (n, h, a) in fixtures_all if n not in filled]
    if not unfilled:
        return IngestResult(note="все групповые матчи уже внесены")

    text = await tavily_client.search_results(day, api_key=settings.tavily_api_key)
    if not text.strip():
        return IngestResult(note="Tavily ничего не вернул — попробуй позже или вручную")

    parsed = await groq_client.extract_results(
        text, unfilled, api_key=settings.groq_api_key, model=settings.groq_model
    )
    matched, unmatched = match_results_to_fixtures(parsed, fixtures_all)
    # Не перезаписываем уже подтверждённые результаты автоматически.
    matched = [m for m in matched if m.match_number not in filled]
    if not matched and not unmatched:
        return IngestResult(note="не нашёл сыгранных матчей из числа незаполненных")
    return IngestResult(matched=matched, unmatched=unmatched)
