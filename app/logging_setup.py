"""Logging setup for all entry points: one format, and secrets hidden in every line."""

import logging
import re

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# When a database rule refuses a row, Postgres sends the failed row back as a "DETAIL:" line,
# e.g. "DETAIL:  Failing row contains (7, 123, <name>, <phone>, ...)". asyncpg puts it into
# its error text, so a traceback shows it, even with SQLAlchemy's hide_parameters. Name and
# phone must never reach a log (CLAUDE.md section 9), so every DETAIL line is hidden
# (Step 2.2, privacy A). The rule's name stays in the line before it.
POSTGRES_DETAIL = re.compile(r"DETAIL:.*")  # "." stops at the end of the line
HIDDEN_DETAIL = "DETAIL: [hidden: may contain personal data]"


class RedactingFormatter(logging.Formatter):
    """Hide secrets and Postgres DETAIL lines in the final log line, tracebacks included.

    A second safety net (CLAUDE.md section 13, D4 B): our code never logs secrets or personal
    data, but an error message from a library might (e.g. a request URL that contains the bot
    token, or a database error with the refused row).
    """

    def __init__(self, fmt: str, secrets: list[str]) -> None:
        super().__init__(fmt)
        # Skip empty strings: replacing "" would put *** between every character
        self._secrets = [secret for secret in secrets if secret]

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        line = POSTGRES_DETAIL.sub(HIDDEN_DETAIL, line)
        for secret in self._secrets:
            line = line.replace(secret, "***")
        return line


def setup_logging(secrets: list[str], level: int = logging.INFO) -> None:
    """Send logs to the terminal (stderr) with secrets hidden. Call once, at startup."""
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter(LOG_FORMAT, secrets))
    logging.basicConfig(level=level, handlers=[handler])
