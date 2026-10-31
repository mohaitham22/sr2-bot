"""Tests for app/db/models.py: the rules the database itself enforces (Step 2.2).

They run on the test database (tests/conftest.py). Its tables come from the Alembic migration,
so these tests check the models and the migration together. Skipped without DATABASE_URL.

Every insert that must fail runs inside a SAVEPOINT (session.begin_nested()). In Postgres one
error aborts the whole transaction; the savepoint undoes only the failed insert, so the test can
go on, and the db fixture's rollback still cleans up everything at the end (D4 A).
All names, phones and texts here are fake.
"""

import logging
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Base,
    Compound,
    Message,
    Prediction,
    ServiceRequest,
    Unit,
    User,
    UserUnit,
)
from app.db.repositories import create_service_request
from app.logging_setup import LOG_FORMAT, RedactingFormatter
from app.schemas.labels import CATEGORIES, SUBCATEGORIES, URGENCIES
from tests.conftest import FAKE_NAME, FAKE_PHONE, RunDb, add_test_unit, add_test_user

# Fixed times, so no rule depends on the laptop's clock vs the database's clock
LONG_AGO = datetime(2000, 1, 1, tzinfo=UTC)
FAR_FUTURE = datetime(2100, 1, 1, tzinfo=UTC)


async def assert_insert_refused(session: AsyncSession, row: Base, expected: str) -> None:
    """Insert one row inside a SAVEPOINT. It must fail, and the error must name `expected`."""
    with pytest.raises(IntegrityError) as caught:
        async with session.begin_nested():  # SAVEPOINT; on the error: ROLLBACK TO SAVEPOINT
            session.add(row)
            await session.flush()
    assert expected in str(caught.value)


def sr_row(unit_id: int, **changes: object) -> ServiceRequest:
    """A valid SR row, with some values changed. In the app, the repository makes the ticket."""
    values: dict[str, object] = {
        "ticket_no": "SR-20261031-9001",
        "unit_id": unit_id,
        "description": "Test: a door handle came off",
        "language": "en",
        "category": "carpentry",
        "subcategory": None,
        "urgency": "medium",
    }
    values.update(changes)
    return ServiceRequest(**values)


def prediction_row(sr_id: int, **changes: object) -> Prediction:
    """A valid prediction row, with some values changed."""
    values: dict[str, object] = {
        "sr_id": sr_id,
        "model_name": "tfidf_logreg",
        "model_version": "1.0.0",
        "category": "plumbing",
        "category_confidence": 0.87,
        "subcategory": None,
        "urgency": "low",
        "urgency_confidence": 0.61,
        "needs_review": False,
    }
    values.update(changes)
    return Prediction(**values)


@dataclass
class Existing:
    """Valid rows that are already saved, so a test can try to break a rule against them."""

    unit: Unit
    user: User
    sr: ServiceRequest


async def add_existing_rows(session: AsyncSession) -> Existing:
    """A compound, a unit, a user, their user_units link, an SR and its prediction."""
    unit = await add_test_unit(session)
    user = await add_test_user(session)
    session.add(UserUnit(user_id=user.id, unit_id=unit.id))
    sr = await create_service_request(
        session,
        unit_id=unit.id,
        user_id=user.id,
        description="Test: the kitchen tap drips",
        language="en",
        category="plumbing",
        subcategory=None,
        urgency="low",
    )
    session.add(prediction_row(sr.id))
    await session.flush()
    # Forget the objects (the rows stay in the database). SQLAlchemy keeps one object per
    # primary key in memory (the identity map) and would refuse a second UserUnit with the same
    # key itself. We want the DATABASE to refuse it.
    session.expunge_all()
    return Existing(unit, user, sr)


async def count(session: AsyncSession, model: type[Base]) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0


# --- Valid rows are accepted ---


def test_all_seven_tables_take_a_valid_row(db: RunDb) -> None:
    async def scenario(session: AsyncSession) -> None:
        existing = await add_existing_rows(session)
        session.add(
            Message(
                telegram_chat_id=existing.user.telegram_user_id,
                sr_id=existing.sr.id,
                role="user",
                text="Test: the kitchen tap drips",
            )
        )
        await session.flush()

        for model in (Compound, Unit, User, UserUnit, ServiceRequest, Prediction, Message):
            assert await count(session, model) == 1, model.__tablename__

    db(scenario)


