"""Step 1.8: the label mapping. NYC 311 housing problem -> our category and urgency.

docs/labeling_guide.md explains the rules in words; this file is the same rules as code.
Change a mapping rule HERE, nowhere else: ml/prepare_311.py (and later the synthetic data) read it.
The label names themselves live in app/schemas/labels.py (Step 2.2 D3 A).

A 311 problem has 3 levels: complaint_type / descriptor / descriptor_2, for example
WATER LEAK / HEAVY FLOW / AT WALL OR CEILING. A rule names the 3 levels; ANY matches every value.
The most specific rule wins (see map_problem). A problem with no rule is an error, so a new kind
of complaint in a newer export never gets a label by accident.
"""

from dataclasses import dataclass
from typing import Literal

# Re-export: ml/prepare_311.py, eval/check_test_set.py and the tests import CATEGORIES and
# URGENCIES from here. This file doesn't use them, so "noqa: F401" tells ruff that the unused
# import is on purpose.
from app.schemas.labels import CATEGORIES, URGENCIES, Category, Urgency  # noqa: F401

DropReason = Literal["two_categories", "not_in_egypt", "not_maintenance", "bad_row"]

ANY = "*"  # in a rule: any value at this level


@dataclass(frozen=True)
class Label:
    """Keep the row, with these labels."""

    category: Category
    urgency: Urgency
    subcategory: str = ""  # only ac for now: heating / ventilation (D1 A). Cooling: Phase 2


@dataclass(frozen=True)
class Drop:
    """Leave the row out of our data, for this reason."""

    reason: DropReason


TWO_CATEGORIES = Drop("two_categories")  # one row = two problems in two categories
NOT_IN_EGYPT = Drop("not_in_egypt")  # NYC-only things: radiators, steam pipes, fire escapes
NOT_MAINTENANCE = Drop("not_maintenance")  # paperwork or staff: nothing to repair
BAD_ROW = Drop("bad_row")


class UnmappedProblemError(LookupError):
    """No rule matches this 311 problem: add one to RULES."""


