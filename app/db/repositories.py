"""Step 2.2: database actions, written once (the repository layer).

For now only what Step 2.2 needs: saving a service request with its ticket number.
Phase 3 adds more (find a user by Telegram ID, /status, /forget).

The functions take a session and never commit. The caller decides when the whole unit of work
is done, e.g. the SR and its prediction together: all saved, or nothing.
"""

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServiceRequest
from app.schemas.labels import Category, Subcategory, Urgency

TICKET_PREFIX = "SR"

# One query, two answers from Postgres (design notes 2.6):
# - nextval(): the next number of the id sequence. Postgres gives every caller a different
#   number, even two callers at the same moment, and never gives a number back, so two SRs can
#   never get the same id (and so never the same ticket). A failed insert leaves a gap.
# - now() is the start time of the current transaction, so the INSERT that follows in the same
#   transaction gets the same created_at. The ticket date is always the Cairo date of created_at.
# - The Cairo date comes from Postgres, which has its own time-zone data. Python on Windows has
#   none without the tzdata package. Cairo has summer time, so never add a fixed "+2".
NEXT_ID_AND_CAIRO_DATE = text(
    "SELECT nextval(pg_get_serial_sequence('service_requests', 'id')) AS id,"
    " (now() AT TIME ZONE 'Africa/Cairo')::date AS cairo_date"
)


def make_ticket_no(cairo_date: date, sr_id: int) -> str:
    """The ticket number SR-YYYYMMDD-NNNN (design notes 2.6, D5 B).

    NNNN = the SR's id with zeros in front, up to 4 digits. A bigger id is kept whole:
        make_ticket_no(date(2026, 10, 31), 42)    -> "SR-20261031-0042"
        make_ticket_no(date(2026, 10, 31), 10342) -> "SR-20261031-10342"
    """
    if sr_id < 1:
        raise ValueError(f"sr_id must be 1 or more, not {sr_id}")
    return f"{TICKET_PREFIX}-{cairo_date:%Y%m%d}-{sr_id:04d}"


async def create_service_request(
    session: AsyncSession,
    *,
    unit_id: int,
    user_id: int | None,
    description: str,
    language: str,
    category: Category,
    subcategory: Subcategory | None,
    urgency: Urgency,
) -> ServiceRequest:
    """Add a new SR with its ticket number to the session. The caller commits.

    The SR is sent to the database at once (flush), so the CHECK and foreign key rules run
    here: a wrong value raises sqlalchemy.exc.IntegrityError now, not later at the commit.
    status ("open") and created_at (now) come from the database defaults; SQLAlchemy reads
    them back in the same INSERT (RETURNING), so sr.created_at works without another query.
    """
    row = (await session.execute(NEXT_ID_AND_CAIRO_DATE)).one()
    sr = ServiceRequest(
        id=row.id,  # the number we took, so the ticket and the id always agree
        ticket_no=make_ticket_no(row.cairo_date, row.id),
        unit_id=unit_id,
        user_id=user_id,
        description=description,
        language=language,
        category=category,
        subcategory=subcategory,
        urgency=urgency,
    )
    session.add(sr)
    await session.flush()  # send the INSERT now (inside the transaction), don't commit
    return sr
