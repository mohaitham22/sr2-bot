"""Logging setup for all entry points: one format, and secrets hidden in every line."""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class RedactingFormatter(logging.Formatter):
    """Replace each secret with *** in the final log line, tracebacks included.

    A second safety net (CLAUDE.md section 13, D4 B): our code never logs secrets, but an
    error message from a library might (e.g. a request URL that contains the bot token).
    """

    def __init__(self, fmt: str, secrets: list[str]) -> None:
        super().__init__(fmt)
        # Skip empty strings: replacing "" would put *** between every character
        self._secrets = [secret for secret in secrets if secret]

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        for secret in self._secrets:
            line = line.replace(secret, "***")
        return line


def setup_logging(secrets: list[str], level: int = logging.INFO) -> None:
    """Send logs to the terminal (stderr) with secrets hidden. Call once, at startup."""
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter(LOG_FORMAT, secrets))
    logging.basicConfig(level=level, handlers=[handler])
