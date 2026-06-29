"""MobileTest JSON: in-memory dataclasses + loader/validator.

The schema is intentionally small (parallel to web `driver.Test`). Action
vocabulary is constrained to the primitives `simctl` exposes natively, so no
external WebDriverAgent / Appium dependency is required.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


LAUNCH = "launch"
TERMINATE = "terminate"
OPENURL = "openurl"
WAIT = "wait"
CAPTURE = "capture"

STEP_KINDS = (LAUNCH, TERMINATE, OPENURL, WAIT, CAPTURE)

_REQUIRED_BY_KIND: dict[str, frozenset[str]] = {
    LAUNCH: frozenset(),
    TERMINATE: frozenset(),
    OPENURL: frozenset({"url"}),
    WAIT: frozenset({"seconds"}),
    CAPTURE: frozenset({"name"}),
}


@dataclass(frozen=True)
class MobileFlowStep:
    """One step of a mobile flow. Fields are union-typed by `kind`."""

    kind: str
    url: Optional[str] = None
    seconds: Optional[float] = None
    name: Optional[str] = None

    def to_dict(self) -> dict:
        out: dict = {"kind": self.kind}
        for attr in ("url", "seconds", "name"):
            v = getattr(self, attr)
            if v is not None:
                out[attr] = v
        return out


@dataclass(frozen=True)
class MobileTest:
    """A named simulator flow."""

    __test__ = False

    name: str
    flow: list[MobileFlowStep]
    app: Optional[str] = None
    bundle_id: Optional[str] = None
    device: Optional[str] = None
    runtime: Optional[str] = None

    def to_dict(self) -> dict:
        out: dict = {"name": self.name, "flow": [s.to_dict() for s in self.flow]}
        for attr in ("app", "bundle_id", "device", "runtime"):
            v = getattr(self, attr)
            if v is not None:
                out[attr] = v
        return out


@dataclass(frozen=True)
class MobileCaptureArtifact:
    """A screenshot produced by a mobile `capture` step."""

    name: str
    step_index: int
    screenshot_path: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MobileRunResult:
    """The output of running one mobile test: per-capture artifacts + device info."""

    test_name: str
    device_udid: str
    device_name: str
    runtime: str
    bundle_id: Optional[str] = None
    captures: list[MobileCaptureArtifact] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def load_mobile_test(path: str | Path) -> MobileTest:
    """Read a mobile-test JSON file from disk and return a validated `MobileTest`."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_mobile_test(raw)


def parse_mobile_test(raw: dict) -> MobileTest:
    """Validate a decoded JSON object and return a `MobileTest`."""
    if not isinstance(raw, dict):
        raise ValueError("mobile test must be a JSON object")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("mobile test must have a non-empty 'name'")

    app = _parse_optional_str(raw.get("app"), "app")
    bundle_id = _parse_optional_str(raw.get("bundle_id"), "bundle_id")
    if not app and not bundle_id:
        raise ValueError("mobile test must declare 'app' (path to .app) or 'bundle_id'")
    device = _parse_optional_str(raw.get("device"), "device")
    runtime = _parse_optional_str(raw.get("runtime"), "runtime")

    flow_raw = raw.get("flow")
    if not isinstance(flow_raw, list) or not flow_raw:
        raise ValueError("mobile test must have a non-empty 'flow' list")
    steps = [_parse_step(s, i) for i, s in enumerate(flow_raw)]

    if not any(s.kind == CAPTURE for s in steps):
        raise ValueError("flow must contain at least one 'capture' step")
    if steps[0].kind not in (LAUNCH, OPENURL):
        raise ValueError("flow must begin with a 'launch' or 'openurl' step")

    capture_names = [s.name for s in steps if s.kind == CAPTURE]
    if len(capture_names) != len(set(capture_names)):
        raise ValueError("capture step names must be unique within a flow")

    return MobileTest(
        name=name.strip(),
        flow=steps,
        app=app,
        bundle_id=bundle_id,
        device=device,
        runtime=runtime,
    )


def _parse_optional_str(raw: object, field_name: str) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"'{field_name}' must be a non-empty string when present")
    return raw.strip()


def _parse_step(raw: object, idx: int) -> MobileFlowStep:
    if not isinstance(raw, dict):
        raise ValueError(f"step {idx}: must be a JSON object")
    kind = raw.get("kind")
    if kind not in STEP_KINDS:
        raise ValueError(
            f"step {idx}: unknown kind {kind!r}; expected one of {list(STEP_KINDS)}"
        )

    missing = _REQUIRED_BY_KIND[kind] - raw.keys()
    if missing:
        raise ValueError(f"step {idx} ({kind}): missing fields {sorted(missing)}")

    url: str | None = None
    seconds: float | None = None
    name: str | None = None

    if kind == OPENURL:
        url_raw = raw["url"]
        if not isinstance(url_raw, str) or not url_raw.strip():
            raise ValueError(f"step {idx} (openurl): 'url' must be a non-empty string")
        url = url_raw.strip()
    elif kind == WAIT:
        secs_raw = raw["seconds"]
        if isinstance(secs_raw, bool) or not isinstance(secs_raw, (int, float)):
            raise ValueError(f"step {idx} (wait): 'seconds' must be a positive number")
        seconds = float(secs_raw)
        if seconds <= 0:
            raise ValueError(f"step {idx} (wait): 'seconds' must be > 0")
    elif kind == CAPTURE:
        name_raw = raw["name"]
        if not isinstance(name_raw, str) or not name_raw.strip():
            raise ValueError(f"step {idx} (capture): 'name' must be a non-empty string")
        name = name_raw.strip()

    return MobileFlowStep(kind=kind, url=url, seconds=seconds, name=name)
