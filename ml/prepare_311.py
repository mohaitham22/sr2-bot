"""Step 1.8: give every row of the 311 HPD sample our category and urgency.

Run:  uv run python -m ml.prepare_311        (a few seconds)

Reads ml/data/raw/311_hpd_sample.csv (Step 1.7) and applies the rules of ml/label_mapping.py.
Writes ml/data/processed/311_mapped.csv (git-ignored): the kept rows, with category, urgency and
subcategory. Dropped rows are only counted. A problem with no rule stops the run, and no file is
written, so a new kind of complaint never gets a label by accident.

The 311 rows have no text written by residents. So this file is a list of real problems with our
labels (the seeds for the Phase 2 synthetic messages), not a training set of sentences.
"""

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from app.config import ROOT_DIR
from ml.label_mapping import CATEGORIES, URGENCIES, Drop, UnmappedProblemError, map_problem

SAMPLE_CSV = ROOT_DIR / "ml" / "data" / "raw" / "311_hpd_sample.csv"
MAPPED_CSV = ROOT_DIR / "ml" / "data" / "processed" / "311_mapped.csv"

PROBLEM_COLUMNS = ["complaint_type", "descriptor", "descriptor_2"]  # the 3 levels of the problem
KEEP_COLUMNS = ["unique_key", "created_date", *PROBLEM_COLUMNS]  # copied from the sample
LABEL_COLUMNS = ["category", "urgency", "subcategory"]  # added by the mapping


@dataclass
class Summary:
    """What one run did, in numbers."""

    rows_read: int = 0
    categories: Counter[str] = field(default_factory=Counter)
    urgencies: Counter[str] = field(default_factory=Counter)
    subcategories: Counter[str] = field(default_factory=Counter)
    dropped: Counter[str] = field(default_factory=Counter)  # per drop reason
    unmapped: set[tuple[str, ...]] = field(default_factory=set)  # problems with no rule

    @property
    def kept(self) -> int:
        return self.categories.total()


def prepare(sample_csv: Path, mapped_csv: Path) -> Summary:
    """Map every row of the sample. Writes mapped_csv only if every problem has a rule."""
    summary = Summary()
    mapped_csv.parent.mkdir(parents=True, exist_ok=True)
    # Write to a .part file first and rename it at the end, like ml/sample_311.py
    part = mapped_csv.with_name(mapped_csv.name + ".part")
    with (
        sample_csv.open(encoding="utf-8", newline="") as src,
        part.open("w", encoding="utf-8", newline="") as out,
    ):
        reader = csv.DictReader(src)
        missing = [name for name in KEEP_COLUMNS if name not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"Columns not in {sample_csv.name}: {missing}")
        writer = csv.DictWriter(out, fieldnames=KEEP_COLUMNS + LABEL_COLUMNS)
        writer.writeheader()
        for row in reader:
            summary.rows_read += 1
            problem = tuple(row[name] for name in PROBLEM_COLUMNS)
            try:
                result = map_problem(*problem)
            except UnmappedProblemError:
                summary.unmapped.add(problem)  # collect them all, then stop (below)
                continue
            if isinstance(result, Drop):
                summary.dropped[result.reason] += 1
                continue
            summary.categories[result.category] += 1
            summary.urgencies[result.urgency] += 1
            if result.subcategory:
                summary.subcategories[result.subcategory] += 1
            writer.writerow(
                {name: row[name] for name in KEEP_COLUMNS}
                | {
                    "category": result.category,
                    "urgency": result.urgency,
                    "subcategory": result.subcategory,
                }
            )
    if summary.unmapped:
        part.unlink()
        return summary
    part.replace(mapped_csv)
    return summary


def print_counts(title: str, counts: Counter[str], order: tuple[str, ...], total: int) -> None:
    """One small table: name, rows, share of `total`. Biggest first."""
    print(f"\n{title:14} {'rows':>7}  share")
    for name in sorted(order, key=lambda name: -counts[name]):
        share = 100 * counts[name] / total if total else 0.0
        print(f"{name:14} {counts[name]:7,}  {share:5.1f}%")


def main() -> None:
    if not SAMPLE_CSV.exists():
        raise SystemExit(f"Sample not found: {SAMPLE_CSV.relative_to(ROOT_DIR)}. Run ml.sample_311")

    summary = prepare(SAMPLE_CSV, MAPPED_CSV)

    if summary.unmapped:
        problems = "\n".join(" / ".join(problem) for problem in sorted(summary.unmapped))
        raise SystemExit(
            f"No rule for {len(summary.unmapped)} problem(s); nothing written. "
            f"Add rules to ml/label_mapping.py:\n{problems}"
        )
    kept = summary.kept
    dropped = summary.dropped.total()
    print(f"Read {summary.rows_read:,} rows: kept {kept:,}, dropped {dropped:,}.")
    print_counts("category", summary.categories, CATEGORIES, kept)
    print_counts("urgency", summary.urgencies, URGENCIES, kept)
    # Share of the ac rows, not of all rows: this is the imbalance of D1 (no cooling in NYC)
    ac_rows = summary.categories["ac"]
    print_counts("ac subcategory", summary.subcategories, tuple(summary.subcategories), ac_rows)
    print("\ndropped:", ", ".join(f"{r} {n:,}" for r, n in summary.dropped.most_common()))
    print(f"\nWrote {MAPPED_CSV.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
