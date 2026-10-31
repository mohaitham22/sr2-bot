"""Tests for app/schemas/labels.py: the labels exist in one place only (Step 2.2 D3 A)."""

from app.schemas import labels
from ml import label_mapping


def test_ml_uses_the_app_labels_not_a_copy() -> None:
    # "is" = the very same object, so ml/ can't drift away from the app's list
    assert label_mapping.CATEGORIES is labels.CATEGORIES
    assert label_mapping.URGENCIES is labels.URGENCIES


def test_ac_subcategories() -> None:
    assert labels.SUBCATEGORIES == ("cooling", "heating", "ventilation")


def test_the_311_mapping_uses_only_known_subcategories() -> None:
    used = {
        result.subcategory
        for result in label_mapping.RULES.values()
        if isinstance(result, label_mapping.Label) and result.subcategory
    }
    assert used <= set(labels.SUBCATEGORIES)
