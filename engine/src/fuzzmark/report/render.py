"""Render a run's captures, baselines, diffs, and errors as a static HTML report.

Pure: takes a RunResult-shaped dict in, writes files to disk, returns a Report.
The HTML is self-contained — all assets (capture/baseline/diff PNGs) are copied
into the output directory, so the report folder is portable and trivially
served from any static host.

Captures tagged with a `viewport` are grouped under per-viewport sections with
their own verdict summaries; untagged captures render in a single flat list as
before.
"""

from __future__ import annotations

import html
import shutil
from pathlib import Path
from typing import Iterable, Optional

from ..baselines import baseline_path as baseline_target_path
from ..compare import (
    CONTENT_CHANGE,
    DEFAULT_THRESHOLD,
    LAYOUT_BREAK,
    PASS,
    SIZE_SHIFT,
    MaskRegion,
    compare_images,
)
from .models import NO_BASELINE, Report, ReportEntry


_VERDICT_ORDER = {
    LAYOUT_BREAK: 0,
    CONTENT_CHANGE: 1,
    SIZE_SHIFT: 2,
    NO_BASELINE: 3,
    "error": 4,
    PASS: 5,
}
_IMAGES_SUBDIR = "images"


def render_report(
    run_result: dict,
    output_dir: str | Path,
    *,
    baselines_dir: str | Path | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    masks: dict[str, list[MaskRegion]] | None = None,
) -> Report:
    """Build the report directory and return the populated `Report` model.

    Args:
        run_result: A `RunResult.to_dict()` shape — `test_name`, `captures`,
            `console_errors`, `page_errors`, `failed_requests`.
        output_dir: Destination directory; created if missing. Existing files
            are overwritten so re-running is idempotent.
        baselines_dir: Optional directory of approved baselines. Untagged
            captures resolve to `<baselines>/<name>.png`; viewport-tagged
            captures resolve to `<baselines>/<viewport>/<name>.png`. Captures
            without a matching baseline are recorded with the `no-baseline`
            verdict.
        threshold: SSIM threshold passed to the comparison engine.
        masks: Optional map of capture name → list of `MaskRegion` blanked on
            both baseline and capture before scoring. Applies to every viewport
            of that capture name.
    """
    out_dir = Path(output_dir)
    images_dir = out_dir / _IMAGES_SUBDIR
    images_dir.mkdir(parents=True, exist_ok=True)

    baselines = Path(baselines_dir) if baselines_dir is not None else None
    masks_by_name = masks
    entries = [
        _build_entry(
            capture,
            images_dir,
            baselines,
            threshold,
            masks=_masks_for(capture, masks_by_name),
        )
        for capture in run_result.get("captures", [])
    ]

    report = Report(
        test_name=run_result.get("test_name", ""),
        entries=entries,
        console_errors=list(run_result.get("console_errors", [])),
        page_errors=list(run_result.get("page_errors", [])),
        failed_requests=list(run_result.get("failed_requests", [])),
        output_dir=str(out_dir),
    )

    index_path = out_dir / "index.html"
    index_path.write_text(_render_html(report), encoding="utf-8")
    report.index_path = str(index_path)
    return report


def _masks_for(
    capture: dict, override: dict[str, list[MaskRegion]] | None
) -> list[MaskRegion] | None:
    """Return masks for one capture: CLI override per-capture name wins, else the per-capture list from the run result."""
    if override is not None and capture["name"] in override:
        return override[capture["name"]]
    raw = capture.get("masks")
    if not raw:
        return None
    return [MaskRegion(**m) for m in raw]


def _image_key(name: str, viewport: Optional[str]) -> str:
    return f"{viewport}__{name}" if viewport else name


def _build_entry(
    capture: dict,
    images_dir: Path,
    baselines_dir: Path | None,
    threshold: float,
    *,
    masks: list[MaskRegion] | None = None,
) -> ReportEntry:
    name = capture["name"]
    step_index = capture["step_index"]
    viewport = capture.get("viewport") or None
    src = Path(capture["screenshot_path"])
    image_key = _image_key(name, viewport)
    capture_dst = images_dir / f"{image_key}.png"
    shutil.copyfile(src, capture_dst)

    baseline_src: Path | None = None
    if baselines_dir is not None:
        candidate = baseline_target_path(baselines_dir, name, viewport=viewport)
        if candidate.exists():
            baseline_src = candidate

    if baseline_src is None:
        return ReportEntry.no_baseline(
            name=name,
            step_index=step_index,
            capture_path=str(capture_dst),
            viewport=viewport,
        )

    baseline_dst = images_dir / f"{image_key}__baseline.png"
    diff_dst = images_dir / f"{image_key}__diff.png"
    shutil.copyfile(baseline_src, baseline_dst)
    result = compare_images(
        baseline_dst,
        capture_dst,
        threshold=threshold,
        diff_path=diff_dst,
        masks=masks,
    )
    return ReportEntry.from_compare(
        name=name,
        step_index=step_index,
        capture_path=str(capture_dst),
        result=result,
        viewport=viewport,
    )


