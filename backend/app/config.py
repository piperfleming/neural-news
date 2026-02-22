"""Application configuration from environment."""
from pathlib import Path
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    _ENV_PATH = Path(__file__).resolve().parent.parent / ".env"  # backend/.env

    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://localhost:5432/parsley_db"

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, v: str) -> str:
        # Common pitfall: copying .env.example but not replacing placeholders.
        if "USER:PASSWORD@HOST" in v or "HOST:5432/DATABASE_NAME" in v:
            raise ValueError(
                "DATABASE_URL still contains placeholders. "
                "Edit backend/.env and replace USER/PASSWORD/HOST/DATABASE_NAME with a real Postgres connection string."
            )
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must start with 'postgresql+asyncpg://'. "
                "If you copied a connection string that starts with 'postgresql://', change the scheme to 'postgresql+asyncpg://'."
            )

        parsed = urlparse(v)
        if not parsed.hostname:
            raise ValueError("DATABASE_URL is missing a hostname.")
        if parsed.hostname.upper() == "HOST":
            raise ValueError(
                "DATABASE_URL hostname is still the placeholder 'HOST'. "
                "Edit backend/.env and replace it with your real database host (e.g. localhost or a Neon host)."
            )
        return v

    # App
    app_env: str = "development"
    debug: bool = True

    # LLM
    openai_api_key: str = ""

    # Auth / JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_expiration_minutes: int = 1440  # 24 hours

    # Admin access
    admin_emails: str = ""


settings = Settings()
