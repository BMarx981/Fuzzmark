"""Fuzzmark project file: a single JSON that bundles base_url, viewports,
session, custom tables, cached scan, baselines directory, and test paths.

See `docs/project-json-schema.md` for the user-facing schema reference.
"""

from .init import init_project
from .load import ProjectError, load_project, parse_project
from .models import Project, ProjectViewport

__all__ = [
    "Project",
    "ProjectError",
    "ProjectViewport",
    "init_project",
    "load_project",
    "parse_project",
]
