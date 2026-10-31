"""Shared test setup: the test databases for the integration tests.

pytest reads this file by itself. A test that doesn't ask for `db`, `test_db_url`,
`alembic_config`, `redis_db` or `test_redis_url` never touches a database.

Redis (Step 2.3 D2 A): database 15 of the same Redis (the app uses 0), emptied (FLUSHDB) before
and after each test. The guard refuses any other number. Skipped without REDIS_URL, failed with
what to start when Redis is off: the same rules as Postgres below.

Postgres (Step 2.2 D4 A):

- Which database: DATABASE_URL from .env with "_test" added to the name (srbot -> srbot_test).
  Your dev database is never used: every helper refuses a name that doesn't end in "_test".
- No DATABASE_URL (CI until Step 2.11): the database tests are skipped.
- DATABASE_URL set, but Postgres is off: they fail and say what to start. A silent skip would
  hide a stopped Docker.
- Once per test run: create srbot_test if it is missing, then `alembic upgrade head` on it.
  So the tests also prove that the migrations build the tables the code expects.
- Async without pytest-asyncio (D5 A): each test runs its scenario with asyncio.run().
"""

import asyncio
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

import pytest
from alembic import command
from alembic.config import Config
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ROOT_DIR, get_settings
from app.db.models import Compound, Unit, User
from app.db.session import database_url, make_engine
from app.memory.session_store import make_redis

TEST_SUFFIX = "_test"
TEST_REDIS_DB = 15  # Redis has databases 0-15; the app uses 0 (the end of REDIS_URL)
# Fake values for the test rows (all fictional)
FAKE_NAME = "Test Resident"
FAKE_PHONE = "+0000000000"  # E.164 shape, but no country has the code 0
START_POSTGRES = "Start Rancher Desktop, then: docker compose up -d --wait postgres redis"
START_REDIS = START_POSTGRES  # the same command starts both

# A test scenario: an async function that gets a session. RunDb runs one (the `db` fixture).
# Test files import these two names for their type hints.
Scenario = Callable[[AsyncSession], Awaitable[None]]
RunDb = Callable[[Scenario], None]
# The same for Redis: a scenario gets a client on database 15 (the `redis_db` fixture)
RedisScenario = Callable[[Redis], Awaitable[None]]
RunRedis = Callable[[RedisScenario], None]


def require_test_database(url: URL) -> URL:
    """The safety guard (D4 A): stop unless the database name ends in "_test"."""
    if not (url.database or "").endswith(TEST_SUFFIX):
        raise RuntimeError(
            f"Refusing to use the database {url.database!r} in tests: "
            f"its name must end in {TEST_SUFFIX!r}, so dev data can never be wiped"
        )
    return url


def make_alembic_config(url: URL) -> Config:
    """Alembic's settings from alembic.ini, pointed at the test database (env.py reads this)."""
    config = Config(ROOT_DIR / "alembic.ini")
    config.attributes["database_url"] = require_test_database(url)
    return config


async def create_database_if_missing(url: URL) -> None:
    """Create the test database once. Connects to the built-in "postgres" database for that.

    AUTOCOMMIT: CREATE DATABASE can't run inside a transaction.
    """
    name = require_test_database(url).database
    engine = make_engine(url.set(database="postgres"), pooled=False)
    try:
        async with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as connection:
            exists = await connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
            )
            if not exists:
                # A name can't be a query parameter. It is our own .env value + "_test"
                await connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await engine.dispose()


async def run_in_rollback(url: URL, scenario: Scenario) -> None:
    """Run one scenario in a transaction that is rolled back at the end: nothing is kept.

    join_transaction_mode="create_savepoint": the session runs inside our outer transaction.
    Its commit() only ends a savepoint, so the outer rollback still removes everything, and
    `async with session.begin_nested():` makes a SAVEPOINT for an insert that must fail.
    """
    engine = make_engine(require_test_database(url), pooled=False)
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            session = AsyncSession(
                bind=connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            )
            try:
                await scenario(session)
            finally:
                await session.close()
                await outer.rollback()
    finally:
        await engine.dispose()


async def add_test_unit(session: AsyncSession) -> Unit:
    """A fake compound with one unit, B-204. The test database has no registry loaded."""
    compound = Compound(name_en="Test Compound", name_ar="مجمع تجريبي")
    session.add(compound)
    await session.flush()  # now compound.id is known
    unit = Unit(compound_id=compound.id, building="B", unit_number="B-204")
    session.add(unit)
    await session.flush()
    return unit


