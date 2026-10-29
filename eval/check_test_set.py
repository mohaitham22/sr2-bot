"""Step 2.1: check the test set before we freeze it.

Run:  uv run python -m eval.check_test_set
      uv run python -m eval.check_test_set --path eval/test_set_original.csv

The test set (eval/test_set.csv) gives our final scores, so every row must follow our own rules:
the labeling guide (category, urgency), design notes section 1 (the clean form of each field) and
the unit registry (app/db/seed/units.csv). This script checks every row and prints each problem,
then the coverage (rows per label, language, tag and field) and the file's SHA-256 hash.
Exit code 1 if there is any problem, so another script can stop on it.

The terminal shows only ids, column names, labels and counts: never a message, a name or a phone
(CLAUDE.md section 9). Momo's terminal can't print Arabic either.
"""

import argparse
import csv
import hashlib
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.config import ROOT_DIR
from app.db.seed.generate_units import UNITS_CSV
from ml.label_mapping import CATEGORIES, URGENCIES

TEST_SET_CSV = ROOT_DIR / "eval" / "test_set.csv"

COLUMNS = [
    "id",
    "text",
    "language",
    "category",
    "urgency",
    "compound",
    "building",
    "unit_number",
    "name",
    "phone",
    "author",
    "notes",
]
LOCATION_AND_CONTACT = ["compound", "building", "unit_number", "name", "phone"]
LANGUAGES = ("ar", "en", "mixed")
AUTHORS = ("ai",)  # ai = Claude (chat). Add a code here when someone else writes rows
# Tags in the notes column, separated by ";". Scores per tag show where the models are weak
TAGS = {
    "franco": "Arabic written in Latin letters and digits (3 = ع, 7 = ح)",
    "arabic_digits": "digits written ٠١٢ instead of 012 (checked against the text)",
    "short_compound": "a short or misspelled compound name (Olive for Olive Ridge)",
    "typo": "spelling mistakes",
    "very_short": "a few words only",
    "long": "a long message with many details",
    "self_correction": "the writer corrects a value (204, sorry, 206)",
    "two_problems": "two problems in one message (labeling guide section 5)",
    "vague": "the problem is unclear; only these rows may have no labels (D5 A)",
    "gas": "about gas",
    "water_heater": "about the water heater (labeling guide: plumbing)",
    "check_guide": "a borderline label, checked against the labeling guide",
}

ID = re.compile(r"T\d{3}")
UNIT = re.compile(r"[A-F]-\d{3}")  # the registry form: B-204 = building B, floor 2, apartment 04
UNIT_DIGITS = re.compile(r"\d{3}")  # only the digits: the message names no building
PHONE = re.compile(r"\+[1-9]\d{6,14}")  # E.164: +, country code, number (design notes 1.7)
EGYPT_MOBILE = re.compile(r"\+20(10|11|12|15)\d{8}")  # Egypt: mobiles only (D1 C)
NAME = re.compile(r"[^\W\d_]+(?:[ '.-]+[^\W\d_]+)*")  # letters, and - ' . between words

# --- Text normalization: so "B١٠٤", "b-104" and "B 104" all look the same to the checks ---
# The same idea as normalize() in eval/score_whisper.py. Not imported from there: that module
# loads the Whisper libraries, which a CSV check doesn't need

EASTERN_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "0123456789" * 2)  # ٢٠٤ -> 204
EASTERN_DIGIT = re.compile("[٠-٩۰-۹]")
TASHKEEL = re.compile("[ً-ْٰـ]")  # short-vowel marks, and tatweel (ـ)
LETTER_FORMS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي"})
PUNCTUATION = re.compile(r"[^\w\s]")  # any language: . , - + and ، ؟ and emoji


def normalize(text: str) -> str:
    """Lowercase, digits 0-9, one spelling for Arabic letters, punctuation -> space."""
    text = text.lower().translate(EASTERN_DIGITS)
    text = TASHKEEL.sub("", text).translate(LETTER_FORMS)
    return " ".join(PUNCTUATION.sub(" ", text).split())