def test_telegram_ids_bigger_than_an_integer_fit(db: RunDb) -> None:
    async def scenario(session: AsyncSession) -> None:
        big_id = 8_123_456_789  # more than 2,147,483,647, the biggest integer
        user = await add_test_user(session, telegram_user_id=big_id)
        session.add(Message(telegram_chat_id=big_id, role="bot", text="Test"))
        await session.flush()

        saved = await session.scalar(select(User.telegram_user_id).where(User.id == user.id))
        assert saved == big_id

    db(scenario)


def test_confidence_comes_back_exactly(db: RunDb) -> None:
    """double precision, like Python's float (Step 2.2, Momo: B). As real, 0.87 changed."""

    async def scenario(session: AsyncSession) -> None:
        existing = await add_existing_rows(session)

        saved = await session.scalar(
            select(Prediction.category_confidence).where(Prediction.sr_id == existing.sr.id)
        )
        assert saved == 0.87  # exact, no pytest.approx: stored and read back unchanged

    db(scenario)


def test_a_closed_sr_with_closed_at_is_accepted(db: RunDb) -> None:
    async def scenario(session: AsyncSession) -> None:
        unit = await add_test_unit(session)
        session.add(sr_row(unit.id, status="closed", closed_at=FAR_FUTURE))
        await session.flush()

    db(scenario)


def test_same_unit_number_in_another_compound_is_fine(db: RunDb) -> None:
    async def scenario(session: AsyncSession) -> None:
        unit = await add_test_unit(session)  # B-204 in "Test Compound"
        other = Compound(name_en="Other Test Compound", name_ar="مجمع تجريبي آخر")
        session.add(other)
        await session.flush()

        session.add(Unit(compound_id=other.id, building="B", unit_number=unit.unit_number))
        await session.flush()  # no error: B-204 is unique only inside one compound

    db(scenario)


# --- labels.py and the migration agree (autogenerate does not compare CHECK rules) ---


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_category_is_accepted(db: RunDb, category: str) -> None:
    async def scenario(session: AsyncSession) -> None:
        unit = await add_test_unit(session)
        sr = sr_row(unit.id, category=category)
        session.add(sr)
        await session.flush()
        session.add(prediction_row(sr.id, category=category))
        await session.flush()

    db(scenario)


@pytest.mark.parametrize("urgency", URGENCIES)
def test_every_urgency_is_accepted(db: RunDb, urgency: str) -> None:
    async def scenario(session: AsyncSession) -> None:
        unit = await add_test_unit(session)
        sr = sr_row(unit.id, urgency=urgency)
        session.add(sr)
        await session.flush()
        session.add(prediction_row(sr.id, urgency=urgency))
        await session.flush()

    db(scenario)


@pytest.mark.parametrize("subcategory", SUBCATEGORIES)
def test_every_ac_subcategory_is_accepted(db: RunDb, subcategory: str) -> None:
    async def scenario(session: AsyncSession) -> None:
        unit = await add_test_unit(session)
        sr = sr_row(unit.id, category="ac", subcategory=subcategory)
        session.add(sr)
        await session.flush()
        session.add(prediction_row(sr.id, category="ac", subcategory=subcategory))
        await session.flush()

    db(scenario)


# --- Rows that break a rule are refused, with the rule's name in the error ---

