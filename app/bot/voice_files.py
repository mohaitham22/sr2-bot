"""Where the bot saves test voice notes, and how each file is named (Step 1.5).

Only for our own test recordings with fake data (Step 1.6). In the real flow (Phase 3),
voice notes are transcribed in memory and never saved to disk (CLAUDE.md section 9).
"""

from datetime import date
from pathlib import Path

from app.config import ROOT_DIR

# Git-ignored: audio is personal data and the repo is public
VOICE_DIR = ROOT_DIR / "eval" / "voice" / "raw"

# Bot API limit: bots can download files of up to 20 MB (getFile)
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


def next_voice_path(folder: Path, day: date) -> Path:
    """Reserve a new file name like 2026-10-25_003.ogg (date + number) and return its path.

    The number is 1 higher than the highest number of that day (D1 A).
    The empty file is created right away, so no other handler can take the same name
    before the download fills it. There is no await in here, so asyncio can't switch
    to another task in the middle.
    """
    folder.mkdir(parents=True, exist_ok=True)
    prefix = f"{day.isoformat()}_"
    numbers = [
        int(number)
        for path in folder.glob(f"{prefix}*.ogg")
        # isdecimal(): skip names like 2026-10-25_old.ogg, so int() never fails
        if (number := path.stem.removeprefix(prefix)).isdecimal()
    ]
    path = folder / f"{prefix}{max(numbers, default=0) + 1:03d}.ogg"
    path.touch(exist_ok=False)  # create the empty file; raises an error if it already exists
    return path
