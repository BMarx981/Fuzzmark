"""Load and validate a Test JSON file into a `Test` object.

The JSON schema (spec §5.4) is intentionally small and stable so users can
hand-edit tests in any editor. Validation here is the only enforcement; the
runner trusts what it receives.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import (
    CAPTURE,
    FILL,
    INTERACT,
    INTERACT_ACTIONS,
    STEP_KINDS,
    SUBMIT,
    VISIT,
    FlowStep,
    Test,
)


_REQUIRED_BY_KIND: dict[str, frozenset[str]] = {
    VISIT: frozenset({"url"}),
    FILL: frozenset({"selector", "value"}),
    INTERACT: frozenset({"selector", "action"}),
    SUBMIT: frozenset({"selector"}),
    CAPTURE: frozenset({"name"}),
}


def load_test(path: str | Path) -> Test:
    """Read a Test JSON file from disk and return a validated `Test`."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_test(raw)


def parse_test(raw: dict) -> Test:
    """Validate a decoded JSON object and return a `Test`."""
    if not isinstance(raw, dict):
        raise ValueError("test must be a JSON object")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("test must have a non-empty 'name'")
    flow_raw = raw.get("flow")
    if not isinstance(flow_raw, list) or not flow_raw:
        raise ValueError("test must have a non-empty 'flow' list")

    steps = [_parse_step(s, i) for i, s in enumerate(flow_raw)]
    if not any(s.kind == CAPTURE for s in steps):
        raise ValueError("flow must contain at least one 'capture' step")
    if steps[0].kind != VISIT:
        raise ValueError("flow must begin with a 'visit' step")

    names = [s.name for s in steps if s.kind == CAPTURE]
    if len(names) != len(set(names)):
        raise ValueError("capture step names must be unique within a flow")

    return Test(name=name, flow=steps)


def _parse_step(raw: object, idx: int) -> FlowStep:
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

    if kind == INTERACT:
        action = raw["action"]
        if action not in INTERACT_ACTIONS:
            raise ValueError(
                f"step {idx}: unknown action {action!r}; expected one of {list(INTERACT_ACTIONS)}"
            )
        if action == "select_option" and not raw.get("value"):
            raise ValueError(f"step {idx}: 'select_option' requires a 'value'")

    full_page = raw.get("full_page", True)
    if not isinstance(full_page, bool):
        raise ValueError(f"step {idx}: 'full_page' must be a bool")

    return FlowStep(
        kind=kind,
        url=raw.get("url"),
        selector=raw.get("selector"),
        value=raw.get("value"),
        action=raw.get("action"),
        name=raw.get("name"),
        full_page=full_page,
    )
