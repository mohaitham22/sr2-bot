"""Tests for app/bot/voice_files.py. They use pytest's temporary folder, never eval/voice/raw/."""

from datetime import date
from pathlib import Path

from app.bot.voice_files import next_voice_path

DAY = date(2026, 10, 25)


def test_first_note_of_the_day_is_001(tmp_path: Path) -> None:
    folder = tmp_path / "raw"  # does not exist yet

    path = next_voice_path(folder, DAY)

    assert path == folder / "2026-10-25_001.ogg"
    assert path.exists()  # the name is reserved: an empty file was created
    assert path.stat().st_size == 0


def test_numbers_go_up(tmp_path: Path) -> None:
    names = [next_voice_path(tmp_path, DAY).name for _ in range(3)]

    assert names == ["2026-10-25_001.ogg", "2026-10-25_002.ogg", "2026-10-25_003.ogg"]


def test_next_number_is_highest_plus_one(tmp_path: Path) -> None:
    (tmp_path / "2026-10-25_007.ogg").touch()  # highest number of the day
    (tmp_path / "2026-10-25_old.ogg").touch()  # odd name: skipped
    (tmp_path / "2026-10-24_050.ogg").touch()  # another day: ignored
    (tmp_path / "2026-10-25_099.txt").touch()  # not .ogg: ignored

    assert next_voice_path(tmp_path, DAY).name == "2026-10-25_008.ogg"


def test_new_day_starts_at_001(tmp_path: Path) -> None:
    next_voice_path(tmp_path, DAY)

    assert next_voice_path(tmp_path, date(2026, 10, 26)).name == "2026-10-26_001.ogg"
