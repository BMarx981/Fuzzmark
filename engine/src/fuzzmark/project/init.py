"""Write a starter project JSON file."""

from __future__ import annotations

import json
from pathlib import Path

from .load import ProjectError
from .models import Project, ProjectViewport


def init_project(
    path: str | Path,
    name: str,
    base_url: str,
    viewports: tuple[ProjectViewport, ...] = (),
    overwrite: bool = False,
) -> Project:
    """Write a minimal project JSON file and return the parsed `Project`.

    Raises `ProjectError` if `path` already exists and `overwrite` is False.
    """
    p = Path(path)
    if p.exists() and not overwrite:
        raise ProjectError(f"refusing to overwrite existing file: {p}")

    name = name.strip()
    base_url = base_url.strip()
    if not name:
        raise ProjectError("'name' is required")
    if not base_url:
        raise ProjectError("'base_url' is required")

    project = Project(
        name=name,
        base_url=base_url,
        source_dir=p.parent.resolve(),
        viewports=viewports,
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(project.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return project
