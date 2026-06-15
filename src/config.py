"""Конфигурация приложения через pydantic-settings (читает .env)."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки бота и БД. Значения берутся из переменных окружения / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    bot_token: str = Field(alias="BOT_TOKEN")

    # PostgreSQL
    database_url: str = Field(alias="DATABASE_URL")

    # App
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Telegram-ID администраторов (через запятую/пробел) — доступ к /stats, /results.
    admin_ids: str = Field(default="", alias="ADMIN_IDS")

    # Реальные результаты: football-data.org (надёжный структурированный источник, free tier).
    football_data_token: str = Field(default="", alias="FOOTBALL_DATA_TOKEN")
    # (устарело) Groq/Tavily — веб-поиск результатов оказался ненадёжным, не используется.
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    # Часы (0–23) в зоне schedule_tz: срез результатов и рассылка сводок.
    results_fetch_hour: int = Field(default=6, alias="RESULTS_FETCH_HOUR")
    digest_hour: int = Field(default=14, alias="DIGEST_HOUR")
    schedule_tz: str = Field(default="Europe/Berlin", alias="SCHEDULE_TZ")
    # Мастер-переключатель авто-режима (ночная авто-запись из веба + утренняя рассылка).
    # По умолчанию ВЫКЛ: веб-поиск результатов оказался ненадёжным. Ручной ввод /results
    # и команды /score, /top работают независимо от этого флага.
    results_auto: bool = Field(default=False, alias="RESULTS_AUTO")

    @property
    def admin_id_set(self) -> set[int]:
        """Множество admin telegram_id из строки ADMIN_IDS ("1,2 3")."""
        return {int(x) for x in self.admin_ids.replace(",", " ").split() if x.strip()}

    @property
    def autofetch_enabled(self) -> bool:
        """Авто-получение результатов доступно при наличии токена API и хотя бы одного админа."""
        return bool(self.football_data_token) and bool(self.admin_id_set)


settings = Settings()  # type: ignore[call-arg]