def _ordered(entries: Iterable[ReportEntry]) -> list[ReportEntry]:
    return sorted(
        entries, key=lambda e: (_VERDICT_ORDER.get(e.verdict, 99), e.step_index)
    )


def _rel(path: str, base: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(base.resolve()))
    except ValueError:
        return path


def _group_entries(
    entries: list[ReportEntry],
) -> list[tuple[Optional[str], list[ReportEntry]]]:
    """Return entries grouped by viewport, preserving first-seen order.

    A single None group means no entry was viewport-tagged — render flat.
    """
    order: list[Optional[str]] = []
    buckets: dict[Optional[str], list[ReportEntry]] = {}
    for e in entries:
        key = e.viewport
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(e)
    return [(k, buckets[k]) for k in order]


def _counts(entries: Iterable[ReportEntry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.verdict] = counts.get(e.verdict, 0) + 1
    return counts


def _summary_chips(counts: dict[str, int]) -> str:
    return "".join(
        f'<span class="chip chip-{html.escape(v)}">{html.escape(v)} '
        f'<b>{counts[v]}</b></span>'
        for v in sorted(counts, key=lambda k: _VERDICT_ORDER.get(k, 99))
    )


def _render_html(report: Report) -> str:
    base = Path(report.output_dir)
    title = html.escape(report.test_name or "Fuzzmark report")
    overall_chips = _summary_chips(report.verdict_counts)
    groups = _group_entries(report.entries)
    grouped = len(groups) > 1 or (groups and groups[0][0] is not None)

    if grouped:
        sections = "\n".join(_render_viewport_group(vp, es, base) for vp, es in groups)
    else:
        entries = groups[0][1] if groups else []
        sections = "\n".join(_render_entry(e, base) for e in _ordered(entries))

    errors_html = _render_errors(report)

    return _PAGE.format(
        title=title,
        summary=overall_chips,
        sections=sections or '<p class="empty">No captures in this run.</p>',
        errors=errors_html,
    )


def _render_viewport_group(
    viewport: Optional[str], entries: list[ReportEntry], base: Path
) -> str:
    label = html.escape(viewport or "default")
    counts = _counts(entries)
    chips = _summary_chips(counts)
    body = "\n".join(_render_entry(e, base) for e in _ordered(entries))
    return (
        '<section class="viewport-group">'
        f'<header class="viewport-head"><h2>{label}</h2>'
        f'<div class="summary">{chips}</div></header>'
        f'{body}'
        '</section>'
    )


def _render_entry(entry: ReportEntry, base: Path) -> str:
    verdict = html.escape(entry.verdict)
    head = (
        f'<header><h2>{html.escape(entry.name)}</h2>'
        f'<span class="chip chip-{verdict}">{verdict}</span></header>'
    )
    score_line = ""
    if entry.score is not None and entry.threshold is not None:
        score_line = (
            f'<p class="meta">SSIM {entry.score:.4f} &middot; '
            f'threshold {entry.threshold:.4f}</p>'
        )

    capture_img = _img(entry.capture_path, base, "capture")
    if entry.baseline_path and entry.diff_path:
        body = (
            '<div class="frames">'
            f'<figure><figcaption>baseline</figcaption>'
            f'{_img(entry.baseline_path, base, "baseline")}</figure>'
            f'<figure><figcaption>capture</figcaption>{capture_img}</figure>'
            f'<figure><figcaption>diff</figcaption>'
            f'{_img(entry.diff_path, base, "diff")}</figure>'
            '</div>'
        )
    else:
        body = f'<div class="frames"><figure><figcaption>capture</figcaption>{capture_img}</figure></div>'

    return f'<section class="entry">{head}{score_line}{body}</section>'


def _img(path: str, base: Path, alt: str) -> str:
    src = html.escape(_rel(path, base))
    return f'<a href="{src}" target="_blank"><img src="{src}" alt="{alt}"></a>'


def _render_errors(report: Report) -> str:
    if not report.has_errors:
        return '<section class="errors"><h2>Errors</h2><p class="empty">No errors collected.</p></section>'

    parts = ['<section class="errors"><h2>Errors</h2>']
    if report.console_errors:
        items = "".join(
            f'<li><b>{html.escape(m.get("level", ""))}</b> '
            f'{html.escape(m.get("text", ""))}</li>'
            for m in report.console_errors
        )
        parts.append(f"<h3>Console</h3><ul>{items}</ul>")
    if report.page_errors:
        items = "".join(f"<li>{html.escape(e)}</li>" for e in report.page_errors)
        parts.append(f"<h3>Page errors</h3><ul>{items}</ul>")
    if report.failed_requests:
        rows = "".join(
            "<tr><td>{m}</td><td>{u}</td><td>{s}</td></tr>".format(
                m=html.escape(r.get("method", "")),
                u=html.escape(r.get("url", "")),
                s=html.escape(str(r.get("status") or r.get("failure") or "")),
            )
            for r in report.failed_requests
        )
        parts.append(
            "<h3>Failed requests</h3>"
            f"<table><thead><tr><th>method</th><th>url</th><th>status</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
    parts.append("</section>")
    return "".join(parts)


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{
    --bg: #fbfbfb; --fg: #1a1a1a; --muted: #6b7280; --line: #e5e7eb;
    --pass: #16a34a; --layout-break: #991b1b; --content-change: #dc2626;
    --size-shift: #d97706; --no-baseline: #6b7280; --error: #b45309;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font: 14px/1.5 -apple-system, system-ui, sans-serif;
         color: var(--fg); background: var(--bg); }}
  header.top {{ padding: 24px 32px; border-bottom: 1px solid var(--line); background: white; }}
  header.top h1 {{ margin: 0 0 8px; font-size: 18px; }}
  main {{ padding: 24px 32px; max-width: 1400px; margin: 0 auto; }}
  .chip {{ display: inline-block; padding: 2px 10px; margin-right: 6px;
          border-radius: 999px; font-size: 12px; color: white; }}
  .chip-pass {{ background: var(--pass); }}
  .chip-layout-break {{ background: var(--layout-break); }}
  .chip-content-change {{ background: var(--content-change); }}
  .chip-size-shift {{ background: var(--size-shift); }}
  .chip-no-baseline {{ background: var(--no-baseline); }}
  .chip-error {{ background: var(--error); }}
  .viewport-group {{ margin-bottom: 24px; }}
  .viewport-head {{ display: flex; justify-content: space-between; align-items: center;
                    padding: 8px 0; border-bottom: 1px solid var(--line); margin-bottom: 12px; }}
  .viewport-head h2 {{ margin: 0; font-size: 16px; font-family: ui-monospace, Menlo, monospace; }}
  .entry {{ background: white; border: 1px solid var(--line); border-radius: 8px;
            padding: 16px; margin-bottom: 16px; }}
  .entry header {{ display: flex; justify-content: space-between; align-items: center; }}
  .entry h2 {{ margin: 0; font-size: 15px; font-family: ui-monospace, Menlo, monospace; }}
  .meta {{ margin: 4px 0 12px; color: var(--muted); font-family: ui-monospace, Menlo, monospace; }}
  .frames {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
  .frames figure {{ margin: 0; }}
  .frames figcaption {{ font-size: 12px; color: var(--muted); margin-bottom: 4px; }}
  .frames img {{ width: 100%; height: auto; display: block;
                 border: 1px solid var(--line); border-radius: 4px; background: white; }}
  .errors {{ background: white; border: 1px solid var(--line); border-radius: 8px;
             padding: 16px; }}
  .errors h2 {{ margin: 0 0 12px; font-size: 15px; }}
  .errors h3 {{ font-size: 13px; margin: 12px 0 4px; color: var(--muted); }}
  .errors ul {{ margin: 0; padding-left: 18px; font-family: ui-monospace, Menlo, monospace; font-size: 12px; }}
  .errors table {{ width: 100%; border-collapse: collapse; font-family: ui-monospace, Menlo, monospace; font-size: 12px; }}
  .errors th, .errors td {{ text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--line); }}
  .empty {{ color: var(--muted); }}
</style>
</head>
<body>
<header class="top">
  <h1>{title}</h1>
  <div class="summary">{summary}</div>
</header>
<main>
{sections}
{errors}
</main>
</body>
</html>
"""
