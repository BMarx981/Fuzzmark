"""Data models for a flow: ordered steps that drive a single page session.

The Test JSON in spec §5.4 is the source of truth. These dataclasses are the
in-memory mirror of that JSON; the loader in `flow.py` is the only validator.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from ..capture import ConsoleMessage, FailedRequest
from ..compare import MaskRegion


VISIT = "visit"
FILL = "fill"
INTERACT = "interact"
SUBMIT = "submit"
CAPTURE = "capture"

STEP_KINDS = (VISIT, FILL, INTERACT, SUBMIT, CAPTURE)

CLICK = "click"
CHECK = "check"
UNCHECK = "uncheck"
SELECT_OPTION = "select_option"

INTERACT_ACTIONS = (CLICK, CHECK, UNCHECK, SELECT_OPTION)


@dataclass(frozen=True)
class Viewport:
    """A named viewport size to run a flow at."""

    name: str
    width: int
    height: int

    def to_dict(self) -> dict:
        return {"name": self.name, "width": self.width, "height": self.height}


@dataclass(frozen=True)
class FlowStep:
    """One step of a flow. Fields are union-typed by `kind`; the loader validates."""

    kind: str
    url: Optional[str] = None
    selector: Optional[str] = None
    value: Optional[str] = None
    action: Optional[str] = None
    name: Optional[str] = None
    full_page: bool = True
    mask_selectors: tuple[str, ...] = ()
    mask_regions: tuple[MaskRegion, ...] = ()

    def to_dict(self) -> dict:
        out: dict = {"kind": self.kind}
        for attr in ("url", "selector", "value", "action", "name"):
            v = getattr(self, attr)
            if v is not None:
                out[attr] = v
        if self.kind == CAPTURE and not self.full_page:
            out["full_page"] = False
        if self.mask_selectors:
            out["mask_selectors"] = list(self.mask_selectors)
        if self.mask_regions:
            out["mask_regions"] = [r.to_dict() for r in self.mask_regions]
        return out


@dataclass(frozen=True)
class Test:
    """A named flow. Serializes back to the same shape `load_test` accepts."""

    __test__ = False

    name: str
    flow: list[FlowStep]
    viewports: tuple[Viewport, ...] = ()
    session: Optional[str] = None

    def to_dict(self) -> dict:
        out: dict = {"name": self.name, "flow": [s.to_dict() for s in self.flow]}
        if self.viewports:
            out["viewports"] = [v.to_dict() for v in self.viewports]
        if self.session is not None:
            out["session"] = self.session
        return out


@dataclass(frozen=True)
class CaptureArtifact:
    """A screenshot produced by a `capture` step."""

    name: str
    step_index: int
    screenshot_path: str
    masks: tuple[MaskRegion, ...] = ()
    viewport: Optional[str] = None

    def to_dict(self) -> dict:
        out: dict = {
            "name": self.name,
            "step_index": self.step_index,
            "screenshot_path": self.screenshot_path,
            "masks": [m.to_dict() for m in self.masks],
        }
        if self.viewport is not None:
            out["viewport"] = self.viewport
        return out


@dataclass
class RunResult:
    """The output of running one test: per-capture artifacts plus run-wide errors."""

    test_name: str
    captures: list[CaptureArtifact] = field(default_factory=list)
    console_errors: list[ConsoleMessage] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    failed_requests: list[FailedRequest] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.console_errors or self.page_errors or self.failed_requests)

    def to_dict(self) -> dict:
        return asdict(self)
