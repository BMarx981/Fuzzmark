"""On-disk layout helpers for the baseline store.

Spec section 5.8: baselines live in a version-controllable directory keyed by
capture name. The MVP layout is flat — `<baselines_dir>/<name>.png` — which is
what `report.render_report` already reads. Viewport/state nesting is a later
phase.
"""

from __future__ import annotations

from pathlib import Path


BASELINE_SUFFIX = ".png"


def baseline_path(baselines_dir: str | Path, capture_name: str) -> Path:
    """Return the on-disk path that holds the baseline for `capture_name`."""
    return Path(baselines_dir) / f"{capture_name}{BASELINE_SUFFIX}"


def existing_baselines(baselines_dir: str | Path) -> set[str]:
    """Return the set of capture names that already have a baseline on disk."""
    base = Path(baselines_dir)
    if not base.is_dir():
        return set()
    return {p.stem for p in base.iterdir() if p.is_file() and p.suffix == BASELINE_SUFFIX}
