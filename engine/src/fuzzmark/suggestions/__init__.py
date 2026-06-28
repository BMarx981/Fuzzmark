"""Rule-based fuzzing-value generation keyed off field type and validation metadata."""

from .custom import CustomTablesError, load_custom_tables, merge_tables
from .engine import suggest, suggest_all
from .site import suggest_site
from .models import (
    BOUNDARY,
    CATEGORIES,
    EMPTY,
    FORMAT_INVALID,
    FORMAT_VALID,
    I18N,
    SECURITY,
    TYPE_SPECIFIC,
    Suggestion,
)

__all__ = [
    "suggest",
    "suggest_all",
    "suggest_site",
    "Suggestion",
    "CATEGORIES",
    "EMPTY",
    "BOUNDARY",
    "FORMAT_VALID",
    "FORMAT_INVALID",
    "SECURITY",
    "I18N",
    "TYPE_SPECIFIC",
    "load_custom_tables",
    "merge_tables",
    "CustomTablesError",
]
