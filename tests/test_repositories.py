"""Tests for app/db/repositories.py: the ticket number (Step 2.2).

The make_ticket_no tests need no database, so they run in CI too. The others use the test
database (tests/conftest.py) and are skipped when DATABASE_URL is not set.
All names, phones and texts here are fake.
"""

import asyncio
from datetime import date, timedelta

import pytest
from sqlalchemy import delete, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Compound, ServiceRequest, Unit
from app.db.repositories import create_service_request, make_ticket_no
from app.db.session import make_engine, make_session_factory
from tests.conftest import RunDb, add_test_unit, add_test_user, require_test_database

PARALLEL_SRS = 20


# --- make_ticket_no: no database ---


@pytest.mark.parametrize(
    ("sr_id", "expected"),
    [
        (1, "SR-20261031-0001"),
        (42, "SR-20261031-0042"),
        (9999, "SR-20261031-9999"),
        (10342, "SR-20261031-10342"),  # kept whole, not cut to 4 digits
    ],
)
def test_ticket_number_format(sr_id: int, expected: str) -> None:
    assert make_ticket_no(date(2026, 10, 31), sr_id) == expected


def test_ticket_date_has_zeros_in_month_and_day() -> None:
    assert make_ticket_no(date(2027, 1, 5), 7) == "SR-20270105-0007"


@pytest.mark.parametrize("sr_id", [0, -1])
def test_ticket_number_refuses_ids_below_1(sr_id: int) -> None:
    with pytest.raises(ValueError, match="1 or more"):
        make_ticket_no(date(2026, 10, 31), sr_id)


# --- create_service_request: the test database ---


async def save_test_sr(session: AsyncSession, unit_id: int, user_id: int | None) -> ServiceRequest:
    return await create_service_request(
        session,
        unit_id=unit_id,
        user_id=user_id,
        description="Test: the kitchen tap drips",
        language="en",
        category="plumbing",
        subcategory=None,
        urgency="low",
    )


def test_new_sr_gets_ticket_from_its_id_and_cairo_date(db: RunDb) -> None:
    async def scenario(session: AsyncSession) -> None:
        unit = await add_test_unit(session)
        user = await add_test_user(session)

        sr = await save_test_sr(session, unit.id, user.id)

        # Ask Postgres for the Cairo date of the saved created_at
        cairo_date = await session.scalar(
            text(
                "SELECT (created_at AT TIME ZONE 'Africa/Cairo')::date"
                " FROM service_requests WHERE id = :id"
            ),
            {"id": sr.id},
        )
        assert sr.ticket_no == make_ticket_no(cairo_date, sr.id)
        # The database defaults, read back in the INSERT (no hidden query, no MissingGreenlet)
        assert sr.status == "open"
        assert sr.created_at.utcoffset() == timedelta(0)  # timestamptz comes back in UTC
        assert sr.closed_at is None

    db(scenario)


def test_parallel_srs_get_different_tickets(test_db_url: URL) -> None:
    """20 SRs saved at the same moment, each on its own connection: 20 different tickets.

    It must commit (another connection can't see rows that are not committed), so it can't use
    the `db` fixture's rollback. It deletes its own rows at the end instead.
    """
    asyncio.run(save_in_parallel(require_test_database(test_db_url)))


async def save_in_parallel(url: URL) -> None:
    # No pool: each session opens its own connection, so all 20 really run at the same time
    engine = make_engine(url, pooled=False)
    sessions = make_session_factory(engine)
    compound_id = unit_id = None
    try:
        async with sessions() as session:
            unit = await add_test_unit(session)
            compound_id, unit_id = unit.compound_id, unit.id
            await session.commit()

        async def save_one() -> tuple[int, str]:
            async with sessions() as session:
                sr = await save_test_sr(session, unit.id, user_id=None)
                await session.commit()
                return sr.id, sr.ticket_no

        results = await asyncio.gather(*(save_one() for _ in range(PARALLEL_SRS)))

        ids = {sr_id for sr_id, _ in results}
        tickets = {ticket for _, ticket in results}
        assert len(ids) == PARALLEL_SRS
        assert len(tickets) == PARALLEL_SRS
    finally:
        if compound_id is not None:
            async with sessions() as session:
                await session.execute(
                    delete(ServiceRequest).where(ServiceRequest.unit_id == unit_id)
                )
                await session.execute(delete(Unit).where(Unit.id == unit_id))
                await session.execute(delete(Compound).where(Compound.id == compound_id))
                await session.commit()
        await engine.dispose()
