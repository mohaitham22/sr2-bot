"""Tests for eval/check_test_set.py: text helpers, the row rules, the file checks and the hash.

The rows here are tiny fake test sets: CI never sees the real eval/test_set.csv (git-ignored,
Step 2.1 D6 A). The registry is the real app/db/seed/units.csv. All names and numbers are fake.
"""

import csv
from pathlib import Path

import pytest

from eval.check_test_set import (
    COLUMNS,
    check_file,
    check_row,
    content_hash,
    is_full_name,
    letter_in_text,
    load_registry,
    main,
    normalize,
    number_in_text,
    phone_in_text,
    read_test_set,
)

REGISTRY = load_registry()

# Two rows that follow every rule. Olive Ridge has B-201; Zahret El Loz has E-302
VALID_EN = {
    "id": "T001",
    "text": "The AC is not cooling. Olive Ridge B-201, Sara Mahmoud 01000000001",
    "language": "en",
    "category": "ac",
    "urgency": "medium",
    "compound": "Olive Ridge",
    "building": "B",
    "unit_number": "B-201",
    "name": "Sara Mahmoud",
    "phone": "+201000000001",
    "author": "ai",
    "notes": "",
}
VALID_AR = {
    "id": "T002",
    "text": "الحنفية بتنقط. زهرة اللوز عمارة إي شقة ٣٠٢",
    "language": "ar",
    "category": "plumbing",
    "urgency": "low",
    "compound": "Zahret El Loz",
    "building": "E",
    "unit_number": "E-302",
    "name": "",
    "phone": "",
    "author": "ai",
    "notes": "arabic_digits",
}


def write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


# --- Text helpers ---


def test_normalize_digits_letters_and_punctuation() -> None:
    assert normalize("B١٠٤، شقة!") == "b104 شقه"
    assert normalize("إيه  أ-آ") == "ايه ا ا"


@pytest.mark.parametrize(
    ("letter", "text", "found"),
    [
        ("B", "unit b212", True),  # right before a number
        ("B", "B-204", True),
        ("E", "إي ١٠٧", True),  # the spoken name of the letter
        ("A", "إيه 208", True),
        ("E", "إيه 208", False),  # إيه is A, not E
        ("C", "عمارة سي شقة 3", True),  # right after a building word
        ("C", "عمارة ج", True),
        ("D", "building d", True),
        ("B", "juniper 3emara B", True),  # franco: 3emara = عمارة
        ("A", "a kitchen door", False),  # an English word, not a building
        ("A", "sha2a 812", False),  # franco: the a belongs to sha2a
    ],
)
def test_letter_in_text(letter: str, text: str, found: bool) -> None:
    assert letter_in_text(letter, normalize(text)) is found


def test_number_in_text_needs_a_whole_number() -> None:
    assert number_in_text("204", normalize("unit b204"))
    assert number_in_text("204", normalize("شقة ٢٠٤"))
    assert not number_in_text("204", normalize("2045"))


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("010 0000 0001", True),
        ("+٢٠ ١٠ ٠٠٠٠ ٠٠٠١", True),
        ("0020 100 000 0001", True),
        ("010 0000 0002", False),
    ],
)
def test_phone_in_text(text: str, found: bool) -> None:
    assert phone_in_text("+201000000001", text) is found


@pytest.mark.parametrize(
    ("name", "ok"),
    [("Sara Mahmoud", True), ("سارة محمود", True), ("Mona Abdel-Aziz", True), ("Sara", False)],
)
def test_is_full_name(name: str, ok: bool) -> None:
    assert is_full_name(name) is ok
    assert not is_full_name("Sara 2")


# --- One row ---


@pytest.mark.parametrize("row", [VALID_EN, VALID_AR])
def test_valid_rows_have_no_problems(row: dict[str, str]) -> None:
    assert check_row(row, REGISTRY) == []


