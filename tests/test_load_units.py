"""Tests for app/db/seed/load_units.py: loading the registry, twice (Step 2.2).

The CSV test needs no database. The others load into the test database inside the db fixture's
transaction, so nothing is kept; skipped without DATABASE_URL.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Compound, Unit
from app.db.seed.load_units import LoadResult, RegistryMismatchError, load_units, read_registry
from tests.conftest import RunDb

REGISTRY = read_registry()


def test_the_csv_has_188_units_in_4_compounds() -> None:
    assert len(REGISTRY) == 188
    assert len({row["compound_en"] for row in REGISTRY}) == 4


def test_loading_twice_adds_nothing_the_second_time(db: RunDb) -> None:
    async def scenario(session: AsyncSession) -> None:
        first = await load_units(session, REGISTRY)
        second = await load_units(session, REGISTRY)

        assert first == LoadResult(
            compounds_new=4, compounds_existing=0, units_new=188, units_existing=0
        )
        assert second == LoadResult(
            compounds_new=0, compounds_existing=4, units_new=0, units_existing=188
        )
        assert await session.scalar(select(func.count()).select_from(Compound)) == 4
        assert await session.scalar(select(func.count()).select_from(Unit)) == 188

    db(scenario)


def test_units_point_to_the_right_compound(db: RunDb) -> None:
    async def scenario(session: AsyncSession) -> None:
        await load_units(session, REGISTRY)

        pairs = await session.execute(
            select(Compound.name_en, Unit.unit_number).join(
                Compound, Unit.compound_id == Compound.id
            )
        )
        saved = {tuple(pair) for pair in pairs}  # a Row behaves like a tuple
        assert saved == {(row["compound_en"], row["unit_number"]) for row in REGISTRY}

    db(scenario)


def test_a_changed_arabic_name_stops_the_load(db: RunDb) -> None:
    async def scenario(session: AsyncSession) -> None:
        await load_units(session, REGISTRY)
        changed = [{**row, "compound_ar": row["compound_ar"] + "x"} for row in REGISTRY]

        with pytest.raises(RegistryMismatchError, match="another Arabic name"):
            await load_units(session, changed)

    db(scenario)


def test_a_renamed_compound_stops_the_load(db: RunDb) -> None:
    """A new English name with an Arabic name that another compound has: refused, not a copy."""

    async def scenario(session: AsyncSession) -> None:
        await load_units(session, REGISTRY)
        first = REGISTRY[0]["compound_en"]
        renamed = [
            {**row, "compound_en": "Renamed Test Compound"} if row["compound_en"] == first else row
            for row in REGISTRY
        ]

        with pytest.raises(RegistryMismatchError, match="not in the database"):
            await load_units(session, renamed)

    db(scenario)
