"""Step 2.2: the database tables as Python classes (SQLAlchemy ORM).

The design is docs/design_notes.md section 2 (Step 1.11): 7 tables, their rules, the ON DELETE
rules and the indexes. When a table changes here, change the design notes in the same PR.

These classes only describe the tables. Alembic compares them with the database and writes a
migration (migrations/versions/), and the migration creates or changes the tables. Never change
a table by hand in psql.

The rules the database itself enforces (constraints) are written here too, so wrong data can't
get in even if the Python code has a bug. Every constraint and index gets a fixed name
(NAMING_CONVENTION), so a later migration can find it, and an error says which rule failed.

Personal data (CLAUDE.md section 9): users.name, users.phone, service_requests.description and
messages.text. They have a comment in the database too. Never log a row of these tables.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import ClassVar

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Identity,
    MetaData,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeEngine

from app.schemas.labels import CATEGORIES, SUBCATEGORIES, URGENCIES

# Allowed values of the other text columns (design notes 2.2). Labels: app/schemas/labels.py
LANGUAGES = ("ar", "en")
SR_STATUSES = ("open", "in_progress", "closed")
MESSAGE_ROLES = ("user", "bot")

PERSONAL_DATA = "Personal data (CLAUDE.md section 9): never in logs, traces or git"

# How SQLAlchemy names constraints and indexes. It fills in the %(...)s parts, e.g.
# CheckConstraint(..., name="phone_e164") on the table users -> ck_users_phone_e164
NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
}


class Base(DeclarativeBase):
    """The parent of every table class: the settings they share.

    Plain DeclarativeBase, not MappedAsDataclass: a dataclass would print every column in its
    repr(), so a logged object would show a name or a phone.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Python type -> Postgres type, for each Mapped[...] that doesn't name its own type.
    # ClassVar: a setting of the class, not a column (SQLAlchemy skips ClassVar attributes)
    type_annotation_map: ClassVar[dict[type, TypeEngine]] = {
        str: Text(),  # text: no length limit to guess (Postgres stores varchar(n) the same way)
        datetime: DateTime(timezone=True),  # timestamptz: saved as UTC (design notes 2.8)
        # double precision: 8 bytes like Python's float, so a value comes back exactly as saved.
        # real (4 bytes) would give back 0.87 as 0.8700000047683716 (Step 2.2)
        float: Double(),
    }


def one_of(column: str, values: Sequence[str]) -> str:
    """SQL for a CHECK rule: the column holds one of these values.

    Example: one_of("urgency", URGENCIES) -> "urgency IN ('low', 'medium', 'high')".
    Only for our own constant lists, never for user input (the values are pasted into SQL).
    """
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


def label_checks() -> list[CheckConstraint]:
    """The label rules of service_requests and predictions. A new set for each table.

    Labels are text + CHECK, not a Postgres ENUM (Step 1.11). A label change needs a
    hand-written migration (CLAUDE.md section 13, 2026-10-31).
    """
    return [
        CheckConstraint(one_of("category", CATEGORIES), name="category"),
        CheckConstraint(one_of("urgency", URGENCIES), name="urgency"),
        # Only ac has a subcategory, and there it may be empty too (Step 1.8 D1 A)
        CheckConstraint(
            f"subcategory IS NULL OR (category = 'ac' AND {one_of('subcategory', SUBCATEGORIES)})",
            name="subcategory",
        ),
    ]


# Mapped[str] = NOT NULL, Mapped[str | None] = NULL allowed. Labels are Mapped[str], not
# Mapped[Category]: SQLAlchemy would turn a Literal type into a Postgres ENUM.
# Identity(always=True) = GENERATED ALWAYS AS IDENTITY: Postgres numbers the rows and refuses an
# id from us. Only service_requests uses BY DEFAULT (see there).


class Compound(Base):
    """The 4 fictional compounds of the registry (D6 B). Loaded from app/db/seed/units.csv."""

    __tablename__ = "compounds"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    name_en: Mapped[str] = mapped_column(unique=True)  # "Olive Ridge"
    name_ar: Mapped[str] = mapped_column(unique=True)  # "أوليف ريدج"


class Unit(Base):
    """The 188 units of the mock registry (Step 1.9). Read-only for the bot."""

    __tablename__ = "units"
    __table_args__ = (
        # B-204 exists in two compounds, so a unit number is unique only inside its compound
        UniqueConstraint("compound_id", "unit_number"),
        CheckConstraint("building ~ '^[A-F]$'", name="building_letter"),
        CheckConstraint("unit_number ~ '^[A-F]-[0-9]{3}$'", name="unit_number_format"),
        # building copies the first letter (for the "top buildings" chart), so they must agree
        CheckConstraint("left(unit_number, 1) = building", name="unit_number_in_building"),
    )

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    compound_id: Mapped[int] = mapped_column(ForeignKey("compounds.id", ondelete="RESTRICT"))
    building: Mapped[str]  # "B"
    unit_number: Mapped[str]  # "B-204" = building B, floor 2, apartment 04


