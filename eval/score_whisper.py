"""Step 1.6: score every transcript in results.csv against reference.csv.

Run:  uv run python -m eval.score_whisper

Writes, all in eval/voice/:
- scores.csv: automatic scores only (WER, CER, language, number checks), one row per transcript.
- review.md: each reference next to its different transcripts and their judgments, for reading.
Then prints a summary per engine, model and language setting.

"Usable" is a judgment, kept apart in judgments.csv (D9 A): one row per different transcript,
filled by Claude first and checked by Momo. The rule that turns it into usable yes/no is
D3 B (see `is_usable`). The terminal shows only numbers, never transcript text (section 9).
"""

import csv
import hashlib
import re
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from eval.whisper_test import REFERENCE_CSV, RESULTS_CSV, VOICE_DIR

SCORES_CSV = VOICE_DIR / "scores.csv"
JUDGMENTS_CSV = VOICE_DIR / "judgments.csv"
REVIEW_MD = VOICE_DIR / "review.md"

# --- Text normalization: make two texts comparable before we count differences ---

EASTERN_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "0123456789" * 2)  # ٢٠٤ -> 204
TASHKEEL = re.compile("[ً-ْٰـ]")  # short-vowel marks, and tatweel (ـ)
LETTER_FORMS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي"})
PUNCTUATION = re.compile(r"[^\w\s]")  # any language: . , ? - and ، ؛ ؟


def normalize(text: str) -> str:
    """Same digits, no tashkeel, one spelling for letters people write in two ways."""
    text = text.lower().translate(EASTERN_DIGITS)
    text = TASHKEEL.sub("", text).translate(LETTER_FORMS)
    text = PUNCTUATION.sub(" ", text)
    return " ".join(text.split())


