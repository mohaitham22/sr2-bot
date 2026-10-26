"""Tests for app/config.py. They use fake values only and never read the real .env."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings

ENV_NAMES = [
    "TELEGRAM_BOT_TOKEN",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "STT_MODEL",
    "VOICE_SAVE_USER_IDS",
]

FAKE_SECRETS = {
    "TELEGRAM_BOT_TOKEN": "fake-telegram-token",
    "GROQ_API_KEY": "fake-groq-key",
    "GEMINI_API_KEY": "fake-gemini-key",
    "DATABASE_URL": "postgresql://user:fake-db-password@localhost:5432/db",
    "REDIS_URL": "redis://:fake-redis-password@localhost:6379/0",
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove our variables from the environment, so every test starts empty, like CI."""
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_settings_load_without_env_file() -> None:
    settings = Settings(_env_file=None)  # _env_file=None: ignore the real .env

    assert all(value is None for value in settings.model_dump().values())


def test_secrets_hidden_when_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in FAKE_SECRETS.items():
        monkeypatch.setenv(name, value)
    settings = Settings(_env_file=None)

    printed = str(settings) + repr(settings)
    for value in FAKE_SECRETS.values():
        assert value not in printed
    assert settings.groq_api_key is not None
    assert settings.groq_api_key.get_secret_value() == "fake-groq-key"


def test_empty_value_means_not_set(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TELEGRAM_BOT_TOKEN=\nSTT_MODEL=\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.telegram_bot_token is None
    assert settings.stt_model is None


def test_require_names_the_missing_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-telegram-token")
    settings = Settings(_env_file=None)

    settings.require("telegram_bot_token")  # set, so no error

    with pytest.raises(RuntimeError, match="GROQ_API_KEY") as error:
        settings.require("telegram_bot_token", "groq_api_key")
    assert "TELEGRAM_BOT_TOKEN" not in str(error.value)


def test_voice_user_ids_are_a_json_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_SAVE_USER_IDS", "[111, 222]")  # fake IDs

    settings = Settings(_env_file=None)

    assert settings.voice_save_user_ids == frozenset({111, 222})


@pytest.mark.parametrize("value", ["111", "abc"])  # no brackets / not a number
def test_voice_user_ids_wrong_format_stops_at_startup(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("VOICE_SAVE_USER_IDS", value)

    with pytest.raises(ValidationError, match="voice_save_user_ids"):
        Settings(_env_file=None)
