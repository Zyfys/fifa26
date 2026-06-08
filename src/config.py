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

    # Telegram-ID администраторов (через запятую/пробел) — доступ к /stats.
    admin_ids: str = Field(default="", alias="ADMIN_IDS")

    @property
    def admin_id_set(self) -> set[int]:
        """Множество admin telegram_id из строки ADMIN_IDS ("1,2 3")."""
        return {int(x) for x in self.admin_ids.replace(",", " ").split() if x.strip()}


settings = Settings()  # type: ignore[call-arg]