REFUSED = [
    # service_requests
    pytest.param(lambda e: sr_row(e.unit.id, category="Plumbing"), "ck_service_requests_category", id="category with a capital"),
    pytest.param(lambda e: sr_row(e.unit.id, category="hvac"), "ck_service_requests_category", id="unknown category"),
    pytest.param(lambda e: sr_row(e.unit.id, urgency="urgent"), "ck_service_requests_urgency", id="unknown urgency"),
    pytest.param(lambda e: sr_row(e.unit.id, language="fr"), "ck_service_requests_language", id="language fr"),
    pytest.param(lambda e: sr_row(e.unit.id, status="done"), "ck_service_requests_status", id="status done"),
    pytest.param(lambda e: sr_row(e.unit.id, subcategory="heating"), "ck_service_requests_subcategory", id="subcategory on carpentry"),
    pytest.param(lambda e: sr_row(e.unit.id, category="ac", subcategory="split_unit"), "ck_service_requests_subcategory", id="unknown ac subcategory"),
    pytest.param(lambda e: sr_row(e.unit.id, closed_at=FAR_FUTURE), "ck_service_requests_closed_at_if_closed", id="closed_at on an open SR"),
    pytest.param(lambda e: sr_row(e.unit.id, status="closed"), "ck_service_requests_closed_at_if_closed", id="closed SR without closed_at"),
    pytest.param(lambda e: sr_row(e.unit.id, status="closed", closed_at=LONG_AGO), "ck_service_requests_closed_after_created", id="closed before created"),
    pytest.param(lambda e: sr_row(e.unit.id, ticket_no="SR-1"), "ck_service_requests_ticket_no_format", id="ticket too short"),
    pytest.param(lambda e: sr_row(e.unit.id, ticket_no="sr-20261031-0001"), "ck_service_requests_ticket_no_format", id="ticket in small letters"),
    pytest.param(lambda e: sr_row(e.unit.id, ticket_no=e.sr.ticket_no), "uq_service_requests_ticket_no", id="duplicate ticket"),
    pytest.param(lambda e: sr_row(999_999), "fk_service_requests_unit_id_units", id="unit that doesn't exist"),
    pytest.param(lambda e: sr_row(e.unit.id, description=None), 'column "description"', id="no description"),
    # users
    pytest.param(lambda e: User(telegram_user_id=2, name=FAKE_NAME, phone="00000000000"), "ck_users_phone_e164", id="phone without +"),
    pytest.param(lambda e: User(telegram_user_id=2, name=FAKE_NAME, phone="+0 000 000 0000"), "ck_users_phone_e164", id="phone with spaces"),
    pytest.param(lambda e: User(telegram_user_id=e.user.telegram_user_id, name=FAKE_NAME, phone=FAKE_PHONE), "uq_users_telegram_user_id", id="duplicate telegram id"),
    # units and compounds
    pytest.param(lambda e: Unit(compound_id=e.unit.compound_id, building="B", unit_number="B-204"), "uq_units_compound_id_unit_number", id="duplicate unit"),
    pytest.param(lambda e: Unit(compound_id=e.unit.compound_id, building="G", unit_number="G-101"), "ck_units_building_letter", id="building G"),
    pytest.param(lambda e: Unit(compound_id=e.unit.compound_id, building="B", unit_number="B-20"), "ck_units_unit_number_format", id="unit with 2 digits"),
    pytest.param(lambda e: Unit(compound_id=e.unit.compound_id, building="B", unit_number="C-204"), "ck_units_unit_number_in_building", id="unit C-204 in building B"),
    pytest.param(lambda e: Compound(name_en="Test Compound", name_ar="اسم آخر"), "uq_compounds_name_en", id="duplicate compound name"),
    # user_units, predictions, messages
    pytest.param(lambda e: UserUnit(user_id=e.user.id, unit_id=e.unit.id), "pk_user_units", id="same user-unit link twice"),
    pytest.param(lambda e: prediction_row(e.sr.id, category_confidence=1.5), "ck_predictions_category_confidence_range", id="confidence above 1"),
    pytest.param(lambda e: prediction_row(e.sr.id, urgency_confidence=-0.1), "ck_predictions_urgency_confidence_range", id="confidence below 0"),
    pytest.param(lambda e: prediction_row(e.sr.id, model_version="2.0.0", category="Plumbing"), "ck_predictions_category", id="prediction with an unknown category"),
    pytest.param(lambda e: prediction_row(e.sr.id), "uq_predictions_sr_id_model_name_model_version", id="same model version answers twice"),
    pytest.param(lambda e: Message(telegram_chat_id=1, role="system", text="Test"), "ck_messages_role", id="message role system"),
]  # fmt: skip