# How a building letter can appear in a message, after normalize() (design notes 1.4):
# the Latin letter, the spoken name of the letter (إيه -> ايه), or the Arabic letter
LETTER_FORMS_IN_TEXT = {
    "A": ("a", "ايه", "ا"),
    "B": ("b", "بي", "ب"),
    "C": ("c", "سي", "ج"),
    "D": ("d", "دي", "د"),
    "E": ("e", "اي", "ه"),
    "F": ("f", "اف"),  # و is not used for F: it also means "and"
}
BUILDING_WORDS = ("عماره", "مبني", "بلوك", "3emara", "building", "bldg", "block")  # 3emara: franco


def letter_in_text(letter: str, normalized_text: str) -> bool:
    """True if the text names building `letter`: right before a number ("b212", "بي 611"),
    or right after a building word ("عماره سي", "building c").

    A letter alone doesn't count: "a" is also an English word.
    """
    for form in LETTER_FORMS_IN_TEXT[letter]:
        before_number = rf"(?<!\w){form} ?\d"
        after_building_word = rf"(?:{'|'.join(BUILDING_WORDS)}) {form}(?!\w)"
        if re.search(before_number, normalized_text) or re.search(
            after_building_word, normalized_text
        ):
            return True
    return False


def number_in_text(number: str, normalized_text: str) -> bool:
    """True if `number` appears as a whole number: 204 counts in "b204", not in "2045"."""
    return re.search(rf"(?<!\d){number}(?!\d)", normalized_text) is not None


def phone_in_text(phone: str, text: str) -> bool:
    """True if the number's digits appear in the text, written with 0, +20 or 0020."""
    digits = re.sub(r"\D", "", text.translate(EASTERN_DIGITS))
    national = phone.removeprefix("+20") if phone.startswith("+20") else phone[1:]
    return national in digits


def is_full_name(name: str) -> bool:
    """Design notes 1.6: at least 2 words, 3-80 characters, letters only (and - ' .)."""
    return NAME.fullmatch(name) is not None and len(name.split()) >= 2 and 3 <= len(name) <= 80


# --- The unit registry, shaped for the checks ---


@dataclass(frozen=True)
class Registry:
    units: dict[str, frozenset[str]]  # compound_en -> its units: {"A-101", "B-204", ...}
    spellings: dict[str, tuple[str, ...]]  # compound_en -> words that name it in a message

    def buildings(self, compound: str) -> set[str]:
        return {unit[0] for unit in self.units[compound]}

    def all_units(self) -> frozenset[str]:
        return frozenset().union(*self.units.values())


# Spellings a resident might use besides the registry names, kept in the test set on purpose
EXTRA_SPELLINGS = {"Juniper Bay": ("juniber",)}  # franco: Arabic has no p, so p -> b


def load_registry(path: Path = UNITS_CSV) -> Registry:
    """Read units.csv. A compound counts as named in a message if the first word of its
    English or Arabic name appears ("olive", "اوليف"): residents shorten names."""
    units: dict[str, set[str]] = {}
    spellings: dict[str, tuple[str, ...]] = {}
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            compound = row["compound_en"]
            units.setdefault(compound, set()).add(row["unit_number"])
            first_words = (normalize(compound).split()[0], normalize(row["compound_ar"]).split()[0])
            spellings[compound] = first_words + EXTRA_SPELLINGS.get(compound, ())
    return Registry({name: frozenset(found) for name, found in units.items()}, spellings)


# --- The checks ---


def read_test_set(path: Path) -> list[dict[str, str]]:
    """The rows as dicts. Stops if the header is not exactly COLUMNS."""
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"the columns must be {COLUMNS}, found {reader.fieldnames!a}")
        return list(reader)


def check_labels(row: dict[str, str], tags: list[str]) -> list[str]:
    category, urgency = row["category"], row["urgency"]
    if not category and not urgency:
        if "vague" in tags:
            return []  # D5 A: too vague for any category, kept for the extraction tests
        return ["category, urgency: empty, but only a row tagged vague may have no labels"]
    problems = []
    if category not in CATEGORIES:
        problems.append(f"category: {category!a} is not one of the 8 categories")
    if urgency not in URGENCIES:
        problems.append(f"urgency: {urgency!a} is not low, medium or high")
    return problems


