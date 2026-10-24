"""App settings, read from environment variables and the .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (the folder that holds pyproject.toml), so .env is found from any working directory
ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """All settings are optional for now; entry points call `require()` (CLAUDE.md section 13)."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # "KEY=" with no value means "not set", not ""
        extra="ignore",  # other variables in .env (e.g. Postgres ones) are not an error
    )

    # Secrets: SecretStr shows "**********" when printed
    telegram_bot_token: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    database_url: SecretStr | None = None
    redis_url: SecretStr | None = None

    # Not secret
    stt_model: str | None = None

    def require(self, *names: str) -> None:
        """Fail fast: stop if any of the named settings is not set.

        Example: get_settings().require("telegram_bot_token")
        """
        missing = [name.upper() for name in names if getattr(self, name) is None]
        if missing:
            raise RuntimeError(
                f"Missing setting(s) in .env: {', '.join(missing)}. See .env.example."
            )


@lru_cache
def get_settings() -> Settings:
    """Create the settings once, then return the same object on every call."""
    return Settings()
