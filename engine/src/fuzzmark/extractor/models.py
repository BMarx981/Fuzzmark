"""Data models for extracted form fields."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class Validation:
    """Validation metadata read from a control's HTML attributes."""

    required: bool = False
    maxlength: Optional[int] = None
    minlength: Optional[int] = None
    min: Optional[str] = None
    max: Optional[str] = None
    step: Optional[str] = None
    pattern: Optional[str] = None
    accept: Optional[str] = None


@dataclass
class Option:
    """A single option within a select control."""

    value: str
    label: str


@dataclass
class Field:
    """An interactive form control discovered on a page."""

    selector: str
    kind: str
    type: Optional[str]
    name: Optional[str]
    id: Optional[str]
    label: Optional[str]
    validation: Validation
    options: list[Option] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
