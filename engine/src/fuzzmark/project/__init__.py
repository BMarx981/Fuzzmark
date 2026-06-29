"""Fuzzmark project file: a single JSON that bundles base_url, viewports,
session, custom tables, cached scan, baselines directory, and test paths.

See `docs/project-json-schema.md` for the user-facing schema reference.
"""

from .init import init_project
from .load import ProjectError, load_project, parse_project
from .models import Project, ProjectViewport
from .update import add_test_path, set_base_url, set_scan_path

__all__ = [
    "Project",
    "ProjectError",
    "ProjectViewport",
    "add_test_path",
    "init_project",
    "load_project",
    "parse_project",
    "set_base_url",
    "set_scan_path",
]
