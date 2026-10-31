"""Tests for the test setup itself (tests/conftest.py): the "_test" guard (D4 A). No database."""

import pytest
from sqlalchemy.engine import make_url

from tests.conftest import make_alembic_config, require_test_database


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
