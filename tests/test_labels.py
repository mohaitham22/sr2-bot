"""Tests for app/schemas/labels.py: the labels exist in one place only (Step 2.2 D3 A)."""

from app.db import models
from app.schemas import labels
from ml import label_mapping


def test_ml_uses_the_app_labels_not_a_copy() -> None:
    # "is" = the very same object, so ml/ can't drift away from the app's list
    assert label_mapping.CATEGORIES is labels.CATEGORIES
    assert label_mapping.URGENCIES is labels.URGENCIES


def test_database_uses_the_shared_language_and_role_lists() -> None:
    # Step 2.3: the database CHECK rules and the session store read the very same lists
    assert models.LANGUAGES is labels.LANGUAGES
    assert models.MESSAGE_ROLES is labels.MESSAGE_ROLES


def test_language_and_role_values() -> None:
    # Migration 1 writes these lists out in full: a change here needs a new migration
    assert labels.LANGUAGES == ("ar", "en")
    assert labels.MESSAGE_ROLES == ("user", "bot")


def test_ac_subcategories() -> None:
    assert labels.SUBCATEGORIES == ("cooling", "heating", "ventilation")


def test_the_311_mapping_uses_only_known_subcategories() -> None:
    used = {
        result.subcategory
        for result in label_mapping.RULES.values()
        if isinstance(result, label_mapping.Label) and result.subcategory
    }
    assert used <= set(labels.SUBCATEGORIES)