# Urgency (D8 A): only the problem decides, never who lives there or the season.
# high = danger now, or a basic service completely gone; medium = something important doesn't
# work; low = cosmetic or small. When one 311 row mixes two levels ("BROKEN/MISSING/LEAKING"),
# it gets the higher one.
RULES: dict[tuple[str, str, str], Label | Drop] = {
    # --- HEAT/HOT WATER: ac covers heating (D1 A) ---
    ("HEAT/HOT WATER", ANY, "NO HEAT"): Label("ac", "medium", "heating"),
    ("HEAT/HOT WATER", ANY, "HEAT ON IN SUMMER"): Label("ac", "low", "heating"),
    ("HEAT/HOT WATER", ANY, "NO HOT WATER"): Label("plumbing", "medium"),
    ("HEAT/HOT WATER", ANY, "NO HEAT AND NO HOT WATER"): TWO_CATEGORIES,
    # --- UNSANITARY CONDITION ---
    ("UNSANITARY CONDITION", "PESTS", ANY): Label("pest_control", "medium"),
    ("UNSANITARY CONDITION", "MOLD", ANY): Label("general", "medium"),  # D4 A
    ("UNSANITARY CONDITION", "GARBAGE/RECYCLING STORAGE", ANY): Label("general", "low"),
    ("UNSANITARY CONDITION", "GARBAGE/RECYCLING STORAGE", "ACCUMULATION"): Label(
        "general", "medium"
    ),
    ("UNSANITARY CONDITION", "SEWAGE", ANY): Label("plumbing", "high"),
    # --- PLUMBING: medium, unless a rule below says otherwise ---
    ("PLUMBING", ANY, ANY): Label("plumbing", "medium"),
    ("PLUMBING", "WATER SUPPLY", "NO WATER"): Label("plumbing", "high"),  # no water at all
    ("PLUMBING", "WATER SUPPLY", "SCALDING HOT WATER"): Label("plumbing", "high"),  # burns
    ("PLUMBING", "BATHTUB/SHOWER", "LEAKING INTO OTHER APARTMENT"): Label("plumbing", "high"),
    ("PLUMBING", "SEWER", ANY): Label("plumbing", "high"),
    ("PLUMBING", "BASIN/SINK", "BASIN CHIPPED OR RUSTED"): Label("plumbing", "low"),
    ("PLUMBING", "BATHTUB/SHOWER", "CHIPPED OR RUSTED"): Label("plumbing", "low"),
    ("PLUMBING", "TOILET", "BOWL LOOSE OR WOBBLY"): Label("plumbing", "low"),
    ("PLUMBING", "TOILET", "CONTINUOUSLY RUNS"): Label("plumbing", "low"),
    ("PLUMBING", "RADIATOR", ANY): NOT_IN_EGYPT,  # NYC central steam heating
    ("PLUMBING", "STEAM PIPE/RISER", ANY): NOT_IN_EGYPT,
    ("PLUMBING", "BOILER", ANY): NOT_IN_EGYPT,
    # --- WATER LEAK: the size decides ---
    ("WATER LEAK", "HEAVY FLOW", ANY): Label("plumbing", "high"),
    ("WATER LEAK", "SLOW LEAK", ANY): Label("plumbing", "medium"),
    ("WATER LEAK", "DAMP SPOT", ANY): Label("plumbing", "low"),
    # --- PAINT/PLASTER: general (paint and plaster work) ---
    ("PAINT/PLASTER", ANY, ANY): Label("general", "low"),
    ("PAINT/PLASTER", ANY, "COLLAPSING OR FALLING"): Label("general", "high"),  # wall or ceiling
    ("PAINT/PLASTER", "RADIATOR", ANY): NOT_IN_EGYPT,
    # --- DOOR/WINDOW: carpentry = anything that opens, closes or locks (D2 A) ---
    ("DOOR/WINDOW", ANY, ANY): Label("carpentry", "low"),
    ("DOOR/WINDOW", "DOOR", "BROKEN OR MISSING"): Label("carpentry", "medium"),
    ("DOOR/WINDOW", "DOOR", "LOCK BROKEN OR MISSING"): Label("carpentry", "medium"),
    ("DOOR/WINDOW", "DOOR", "NEEDS KEY FOR EXIT"): Label("carpentry", "medium"),
    ("DOOR/WINDOW", "DOOR FRAME", ANY): Label("carpentry", "medium"),
    ("DOOR/WINDOW", "WINDOW PANE", ANY): Label("carpentry", "medium"),  # broken glass
    ("DOOR/WINDOW", "DOOR TO DUMBWAITER", ANY): NOT_IN_EGYPT,
    # --- FLOORING/STAIRS: general, Egyptian floors are mostly tiles (D3 A) ---
    ("FLOORING/STAIRS", ANY, ANY): Label("general", "low"),
    ("FLOORING/STAIRS", "FLOOR", "HOLE IN WALKING AREA"): Label("general", "medium"),
    ("FLOORING/STAIRS", "STAIRS", ANY): Label("general", "medium"),
    ("FLOORING/STAIRS", "STAIRS", "STAIR COVERING TORN OR MISSING"): Label("general", "low"),
    ("FLOORING/STAIRS", "STAIRS", "CONSECUTIVE STEPS BROKEN/MISSING"): Label("general", "high"),
    ("FLOORING/STAIRS", "STAIRS", "STAIRCASE SAGGING OR MISSING"): Label("general", "high"),
    ("FLOORING/STAIRS", "STAIRS", "LANDING PLATFORM MISSING"): Label("general", "high"),
    # --- GENERAL: a mixed group, so no default: every descriptor is named ---
    ("GENERAL", "COOKING GAS", ANY): Label("gas", "medium"),  # gas is off: no danger now (D5)
    ("GENERAL", "BELL/BUZZER/INTERCOM", ANY): Label("electricity", "low"),
    ("GENERAL", "CABINET", ANY): Label("carpentry", "low"),
    ("GENERAL", "CABINET", "FALLING OFF WALL"): Label("carpentry", "medium"),
    ("GENERAL", "VENTILATION SYSTEM", ANY): Label("ac", "medium", "ventilation"),
    ("GENERAL", "MAILBOX", ANY): Label("general", "low"),
    ("GENERAL", "JANITOR/SUPER", ANY): NOT_MAINTENANCE,
    ("GENERAL", "SIGNAGE MISSING", ANY): NOT_MAINTENANCE,  # legal notices on the wall
    # --- ELECTRIC: medium, unless a rule below says otherwise ---
    ("ELECTRIC", ANY, ANY): Label("electricity", "medium"),
    ("ELECTRIC", "WIRING", "EXPOSED"): Label("electricity", "high"),
    ("ELECTRIC", "WIRING", "FRAYED"): Label("electricity", "high"),
    ("ELECTRIC", "LIGHTING", "FIXTURE WET OR FLOODED"): Label("electricity", "high"),
    ("ELECTRIC", "LIGHTING", "FIXTURE SPARKS WHEN TURNED ON"): Label("electricity", "high"),
    ("ELECTRIC", "LIGHTING", "SMOKING OR SPARKING"): Label("electricity", "high"),
    ("ELECTRIC", "POWER OUTAGE", "ENTIRE APARTMENT"): Label("electricity", "high"),
    ("ELECTRIC", "POWER OUTAGE", "ENTIRE BUILDING"): Label("electricity", "high"),
    ("ELECTRIC", "OUTLET/SWITCH", "MISSING COVER PLATE"): Label("electricity", "low"),
    # --- APPLIANCE: appliances (D6 B). Gas that doesn't reach the stove is gas ---
    ("APPLIANCE", ANY, ANY): Label("appliances", "low"),
    ("APPLIANCE", "ELECTRIC/GAS RANGE", "NO GAS"): Label("gas", "medium"),
    ("APPLIANCE", "ELECTRIC/GAS RANGE", "NO GAS OR ELECTRICITY"): Label("appliances", "medium"),
    ("APPLIANCE", "ELECTRIC/GAS RANGE", "PILOT LIGHT OUT"): Label("appliances", "medium"),
    ("APPLIANCE", "ELECTRIC/GAS RANGE", "RANGE/OVEN BROKEN OR MISSING"): Label(
        "appliances", "medium"
    ),
    ("APPLIANCE", "REFRIGERATOR", "BROKEN OR MISSING"): Label("appliances", "medium"),
    # --- SAFETY: a mixed group, so no default ---
    ("SAFETY", "SMOKE DETECTOR", ANY): Label("electricity", "medium"),
    ("SAFETY", "CARBON MONOXIDE DETECTOR", ANY): Label("electricity", "medium"),
    ("SAFETY", "OUTLET COVER", ANY): Label("electricity", "low"),
    ("SAFETY", "SPRINKLER", ANY): Label("plumbing", "medium"),
    # D8 A: a child at home doesn't change the urgency, so both details get the same label
    ("SAFETY", "WINDOW GUARD BROKEN/MISSING", ANY): Label("general", "medium"),
    ("SAFETY", "FIRE ESCAPE", ANY): NOT_IN_EGYPT,
    ("Safety", "Safety", "Safety"): BAD_ROW,  # 1 row in the year; the real type is SAFETY
    # --- ELEVATOR, OUTSIDE BUILDING: general ---
    ("ELEVATOR", ANY, ANY): Label("general", "low"),
    ("OUTSIDE BUILDING", ANY, ANY): Label("general", "low"),
    ("OUTSIDE BUILDING", ANY, "LEAKING"): Label("general", "medium"),  # roof, skylight, hatch
    ("OUTSIDE BUILDING", "PORCH/BALCONY", ANY): Label("general", "high"),  # railing: fall risk
}


def map_problem(complaint_type: str, descriptor: str, descriptor_2: str) -> Label | Drop:
    """The label of one 311 problem. The most specific matching rule wins.

    Order: all 3 levels, then type + descriptor, then type + details, then the type alone.
    Example: PLUMBING / WATER SUPPLY / NO WATER has its own rule (high), so the
    PLUMBING / ANY / ANY default (medium) is not used.
    """
    for key in (
        (complaint_type, descriptor, descriptor_2),
        (complaint_type, descriptor, ANY),
        (complaint_type, ANY, descriptor_2),
        (complaint_type, ANY, ANY),
    ):
        if key in RULES:
            return RULES[key]
    raise UnmappedProblemError(f"No rule for {complaint_type} / {descriptor} / {descriptor_2}")
