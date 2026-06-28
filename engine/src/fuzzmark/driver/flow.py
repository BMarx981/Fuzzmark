"""Load and validate a Test JSON file into a `Test` object.

The JSON schema (spec §5.4) is intentionally small and stable so users can
hand-edit tests in any editor. Validation here is the only enforcement; the
runner trusts what it receives.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..compare import MaskRegion
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
    Viewport,
)


_VIEWPORT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


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

    viewports = _parse_viewports(raw.get("viewports"))
    session = _parse_session(raw.get("session"))

    return Test(name=name, flow=steps, viewports=viewports, session=session)


def _parse_session(raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("'session' must be a non-empty string path when present")
    return raw.strip()


def _parse_viewports(raw: object) -> tuple[Viewport, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not raw:
        raise ValueError("'viewports' must be a non-empty list when present")
    parsed = tuple(_parse_viewport(v, i) for i, v in enumerate(raw))
    names = [v.name for v in parsed]
    if len(names) != len(set(names)):
        raise ValueError("viewport names must be unique within a test")
    return parsed


def _parse_viewport(raw: object, idx: int) -> Viewport:
    where = f"viewports[{idx}]"
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: must be an object")
    name = raw.get("name")
    if not isinstance(name, str) or not _VIEWPORT_NAME_RE.match(name):
        raise ValueError(
            f"{where}: 'name' must match [A-Za-z0-9][A-Za-z0-9_-]*"
        )
    try:
        width = int(raw["width"])
        height = int(raw["height"])
    except KeyError as exc:
        raise ValueError(f"{where}: missing field {exc.args[0]!r}") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{where}: width/height must be integers") from exc
    if width <= 0 or height <= 0:
        raise ValueError(f"{where}: width and height must be positive")
    return Viewport(name=name, width=width, height=height)


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

    mask_selectors, mask_regions = _parse_masks(raw, idx, kind)

    return FlowStep(
        kind=kind,
        url=raw.get("url"),
        selector=raw.get("selector"),
        value=raw.get("value"),
        action=raw.get("action"),
        name=raw.get("name"),
        full_page=full_page,
        mask_selectors=mask_selectors,
        mask_regions=mask_regions,
    )


def _parse_masks(
    raw: dict, idx: int, kind: str
) -> tuple[tuple[str, ...], tuple[MaskRegion, ...]]:
    selectors = raw.get("mask_selectors")
    regions = raw.get("mask_regions")
    if selectors is None and regions is None:
        return (), ()
    if kind != CAPTURE:
        raise ValueError(
            f"step {idx} ({kind}): 'mask_selectors'/'mask_regions' are only valid on capture steps"
        )

    parsed_selectors: tuple[str, ...] = ()
    if selectors is not None:
        if not isinstance(selectors, list) or not all(
            isinstance(s, str) and s.strip() for s in selectors
        ):
            raise ValueError(
                f"step {idx}: 'mask_selectors' must be a list of non-empty strings"
            )
        parsed_selectors = tuple(s.strip() for s in selectors)

    parsed_regions: tuple[MaskRegion, ...] = ()
    if regions is not None:
        if not isinstance(regions, list):
            raise ValueError(f"step {idx}: 'mask_regions' must be a list")
        parsed_regions = tuple(_parse_region(r, idx, i) for i, r in enumerate(regions))

    return parsed_selectors, parsed_regions


def _parse_region(raw: object, step_idx: int, region_idx: int) -> MaskRegion:
    where = f"step {step_idx} mask_regions[{region_idx}]"
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: must be an object")
    try:
        x = int(raw["x"])
        y = int(raw["y"])
        width = int(raw["width"])
        height = int(raw["height"])
    except KeyError as exc:
        raise ValueError(f"{where}: missing field {exc.args[0]!r}") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{where}: x/y/width/height must be integers") from exc
    if width <= 0 or height <= 0:
        raise ValueError(f"{where}: width and height must be positive")
    source = raw.get("source", "region")
    if not isinstance(source, str) or not source:
        raise ValueError(f"{where}: 'source' must be a non-empty string")
    return MaskRegion(x=x, y=y, width=width, height=height, source=source)