def test_vague_row_may_have_no_labels() -> None:
    row = {**VALID_EN, "category": "", "urgency": "", "notes": "vague"}
    assert check_row(row, REGISTRY) == []


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"id": "1"}, "id: '1' is not like T001"),
        ({"language": "fr"}, "language: 'fr'"),
        ({"author": "bob"}, "author: 'bob'"),
        ({"category": "fire"}, "category: 'fire'"),
        ({"urgency": "urgent"}, "urgency: 'urgent'"),
        ({"category": "", "urgency": ""}, "only a row tagged vague may have no labels"),
        ({"notes": "funny"}, "unknown tag 'funny'"),
        ({"notes": "typo;typo"}, "a tag appears twice"),
        ({"notes": "arabic_digits"}, "the text has no Arabic digits"),
        ({"compound": "Lotus Ridge"}, "'Lotus Ridge' is not in the registry"),
        ({"compound": "Bostan El Nada"}, "compound: not found in the text"),  # has B-201 too
        ({"building": "12"}, "building: '12' is not a letter A-F"),
        ({"building": "C"}, "building: must be B, the letter of unit B-201"),
        ({"unit_number": "201"}, "write B-201, with the building letter"),
        ({"unit_number": "B201"}, "'B201' is not like B-204 or 204"),
        ({"unit_number": "B-204"}, "B-204 is not in Olive Ridge"),
        ({"text": VALID_EN["text"].replace("B-201", "201")}, "building: B not found in the text"),
        ({"name": "Sara"}, "name: not a full name"),
        ({"name": "Mona Adel"}, "name: not found in the text"),
        ({"phone": "01000000001"}, "phone: not E.164"),
        ({"phone": "+20223456789"}, "phone: not E.164"),  # an Egyptian landline (D1 C)
        ({"phone": "+201000000002"}, "phone: not found in the text"),
    ],
)
def test_each_rule_finds_its_problem(changes: dict[str, str], expected: str) -> None:
    problems = check_row({**VALID_EN, **changes}, REGISTRY)
    assert any(expected in problem for problem in problems), problems


def test_arabic_digits_need_the_tag() -> None:
    problems = check_row({**VALID_AR, "notes": ""}, REGISTRY)
    assert problems == ["notes: the text has Arabic digits, but no tag arabic_digits"]


# --- The whole file ---


def test_check_file_finds_repeated_ids_and_texts() -> None:
    same_text = {**VALID_EN, "id": "T003", "text": VALID_EN["text"].upper()}  # case doesn't count
    problems = check_file([VALID_EN, VALID_AR, {**VALID_AR}, same_text], REGISTRY)
    assert ("T002", "id: used twice") in problems
    assert ("T002", "text: the same message as T002") in problems
    assert ("T003", "text: the same message as T001") in problems


def test_read_test_set_stops_on_wrong_columns(tmp_path: Path) -> None:
    path = tmp_path / "test_set.csv"
    path.write_text("id,text,category\nT001,hi,ac\n", encoding="utf-8")
    with pytest.raises(ValueError, match="the columns must be"):
        read_test_set(path)


def test_row_with_a_wrong_number_of_fields(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "test_set.csv", [VALID_EN])
    with path.open("a", encoding="utf-8", newline="") as file:
        file.write("T002,a sink, unquoted,en,plumbing,low,,,,,,ai,\n")  # 13 fields, not 12
    problems = check_file(read_test_set(path), REGISTRY)
    assert problems == [("T002", "row: wrong number of fields (a comma outside quotes?)")]


def test_content_hash_ignores_windows_line_ends(tmp_path: Path) -> None:
    lf, crlf = tmp_path / "lf.csv", tmp_path / "crlf.csv"
    lf.write_bytes(b"id,text\nT001,hi\n")
    crlf.write_bytes(b"id,text\r\nT001,hi\r\n")
    assert content_hash(lf) == content_hash(crlf)
    assert len(content_hash(lf)) == 64  # SHA-256 = 64 hex characters


# --- main(): exit code and privacy ---


def test_main_exit_code_and_ascii_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = write_csv(tmp_path / "good.csv", [VALID_EN, VALID_AR])
    assert main(["--path", str(good)]) == 0

    bad = write_csv(tmp_path / "bad.csv", [{**VALID_AR, "name": "سارة محمود"}])
    assert main(["--path", str(bad)]) == 1
    output = capsys.readouterr().out
    assert "T002  name: not found in the text" in output
    # Section 9 + a cp1252 terminal: no message text, no name, nothing but ASCII
    assert output.isascii()
    assert "Sara" not in output
    assert "cooling" not in output
