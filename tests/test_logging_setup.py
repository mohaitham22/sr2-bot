"""Tests for app/logging_setup.py: secrets never reach the log line. Fake token only."""

import logging
import sys

from app.logging_setup import LOG_FORMAT, RedactingFormatter

FAKE_TOKEN = "123456789:FAKE-token-for-tests-only"


def make_record(msg: str, *args: object, exc_info=None) -> logging.LogRecord:
    """A log record like the one logger.error(msg, *args) would create."""
    return logging.LogRecord("test", logging.ERROR, __file__, 1, msg, args, exc_info)


def test_token_hidden_in_message() -> None:
    formatter = RedactingFormatter(LOG_FORMAT, secrets=[FAKE_TOKEN])
    record = make_record("url=https://api.telegram.org/bot%s/getUpdates", FAKE_TOKEN)

    line = formatter.format(record)

    assert FAKE_TOKEN not in line
    assert "bot***/getUpdates" in line


def test_token_hidden_in_traceback() -> None:
    formatter = RedactingFormatter(LOG_FORMAT, secrets=[FAKE_TOKEN])
    try:
        raise ValueError(f"bad url https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage")
    except ValueError:
        record = make_record("request failed", exc_info=sys.exc_info())

    line = formatter.format(record)

    assert "Traceback" in line
    assert FAKE_TOKEN not in line


def test_empty_secret_is_ignored() -> None:
    formatter = RedactingFormatter(LOG_FORMAT, secrets=[""])

    line = formatter.format(make_record("normal line"))

    assert line.endswith("normal line")
    assert "***" not in line