@pytest.mark.parametrize(("make_row", "expected"), REFUSED)
def test_breaking_a_rule_is_refused(
    db: RunDb, make_row: Callable[[Existing], Base], expected: str
) -> None:
    async def scenario(session: AsyncSession) -> None:
        existing = await add_existing_rows(session)
        await assert_insert_refused(session, make_row(existing), expected)

    db(scenario)


def test_a_refused_insert_keeps_the_rest_of_the_test(db: RunDb) -> None:
    """The SAVEPOINT undid only the failed insert: the first unit is still there, and the
    transaction still works (a new query runs). Without it: "current transaction is aborted"."""

    async def scenario(session: AsyncSession) -> None:
        unit = await add_test_unit(session)
        duplicate = Unit(compound_id=unit.compound_id, building="B", unit_number="B-204")
        await assert_insert_refused(session, duplicate, "uq_units_compound_id_unit_number")

        units = await session.scalar(
            select(func.count()).select_from(Unit).where(Unit.compound_id == unit.compound_id)
        )
        assert units == 1

    db(scenario)


def test_a_refused_row_never_reaches_the_log(db: RunDb) -> None:
    """Privacy (Step 2.2, privacy A): Postgres sends the refused row back as DETAIL, with the
    name and phone in it. The raw traceback shows it; our log formatter must not."""
    name, bad_phone = "Test Privacy Name", "0100000000"

    async def scenario(session: AsyncSession) -> None:
        with pytest.raises(IntegrityError) as caught:
            async with session.begin_nested():
                session.add(User(telegram_user_id=3, name=name, phone=bad_phone))
                await session.flush()

        error = caught.value
        raw = "".join(traceback.format_exception(error))
        assert name in raw  # the leak is real: without the formatter, the name would be logged
        exc_info = (type(error), error, error.__traceback__)  # what logger.exception() passes
        record = logging.LogRecord(
            "test", logging.ERROR, __file__, 1, "saving failed", None, exc_info
        )
        line = RedactingFormatter(LOG_FORMAT, secrets=[]).format(record)
        assert name not in line
        assert bad_phone not in line
        assert "ck_users_phone_e164" in line

    db(scenario)


# --- ON DELETE rules (design notes 2.7) ---


def test_deleting_a_user_keeps_their_srs_and_removes_their_links(db: RunDb) -> None:
    async def scenario(session: AsyncSession) -> None:
        existing = await add_existing_rows(session)

        await session.execute(delete(User).where(User.id == existing.user.id))

        user_id = await session.scalar(
            select(ServiceRequest.user_id).where(ServiceRequest.id == existing.sr.id)
        )
        assert user_id is None  # SET NULL: the SR stays for the dashboard (/forget, D8 C)
        assert await count(session, UserUnit) == 0  # CASCADE

    db(scenario)


def test_deleting_an_sr_deletes_its_predictions_and_messages(db: RunDb) -> None:
    async def scenario(session: AsyncSession) -> None:
        existing = await add_existing_rows(session)
        session.add(Message(telegram_chat_id=1, sr_id=existing.sr.id, role="user", text="Test"))
        await session.flush()

        await session.execute(delete(ServiceRequest).where(ServiceRequest.id == existing.sr.id))

        assert await count(session, Prediction) == 0  # CASCADE
        assert await count(session, Message) == 0  # CASCADE

    db(scenario)


def test_a_unit_with_an_sr_cannot_be_deleted(db: RunDb) -> None:
    async def scenario(session: AsyncSession) -> None:
        unit = await add_test_unit(session)
        session.add(sr_row(unit.id))
        await session.flush()

        with pytest.raises(IntegrityError, match="fk_service_requests_unit_id_units"):
            async with session.begin_nested():
                await session.execute(delete(Unit).where(Unit.id == unit.id))

    db(scenario)


def test_a_compound_with_units_cannot_be_deleted(db: RunDb) -> None:
    async def scenario(session: AsyncSession) -> None:
        unit = await add_test_unit(session)

        with pytest.raises(IntegrityError, match="fk_units_compound_id_compounds"):
            async with session.begin_nested():
                await session.execute(delete(Compound).where(Compound.id == unit.compound_id))

    db(scenario)
