"""Tests for eval/score_whisper.py: normalization, WER/CER, the number check and the usable rule.

All texts, numbers and names here are fake.
"""

import pytest

from eval.score_whisper import (
    Judgment,
    cer,
    edit_distance,
    has_number,
    is_usable,
    normalize,
    number_check,
    transcript_id,
    wer,
)

# --- normalize ---


def test_normalize_arabic_spelling_and_tashkeel() -> None:
    # ة/ه and ى/ي are written both ways; tashkeel and tatweel are removed
    assert normalize("الحنفيه بتنقط فى الحمّام") == normalize("الحنفية بتنقط في الحمام")
    assert normalize("أنا إيه آخر") == "انا ايه اخر"
    assert normalize("مـــيه") == "ميه"  # tatweel (ـ) stretches a word; it is not a letter


def test_normalize_digits_case_and_punctuation() -> None:
    assert normalize("Unit B-204, ٢٠٤؟") == "unit b 204 204"
    assert normalize("  The AC،   is   broken.  ") == "the ac is broken"


# --- edit distance, WER, CER ---


def test_edit_distance_on_letters_and_words() -> None:
    assert edit_distance("kitten", "sitting") == 3  # 2 substitutions + 1 insertion
    assert edit_distance(["a", "b", "c"], ["a", "c"]) == 1  # 1 deletion
    assert edit_distance([], ["x", "y"]) == 2  # 2 insertions


def test_wer_is_zero_when_only_spelling_differs() -> None:
    # Without normalization this would be 2 wrong words out of 4 = 50%
    assert wer("الحنفية بتنقط في الحمام", "الحنفيه بتنقط فى الحمام") == 0.0


def test_wer_counts_word_errors_and_can_pass_one() -> None:
    assert wer("the sink is leaking", "the sink is working") == 0.25
    assert wer("hi", "hi there you all") == 3.0  # 3 extra words / 1 reference word


def test_cer_counts_letters() -> None:
    assert cer("abcd", "abxd") == 0.25


# --- number check (strict, digits only) ---


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("call me on 01912345678", "01912345678"),
        ("call me on 019 1234 5678", "01912345678"),  # groups split by spaces
        ("0 1 9 1 2 3 4 5 6 7 8", "01912345678"),  # said digit by digit
        ("رقمي ٠١٩١٢٣٤٥٦٧٨", "01912345678"),  # Arabic-Indic digits
        ("unit B-204 please", "B-204"),  # only the digits are checked
        ("unit 204 01912345678", "204"),  # two numbers side by side: each is found
        ("unit 204 01912345678", "01912345678"),
        ("building 5, unit 12", "5"),
    ],
)
def test_has_number_finds_the_number(text: str, expected: str) -> None:
    assert has_number(text, expected)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("unit 2045", "5"),  # a digit inside a bigger number is not the number
        ("unit 240", "204"),  # digits swapped
        ("ميتين وأربعة", "204"),  # number in words: the judgment decides, not this check
        ("phone 0191234567", "01912345678"),  # one digit missing
    ],
)
def test_has_number_misses_wrong_or_word_numbers(text: str, expected: str) -> None:
    assert not has_number(text, expected)


def test_number_check_dash_when_not_in_the_note() -> None:
    assert number_check("anything", "") == "-"
    assert number_check("unit 307", "307") == "yes"
    assert number_check("unit 370", "307") == "no"


def test_transcript_id_ignores_spelling_marks() -> None:
    assert transcript_id("الحنفية بتنقط.") == transcript_id("الحنفيه بتنقط")
    assert transcript_id("unit 204") != transcript_id("unit 240")


# --- the usable rule (D3 B) ---


def make_judgment(**changes: str) -> Judgment:
    values = {
        "file": "a.ogg",
        "transcript_id": "abc12345",
        "issue_clear": "yes",
        "compound_ok": "yes",
        "building_ok": "yes",
        "unit_ok": "yes",
        "phone_ok": "yes",
        "reason": "fake",
        "judged_by": "claude",
    }
    return Judgment(**(values | changes))


def test_usable_needs_issue_and_location() -> None:
    assert is_usable(make_judgment())
    assert not is_usable(make_judgment(issue_clear="no"))
    assert not is_usable(make_judgment(unit_ok="no"))
    assert not is_usable(make_judgment(compound_ok="no"))


def test_usable_ignores_phone_and_fields_not_said() -> None:
    assert is_usable(make_judgment(phone_ok="no"))  # D3 B: the phone is scored apart
    assert is_usable(make_judgment(compound_ok="-", building_ok="-", unit_ok="-"))
