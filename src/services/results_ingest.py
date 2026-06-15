"""Оркестрация авто-получения результатов: football-data.org → маппинг названий →
сопоставление с расписанием бота.

Возвращает кандидатов (привязанные + непривязанные). Запись в БД — в auto_ingest.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.data.teams_en import ru_name
from src.db import repo
from src.services import football_api
from src.services.result_matching import (
    MatchedResult,
    ParsedResult,
    UnmatchedResult,
    match_results_to_fixtures,
)

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    matched: list[MatchedResult] = field(default_factory=list)
    unmatched: list[UnmatchedResult] = field(default_factory=list)
    note: str | None = None  # пояснение, если кандидатов нет


async def fetch_candidates(session: AsyncSession) -> IngestResult:
    if not settings.football_data_token:
        return IngestResult(note="нет FOOTBALL_DATA_TOKEN — используй ручной ввод")

    fixtures_all = await repo.list_group_fixtures(session)
    filled = await repo.get_actual_results(session)

    raw = await football_api.fetch_finished_results(token=settings.football_data_token)
    if not raw:
        return IngestResult(note="API не вернул сыгранных матчей — попробуй позже или вручную")

    # Английские названия источника → русские из расписания. Несопоставимые имена пропускаем.
    parsed: list[ParsedResult] = []
    unknown: set[str] = set()
    for home_en, away_en, hs, as_ in raw:
        rh, ra = ru_name(home_en), ru_name(away_en)
        if rh is None:
            unknown.add(home_en)
        if ra is None:
            unknown.add(away_en)
        if rh and ra:
            parsed.append(ParsedResult(rh, ra, hs, as_))
    if unknown:
        logger.info(
            "football-data: не сопоставлены названия (добавь в teams_en): %s",
            ", ".join(sorted(unknown)),
        )

    matched, unmatched = match_results_to_fixtures(parsed, fixtures_all)
    # Берём новые и изменившиеся (корректировки счёта от источника), пропускаем
    # уже совпадающие — чтобы не сбрасывать digested и не слать повторную сводку.
    matched = [
        m
        for m in matched
        if filled.get(m.match_number) != (m.home_score, m.away_score)
    ]
    if not matched and not unmatched:
        return IngestResult(note="нет новых сыгранных матчей из расписания бота")
    return IngestResult(matched=matched, unmatched=unmatched)


async def auto_ingest(session: AsyncSession) -> IngestResult:
    """Найти результаты и СРАЗУ записать распознанные (без подтверждения).

    Пишет только уверенно сопоставленные с расписанием (барьер result_matching);
    нераспознанное не пишет — остаётся в `unmatched` для ручного ввода/исправления.
    """
    ingest = await fetch_candidates(session)
    for m in ingest.matched:
        await repo.upsert_actual_result(
            session, m.match_number, m.home_score, m.away_score
        )
    if ingest.matched:
        await session.commit()
    return ingest
