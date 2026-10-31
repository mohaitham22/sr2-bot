"""Tests for app/logging_setup.py: secrets never reach the log line. Fake token only."""

import logging
import sys

import pytest

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


FAKE_NAME = "Fake Resident"
FAKE_PHONE = "0100000000"
# What asyncpg's error text looks like when a CHECK rule refuses a row
REFUSED_ROW = (
    'new row for relation "users" violates check constraint "ck_users_phone_e164"\n'
    f"DETAIL:  Failing row contains (7, 123, {FAKE_NAME}, {FAKE_PHONE}, 2026-10-31 12:00:00+00)."
)


def test_postgres_detail_hidden_in_message() -> None:
    formatter = RedactingFormatter(LOG_FORMAT, secrets=[])

    line = formatter.format(make_record("saving the user failed: %s", REFUSED_ROW))

    assert FAKE_NAME not in line
    assert FAKE_PHONE not in line
    assert "DETAIL: [hidden: may contain personal data]" in line
    assert "ck_users_phone_e164" in line  # the rule's name stays: enough to debug


def test_postgres_detail_hidden_in_chained_traceback() -> None:
    """The DETAIL hides in the CAUSE of the error; a traceback prints every link of the chain."""

    class FakeDriverError(Exception):
        pass

    formatter = RedactingFormatter(LOG_FORMAT, secrets=[])
    try:
        try:
            raise FakeDriverError(REFUSED_ROW)
        except FakeDriverError as cause:
            raise RuntimeError("insert failed") from cause
    except RuntimeError:
        record = make_record("saving the user failed", exc_info=sys.exc_info())

    line = formatter.format(record)

    assert "direct cause" in line  # the chain is printed ...
    assert FAKE_NAME not in line  # ... but not the row
    assert FAKE_PHONE not in line


@pytest.mark.parametrize(
    "error_text",
    [
        # asyncpg's text for a value of the wrong type: one row, and many rows at once
        f"invalid input for query argument $3: '{FAKE_PHONE}' (expected str, got int)",
        (  # one string in two parts (parentheses: not a missing comma)
            f"invalid input for query argument $2 in element #0 of executemany() sequence: "
            f"'{FAKE_NAME}' ('str' object cannot be interpreted as an integer)"
        ),
    ],
)
def test_wrong_type_value_hidden(error_text: str) -> None:
    formatter = RedactingFormatter(LOG_FORMAT, secrets=[])

    line = formatter.format(make_record("saving failed: %s", error_text))

    assert FAKE_NAME not in line
    assert FAKE_PHONE not in line
    assert "query argument $" in line  # which argument it was stays: enough to debug
    assert "[hidden: may contain personal data]" in line


def test_empty_secret_is_ignored() -> None:
    formatter = RedactingFormatter(LOG_FORMAT, secrets=[""])

    line = formatter.format(make_record("normal line"))

    assert line.endswith("normal line")
    assert "***" not in line
