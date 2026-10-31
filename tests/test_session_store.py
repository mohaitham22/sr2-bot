"""Tests for app/memory/session_store.py (Step 2.3).

Without Redis (they run in CI too): the models, make_redis(), and the error when Redis is off.
With the real Redis (D2 A): database 15, emptied before and after each test (`redis_db` in
tests/conftest.py). Each test makes its own SessionStore, so it can choose the timer and N.
Fake values only: the name and phone come from conftest.py.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError
from redis.asyncio import Redis

from app.memory.session_store import (
    CONNECT_TIMEOUT_SECONDS,
    READ_TIMEOUT_SECONDS,
    REQUIRED_FIELDS,
    CollectedFields,
    HistoryMessage,
    Session,
    SessionDataLost,
    SessionStore,
    SessionStoreUnavailable,
    history_key,
    make_redis,
    session_key,
)
from tests.conftest import FAKE_NAME, FAKE_PHONE, RunRedis

CHAT = 1001  # fake chat IDs
OTHER_CHAT = 1002
TTL = timedelta(minutes=30)
TTL_MS = 30 * 60 * 1000
FAKE_PROBLEM = "The AC is not cooling."
CLOSED_PORT_URL = "redis://127.0.0.1:6390/15"  # nothing listens on port 6390


def make_store(redis: Redis, ttl: timedelta = TTL, max_messages: int = 10) -> SessionStore:
    return SessionStore(redis, ttl=ttl, max_messages=max_messages)


def filled_session() -> Session:
    """A session with every field except unit_number (fake values)."""
    return Session(
        collected=CollectedFields(
            compound="Olive Ridge",
            building="B",
            name=FAKE_NAME,
            phone=FAKE_PHONE,
            issue_description=FAKE_PROBLEM,
        ),
        step="ask_missing",
        language="en",
    )


# --- The models (no Redis) ---


def test_required_fields_are_the_fields_of_the_model() -> None:
    assert len(REQUIRED_FIELDS) == 6
    assert set(REQUIRED_FIELDS) == set(CollectedFields.model_fields)


def test_missing_fields_in_asking_order() -> None:
    # Design notes 1.9: the problem first, then the unit, then the contact
    assert Session().missing_fields == [
        "issue_description",
        "compound",
        "building",
        "unit_number",
        "name",
        "phone",
    ]
    assert filled_session().missing_fields == ["unit_number"]


def test_json_round_trip() -> None:
    session = filled_session()

    text = session.model_dump_json()

    assert Session.model_validate_json(text) == session
    assert "missing_fields" not in text  # computed, never stored


def test_printed_form_hides_personal_data() -> None:
    session = filled_session()
    message = HistoryMessage(role="user", text=f"I am {FAKE_NAME}, call {FAKE_PHONE}")

    printed = str(session) + repr(session) + str(message) + repr(message)

    for value in (FAKE_NAME, FAKE_PHONE, FAKE_PROBLEM):
        assert value not in printed
    assert "Olive Ridge" in printed  # the unit stays visible, for debugging


def test_validation_error_hides_the_value() -> None:
    with pytest.raises(ValidationError) as error:
        Session(language=FAKE_PHONE)  # wrong on purpose

    assert "language" in str(error.value)
    assert FAKE_PHONE not in str(error.value)


def test_a_typo_in_step_fails_at_once() -> None:
    session = Session()

    with pytest.raises(ValidationError, match="step"):
        session.step = "confrim"  # wrong on purpose


def test_unknown_key_is_refused() -> None:
    with pytest.raises(ValidationError, match="old_field"):
        Session.model_validate_json('{"old_field": 1}')


def test_time_without_a_time_zone_is_refused() -> None:
    with pytest.raises(ValidationError, match="updated_at"):
        Session(updated_at=datetime(2026, 10, 31, 12, 0))  # no tzinfo = "naive"


# --- make_redis() and the store's own checks (no Redis: nothing connects) ---


def test_make_redis_timeouts_and_no_retry() -> None:
    connection = make_redis(CLOSED_PORT_URL).connection_pool.make_connection()

    assert connection.socket_connect_timeout == CONNECT_TIMEOUT_SECONDS == 2.0
    assert connection.socket_timeout == READ_TIMEOUT_SECONDS == 1.0
    assert connection.retry.get_retries() == 0


@pytest.mark.parametrize(
    ("ttl", "max_messages"),
    [(timedelta(0), 10), (timedelta(microseconds=500), 10), (TTL, 0)],
)
def test_store_refuses_a_zero_timer_or_zero_history(ttl: timedelta, max_messages: int) -> None:
    with pytest.raises(ValueError, match="at least"):
        SessionStore(make_redis(CLOSED_PORT_URL), ttl=ttl, max_messages=max_messages)


# Every store method, called on a store whose Redis is off
CALLS: dict[str, Callable[[SessionStore], Awaitable[object]]] = {
    "load": lambda store: store.load(CHAT),
    "save": lambda store: store.save(CHAT, Session()),
    "add_message": lambda store: store.add_message(CHAT, "user", "fake message"),
    "get_history": lambda store: store.get_history(CHAT),
    "clear": lambda store: store.clear(CHAT),
}


@pytest.mark.parametrize("call", CALLS.values(), ids=CALLS.keys())
def test_redis_off_gives_one_clear_error(call: Callable[[SessionStore], Awaitable[object]]) -> None:
    async def scenario() -> None:
        # A short connect timeout, so the test is fast (make_redis's 2 s is tested above)
        redis = Redis.from_url(CLOSED_PORT_URL, socket_connect_timeout=0.2)
        try:
            with pytest.raises(SessionStoreUnavailable, match="Redis did not answer"):
                await call(make_store(redis))
        finally:
            await redis.aclose()

    asyncio.run(scenario())


# --- The store, on the real Redis (database 15) ---


def test_save_then_load(redis_db: RunRedis) -> None:
    async def scenario(redis: Redis) -> None:
        store = make_store(redis)
        session = filled_session()
        before = session.updated_at

        await store.save(CHAT, session)

        assert session.updated_at >= before  # save() stamps the time
        assert await store.load(CHAT) == session
        assert await store.load(OTHER_CHAT) is None  # no session = None, not an error
        assert await redis.keys("*") == [session_key(CHAT)] == ["session:1001"]

    redis_db(scenario)


def test_chats_are_separate(redis_db: RunRedis) -> None:
    async def scenario(redis: Redis) -> None:
        store = make_store(redis)
        await store.save(CHAT, filled_session())
        await store.save(OTHER_CHAT, Session(language="ar"))
        await store.add_message(CHAT, "user", "fake message")

        await store.clear(CHAT)

        assert await store.load(CHAT) is None
        other = await store.load(OTHER_CHAT)
        assert other is not None and other.language == "ar"
        assert await store.get_history(OTHER_CHAT) == []

    redis_db(scenario)


def test_history_keeps_the_order_and_only_the_last_n(redis_db: RunRedis) -> None:
    async def scenario(redis: Redis) -> None:
        store = make_store(redis, max_messages=3)
        for number in range(1, 6):
            await store.add_message(CHAT, "user" if number % 2 else "bot", f"message {number}")

        history = await store.get_history(CHAT)

        assert [message.text for message in history] == ["message 3", "message 4", "message 5"]
        assert [message.role for message in history] == ["user", "bot", "user"]
        assert await redis.llen(history_key(CHAT)) == 3  # really dropped, not only hidden

    redis_db(scenario)


def test_every_write_restarts_both_timers(redis_db: RunRedis) -> None:
    """Sliding expiry, checked with PTTL (milliseconds left) instead of waiting 30 minutes."""

    async def scenario(redis: Redis) -> None:
        store = make_store(redis)
        keys = (session_key(CHAT), history_key(CHAT))
        await store.save(CHAT, Session())
        await store.add_message(CHAT, "user", "fake message")

        for write in (
            lambda: store.add_message(CHAT, "bot", "fake reply"),
            lambda: store.save(CHAT, Session(step="ask_missing")),
        ):
            for key in keys:
                await redis.pexpire(key, 5_000)  # pretend 29 min 55 s have passed
            await write()
            for key in keys:
                assert await redis.pttl(key) > TTL_MS - 5_000  # back to about 30 minutes

    redis_db(scenario)


def test_reading_does_not_restart_the_timer(redis_db: RunRedis) -> None:
    async def scenario(redis: Redis) -> None:
        store = make_store(redis)
        await store.save(CHAT, Session())
        await store.add_message(CHAT, "user", "fake message")
        await redis.pexpire(session_key(CHAT), 5_000)
        await redis.pexpire(history_key(CHAT), 5_000)

        await store.load(CHAT)
        await store.get_history(CHAT)

        assert await redis.pttl(session_key(CHAT)) <= 5_000
        assert await redis.pttl(history_key(CHAT)) <= 5_000

    redis_db(scenario)


def test_keys_expire_by_themselves(redis_db: RunRedis) -> None:
    """The one test that really waits: Redis deletes both keys when the timer runs out."""

    async def scenario(redis: Redis) -> None:
        store = make_store(redis, ttl=timedelta(milliseconds=200))
        await store.save(CHAT, filled_session())
        await store.add_message(CHAT, "user", "fake message")
        assert await redis.exists(session_key(CHAT), history_key(CHAT)) == 2

        await asyncio.sleep(0.6)  # 3x the timer: safe on a slow machine

        assert await redis.exists(session_key(CHAT), history_key(CHAT)) == 0
        assert await store.load(CHAT) is None
        assert await store.get_history(CHAT) == []

    redis_db(scenario)


def test_clear_deletes_both_keys(redis_db: RunRedis) -> None:
    async def scenario(redis: Redis) -> None:
        store = make_store(redis)
        await store.save(CHAT, filled_session())
        await store.add_message(CHAT, "user", "fake message")

        await store.clear(CHAT)
        await store.clear(CHAT)  # nothing left to delete: still no error

        assert await redis.exists(session_key(CHAT), history_key(CHAT)) == 0

    redis_db(scenario)


@pytest.mark.parametrize(
    "broken",
    [
        "not json at all",
        f'{{"language": "{FAKE_PHONE}"}}',  # a wrong value that is personal data
        '{"old_field": 1}',  # saved by an older version of the code
    ],
    ids=["not-json", "wrong-value", "removed-field"],
)
def test_unreadable_session_is_deleted_and_reported(
    redis_db: RunRedis, caplog: pytest.LogCaptureFixture, broken: str
) -> None:
    async def scenario(redis: Redis) -> None:
        store = make_store(redis)
        await store.add_message(CHAT, "user", f"call me on {FAKE_PHONE}")
        await redis.set(session_key(CHAT), broken)

        with pytest.raises(SessionDataLost) as error:
            await store.load(CHAT)

        # `from None`: the validation error is cut off, a traceback won't print it
        assert error.value.__cause__ is None
        assert error.value.__suppress_context__
        assert await redis.exists(session_key(CHAT), history_key(CHAT)) == 0  # both deleted

    caplog.set_level(logging.WARNING, logger="app.memory.session_store")
    redis_db(scenario)

    [record] = caplog.records  # exactly one log line
    assert "chat_id=1001" in record.getMessage()
    assert "ValidationError" in record.getMessage()
    assert FAKE_PHONE not in caplog.text


def test_unreadable_history_is_deleted_and_reported(
    redis_db: RunRedis, caplog: pytest.LogCaptureFixture
) -> None:
    async def scenario(redis: Redis) -> None:
        store = make_store(redis)
        await store.save(CHAT, filled_session())
        await redis.rpush(history_key(CHAT), f'{{"role": "admin", "text": "{FAKE_PHONE}"}}')

        with pytest.raises(SessionDataLost):
            await store.get_history(CHAT)

        assert await redis.exists(session_key(CHAT), history_key(CHAT)) == 0

    caplog.set_level(logging.WARNING, logger="app.memory.session_store")
    redis_db(scenario)

    assert len(caplog.records) == 1
    assert FAKE_PHONE not in caplog.text