def check_tags(text: str, tags: list[str]) -> list[str]:
    problems = [f"notes: unknown tag {tag!a}" for tag in tags if tag not in TAGS]
    if len(set(tags)) < len(tags):
        problems.append("notes: a tag appears twice")
    has_eastern_digits = EASTERN_DIGIT.search(text) is not None
    if has_eastern_digits and "arabic_digits" not in tags:
        problems.append("notes: the text has Arabic digits, but no tag arabic_digits")
    if "arabic_digits" in tags and not has_eastern_digits:
        problems.append("notes: tag arabic_digits, but the text has no Arabic digits")
    return problems


def check_location(row: dict[str, str], normalized_text: str, registry: Registry) -> list[str]:
    """compound, building and unit_number: the registry form, in the registry, and in the text."""
    problems = []
    compound, building, unit = row["compound"], row["building"], row["unit_number"]

    if compound and compound not in registry.units:
        problems.append(f"compound: {compound!a} is not in the registry")
        compound = ""  # the checks below can't use it
    elif compound and not any(word in normalized_text for word in registry.spellings[compound]):
        problems.append("compound: not found in the text")

    if building and not re.fullmatch("[A-F]", building):
        problems.append(f"building: {building!a} is not a letter A-F")
        building = ""  # the checks below can't use it
    elif building:
        if compound and building not in registry.buildings(compound):
            problems.append(f"building: {compound} has no building {building}")
        if not letter_in_text(building, normalized_text):
            problems.append(f"building: {building} not found in the text")

    if not unit:
        return problems
    if UNIT.fullmatch(unit):
        if building != unit[0]:  # design notes 1.4: the unit's letter is the building
            problems.append(f"building: must be {unit[0]}, the letter of unit {unit}")
        if compound and unit not in registry.units[compound]:
            problems.append(f"unit_number: {unit} is not in {compound}")
        if not compound and unit not in registry.all_units():
            problems.append(f"unit_number: {unit} is in no compound")
    elif UNIT_DIGITS.fullmatch(unit):
        if building:  # design notes 1.5: 3 digits + a known building -> B-204
            problems.append(f"unit_number: write {building}-{unit}, with the building letter")
        candidates = registry.units[compound] if compound else registry.all_units()
        if not any(known[2:] == unit for known in candidates):
            problems.append(f"unit_number: no unit {unit} in {compound or 'any compound'}")
    else:
        problems.append(f"unit_number: {unit!a} is not like B-204 or 204")
        return problems
    if not number_in_text(unit[-3:], normalized_text):
        problems.append(f"unit_number: {unit[-3:]} not found in the text")
    return problems


def check_contact(row: dict[str, str]) -> list[str]:
    """name and phone: the clean form (design notes 1.6, 1.7), and in the text."""
    problems = []
    name, phone = row["name"], row["phone"]
    if name and not is_full_name(name):
        problems.append("name: not a full name (2+ words, letters only)")
    if name and name not in row["text"]:
        problems.append("name: not found in the text")
    if phone:
        egyptian_but_wrong = phone.startswith("+20") and not EGYPT_MOBILE.fullmatch(phone)
        if not PHONE.fullmatch(phone) or egyptian_but_wrong:
            problems.append("phone: not E.164, like +201XXXXXXXXX")
        elif not phone_in_text(phone, row["text"]):
            problems.append("phone: not found in the text")
    return problems


def check_row(row: dict[str, str], registry: Registry) -> list[str]:
    """Every problem in one row, as "column: what is wrong". An empty list = the row is fine."""
    text = row["text"]
    tags = row["notes"].split(";") if row["notes"] else []
    problems = []
    if not ID.fullmatch(row["id"]):
        problems.append(f"id: {row['id']!a} is not like T001")
    if not text.strip():
        problems.append("text: empty")
    if row["language"] not in LANGUAGES:
        problems.append(f"language: {row['language']!a} is not ar, en or mixed")
    if row["author"] not in AUTHORS:
        problems.append(f"author: {row['author']!a} is not in {AUTHORS}")
    problems += check_labels(row, tags)
    problems += check_tags(text, tags)
    problems += check_location(row, normalize(text), registry)
    problems += check_contact(row)
    return problems


