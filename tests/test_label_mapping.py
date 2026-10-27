"""Tests for ml/label_mapping.py. Only the rules themselves: no data file needed, so CI can run it."""

from typing import get_args

import pytest

from ml.label_mapping import (
    ANY,
    CATEGORIES,
    RULES,
    URGENCIES,
    Drop,
    DropReason,
    Label,
    UnmappedProblemError,
    map_problem,
)


def test_the_8_categories_and_3_urgencies() -> None:
    # Changing a label list is a project decision (Step 1.8 D5/D6 B, D8 A): this test makes it
    # a conscious one
    assert set(CATEGORIES) == {
        "plumbing",
        "electricity",
        "ac",
        "carpentry",
        "pest_control",
        "gas",
        "appliances",
        "general",
    }
    assert URGENCIES == ("low", "medium", "high")


def test_every_rule_is_well_formed() -> None:
    for key, result in RULES.items():
        assert key[0] != ANY, key  # a rule always names the complaint type
        if isinstance(result, Label):
            assert result.category in CATEGORIES, key
            assert result.urgency in URGENCIES, key
            # sub-labels are only for ac so far (D1 A)
            assert result.subcategory in ("", "heating", "ventilation"), key
            assert (result.subcategory != "") == (result.category == "ac"), key
        else:
            assert isinstance(result, Drop), key
            assert result.reason in get_args(DropReason), key


@pytest.mark.parametrize(
    ("problem", "expected"),
    [
        # the most specific rule wins over the type's default (medium)
        (("PLUMBING", "WATER SUPPLY", "NO WATER"), Label("plumbing", "high")),
        (("PLUMBING", "WATER SUPPLY", "LOW WATER PRESSURE"), Label("plumbing", "medium")),
        (("PLUMBING", "TOILET", "CONTINUOUSLY RUNS"), Label("plumbing", "low")),
        # safety cases
        (("WATER LEAK", "HEAVY FLOW", "AT WALL OR CEILING"), Label("plumbing", "high")),
        (("ELECTRIC", "LIGHTING", "FIXTURE WET OR FLOODED"), Label("electricity", "high")),
        (("UNSANITARY CONDITION", "SEWAGE", "RAW SEWAGE ACCUMULATION"), Label("plumbing", "high")),
        (("PAINT/PLASTER", "CEILING", "COLLAPSING OR FALLING"), Label("general", "high")),
        # ac covers heating and ventilation, with a sub-label (D1 A)
        (("HEAT/HOT WATER", "APARTMENT ONLY", "NO HEAT"), Label("ac", "medium", "heating")),
        (
            ("GENERAL", "VENTILATION SYSTEM", "BROKEN OR MISSING"),
            Label("ac", "medium", "ventilation"),
        ),
        (("HEAT/HOT WATER", "ENTIRE BUILDING", "NO HOT WATER"), Label("plumbing", "medium")),
        # gas vs appliances: gas that doesn't reach the stove is gas; a broken stove is appliances
        (("GENERAL", "COOKING GAS", "SHUT-OFF"), Label("gas", "medium")),
        (("APPLIANCE", "ELECTRIC/GAS RANGE", "NO GAS"), Label("gas", "medium")),
        (
            ("APPLIANCE", "ELECTRIC/GAS RANGE", "NO GAS OR ELECTRICITY"),
            Label("appliances", "medium"),
        ),
        (("APPLIANCE", "REFRIGERATOR", "BROKEN DOOR SEAL"), Label("appliances", "low")),
        # dropped rows
        (("HEAT/HOT WATER", "ENTIRE BUILDING", "NO HEAT AND NO HOT WATER"), Drop("two_categories")),
        (("PLUMBING", "RADIATOR", "CRACKED OR LEAKING"), Drop("not_in_egypt")),
        (("GENERAL", "SIGNAGE MISSING", "FLOOR NUMBER"), Drop("not_maintenance")),
    ],
)
def test_map_problem(problem: tuple[str, str, str], expected: Label | Drop) -> None:
    assert map_problem(*problem) == expected


def test_who_lives_there_does_not_change_the_urgency() -> None:
    # D8 A: the 311 data splits window guards by "child under 11"; our labels must not
    with_child = map_problem("SAFETY", "WINDOW GUARD BROKEN/MISSING", "CHILD UNDER 11")
    without_child = map_problem("SAFETY", "WINDOW GUARD BROKEN/MISSING", "NO CHILD UNDER 11")
    assert with_child == without_child


def test_type_and_descriptor_beat_type_and_details(monkeypatch: pytest.MonkeyPatch) -> None:
    # A fake type, so the real rules don't matter. setitem undoes itself after the test
    monkeypatch.setitem(RULES, ("TEST", ANY, ANY), Label("general", "low"))
    monkeypatch.setitem(RULES, ("TEST", ANY, "DETAIL"), Label("general", "medium"))
    monkeypatch.setitem(RULES, ("TEST", "DESC", ANY), Label("general", "high"))

    assert map_problem("TEST", "DESC", "DETAIL").urgency == "high"
    assert map_problem("TEST", "OTHER", "DETAIL").urgency == "medium"
    assert map_problem("TEST", "OTHER", "OTHER").urgency == "low"


@pytest.mark.parametrize(
    "problem",
    [
        ("NEW TYPE", "SOMETHING", "ELSE"),  # a complaint type we have never seen
        ("GENERAL", "NEW DESCRIPTOR", "N/A"),  # GENERAL has no default on purpose
        ("SAFETY", "NEW DESCRIPTOR", "N/A"),  # SAFETY too
    ],
)
def test_an_unknown_problem_stops_with_its_name(problem: tuple[str, str, str]) -> None:
    with pytest.raises(UnmappedProblemError, match="NEW"):
        map_problem(*problem)
