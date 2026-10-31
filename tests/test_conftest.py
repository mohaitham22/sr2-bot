"""Tests for the test setup itself (tests/conftest.py): the guards. No database, no Redis.

The "_test" guard for Postgres (Step 2.2 D4 A) and the database-15 guard for Redis (Step 2.3
D2 A). make_redis() connects only on the first command, so these tests run in CI too.
"""

import pytest
from sqlalchemy.engine import make_url

from app.memory.session_store import make_redis
from tests.conftest import (
    make_alembic_config,
    require_test_database,
    require_test_redis,
    with_test_redis_db,
)


@pytest.mark.parametrize("name", ["srbot", "srbot_testing", "test_srbot", "", None])
def test_guard_refuses_a_database_not_ending_in_test(name: str | None) -> None:
    url = make_url("postgresql+asyncpg://user:fake-password@127.0.0.1:5432").set(database=name)

    with pytest.raises(RuntimeError, match="must end in '_test'"):
        require_test_database(url)


def test_guard_accepts_a_test_database() -> None:
    url = make_url("postgresql+asyncpg://user:fake-password@127.0.0.1:5432/srbot_test")

    assert require_test_database(url) is url


def test_alembic_is_never_pointed_at_a_dev_database() -> None:
    url = make_url("postgresql+asyncpg://user:fake-password@127.0.0.1:5432/srbot")

    with pytest.raises(RuntimeError, match="must end in '_test'"):
        make_alembic_config(url)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("redis://127.0.0.1:6379/0", "redis://127.0.0.1:6379/15"),
        ("redis://127.0.0.1:6379", "redis://127.0.0.1:6379/15"),  # no number = database 0
        ("redis://:fake-password@127.0.0.1:6379/3", "redis://:fake-password@127.0.0.1:6379/15"),
    ],
)
def test_redis_url_is_moved_to_database_15(url: str, expected: str) -> None:
    test_url = with_test_redis_db(url)

    assert test_url == expected
    require_test_redis(make_redis(test_url))  # no error


@pytest.mark.parametrize(
    "url",
    [
        "redis://127.0.0.1:6379/0",
        "redis://127.0.0.1:6379",
        "redis://127.0.0.1:6379/15?db=0",  # the trap: "?db=" beats the path
    ],
)
def test_redis_guard_refuses_a_database_other_than_15(url: str) -> None:
    with pytest.raises(RuntimeError, match="Refusing to use Redis database 0"):
        require_test_redis(make_redis(url))