def check_file(rows: list[dict[str, str]], registry: Registry) -> list[tuple[str, str]]:
    """(row id, problem) for every row, plus ids and texts that appear twice."""
    problems: list[tuple[str, str]] = []
    first_id: dict[str, str] = {}  # normalized text -> the id that had it first
    seen_ids: set[str] = set()
    for row in rows:
        row_id = ascii(row["id"])[1:-1]  # safe to print, even if the id has odd characters
        if None in row or None in row.values():  # csv puts extra or missing fields under None
            problems.append((row_id, "row: wrong number of fields (a comma outside quotes?)"))
            continue
        problems += [(row_id, problem) for problem in check_row(row, registry)]
        if row["id"] in seen_ids:
            problems.append((row_id, "id: used twice"))
        seen_ids.add(row["id"])
        key = normalize(row["text"])
        if key in first_id:
            problems.append((row_id, f"text: the same message as {first_id[key]}"))
        first_id.setdefault(key, row_id)
    return problems


# --- Coverage and hash ---


def print_counts(title: str, counts: Counter[str], keys: Sequence[str], total: int) -> None:
    print(f"\n{title}")
    for key in keys:
        print(f"  {key:<16}{counts[key]:>5}{100 * counts[key] / total:>7.1f}%")


def print_coverage(rows: list[dict[str, str]]) -> None:
    total = len(rows)
    print(f"\nRows: {total}")
    categories = Counter(row["category"] or "(none)" for row in rows)
    print_counts("Category", categories, [*CATEGORIES, "(none)"], total)
    urgencies = Counter(row["urgency"] or "(none)" for row in rows)
    print_counts("Urgency", urgencies, [*URGENCIES, "(none)"], total)
    print_counts("Language", Counter(row["language"] for row in rows), LANGUAGES, total)
    print_counts("Author", Counter(row["author"] for row in rows), AUTHORS, total)
    tags = Counter(tag for row in rows for tag in row["notes"].split(";") if tag)
    print_counts("Tag", tags, list(TAGS), total)

    print("\nCategory x urgency")
    print(f"  {'':<16}" + "".join(f"{urgency:>8}" for urgency in URGENCIES))
    pairs = Counter((row["category"], row["urgency"]) for row in rows)
    for category in CATEGORIES:
        print(f"  {category:<16}" + "".join(f"{pairs[category, u]:>8}" for u in URGENCIES))

    fields = Counter(column for row in rows for column in LOCATION_AND_CONTACT if row[column])
    fields["full location"] = sum(
        all(row[c] for c in ("compound", "building", "unit_number")) for row in rows
    )
    fields["no field at all"] = sum(not any(row[c] for c in LOCATION_AND_CONTACT) for row in rows)
    keys = [*LOCATION_AND_CONTACT, "full location", "no field at all"]
    print_counts("Expected fields (rows that have them)", fields, keys, total)


def content_hash(path: Path) -> str:
    """SHA-256 of the file, with Windows line ends (CRLF) read as LF.

    Git on Windows may turn LF into CRLF (core.autocrlf): other bytes, same content. Hashing
    with one kind of line end gives the same fingerprint on every machine.
    """
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the test set (Step 2.1).")
    parser.add_argument("--path", type=Path, default=TEST_SET_CSV, help="the CSV to check")
    args = parser.parse_args(argv)
    try:
        rows = read_test_set(args.path)
    except ValueError as error:
        print(f"Can't check {args.path.name}: {error}")
        return 1

    problems = check_file(rows, load_registry())
    for row_id, problem in problems:
        print(f"{row_id}  {problem}")
    print_coverage(rows)

    per_column = Counter(problem.split(":")[0] for _, problem in problems)
    print(f"\nProblems: {len(problems)} in {len({row_id for row_id, _ in problems})} rows")
    for column, count in per_column.most_common():
        print(f"  {column:<16}{count:>5}")
    print(f"\nSHA-256 (line ends read as LF): {content_hash(args.path)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
