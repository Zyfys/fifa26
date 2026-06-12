"""Async-движок и фабрика сессий SQLAlchemy."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

# Явные лимиты пула — Postgres на VPS общий с другим проектом, бот не должен
# выедать max_connections (итого до pool_size + max_overflow соединений).
_pool_kwargs: dict[str, Any] = (
    {"pool_size": 5, "max_overflow": 5, "pool_timeout": 30}
    if settings.database_url.startswith("postgresql")
    else {}
)

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True, **_pool_kwargs)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
