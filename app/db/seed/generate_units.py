"""Step 1.9: the mock unit registry. A fake list of compounds, buildings and units.

Run:  uv run python -m app.db.seed.generate_units        (less than a second)

We may not use Emaar's real units (CLAUDE.md section 9), so we make our own. Everything here is
fictional: 4 invented compound names (web check on 2026-10-27: no real compound in Egypt uses
them), buildings A to F, and units like B-204 = building B, floor 2, apartment 04.

The sizes are random, but the seed is fixed: the same seed and the same code give the same file
on every run and every machine. Writes app/db/seed/units.csv, which is committed (D2 A). Never
edit the CSV by hand: change this file and run it again. tests/test_generate_units.py checks that
the committed CSV is exactly what this script makes.

Later the CSV is loaded into the Postgres table `units`. The bot checks extracted units against
it, and offers returning users their saved unit ("Is this for Unit B-204?").
The terminal shows only English names: it can't print Arabic.
"""

import csv
import random
from collections import Counter
from dataclasses import astuple, dataclass, fields
from pathlib import Path

from app.config import ROOT_DIR

UNITS_CSV = ROOT_DIR / "app" / "db" / "seed" / "units.csv"

# --- The recipe of the registry. Change it here, nowhere else, then run the script again ---
SEED = 42
# (English, Arabic): residents may write either. English-style names are written in Arabic
# letters, Arabic names in English letters, as in real Egyptian compounds (D3)
COMPOUNDS: list[tuple[str, str]] = [
    ("Olive Ridge", "أوليف ريدج"),
    ("Juniper Bay", "جونيبر باي"),
    ("Bostan El Nada", "بستان الندى"),
    ("Zahret El Loz", "زهرة اللوز"),
]
# Buildings are letters, like the brief's "B-204" (D4 B). Only A to F: no P, which sounds the
# same as B in Egyptian Arabic ("بي")
BUILDING_LETTERS = "ABCDEF"
# (smallest, biggest), both included. The seed picks a number in each range (D5 B)
BUILDINGS_PER_COMPOUND = (3, 6)
FLOORS_PER_BUILDING = (3, 6)
APARTMENTS_PER_FLOOR = (2, 4)  # the same on every floor of one building


@dataclass(frozen=True)
class Unit:
    """One row of the registry. The key is (compound_en, building, unit_number)."""

    compound_en: str
    compound_ar: str
    building: str  # "B"
    unit_number: str  # "B-204"


COLUMNS = [field.name for field in fields(Unit)]  # the CSV header, in this order


def unit_number(building: str, floor: int, apartment: int) -> str:
    """("B", 2, 4) -> "B-204": building, floor, then the apartment as 2 digits."""
    return f"{building}-{floor}{apartment:02d}"


def build_registry(seed: int = SEED) -> list[Unit]:
    """Make every unit. Only the seed decides the sizes; no file is read or written."""
    # Our own generator, not random.seed(): other code that uses `random` can't change our numbers.
    # The order of the randint calls is part of the recipe: change the loops, and the file changes
    rng = random.Random(seed)
    units = []
    for compound_en, compound_ar in COMPOUNDS:
        buildings = BUILDING_LETTERS[: rng.randint(*BUILDINGS_PER_COMPOUND)]
        for building in buildings:
            floors = rng.randint(*FLOORS_PER_BUILDING)
            apartments = rng.randint(*APARTMENTS_PER_FLOOR)
            for floor in range(1, floors + 1):
                for apartment in range(1, apartments + 1):
                    number = unit_number(building, floor, apartment)
                    units.append(Unit(compound_en, compound_ar, building, number))
    return units


def check_registry(units: list[Unit]) -> list[str]:
    """Every broken rule, one line each. An empty list means all good.

    The messages name compounds in English only: the terminal can't print Arabic.
    """
    problems = []
    keys = Counter((unit.compound_en, unit.building, unit.unit_number) for unit in units)
    problems += [f"duplicate key: {' / '.join(key)}" for key, n in keys.items() if n > 1]

    # One Arabic name per compound, and one compound per Arabic name.
    # sorted: a set's order changes from run to run, and the messages must keep one order
    names = sorted({(unit.compound_en, unit.compound_ar) for unit in units})
    arabic_names = Counter(english for english, _ in names)
    problems += [f"{en} has {n} Arabic names" for en, n in arabic_names.items() if n > 1]
    compounds_per_arabic = Counter(arabic for _, arabic in names)
    for arabic, n in compounds_per_arabic.items():
        if n > 1:
            shared = sorted(english for english, other in names if other == arabic)
            problems.append(f"one Arabic name for {n} compounds: {', '.join(shared)}")

    # A unit must start with its own building: "C-204" can't be in building B
    problems += [
        f"{unit.unit_number} is not in building {unit.building} ({unit.compound_en})"
        for unit in units
        if not unit.unit_number.startswith(f"{unit.building}-")
    ]
    return problems


def write_csv(units: list[Unit], path: Path) -> None:
    """Write the registry. A .part file is renamed at the end, like ml/prepare_311.py."""
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    with part.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(astuple(unit) for unit in units)
    part.replace(path)


def main() -> None:
    units = build_registry(SEED)
    problems = check_registry(units)
    if problems:
        raise SystemExit("Registry NOT written:\n" + "\n".join(problems))
    write_csv(units, UNITS_CSV)

    buildings = {(unit.compound_en, unit.building) for unit in units}
    print(
        f"Seed {SEED}: {len(units)} units in {len(buildings)} buildings, {len(COMPOUNDS)} compounds"
    )
    print("Checks passed: no duplicate key, one Arabic name per compound, units match buildings.")
    print(f"\n{'compound':16} {'buildings':>9} {'units':>6}")
    for compound_en, _ in COMPOUNDS:
        n_buildings = sum(1 for compound, _ in buildings if compound == compound_en)
        n_units = sum(1 for unit in units if unit.compound_en == compound_en)
        print(f"{compound_en:16} {n_buildings:9} {n_units:6}")
    print(f"\nWrote {UNITS_CSV.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
