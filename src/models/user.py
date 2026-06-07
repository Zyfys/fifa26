"""Модель пользователя бота."""

from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class User(Base):
    """Пользователь Telegram, проходящий прогноз."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))

    # Текущий шаг прохождения (напр. "group:A", "bracket:R16", "awards", "tot", "done").
    progress: Mapped[str] = mapped_column(String(32), default="start")

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
