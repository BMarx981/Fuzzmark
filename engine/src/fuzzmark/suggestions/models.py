"""Data models for generated fuzzing suggestions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


EMPTY = "empty"
BOUNDARY = "boundary"
FORMAT_VALID = "format-valid"
FORMAT_INVALID = "format-invalid"
SECURITY = "security"
I18N = "i18n"
TYPE_SPECIFIC = "type-specific"

CATEGORIES = (EMPTY, BOUNDARY, FORMAT_VALID, FORMAT_INVALID, SECURITY, I18N, TYPE_SPECIFIC)


@dataclass(frozen=True)
class Suggestion:
    """A rule-generated candidate value for a field."""

    category: str
    value: str
    label: str
    field_ref: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def with_field(self, selector: str) -> "Suggestion":
        return Suggestion(self.category, self.value, self.label, selector)
