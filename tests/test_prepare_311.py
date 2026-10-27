"""Tests for ml/prepare_311.py. A tiny fake sample in a temporary folder: no real data needed."""

import csv
from collections import Counter
from pathlib import Path

import pytest

from ml.prepare_311 import KEEP_COLUMNS, LABEL_COLUMNS, Summary, prepare, print_counts

# The real sample has 14 columns; one extra column is enough to check that it is not copied
SAMPLE_HEADER = [*KEEP_COLUMNS, "borough"]


def sample_row(key: str, complaint: str, descriptor: str, details: str) -> list[str]:
    """One row as ml/sample_311.py writes it."""
    return [key, "2026-01-15T08:30:00", complaint, descriptor, details, "BROOKLYN"]


def run(
    tmp_path: Path, rows: list[list[str]], header: list[str] = SAMPLE_HEADER
) -> tuple[Summary, Path]:
    """Write a fake sample with these rows, then run prepare on it."""
    sample = tmp_path / "sample.csv"
    with sample.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    mapped = tmp_path / "processed" / "mapped.csv"  # the folder doesn't exist yet
    return prepare(sample, mapped), mapped


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_keeps_mapped_rows_with_labels_and_counts_the_dropped_ones(tmp_path: Path) -> None:
    summary, mapped = run(
        tmp_path,
        [
            sample_row("1007", "PLUMBING", "WATER SUPPLY", "NO WATER"),
            sample_row("1017", "HEAT/HOT WATER", "APARTMENT ONLY", "NO HEAT"),
            sample_row("1027", "HEAT/HOT WATER", "ENTIRE BUILDING", "NO HEAT AND NO HOT WATER"),
            sample_row("1037", "GENERAL", "SIGNAGE MISSING", "FLOOR NUMBER"),
        ],
    )

    assert summary.rows_read == 4
    assert summary.kept == 2
    assert summary.categories == {"plumbing": 1, "ac": 1}
    assert summary.urgencies == {"high": 1, "medium": 1}
    assert summary.subcategories == {"heating": 1}
    assert summary.dropped == {"two_categories": 1, "not_maintenance": 1}
    assert summary.unmapped == set()

    first, second = read_rows(mapped)
    assert list(first) == KEEP_COLUMNS + LABEL_COLUMNS  # "borough" is not copied
    assert first == {
        "unique_key": "1007",
        "created_date": "2026-01-15T08:30:00",
        "complaint_type": "PLUMBING",
        "descriptor": "WATER SUPPLY",
        "descriptor_2": "NO WATER",
        "category": "plumbing",
        "urgency": "high",
        "subcategory": "",
    }
    assert (second["unique_key"], second["category"], second["subcategory"]) == (
        "1017",
        "ac",
        "heating",
    )
    assert not mapped.with_name(mapped.name + ".part").exists()  # renamed at the end


def test_a_problem_with_no_rule_writes_no_file(tmp_path: Path) -> None:
    summary, mapped = run(
        tmp_path,
        [
            sample_row("2007", "PLUMBING", "TOILET", "BOWL STOPPED UP"),  # has a rule
            sample_row("2017", "NEW TYPE", "A", "B"),
            sample_row("2027", "NEW TYPE", "A", "B"),  # the same problem again: listed once
            sample_row("2037", "GENERAL", "NEW DESCRIPTOR", "N/A"),
        ],
    )

    assert summary.unmapped == {("NEW TYPE", "A", "B"), ("GENERAL", "NEW DESCRIPTOR", "N/A")}
    assert not mapped.exists()
    assert not mapped.with_name(mapped.name + ".part").exists()  # the half file is deleted


def test_a_missing_column_stops_with_a_clear_message(tmp_path: Path) -> None:
    header = [name for name in SAMPLE_HEADER if name != "descriptor_2"]

    with pytest.raises(SystemExit, match="descriptor_2"):
        run(tmp_path, [], header=header)


def test_print_counts_biggest_first_and_no_crash_on_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # "medium" is not in the Counter: a Counter gives 0 for a missing name, a dict would crash
    print_counts("urgency", Counter(high=1, low=3), ("low", "medium", "high"), total=4)
    print_counts("ac subcategory", Counter(), (), total=0)  # a file with no ac rows

    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in lines if line] == [
        "urgency",
        "low",
        "high",
        "medium",
        "ac",
    ]
    assert "75.0%" in lines[2]  # low: 3 of 4
