"""Step 1.7: take a sample of HPD housing complaints from the local NYC 311 export.

Run:  uv run python -m ml.sample_311        (reads 15 GB: a few minutes)

Source: Momo's full export of "311 Service Requests from 2020 to Present" (NYC Open Data,
dataset erm2-nwe9, exported 2026-10-22) in ml/data/raw/. We filter this file instead of
calling the API (Step 1.7 D1 B). The settings below are the whole recipe: the same export and
the same settings give the same two files. A newer export can differ a little, because the
dataset changes every day (late rows, new statuses).

The CSV is read row by row, so memory stays small. Writes, in ml/data/raw/ (git-ignored):
- 311_hpd_sample.csv: about 10% of the HPD rows in the window, 14 columns (D2 A, D3 A).
- 311_hpd_population_counts.csv: ALL HPD rows in the window, counted per complaint type,
  descriptor and additional details. With it we can check that the sample looks like the whole.
The terminal shows only numbers.
"""

import csv
import logging
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.config import ROOT_DIR
from app.logging_setup import setup_logging

logger = logging.getLogger("ml.sample_311")

RAW_DIR = ROOT_DIR / "ml" / "data" / "raw"
SOURCE_CSV = RAW_DIR / "311_Service_Requests_from_2020_to_Present_20261022.csv"
SAMPLE_CSV = RAW_DIR / "311_hpd_sample.csv"
COUNTS_CSV = RAW_DIR / "311_hpd_population_counts.csv"

# --- The filters: the recipe of the sample. Change them here, nowhere else ---
AGENCY = "HPD"  # Housing Preservation & Development, the city's housing agency
START = datetime(2025, 10, 1)  # first day included
END = datetime(2026, 10, 1)  # first day NOT included: 12 full months, Oct 2025 to Sep 2026
SAMPLE_LAST_DIGIT = "7"  # keep rows whose unique_key ends in 7: about 10%, spread over the year
MAX_ROWS = 100_000  # safety cap for the sample file

# Column name in the export (website name) -> stable API field name. Only these are kept (D3 A).
# The website renamed some columns ("formerly ..."); the API names stayed, so later code uses them
COLUMNS = {
    "Unique Key": "unique_key",
    "Created Date": "created_date",
    "Closed Date": "closed_date",
    "Agency": "agency",
    "Problem (formerly Complaint Type)": "complaint_type",
    "Problem Detail (formerly Descriptor)": "descriptor",
    "Additional Details": "descriptor_2",
    "Location Type": "location_type",
    "Incident Zip": "incident_zip",
    "Borough": "borough",
    "Status": "status",
    "Resolution Description": "resolution_description",
    "Resolution Action Updated Date": "resolution_action_updated_date",
    "Open Data Channel Type": "open_data_channel_type",
}
DATE_COLUMNS = {"created_date", "closed_date", "resolution_action_updated_date"}
COUNT_KEYS = ["complaint_type", "descriptor", "descriptor_2"]  # the 3 levels of the problem

# How the export writes dates: 10/21/2026 02:49:57 AM (New York time, no time zone)
DATE_FORMAT = "%m/%d/%Y %I:%M:%S %p"
PROGRESS_EVERY = 2_000_000  # log a line every 2 million rows, so we see it is still working


@dataclass
class Summary:
    """What one run did, in numbers."""

    rows_read: int = 0
    bad_rows: int = 0  # wrong number of fields: skipped
    hpd_in_window: int = 0  # the population: every HPD row in the window
    sample_rows: int = 0
    cut_rows: int = 0  # sample rows NOT written because of MAX_ROWS


def column_positions(header: list[str]) -> dict[str, int]:
    """Map each API name to the position of its column in the export. Stops if one is missing."""
    missing = [name for name in COLUMNS if name not in header]
    if missing:
        raise SystemExit(f"Columns not in the export (renamed again?): {missing}")
    return {api_name: header.index(name) for name, api_name in COLUMNS.items()}