class User(Base):
    """A resident's profile. Made at the first "yes" to a summary, not at /start."""

    __tablename__ = "users"
    __table_args__ = (
        # A second safety net: Python checks the full phone rule first (design notes 1.7)
        CheckConstraint(r"phone ~ '^\+[0-9]{7,15}$'", name="phone_e164"),
    )

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    # bigint: Telegram IDs can be bigger than an integer holds (about 2.1 billion)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    name: Mapped[str] = mapped_column(comment=PERSONAL_DATA)  # full name, as written (D2 B)
    phone: Mapped[str] = mapped_column(comment=PERSONAL_DATA)  # E.164: +201XXXXXXXXX (D1 C)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class UserUnit(Base):
    """Which user lives in which unit (many-to-many, design notes 2.4). Saved only after "yes"."""

    __tablename__ = "user_units"

    # The two columns together are the primary key (a composite key): one row per pair
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("units.id", ondelete="RESTRICT"), primary_key=True
    )
    confirmed_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ServiceRequest(Base):
    """One confirmed service request. The dashboard reads mostly this table (through a view)."""

    __tablename__ = "service_requests"
    __table_args__ = (
        *label_checks(),
        CheckConstraint(one_of("language", LANGUAGES), name="language"),
        CheckConstraint(one_of("status", SR_STATUSES), name="status"),
        # SR-YYYYMMDD-NNNN: Cairo date + the id, at least 4 digits (design notes 2.6)
        CheckConstraint("ticket_no ~ '^SR-[0-9]{8}-[0-9]{4,}$'", name="ticket_no_format"),
        # closed_at is set exactly when the SR is closed ...
        CheckConstraint(
            "(status = 'closed') = (closed_at IS NOT NULL)", name="closed_at_if_closed"
        ),
        # ... and never before it was created. NULL >= x is NULL, and NULL passes a CHECK,
        # so open SRs (closed_at NULL) pass this rule
        CheckConstraint("closed_at >= created_at", name="closed_after_created"),
    )

    # BY DEFAULT, not ALWAYS: the app inserts the id it took from the sequence for the ticket
    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    ticket_no: Mapped[str] = mapped_column(unique=True)
    # Empty after /forget (ON DELETE SET NULL, D8 C). Indexed for /status and /forget (D6 A)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # Always a real registry unit (D3 A). Indexed for the "top units" chart (D6 A)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    # The problem in the user's words; "[deleted]" after /forget
    description: Mapped[str] = mapped_column(comment=PERSONAL_DATA)
    language: Mapped[str]
    # The FINAL labels. What each model said is in predictions (design notes 2.5)
    category: Mapped[str]
    subcategory: Mapped[str | None]
    urgency: Mapped[str]
    status: Mapped[str] = mapped_column(server_default="open")
    # When the user confirmed. Indexed for the charts by date (D6 A)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    closed_at: Mapped[datetime | None]


class Prediction(Base):
    """Every model answer for an SR (D7 A): one row per SR per model version."""

    __tablename__ = "predictions"
    __table_args__ = (
        # Starts with sr_id, so its index also serves searches by sr_id: no own index (D6 A)
        UniqueConstraint("sr_id", "model_name", "model_version"),
        *label_checks(),
        CheckConstraint("category_confidence BETWEEN 0 AND 1", name="category_confidence_range"),
        CheckConstraint("urgency_confidence BETWEEN 0 AND 1", name="urgency_confidence_range"),
    )

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    sr_id: Mapped[int] = mapped_column(ForeignKey("service_requests.id", ondelete="CASCADE"))
    model_name: Mapped[str]  # "tfidf_logreg"
    model_version: Mapped[str]  # "1.0.0"
    category: Mapped[str]
    category_confidence: Mapped[float]
    subcategory: Mapped[str | None]
    urgency: Mapped[str]
    urgency_confidence: Mapped[float]
    needs_review: Mapped[bool]  # a confidence below the threshold (set in Phase 4)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Message(Base):
    """The conversation history kept in Postgres. The short-term copy for the LLM is in Redis."""

    __tablename__ = "messages"
    __table_args__ = (CheckConstraint(one_of("role", MESSAGE_ROLES), name="role"),)

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    # No user_id: the first messages come before a profile exists. /forget deletes by chat ID,
    # so it is indexed (D6 A). In a private chat, the chat ID = the user's Telegram ID
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    # Filled when the SR is saved; a message may belong to no SR
    sr_id: Mapped[int | None] = mapped_column(ForeignKey("service_requests.id", ondelete="CASCADE"))
    role: Mapped[str]
    # For a voice note: the confirmed transcript. Audio is never stored
    text: Mapped[str] = mapped_column(comment=PERSONAL_DATA)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
