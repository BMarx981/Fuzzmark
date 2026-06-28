"""Data models for a Fuzzmark project (spec §9).

A project bundles the bits that the CLI otherwise threads through as loose
flags: base URL, viewports, paths to the session/custom tables/scan map,
the baselines directory, and the list of tests that belong to it. All path
fields are stored as the user wrote them (potentially relative); the
`*_resolved` properties resolve them against the directory containing the
project file so the bundle is portable across machines.

Browser-free by construction — the loader and these models do not import
extractor, driver, or capture.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ProjectViewport:
    """A named viewport entry in a project file."""

    name: str
    width: int
    height: int

    def to_dict(self) -> dict:
        return {"name": self.name, "width": self.width, "height": self.height}


@dataclass(frozen=True)
class Project:
    """A Fuzzmark project loaded from disk."""

    name: str
    base_url: str
    source_dir: Path
    viewports: tuple[ProjectViewport, ...] = ()
    session: Optional[str] = None
    tables: Optional[str] = None
    scan: Optional[str] = None
    baselines: Optional[str] = None
    tests: tuple[str, ...] = ()

    @property
    def session_resolved(self) -> Optional[Path]:
        return self._resolve(self.session)

    @property
    def tables_resolved(self) -> Optional[Path]:
        return self._resolve(self.tables)

    @property
    def scan_resolved(self) -> Optional[Path]:
        return self._resolve(self.scan)

    @property
    def baselines_resolved(self) -> Optional[Path]:
        return self._resolve(self.baselines)

    @property
    def tests_resolved(self) -> tuple[Path, ...]:
        return tuple(self._resolve_str(t) for t in self.tests)

    def _resolve(self, p: Optional[str]) -> Optional[Path]:
        return None if p is None else self._resolve_str(p)

    def _resolve_str(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else (self.source_dir / path).resolve()

    def to_dict(self) -> dict:
        out: dict = {"name": self.name, "base_url": self.base_url}
        if self.viewports:
            out["viewports"] = [v.to_dict() for v in self.viewports]
        if self.session is not None:
            out["session"] = self.session
        if self.tables is not None:
            out["tables"] = self.tables
        if self.scan is not None:
            out["scan"] = self.scan
        if self.baselines is not None:
            out["baselines"] = self.baselines
        if self.tests:
            out["tests"] = list(self.tests)
        return out
