"""App settings, read from environment variables and the .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import PositiveFloat, PositiveInt, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (the folder that holds pyproject.toml), so .env is found from any working directory
ROOT_DIR = Path(__file__).resolve().parents[1]

# The LLM providers app/services/llm.py can use (Step 2.4). Azure OpenAI comes later (stretch S12)
LLMProvider = Literal["groq", "gemini"]


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
    # Folder for the downloaded Whisper models (several GB; Step 1.6 D5 A). Not set: Hugging Face's
    # default cache on C:. A relative path starts at ROOT_DIR, not at the current folder.
    stt_model_dir: Path | None = None
    # Telegram user IDs whose voice notes the bot saves for testing (D2 A). A JSON list in .env,
    # e.g. [123456789]. Not set: nobody's voice notes are saved. Real IDs never go in the repo.
    voice_save_user_ids: frozenset[int] | None = None

    # Session memory in Redis (Step 2.3). These two have defaults; .env can change them.
    # PositiveInt: a whole number > 0, so "0", "-5" or "abc" in .env stops the app at startup.
    # Seconds without a new message before the session and its history are deleted. Every new
    # message starts the timer again (sliding expiry, D4 A). 1800 = the brief's "30 minutes idle".
    session_ttl_seconds: PositiveInt = 1800
    # How many recent messages the history keeps; one message (user or bot) = one turn (D3 A).
    # 10 is a placeholder until the token budget is set (section 14). Older ones: debt T12.
    history_max_messages: PositiveInt = 10

    # LLM client (Step 2.4). Switching provider = LLM_PROVIDER + LLM_MODEL; the key is the
    # provider's own *_API_KEY above. LLM_BASE_URL only replaces the provider's usual address.
    llm_provider: LLMProvider = "groq"
    llm_model: str | None = None
    llm_base_url: str | None = None
    # Per try vs all tries together, waits included (Momo's change 1): a user never waits longer
    # than the total. PositiveFloat: a number > 0, so "0" or "abc" stops the app at startup.
    llm_timeout_seconds: PositiveFloat = 10.0
    llm_total_timeout_seconds: PositiveFloat = 20.0
    # One JSON line per LLM call, numbers only, for Phase 4 (D5 B). Not set: no file is written.
    llm_usage_file: Path | None = None

    @field_validator("stt_model_dir", "llm_usage_file")
    @classmethod
    def _start_at_root(cls, value: Path | None) -> Path | None:
        """Make a relative path start at the project root, so it is the same folder everywhere."""
        if value is None or value.is_absolute():
            return value
        return ROOT_DIR / value

    @model_validator(mode="after")
    def _total_covers_one_try(self) -> Self:
        """The total time must allow at least one whole try, or the per-try value means nothing."""
        if self.llm_total_timeout_seconds < self.llm_timeout_seconds:
            raise ValueError(
                "LLM_TOTAL_TIMEOUT_SECONDS must be at least LLM_TIMEOUT_SECONDS "
                f"({self.llm_total_timeout_seconds} < {self.llm_timeout_seconds})"
            )
        return self

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