def parse_date(text: str) -> datetime | None:
    """10/21/2026 02:49:57 AM -> datetime. Empty text -> None."""
    return datetime.strptime(text, DATE_FORMAT) if text else None


def to_iso(text: str) -> str:
    """The export's date as ISO 8601 (2026-10-21T02:49:57): sorts correctly, pandas reads it."""
    parsed = parse_date(text)
    return parsed.isoformat() if parsed else ""


def make_sample(
    source: Path, sample_csv: Path, counts_csv: Path, max_rows: int = MAX_ROWS
) -> Summary:
    """Read the export once: count every HPD row in the window, write the sample rows."""
    summary = Summary()
    counts: Counter[tuple[str, ...]] = Counter()
    # Write to a .part file first and rename it at the end: a stopped run never leaves
    # a half sample under the real name
    part = sample_csv.with_name(sample_csv.name + ".part")
    with (
        source.open(encoding="utf-8-sig", newline="") as src,
        part.open("w", encoding="utf-8", newline="") as out,
    ):
        reader = csv.reader(src)
        header = next(reader)
        positions = column_positions(header)
        writer = csv.writer(out)
        writer.writerow(list(positions))  # the API names
        for row in reader:
            summary.rows_read += 1
            if summary.rows_read % PROGRESS_EVERY == 0:
                logger.info("... %s rows read", f"{summary.rows_read:,}")
            if len(row) != len(header):
                summary.bad_rows += 1
                continue
            if row[positions["agency"]] != AGENCY:
                continue
            created = parse_date(row[positions["created_date"]])
            if created is None or not START <= created < END:
                continue

            summary.hpd_in_window += 1
            counts[tuple(row[positions[key]] for key in COUNT_KEYS)] += 1

            if not row[positions["unique_key"]].endswith(SAMPLE_LAST_DIGIT):
                continue
            if summary.sample_rows >= max_rows:
                summary.cut_rows += 1
                continue
            writer.writerow(
                [
                    to_iso(row[i]) if name in DATE_COLUMNS else row[i]
                    for name, i in positions.items()
                ]
            )
            summary.sample_rows += 1
    part.replace(sample_csv)
    write_counts(counts, counts_csv)
    return summary


def write_counts(counts: Counter[tuple[str, ...]], counts_csv: Path) -> None:
    """One row per (complaint_type, descriptor, descriptor_2), biggest first, then A to Z."""
    with counts_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([*COUNT_KEYS, "n"])
        for key, n in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            writer.writerow([*key, n])


def main() -> None:
    setup_logging(secrets=[])  # no secrets here; the same log format as the other scripts
    if not SOURCE_CSV.exists():
        raise SystemExit(f"Export not found: {SOURCE_CSV.relative_to(ROOT_DIR)}")
    size_gb = SOURCE_CSV.stat().st_size / 1e9
    logger.info("Reading %s (%.1f GB) ...", SOURCE_CSV.name, size_gb)
    started = time.perf_counter()

    summary = make_sample(SOURCE_CSV, SAMPLE_CSV, COUNTS_CSV)

    logger.info(
        "Done in %.0f s. Rows read: %s, bad rows: %s. %s rows from %s to %s: %s. Sample: %s",
        time.perf_counter() - started,
        f"{summary.rows_read:,}",
        f"{summary.bad_rows:,}",
        AGENCY,
        START.date(),
        END.date(),
        f"{summary.hpd_in_window:,}",
        f"{summary.sample_rows:,}",
    )
    if summary.cut_rows:
        logger.warning(
            "MAX_ROWS reached: %s sample rows NOT written. The export is newest first, so the "
            "sample misses the oldest months. Raise MAX_ROWS or keep fewer digits.",
            f"{summary.cut_rows:,}",
        )
    logger.info("Wrote %s and %s", SAMPLE_CSV.name, COUNTS_CSV.name)


if __name__ == "__main__":
    main()
