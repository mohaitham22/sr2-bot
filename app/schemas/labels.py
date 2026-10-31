"""The labels of a service request, in one place (Step 2.2 D3 A).

docs/labeling_guide.md says when each label is right. This file only lists the allowed values.
Who reads them: the database CHECK rules (app/db/models.py), the 311 mapping (ml/label_mapping.py),
the test-set checker, and later the classifier and the extraction schema (Steps 2.7-2.8).

Changing a label is more than an edit here: the database has CHECK rules with the old list, and
old rows may use the old label. It needs a hand-written migration (CLAUDE.md section 13,
2026-10-31), because Alembic's autogenerate does not see CHECK changes. Change
docs/labeling_guide.md and ml/label_mapping.py in the same PR.

Step 2.3: the language codes and message roles live here too, because the database (CHECK rules)
and the Redis session store (app/memory/session_store.py) must allow the same values. The same
migration rule applies when they change.
"""

from typing import Literal, get_args

# The brief's 6 categories + gas and appliances (Step 1.8 D5/D6 B)
Category = Literal[
    "plumbing", "electricity", "ac", "carpentry", "pest_control", "gas", "appliances", "general"
]
Urgency = Literal["low", "medium", "high"]
# Only for ac, which covers cooling + heating + ventilation (Step 1.8 D1 A). Other categories: none
Subcategory = Literal["cooling", "heating", "ventilation"]
# The language of a request and of the bot's replies (design notes 1.8). Not the test set's
# "mixed": eval/check_test_set.py has its own list for that column.
Language = Literal["ar", "en"]
# Who wrote a message: the resident or the bot (the messages table and the Redis history)
MessageRole = Literal["user", "bot"]

# The same values as tuples, for loops and CHECK rules (get_args reads them out of the Literal)
CATEGORIES: tuple[Category, ...] = get_args(Category)
URGENCIES: tuple[Urgency, ...] = get_args(Urgency)
SUBCATEGORIES: tuple[Subcategory, ...] = get_args(Subcategory)
LANGUAGES: tuple[Language, ...] = get_args(Language)
MESSAGE_ROLES: tuple[MessageRole, ...] = get_args(MessageRole)
