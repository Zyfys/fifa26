"""Фактические результаты матчей (источник истины для расчёта точности прогнозов).

Заполняется только админом. Адресация по `match_number` — тому же числовому ключу,
что и расписание (`group_matches.match_number` 1..72; на будущее — плей-офф 73..104),
поэтому отдельно команды не дублируем: для групп они определяются через `group_matches`.
"""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Integer, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class ActualResult(Base):
    """Реальный счёт сыгранного матча."""

    __tablename__ = "actual_results"

    match_number: Mapped[int] = mapped_column(Integer, primary_key=True)  # 1..72 (v1)
    home_score: Mapped[int] = mapped_column(SmallInteger)
    away_score: Mapped[int] = mapped_column(SmallInteger)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
