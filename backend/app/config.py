"""Application configuration from environment."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://localhost:5432/parsley_db"

    # App
    app_env: str = "development"
    debug: bool = True

    # LLM
    openai_api_key: str = ""

    # Auth / JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_expiration_minutes: int = 1440  # 24 hours


settings = Settings()
