"""Region-based image masks applied before SSIM.

Spec section 5.7: masks exclude user-defined dynamic regions before scoring so
known-volatile UI (clocks, ad slots, carousels) does not register as a
regression. This module ships the image-side primitive only — selector
resolution (DOM selector → bounding box at capture time) is a later phase
that produces `MaskRegion`s from a running browser.

Pure: numpy in, numpy out. Importable without a browser.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class MaskRegion:
    """An axis-aligned rectangle to blank before comparison.

    Coordinates are in image pixel space, top-left origin. `source` is a free
    label (e.g. a DOM selector or `"region"`) carried through so the report
    can attribute each mask to its origin.
    """

    x: int
    y: int
    width: int
    height: int
    source: str = "region"

    def to_dict(self) -> dict:
        return asdict(self)


def parse_mask_spec(spec: str) -> MaskRegion:
    """Parse a `"x,y,w,h"` (or `"x,y,w,h,source"`) string into a `MaskRegion`.

    Designed for the CLI — humans want a one-shot flag, not JSON.
    """
    parts = [item.strip() for item in spec.split(",")]
    if len(parts) not in (4, 5):
        raise ValueError(
            f"mask spec must be 'x,y,w,h' or 'x,y,w,h,source'; got {spec!r}"
        )
    try:
        x, y, w, h = (int(p) for p in parts[:4])
    except ValueError as exc:
        raise ValueError(f"mask spec coords must be integers: {spec!r}") from exc
    source = parts[4] if len(parts) == 5 and parts[4] else "region"
    if w <= 0 or h <= 0:
        raise ValueError(f"mask spec width/height must be positive: {spec!r}")
    return MaskRegion(x=x, y=y, width=w, height=h, source=source)


def clamp_region(region: MaskRegion, image_shape: tuple[int, ...]) -> MaskRegion | None:
    """Clamp a region to the image bounds; returns None if it lies entirely outside."""
    if len(image_shape) < 2:
        return None
    img_h, img_w = image_shape[:2]
    x0 = max(0, region.x)
    y0 = max(0, region.y)
    x1 = min(img_w, region.x + region.width)
    y1 = min(img_h, region.y + region.height)
    if x1 <= x0 or y1 <= y0:
        return None
    return MaskRegion(
        x=x0,
        y=y0,
        width=x1 - x0,
        height=y1 - y0,
        source=region.source,
    )


def apply_masks(
    image: np.ndarray,
    regions: list[MaskRegion],
    *,
    fill: tuple[int, int, int] = (0, 0, 0),
) -> np.ndarray:
    """Return a copy of `image` with `regions` painted with `fill`.

    Regions clamped to image bounds; fully-out-of-bounds regions are skipped.
    The same masks must be applied to both baseline and candidate so the
    masked-out pixels are bit-identical and contribute nothing to SSIM.
    """
    if not regions:
        return image
    out = image.copy()
    for region in regions:
        clamped = clamp_region(region, image.shape)
        if clamped is None:
            continue
        out[
            clamped.y : clamped.y + clamped.height,
            clamped.x : clamped.x + clamped.width,
        ] = fill
    return out