def edit_distance(reference: Sequence[str], hypothesis: Sequence[str]) -> int:
    """Fewest substitutions, deletions and insertions that turn hypothesis into reference.

    Works on a list of words (for WER) or on a string, letter by letter (for CER).
    """
    previous = list(range(len(hypothesis) + 1))
    for i, ref_item in enumerate(reference, start=1):
        current = [i]
        for j, hyp_item in enumerate(hypothesis, start=1):
            current.append(
                min(
                    previous[j] + 1,  # deletion: a reference item is missing
                    current[j - 1] + 1,  # insertion: an extra item
                    previous[j - 1] + (ref_item != hyp_item),  # substitution (0 if equal)
                )
            )
        previous = current
    return previous[-1]


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate: word edits / words in the reference. Can be above 1.0."""
    ref_words = normalize(reference).split()
    return edit_distance(ref_words, normalize(hypothesis).split()) / max(len(ref_words), 1)


def cer(reference: str, hypothesis: str) -> float:
    """Character error rate: the same idea letter by letter. Fairer for Arabic spelling."""
    ref = normalize(reference)
    return edit_distance(ref, normalize(hypothesis)) / max(len(ref), 1)


# --- Number check: strict and automatic. Numbers written as words do not count here ---

DIGIT_GROUP = re.compile(r"\d+(?:[\s-]+\d+)*")  # digits, maybe split by spaces or dashes


def has_number(text: str, expected: str) -> bool:
    """True if the digits of `expected` appear in the text as one whole number.

    Parts split by spaces or dashes can join: "019 1234 5678" matches 01912345678.
    Only whole parts join, so building "5" is not found inside "2045".
    """
    want = re.sub(r"\D", "", expected)  # "B-204" -> "204": the letter is judged, not checked
    for group in DIGIT_GROUP.findall(text.translate(EASTERN_DIGITS)):
        parts = re.findall(r"\d+", group)
        for start in range(len(parts)):
            joined = ""
            for part in parts[start:]:
                joined += part
                if joined == want:
                    return True
                if len(joined) >= len(want):
                    break
    return False


def number_check(text: str, expected: str) -> str:
    """Return yes / no, or "-" when the note did not include this field."""
    if not expected.strip():
        return "-"
    return "yes" if has_number(text, expected) else "no"


def transcript_id(text: str) -> str:
    """A short ID for a transcript. Texts that only differ in spelling marks get the same ID."""
    return hashlib.sha1(normalize(text).encode("utf-8")).hexdigest()[:8]


# --- Rows ---


class ScoreRow(BaseModel):
    """Automatic scores of one transcript."""

    file: str
    engine: str
    model: str
    language_setting: str
    language: str  # the real language, from reference.csv
    noise: str
    detected_language: str
    language_ok: bool
    transcript_id: str
    wer: float
    cer: float
    unit_found: str  # yes / no / - : the unit's digits appear in the transcript
    building_found: str
    phone_found: str
    rtf: float


class Judgment(BaseModel):
    """A person's (or Claude's) judgment of one transcript. yes / no, or "-" = not in the note."""

    file: str
    transcript_id: str
    issue_clear: str  # could someone tell what the problem is?
    compound_ok: str
    building_ok: str
    unit_ok: str  # the right number, in digits or in words, with the right letter
    phone_ok: str  # all 11 digits right: scored apart, not part of "usable" (D3 B)
    reason: str
    judged_by: str  # "claude" or "momo"


def is_usable(judgment: Judgment) -> bool:
    """D3 B: the problem is clear, and compound, building and unit are right if they were said."""
    fields = (judgment.compound_ok, judgment.building_ok, judgment.unit_ok)
    return judgment.issue_clear == "yes" and all(value in ("yes", "-") for value in fields)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Sequence[BaseModel]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(type(rows[0]).model_fields))
        writer.writeheader()
        writer.writerows(row.model_dump() for row in rows)


def score_row(result: dict[str, str], reference: dict[str, str]) -> ScoreRow:
    """Compare one results.csv row with its reference.csv row."""
    text = result["transcript"]
    return ScoreRow(
        file=result["file"],
        engine=result["engine"],
        model=result["model"],
        language_setting=result["language_setting"],
        language=reference["language"],
        noise=reference["noise"],
        detected_language=result["detected_language"],
        language_ok=result["detected_language"] == reference["language"],
        transcript_id=transcript_id(text),
        wer=round(wer(reference["text"], text), 3),
        cer=round(cer(reference["text"], text), 3),
        unit_found=number_check(text, reference["expected_unit"]),
        building_found=number_check(text, reference["expected_building"]),
        phone_found=number_check(text, reference["expected_phone"]),
        rtf=float(result["rtf"]),
    )


# --- Outputs ---


def write_review(
    path: Path,
    references: dict[str, dict[str, str]],
    results: list[dict[str, str]],
    scores: list[ScoreRow],
    judgments: dict[tuple[str, str], Judgment],
) -> None:
    """A Markdown file to read in VS Code: each reference, then its different transcripts."""
    lines = ["# Whisper test: transcripts to review (Step 1.6)", ""]
    for file, ref in references.items():
        expected = " · ".join(
            f"{field} `{ref['expected_' + field] or '-'}`"
            for field in ("compound", "building", "unit", "phone")
        )
        lines += [
            f"## {ref['id']} · {file} · {ref['language']} · noise: {ref['noise']}",
            "",
            f"**Reference:** {ref['text']}",
            "",
            f"Expected: {expected} · notes: {ref['notes']}",
            "",
        ]
        seen: dict[str, list[ScoreRow]] = defaultdict(list)  # transcript ID -> rows with it
        texts: dict[str, str] = {}
        for result, score in zip(results, scores, strict=True):
            if score.file == file:
                seen[score.transcript_id].append(score)
                texts[score.transcript_id] = result["transcript"]
        for tid, rows in seen.items():
            made_by = ", ".join(f"{r.model} {r.language_setting}" for r in rows)
            first = rows[0]
            judgment = judgments.get((file, tid))
            verdict = "not judged yet"
            if judgment:
                usable = "usable" if is_usable(judgment) else "NOT usable"
                verdict = (
                    f"**{usable}** · issue {judgment.issue_clear} · compound "
                    f"{judgment.compound_ok} · building {judgment.building_ok} · unit "
                    f"{judgment.unit_ok} · phone {judgment.phone_ok} · by {judgment.judged_by}"
                    f" · {judgment.reason}"
                )
            found = (
                f"unit {first.unit_found}, building {first.building_found}, "
                f"phone {first.phone_found}"
            )
            lines += [
                f"### `{tid}` · {made_by}",
                "",
                f"> {texts[tid]}",
                "",
                f"WER {first.wer:.2f} · CER {first.cer:.2f} · digits found: {found}",
                "",
                f"Judgment: {verdict}",
                "",
            ]
    path.write_text("\n".join(lines), encoding="utf-8")


def percent(values: list[bool]) -> str:
    return f"{100 * sum(values) / len(values):.0f}%" if values else "-"


def mean(values: list[float]) -> str:
    return f"{sum(values) / len(values):.2f}" if values else "-"


def print_summary(scores: list[ScoreRow], judgments: dict[tuple[str, str], Judgment]) -> None:
    """One line per engine + model + setting, as a Markdown table. Numbers only."""
    groups: dict[tuple[str, str, str], list[ScoreRow]] = defaultdict(list)
    for score in scores:
        groups[(score.engine, score.model, score.language_setting)].append(score)

    print(
        "| engine | model | setting | usable ar | usable en | phone ok | WER ar | WER en "
        "| CER ar | language ok | unit digits | RTF mean |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for (engine, model, setting), rows in groups.items():
        judged = [
            (r, judgments[(r.file, r.transcript_id)])
            for r in rows
            if (r.file, r.transcript_id) in judgments
        ]
        usable_ar = [is_usable(j) for r, j in judged if r.language == "ar"]
        usable_en = [is_usable(j) for r, j in judged if r.language == "en"]
        phones = [j.phone_ok == "yes" for _, j in judged if j.phone_ok != "-"]
        units = [r.unit_found == "yes" for r in rows if r.unit_found != "-"]
        print(
            f"| {engine} | {model} | {setting} | {percent(usable_ar)} | {percent(usable_en)} "
            f"| {percent(phones)} "
            f"| {mean([r.wer for r in rows if r.language == 'ar'])} "
            f"| {mean([r.wer for r in rows if r.language == 'en'])} "
            f"| {mean([r.cer for r in rows if r.language == 'ar'])} "
            f"| {percent([r.language_ok for r in rows])} | {percent(units)} "
            f"| {mean([r.rtf for r in rows])} |"
        )


def main() -> None:
    references = {row["file_name"]: row for row in read_csv(REFERENCE_CSV)}
    results = read_csv(RESULTS_CSV)
    scores = [score_row(result, references[result["file"]]) for result in results]
    write_csv(SCORES_CSV, scores)

    judgments: dict[tuple[str, str], Judgment] = {}
    if JUDGMENTS_CSV.exists():
        for row in read_csv(JUDGMENTS_CSV):
            judgment = Judgment(**row)
            judgments[(judgment.file, judgment.transcript_id)] = judgment
    write_review(REVIEW_MD, references, results, scores, judgments)

    unique = {(score.file, score.transcript_id) for score in scores}
    print(f"{len(scores)} transcripts, {len(unique)} different, {len(judgments)} judged.")
    print(f"Wrote {SCORES_CSV.name} and {REVIEW_MD.name} in {VOICE_DIR}.\n")
    print_summary(scores, judgments)


if __name__ == "__main__":
    main()
