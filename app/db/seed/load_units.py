"""Step 2.2: load the mock unit registry (units.csv) into the tables compounds and units.

Run:  uv run python -m app.db.seed.load_units        (into DATABASE_URL from .env; about 1 s)
      Run `uv run alembic upgrade head` first: the tables must exist.

Safe to run again (idempotent): it inserts only the rows that are missing (ON CONFLICT DO
NOTHING) and never changes or deletes a row, because a unit may already have SRs. Then it checks
that every CSV row is in the database exactly as written. A difference (e.g. a compound's Arabic
name changed in the CSV) stops it, and nothing is saved: everything is one transaction.

units.csv is made by generate_units.py (Step 1.9), never by hand. The messages name compounds in
English only: the terminal can't print Arabic.
"""

import asyncio
import csv
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Compound, Unit
from app.db.seed.generate_units import UNITS_CSV
from app.db.session import database_url, make_engine, make_session_factory
from app.logging_setup import setup_logging


class RegistryMismatchError(Exception):
    """The database has a registry row that differs from units.csv."""


@dataclass(frozen=True)
class LoadResult:
    """How many rows were new, and how many were there already."""

    compounds_new: int
    compounds_existing: int
    units_new: int
    units_existing: int


def read_registry(path: Path = UNITS_CSV) -> list[dict[str, str]]:
    """The CSV rows: compound_en, compound_ar, building, unit_number."""
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


async def load_units(session: AsyncSession, rows: list[dict[str, str]]) -> LoadResult:
    """Insert the compounds and units that are missing, then check them. Doesn't commit."""
    # 1. Compounds. A dict: one Arabic name per English name, in CSV order
    compounds = {row["compound_en"]: row["compound_ar"] for row in rows}
    # ON CONFLICT DO NOTHING: a row that breaks a UNIQUE rule (name_en or name_ar) is skipped
    # instead of failing. RETURNING gives back only the rows really inserted, so we can count them
    inserted = await session.execute(
        insert(Compound)
        .values([{"name_en": en, "name_ar": ar} for en, ar in compounds.items()])
        .on_conflict_do_nothing()
        .returning(Compound.id)
    )
    compounds_new = len(inserted.all())

    # 2. Read the compounds back (we need their ids), and check the names agree with the CSV
    saved = await session.scalars(select(Compound).where(Compound.name_en.in_(compounds)))
    compound_by_name = {compound.name_en: compound for compound in saved}
    for name_en, name_ar in compounds.items():
        if name_en not in compound_by_name:
            raise RegistryMismatchError(
                f"Compound {name_en!r} is not in the database: its Arabic name belongs to "
                "another compound there"
            )
        if compound_by_name[name_en].name_ar != name_ar:
            raise RegistryMismatchError(
                f"Compound {name_en!r} has another Arabic name in the database than in units.csv"
            )

    # 3. Units. UNIQUE (compound_id, unit_number) decides what "already there" means
    inserted = await session.execute(
        insert(Unit)
        .values(
            [
                {
                    "compound_id": compound_by_name[row["compound_en"]].id,
                    "building": row["building"],
                    "unit_number": row["unit_number"],
                }
                for row in rows
            ]
        )
        .on_conflict_do_nothing()
        .returning(Unit.id)
    )
    units_new = len(inserted.all())

    # 4. Check: every CSV unit is in the database, in the right compound and building
    ids = [compound.id for compound in compound_by_name.values()]
    in_db = {
        (unit.compound_id, unit.building, unit.unit_number)
        for unit in await session.scalars(select(Unit).where(Unit.compound_id.in_(ids)))
    }
    missing = [
        row
        for row in rows
        if (compound_by_name[row["compound_en"]].id, row["building"], row["unit_number"])
        not in in_db
    ]
    if missing:
        first = missing[0]
        raise RegistryMismatchError(
            f"{len(missing)} unit(s) of units.csv are not in the database as written, "
            f"e.g. {first['unit_number']} in {first['compound_en']!r}"
        )

    return LoadResult(
        compounds_new=compounds_new,
        compounds_existing=len(compounds) - compounds_new,
        units_new=units_new,
        units_existing=len(rows) - units_new,
    )


async def main() -> None:
    url = database_url()
    setup_logging(secrets=[url.password or ""])
    rows = read_registry()
    engine = make_engine(url, pooled=False)  # a short program: no pool needed
    try:
        async with make_session_factory(engine)() as session:
            result = await load_units(session, rows)
            await session.commit()  # only reached if every check passed
    finally:
        await engine.dispose()

    print(f"Loaded {UNITS_CSV.name} into the database {url.database!r}:")
    print(f"  compounds: {result.compounds_new} new, {result.compounds_existing} already there")
    print(f"  units:     {result.units_new} new, {result.units_existing} already there")


if __name__ == "__main__":
    asyncio.run(main())
