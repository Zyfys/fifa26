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

    # Реальные результаты матчей: Groq (извлечение), Tavily (веб-поиск).
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    # Час суток (0–23) для дневного автопоиска результатов; пусто — берётся 23.
    results_fetch_hour: int = Field(default=23, alias="RESULTS_FETCH_HOUR")

    @property
    def admin_id_set(self) -> set[int]:
        """Множество admin telegram_id из строки ADMIN_IDS ("1,2 3")."""
        return {int(x) for x in self.admin_ids.replace(",", " ").split() if x.strip()}

    @property
    def groq_enabled(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def tavily_enabled(self) -> bool:
        return bool(self.tavily_api_key)

    @property
    def autofetch_enabled(self) -> bool:
        """Автопоиск результатов доступен только если есть оба ключа и хоть один админ."""
        return self.groq_enabled and self.tavily_enabled and bool(self.admin_id_set)


settings = Settings()  # type: ignore[call-arg]
