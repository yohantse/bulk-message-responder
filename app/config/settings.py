from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/telegram_platform"
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_settings(self) -> Self:
        if self.app_env.lower() == "production":
            if not self.telegram_bot_token or not self.telegram_bot_token.strip():
                raise ValueError("TELEGRAM_BOT_TOKEN must be configured in production")
            if not self.telegram_webhook_secret or not self.telegram_webhook_secret.strip():
                raise ValueError("TELEGRAM_WEBHOOK_SECRET must be configured in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
