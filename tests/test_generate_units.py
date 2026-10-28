"""Tests for app/db/seed/generate_units.py: the mock unit registry (Step 1.9)."""

import csv
import re
from dataclasses import asdict
from pathlib import Path

from app.db.seed.generate_units import (
    APARTMENTS_PER_FLOOR,
    BUILDING_LETTERS,
    BUILDINGS_PER_COMPOUND,
    COLUMNS,
    COMPOUNDS,
    FLOORS_PER_BUILDING,
    SEED,
    UNITS_CSV,
    Unit,
    build_registry,
    check_registry,
    unit_number,
    write_csv,
)

# The size that seed 42 gives. If the recipe changes on purpose, update this number together
# with the new units.csv
EXPECTED_UNITS = 188

OLIVE_EN, OLIVE_AR = COMPOUNDS[0]
JUNIPER_EN, JUNIPER_AR = COMPOUNDS[1]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_unit_number() -> None:
    assert unit_number("B", 2, 4) == "B-204"
    assert unit_number("F", 6, 1) == "F-601"


def test_same_seed_same_units_other_seed_other_units() -> None:
    assert build_registry(SEED) == build_registry(SEED)
    assert build_registry(7) != build_registry(SEED)


def test_the_registry_breaks_no_rule() -> None:
    units = build_registry()

    assert check_registry(units) == []
    # The key check once more, without check_registry: a set keeps each key only once
    keys = {(unit.compound_en, unit.building, unit.unit_number) for unit in units}
    assert len(keys) == len(units)


def test_every_unit_has_the_planned_shape() -> None:
    units = build_registry()
    pattern = re.compile(r"([A-Z])-(\d)(\d\d)")  # building, floor, apartment: "B-204"

    assert {(unit.compound_en, unit.compound_ar) for unit in units} == set(COMPOUNDS)
    for unit in units:
        match = pattern.fullmatch(unit.unit_number)
        assert match, unit.unit_number
        building, floor, apartment = match[1], int(match[2]), int(match[3])
        assert building == unit.building
        assert 1 <= floor <= FLOORS_PER_BUILDING[1]
        assert 1 <= apartment <= APARTMENTS_PER_FLOOR[1]
    for compound_en, _ in COMPOUNDS:
        buildings = sorted({unit.building for unit in units if unit.compound_en == compound_en})
        # Buildings start at A with no gap, and their number is in the planned range
        assert "".join(buildings) == BUILDING_LETTERS[: len(buildings)]
        assert BUILDINGS_PER_COMPOUND[0] <= len(buildings) <= BUILDINGS_PER_COMPOUND[1]


def test_the_recipe_fits_the_letters() -> None:
    # More buildings than letters would silently stop at F; P sounds like B in Arabic ("بي")
    assert BUILDINGS_PER_COMPOUND[1] <= len(BUILDING_LETTERS)
    assert "P" not in BUILDING_LETTERS


def test_check_registry_finds_a_duplicate_key() -> None:
    units = [
        Unit(OLIVE_EN, OLIVE_AR, "B", "B-204"),
        Unit(OLIVE_EN, OLIVE_AR, "B", "B-204"),
        Unit(JUNIPER_EN, JUNIPER_AR, "B", "B-204"),  # same unit, other compound: allowed
    ]

    assert check_registry(units) == ["duplicate key: Olive Ridge / B / B-204"]


def test_check_registry_finds_mixed_up_arabic_names() -> None:
    units = [
        Unit(OLIVE_EN, OLIVE_AR, "A", "A-101"),
        Unit(OLIVE_EN, JUNIPER_AR, "A", "A-102"),  # Olive Ridge with a second Arabic name
        Unit(JUNIPER_EN, JUNIPER_AR, "A", "A-101"),
    ]

    problems = check_registry(units)

    assert problems == [
        "Olive Ridge has 2 Arabic names",
        "one Arabic name for 2 compounds: Juniper Bay, Olive Ridge",
    ]
    # English only: the terminal (cp1252) would crash on Arabic in an error message
    assert all(problem.isascii() for problem in problems)


def test_check_registry_finds_a_unit_outside_its_building() -> None:
    units = [Unit(OLIVE_EN, OLIVE_AR, "B", "C-204")]

    assert check_registry(units) == ["C-204 is not in building B (Olive Ridge)"]


def test_write_csv_round_trip(tmp_path: Path) -> None:
    units = build_registry()
    path = tmp_path / "seed" / "units.csv"  # the folder doesn't exist yet

    write_csv(units, path)

    assert read_rows(path) == [asdict(unit) for unit in units]  # Arabic included
    assert not path.with_name(path.name + ".part").exists()  # renamed at the end


def test_the_committed_csv_is_what_the_script_makes() -> None:
    # Golden file: if this fails, the recipe changed. If the change is on purpose, run
    # `uv run python -m app.db.seed.generate_units` and commit the new units.csv
    rows = read_rows(UNITS_CSV)

    assert len(rows) == EXPECTED_UNITS
    assert list(rows[0]) == COLUMNS
    # Compare the values, not the bytes: git may change the line endings (CRLF / LF)
    assert rows == [asdict(unit) for unit in build_registry()]
