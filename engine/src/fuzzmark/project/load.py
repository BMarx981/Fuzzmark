"""Load and validate a Fuzzmark project JSON file (spec §9).

The schema is intentionally small and stable so projects can be hand-edited
and committed to version control. This loader is the only validator; what
passes it is what the rest of the engine sees.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Project, ProjectViewport


class ProjectError(ValueError):
    """Raised when a project file is missing, unreadable, or malformed."""


_OPTIONAL_STR_FIELDS = ("session", "tables", "scan", "baselines")


def load_project(path: str | Path) -> Project:
    """Read a project JSON file from disk and return a validated `Project`."""
    p = Path(path)
    if not p.exists():
        raise ProjectError(f"project file not found: {p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectError(f"project file is not valid JSON: {p}: {exc}") from exc
    return parse_project(raw, source_dir=p.parent)


def parse_project(raw: object, source_dir: str | Path) -> Project:
    """Validate a decoded JSON object and return a `Project`."""
    if not isinstance(raw, dict):
        raise ProjectError("project must be a JSON object")

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ProjectError("project must have a non-empty 'name'")

    base_url = raw.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        raise ProjectError("project must have a non-empty 'base_url'")

    optional: dict[str, str | None] = {}
    for key in _OPTIONAL_STR_FIELDS:
        v = raw.get(key)
        if v is None:
            optional[key] = None
        elif isinstance(v, str) and v.strip():
            optional[key] = v.strip()
        else:
            raise ProjectError(f"'{key}' must be a non-empty string when present")

    tests = _parse_tests(raw.get("tests"))
    viewports = _parse_viewports(raw.get("viewports"))

    return Project(
        name=name.strip(),
        base_url=base_url.strip(),
        source_dir=Path(source_dir),
        viewports=viewports,
        tests=tests,
        **optional,
    )


def _parse_tests(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ProjectError("'tests' must be a list of path strings when present")
    out: list[str] = []
    for i, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise ProjectError(f"tests[{i}]: must be a non-empty path string")
        out.append(item.strip())
    if len(set(out)) != len(out):
        raise ProjectError("'tests' must not contain duplicate paths")
    return tuple(out)


def _parse_viewports(raw: object) -> tuple[ProjectViewport, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not raw:
        raise ProjectError("'viewports' must be a non-empty list when present")
    parsed: list[ProjectViewport] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ProjectError(f"viewports[{i}]: must be an object")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ProjectError(f"viewports[{i}]: 'name' must be a non-empty string")
        try:
            width = int(item["width"])
            height = int(item["height"])
        except KeyError as exc:
            raise ProjectError(
                f"viewports[{i}]: missing field {exc.args[0]!r}"
            ) from exc
        except (TypeError, ValueError) as exc:
            raise ProjectError(
                f"viewports[{i}]: width/height must be integers"
            ) from exc
        if width <= 0 or height <= 0:
            raise ProjectError(f"viewports[{i}]: width and height must be positive")
        parsed.append(ProjectViewport(name=name.strip(), width=width, height=height))
    names = [v.name for v in parsed]
    if len(set(names)) != len(names):
        raise ProjectError("viewport names must be unique within a project")
    return tuple(parsed)