async def add_test_user(session: AsyncSession, telegram_user_id: int = 1) -> User:
    """A fake resident."""
    user = User(telegram_user_id=telegram_user_id, name=FAKE_NAME, phone=FAKE_PHONE)
    session.add(user)
    await session.flush()
    return user


def with_test_redis_db(url: str) -> str:
    """The same Redis URL with database 15 at its end: redis://host:6379/0 -> .../15."""
    return urlunsplit(urlsplit(url)._replace(path=f"/{TEST_REDIS_DB}"))


def require_test_redis(client: Redis) -> Redis:
    """The safety guard (D2 A): stop unless the client really uses database 15.

    It reads the number the client will use, not the one we asked for: "?db=0" at the end of a
    URL beats the "/15" path (checked in Step 2.3), and FLUSHDB empties a whole database.
    """
    number = client.connection_pool.connection_kwargs.get("db", 0)
    if number != TEST_REDIS_DB:
        raise RuntimeError(
            f"Refusing to use Redis database {number} in tests: only database {TEST_REDIS_DB}, "
            "so dev data can never be wiped"
        )
    return client


async def ping_redis(url: str) -> None:
    """Check once that the test Redis answers."""
    client = require_test_redis(make_redis(url))
    try:
        await client.ping()
    finally:
        await client.aclose()


async def run_on_test_redis(url: str, scenario: RedisScenario) -> None:
    """Run one scenario on an empty database 15, and empty it again at the end."""
    client = require_test_redis(make_redis(url))
    try:
        await client.flushdb()  # FLUSHDB: only this database (15), never the others
        await scenario(client)
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.fixture(scope="session")
def test_db_url() -> URL:
    """The test database's URL. Created and migrated once per test run (scope="session")."""
    if get_settings().database_url is None:
        pytest.skip("DATABASE_URL is not set: database tests skipped (CI until Step 2.11)")
    dev_url = database_url()
    url = require_test_database(dev_url.set(database=f"{dev_url.database}{TEST_SUFFIX}"))
    try:
        asyncio.run(create_database_if_missing(url))
    except (OSError, SQLAlchemyError) as error:
        # Only the error type, never the URL: it contains the password
        pytest.fail(
            f"Can't reach Postgres for the database tests ({type(error).__name__}). "
            f"{START_POSTGRES}",
            pytrace=False,
        )
    command.upgrade(make_alembic_config(url), "head")
    return url


@pytest.fixture
def alembic_config(test_db_url: URL) -> Config:
    """Alembic's settings for the test database, for the migration tests."""
    return make_alembic_config(test_db_url)


@pytest.fixture
def db(test_db_url: URL) -> RunDb:
    """Run a test scenario with a session; everything it writes is rolled back.

    Use:
        def test_something(db: RunDb) -> None:
            async def scenario(session: AsyncSession) -> None:
                ...
            db(scenario)
    """

    def run(scenario: Scenario) -> None:
        asyncio.run(run_in_rollback(test_db_url, scenario))

    return run


@pytest.fixture(scope="session")
def test_redis_url() -> str:
    """The test Redis URL (database 15). Checked once per test run (scope="session")."""
    redis_url = get_settings().redis_url
    if redis_url is None:
        pytest.skip("REDIS_URL is not set: Redis tests skipped (CI until Step 2.11)")
    url = with_test_redis_db(redis_url.get_secret_value())
    try:
        asyncio.run(ping_redis(url))
    except (OSError, RedisError) as error:
        # Only the error type, never the URL: on the server it will hold a password
        pytest.fail(
            f"Can't reach Redis for the session-store tests ({type(error).__name__}). "
            f"{START_REDIS}",
            pytrace=False,
        )
    return url


@pytest.fixture
def redis_db(test_redis_url: str) -> RunRedis:
    """Run a test scenario with a client on an empty database 15; it is emptied again after.

    Use:
        def test_something(redis_db: RunRedis) -> None:
            async def scenario(redis: Redis) -> None:
                ...
            redis_db(scenario)
    """

    def run(scenario: RedisScenario) -> None:
        asyncio.run(run_on_test_redis(test_redis_url, scenario))

    return run
