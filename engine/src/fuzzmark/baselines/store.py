"""On-disk layout helpers for the baseline store.

Spec section 5.8: baselines live in a version-controllable directory keyed by
capture name. Single-viewport tests stay flat as `<baselines_dir>/<name>.png`;
multi-viewport tests nest under the viewport name as
`<baselines_dir>/<viewport>/<name>.png` so a project can keep one shared
baseline tree across all its viewports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


BASELINE_SUFFIX = ".png"


def baseline_path(
    baselines_dir: str | Path,
    capture_name: str,
    viewport: Optional[str] = None,
) -> Path:
    """Return the on-disk path that holds the baseline for `capture_name`.

    Nested under `<viewport>/` when supplied, flat otherwise.
    """
    base = Path(baselines_dir)
    if viewport:
        base = base / viewport
    return base / f"{capture_name}{BASELINE_SUFFIX}"


def existing_baselines(
    baselines_dir: str | Path, viewport: Optional[str] = None
) -> set[str]:
    """Return the set of capture names that already have a baseline on disk.

    Scoped to the `<viewport>/` subdir when supplied, the flat directory
    otherwise.
    """
    base = Path(baselines_dir)
    if viewport:
        base = base / viewport
    if not base.is_dir():
        return set()
    return {p.stem for p in base.iterdir() if p.is_file() and p.suffix == BASELINE_SUFFIX}
