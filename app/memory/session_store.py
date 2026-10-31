"""Step 2.3: the bot's short-term memory in Redis (CLAUDE.md section 8, the brief's memory design).

Two keys per Telegram chat, both deleted 30 minutes after the last message (sliding expiry):
- session:{chat_id}  one JSON text: the service request being filled in (Session)
- history:{chat_id}  a Redis list of JSON texts, one per message: the last N messages

Serialization: Redis stores only text, so a model becomes JSON on the way in
(model_dump_json) and is checked again on the way out (model_validate_json).

Personal data (CLAUDE.md section 9): the name, the phone, the problem text and every message text.
They may stay here only until submit, /reset, /forget or 30 minutes idle. Never log a Session or a
HistoryMessage, and never log a model_dump() of one. As a second line of defence, their printed
form (repr) hides these values, and a validation error never shows the wrong value.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Literal, get_args

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.schemas.labels import Language, MessageRole

logger = logging.getLogger(__name__)

# Section 13 (2026-10-31, Momo's values): local Redis answers in about 1 ms; the reply target is
# under 5 s at p95, and a message makes about 3 Redis calls
CONNECT_TIMEOUT_SECONDS = 2.0
READ_TIMEOUT_SECONDS = 1.0

# The LangGraph nodes of CLAUDE.md section 4: where the conversation is now.
# Step 2.10 (the graph) may change this list.
ConversationStep = Literal[
    "transcribe", "extract", "ask_missing", "confirm", "classify", "save", "reply"
]

# The 6 required fields (design notes section 1), in the order the bot asks for them (1.9):
# first the problem, then the unit, then the contact
RequiredField = Literal["issue_description", "compound", "building", "unit_number", "name", "phone"]
REQUIRED_FIELDS: tuple[RequiredField, ...] = get_args(RequiredField)


def utc_now() -> datetime:
    """The current time in UTC, with its time zone attached (an "aware" datetime)."""
    return datetime.now(UTC)


class StoredModel(BaseModel):
    """The settings shared by every model that is saved in Redis.

    A session may outlive a code change (it lives up to 30 minutes). A new field needs a default,
    so older sessions still load. A removed or renamed field makes older sessions fail
    validation: the store then deletes them and the user starts again (section 13, 2026-10-31).
    """

    model_config = ConfigDict(
        extra="forbid",  # an unknown key (a typo, or a field we removed) is an error
        validate_assignment=True,  # session.step = "confrim" fails at once, not later in Redis
        hide_input_in_errors=True,  # an error never shows the wrong value: it may be a phone
    )


class CollectedFields(StoredModel):
    """The 6 required fields of design notes section 1. None = not known yet.

    The values are cleaned and checked by Python code before they get here (Steps 2.8-2.9),
    e.g. "B-201", "+201XXXXXXXXX". They are not confirmed yet: the user confirms them at the
    summary (node `confirm`), and only then do they go to Postgres.
    """

    compound: str | None = None
    building: str | None = None
    unit_number: str | None = None
    # repr=False: left out when the object is printed. Personal data, as in app/db/models.py
    name: str | None = Field(default=None, repr=False)
    phone: str | None = Field(default=None, repr=False)
    issue_description: str | None = Field(default=None, repr=False)


class Session(StoredModel):
    """The service request being filled in for one chat (the key session:{chat_id})."""

    collected: CollectedFields = Field(default_factory=CollectedFields)
    step: ConversationStep = "extract"  # a new conversation starts by reading the first message
    language: Language | None = None  # None until the language of a message is known
    updated_at: AwareDatetime = Field(default_factory=utc_now)  # the store sets it on every save

    @property
    def missing_fields(self) -> list[RequiredField]:
        """The required fields that are still empty, in the order the bot asks for them.

        Computed every time from `collected`, never stored, so the two can never disagree.
        A @property is not a field: it is not in the JSON that goes to Redis.
        """
        return [name for name in REQUIRED_FIELDS if getattr(self.collected, name) is None]


class HistoryMessage(StoredModel):
    """One message of the conversation (one item of the list history:{chat_id})."""

    role: MessageRole
    text: str = Field(repr=False)  # personal data: it can contain a name or a phone (section 9)
    created_at: AwareDatetime = Field(default_factory=utc_now)


class SessionStoreError(Exception):
    """Every problem of the session store. Catch this to handle them all in one place."""


class SessionStoreUnavailable(SessionStoreError):
    """Redis did not answer in time, or the connection failed. Phase 3: "please try again"."""


class SessionDataLost(SessionStoreError):
    """The saved data of a chat could not be read and was deleted.

    Phase 3: the bot tells the user the conversation restarted (section 13, 2026-10-31).
    """


def make_redis(url: str) -> Redis:
    """A Redis client for the app and the tests. It connects on its first command, not here.

    - decode_responses=True: Redis returns str instead of bytes (our values are UTF-8 JSON).
    - The timeouts: a stuck Redis gives an error after 2 s, it can't freeze the bot.
    - Retry(NoBackoff(), 0): never try a command again by itself. redis-py 8.1 does the same
      by default (checked in Step 2.3); written here so a newer version can't change it, and
      the timeouts stay the real limit.
    Close it with `await client.aclose()` when the program stops.
    """
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=CONNECT_TIMEOUT_SECONDS,
        socket_timeout=READ_TIMEOUT_SECONDS,
        retry=Retry(NoBackoff(), 0),
    )


def session_key(chat_id: int) -> str:
    """The Redis key of a chat's session (CLAUDE.md section 8)."""
    return f"session:{chat_id}"


