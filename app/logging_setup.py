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
# A value of the wrong type (e.g. a name where a number belongs): asyncpg puts the VALUE itself
# into its error, e.g. "invalid input for query argument $1: '<value>' (...)", also for many
# rows at once ("... $1 in element #0 of executemany() sequence: '<value>' ..."). Keep only
# which argument it was (PR #3 review, M1).
QUERY_ARGUMENT = re.compile(r"(query argument \$\d+[^:\n]*:).*")
HIDDEN_ARGUMENT = r"\1 [hidden: may contain personal data]"


class RedactingFormatter(logging.Formatter):
    """Hide secrets and database values in the final log line, tracebacks included.

    A second safety net (CLAUDE.md section 13, D4 B): our code never logs secrets or personal
    data, but an error message from a library might (e.g. a request URL that contains the bot
    token, a database error with the refused row, or a value of the wrong type).
    """

    def __init__(self, fmt: str, secrets: list[str]) -> None:
        super().__init__(fmt)
        # Skip empty strings: replacing "" would put *** between every character
        self._secrets = [secret for secret in secrets if secret]

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        line = POSTGRES_DETAIL.sub(HIDDEN_DETAIL, line)
        line = QUERY_ARGUMENT.sub(HIDDEN_ARGUMENT, line)
        for secret in self._secrets:
            line = line.replace(secret, "***")
        return line


def setup_logging(secrets: list[str], level: int = logging.INFO) -> None:
    """Send logs to the terminal (stderr) with secrets hidden. Call once, at startup."""
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter(LOG_FORMAT, secrets))
    logging.basicConfig(level=level, handlers=[handler])
