"""Tests for ml/sample_311.py. A tiny fake export in a temporary folder: no 15 GB file needed."""

import csv
from pathlib import Path

import pytest

from ml.sample_311 import COLUMNS, Summary, make_sample, to_iso

# The real export has 44 columns; one extra column is enough to check that it is dropped
EXPORT_HEADER = [*COLUMNS, "Incident Address"]

# Dates at the edges of the window [2025-10-01, 2026-10-01)
FIRST_SECOND = "10/01/2025 12:00:00 AM"  # START: included
LAST_SECOND = "09/30/2026 11:59:59 PM"  # just before END: included
AT_END = "10/01/2026 12:00:00 AM"  # END: not included
BEFORE_START = "09/30/2025 11:59:59 PM"  # not included


def export_row(
    key: str,
    created: str,
    agency: str = "HPD",
    complaint: str = "PLUMBING",
    descriptor: str = "WATER LEAK",
    closed: str = "",
) -> list[str]:
    """One row as the export writes it: website column names, US dates."""
    values = dict.fromkeys(EXPORT_HEADER, "")
    values.update(
        {
            "Unique Key": key,
            "Created Date": created,
            "Closed Date": closed,
            "Agency": agency,
            "Problem (formerly Complaint Type)": complaint,
            "Problem Detail (formerly Descriptor)": descriptor,
            "Incident Address": "1 FAKE STREET",
        }
    )
    return [values[name] for name in EXPORT_HEADER]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def run(
    tmp_path: Path, rows: list[list[str]], header: list[str] = EXPORT_HEADER, max_rows: int = 100
) -> Summary:
    """Write a fake export with these rows, then run make_sample on it."""
    export = tmp_path / "export.csv"
    with export.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return make_sample(export, tmp_path / "sample.csv", tmp_path / "counts.csv", max_rows)


def test_keeps_hpd_rows_in_the_window_and_samples_ids_ending_in_7(tmp_path: Path) -> None:
    summary = run(
        tmp_path,
        [
            export_row("1007", FIRST_SECOND, closed="10/02/2025 03:30:00 PM"),  # sample
            export_row("1001", LAST_SECOND),  # population only: ends in 1
            export_row("1017", AT_END),  # outside the window
            export_row("1027", BEFORE_START),  # outside the window
            export_row("1037", FIRST_SECOND, agency="NYPD"),  # not housing
            ["1047", "too", "short"],  # broken row
        ],
    )

    assert summary == Summary(rows_read=6, bad_rows=1, hpd_in_window=2, sample_rows=1)
    [row] = read_rows(tmp_path / "sample.csv")
    assert list(row) == list(COLUMNS.values())  # the 14 API names; the address is dropped
    assert row["unique_key"] == "1007"
    assert row["complaint_type"] == "PLUMBING"
    assert row["created_date"] == "2025-10-01T00:00:00"  # ISO; 12 AM is midnight
    assert row["closed_date"] == "2025-10-02T15:30:00"  # 3:30 PM -> 15:30
    assert row["resolution_action_updated_date"] == ""  # empty stays empty
    assert not (tmp_path / "sample.csv.part").exists()  # renamed at the end


def test_counts_cover_the_whole_population_biggest_first(tmp_path: Path) -> None:
    run(
        tmp_path,
        [
            export_row("2001", FIRST_SECOND, complaint="HEAT/HOT WATER", descriptor="NO HEAT"),
            export_row("2002", FIRST_SECOND),
            export_row("2003", FIRST_SECOND, complaint="HEAT/HOT WATER", descriptor="NO HEAT"),
        ],
    )

    # None of these IDs ends in 7, so the sample is empty, but every row is counted
    assert read_rows(tmp_path / "sample.csv") == []
    assert read_rows(tmp_path / "counts.csv") == [
        {"complaint_type": "HEAT/HOT WATER", "descriptor": "NO HEAT", "descriptor_2": "", "n": "2"},
        {"complaint_type": "PLUMBING", "descriptor": "WATER LEAK", "descriptor_2": "", "n": "1"},
    ]


def test_max_rows_stops_the_sample_and_counts_the_cut_rows(tmp_path: Path) -> None:
    rows = [export_row(key, FIRST_SECOND) for key in ("3007", "3017", "3027")]

    summary = run(tmp_path, rows, max_rows=2)

    assert (summary.sample_rows, summary.cut_rows, summary.hpd_in_window) == (2, 1, 3)
    assert [row["unique_key"] for row in read_rows(tmp_path / "sample.csv")] == ["3007", "3017"]


def test_a_renamed_column_stops_with_a_clear_message(tmp_path: Path) -> None:
    header = [name for name in EXPORT_HEADER if name != "Additional Details"]

    with pytest.raises(SystemExit, match="Additional Details"):
        run(tmp_path, [], header=header)


def test_to_iso() -> None:
    assert to_iso("10/21/2026 02:49:57 PM") == "2026-10-21T14:49:57"
    assert to_iso("01/05/2026 12:30:00 PM") == "2026-01-05T12:30:00"  # 12 PM is noon
    assert to_iso("") == ""