def history_key(chat_id: int) -> str:
    """The Redis key of a chat's history (CLAUDE.md section 8)."""
    return f"history:{chat_id}"


@asynccontextmanager
async def redis_errors() -> AsyncIterator[None]:
    """Turn Redis's connection and timeout errors into our own SessionStoreUnavailable.

    Phase 3 then catches one error of ours, not several of redis-py's. The message holds only the
    error type; the original error stays attached (`from error`) for debugging: it names the
    host and port, never a value we sent.
    """
    try:
        yield
    except (RedisConnectionError, RedisTimeoutError) as error:
        raise SessionStoreUnavailable(f"Redis did not answer ({type(error).__name__})") from error


class SessionStore:
    """The short-term memory of every chat: the session and the last messages, in Redis.

    Made once when the program starts; the entry point reads the settings (section 13,
    2026-10-25). Phase 3 gives it to the handlers as dp["session_store"]:

        store = SessionStore(
            make_redis(settings.redis_url.get_secret_value()),
            ttl=timedelta(seconds=settings.session_ttl_seconds),
            max_messages=settings.history_max_messages,
        )

    Sliding expiry: every write (save, add_message) restarts the timer of BOTH keys, so they are
    deleted together, `ttl` after the last write. Reading (load, get_history) changes nothing.
    Phase 3: add the user's message first, so both timers restart before the slow work (LLM).
    """

    def __init__(self, redis: Redis, *, ttl: timedelta, max_messages: int) -> None:
        # Redis counts in whole milliseconds (PX, PEXPIRE): tests can use a 200 ms timer
        ttl_ms = ttl // timedelta(milliseconds=1)
        if ttl_ms <= 0 or max_messages <= 0:
            raise ValueError("ttl must be at least 1 ms and max_messages at least 1")
        self._redis = redis
        self._ttl_ms = ttl_ms
        self._max_messages = max_messages

    async def load(self, chat_id: int) -> Session | None:
        """The chat's session, or None if it has none (first message, or the timer ran out).

        Raises SessionDataLost if the saved JSON can't be read (broken, or written by an older
        version of the code). Both keys are deleted first, so the next message starts fresh.
        """
        async with redis_errors():
            text = await self._redis.get(session_key(chat_id))
        if text is None:
            return None
        try:
            return Session.model_validate_json(text)
        except ValidationError as error:
            await self._drop_unreadable(chat_id, error)
            raise SessionDataLost(f"chat_id={chat_id}: the saved session was deleted") from None

    async def save(self, chat_id: int, session: Session) -> None:
        """Save the session (it sets session.updated_at to now) and restart both timers.

        One transaction (MULTI ... EXEC): Redis runs the commands together, and no other client
        can see the state between them.
        """
        session.updated_at = utc_now()
        async with redis_errors(), self._redis.pipeline(transaction=True) as pipe:
            pipe.set(session_key(chat_id), session.model_dump_json(), px=self._ttl_ms)
            pipe.pexpire(history_key(chat_id), self._ttl_ms)  # no history yet: does nothing
            await pipe.execute()

    async def add_message(self, chat_id: int, role: MessageRole, text: str) -> None:
        """Add a message at the end of the history, keep only the last N, restart both timers."""
        message = HistoryMessage(role=role, text=text)
        key = history_key(chat_id)
        async with redis_errors(), self._redis.pipeline(transaction=True) as pipe:
            pipe.rpush(key, message.model_dump_json())  # R = right = the end of the list
            # Keep the items from the N-th last (-N) to the last (-1); Redis drops the others
            pipe.ltrim(key, -self._max_messages, -1)
            pipe.pexpire(key, self._ttl_ms)
            pipe.pexpire(session_key(chat_id), self._ttl_ms)  # no session yet: does nothing
            await pipe.execute()

    async def get_history(self, chat_id: int) -> list[HistoryMessage]:
        """The chat's last messages, oldest first; an empty list if there are none.

        Raises SessionDataLost if a message can't be read; both keys are deleted first.
        """
        async with redis_errors():
            items = await self._redis.lrange(history_key(chat_id), 0, -1)
        try:
            return [HistoryMessage.model_validate_json(item) for item in items]
        except ValidationError as error:
            await self._drop_unreadable(chat_id, error)
            raise SessionDataLost(f"chat_id={chat_id}: the saved history was deleted") from None

    async def clear(self, chat_id: int) -> None:
        """Delete the session and the history: on submit, /reset and /forget (D4 A).

        One command with both keys, so they always go together. No error if they don't exist.
        """
        async with redis_errors():
            await self._redis.delete(session_key(chat_id), history_key(chat_id))

    async def _drop_unreadable(self, chat_id: int, error: ValidationError) -> None:
        """Delete a chat's unreadable data and log it: the chat ID and the error type only."""
        await self.clear(chat_id)
        logger.warning(
            "Saved data of chat_id=%s could not be read (%s, %d errors); session and history "
            "deleted",
            chat_id,
            type(error).__name__,
            error.error_count(),
        )
