"""Pure request handlers for the local HTTP API.

Each route is a function `(payload: dict) -> dict`. They never touch
sockets, so they're trivially callable from tests without a server. The
HTTP layer in `app.py` is a thin adapter that parses JSON, dispatches, and
serializes the response.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..project import (
    ProjectError,
    ProjectViewport,
    init_project,
    load_project,
)


API_VERSION = "0.1.0"


class RouteError(Exception):
    """Raised by a route to signal a non-500 error with an HTTP status."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _health(_: dict) -> dict:
    return {"ok": True, "api_version": API_VERSION}


def _require_str(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RouteError(400, f"{key!r} is required")
    return value.strip()


def _projects_load(payload: dict) -> dict:
    path = _require_str(payload, "path")
    try:
        project = load_project(path)
    except ProjectError as exc:
        raise RouteError(400, str(exc)) from exc
    return _project_payload(path, project)


def _projects_init(payload: dict) -> dict:
    path = _require_str(payload, "path")
    name = _require_str(payload, "name")
    base_url = _require_str(payload, "base_url")
    overwrite = bool(payload.get("force", False))
    viewports = tuple(_parse_viewport(v) for v in payload.get("viewports") or ())
    try:
        project = init_project(
            path,
            name=name,
            base_url=base_url,
            viewports=viewports,
            overwrite=overwrite,
        )
    except ProjectError as exc:
        raise RouteError(400, str(exc)) from exc
    return _project_payload(path, project)


def _parse_viewport(spec: object) -> ProjectViewport:
    if not isinstance(spec, dict):
        raise RouteError(400, "each viewport must be a JSON object")
    try:
        name = str(spec["name"]).strip()
        width = int(spec["width"])
        height = int(spec["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RouteError(
            400, "viewport requires 'name' (str), 'width' (int), 'height' (int)"
        ) from exc
    if not name:
        raise RouteError(400, "viewport 'name' must be non-empty")
    if width <= 0 or height <= 0:
        raise RouteError(400, "viewport width/height must be positive")
    return ProjectViewport(name=name, width=width, height=height)


def _project_payload(path: str, project) -> dict:
    out = project.to_dict()
    out["path"] = str(Path(path).resolve())
    out["resolved"] = {
        "source_dir": str(project.source_dir),
        "session": _path_or_none(project.session_resolved),
        "tables": _path_or_none(project.tables_resolved),
        "scan": _path_or_none(project.scan_resolved),
        "baselines": _path_or_none(project.baselines_resolved),
        "tests": [str(p) for p in project.tests_resolved],
    }
    return out


def _path_or_none(p: Path | None) -> str | None:
    return str(p) if p is not None else None


Route = Callable[[dict], dict]

ROUTES: dict[tuple[str, str], Route] = {
    ("GET", "/api/health"): _health,
    ("POST", "/api/projects/load"): _projects_load,
    ("POST", "/api/projects/init"): _projects_init,
}


def dispatch(method: str, path: str, payload: dict) -> dict:
    """Find and invoke the route for (method, path).

    Raises `RouteError(404)` when no route matches. Route exceptions
    propagate as-is.
    """
    handler = ROUTES.get((method.upper(), path))
    if handler is None:
        raise RouteError(404, f"no route for {method} {path}")
    return handler(payload)
