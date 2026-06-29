"""Wire MobileRunResult JSON through the existing compare/baseline/report pipeline.

Pure: synthesizes PNGs in `tmp_path`, builds a `MobileRunResult`, and feeds
`MobileRunResult.to_dict()` to `render_report` and `plan_approval` directly.
No simulator, no browser. Proves the mobile and web result formats interop with
the renderer/approver — the report groups captures under the device viewport
and baselines nest as `<baselines>/<viewport>/<name>.png`.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from fuzzmark.baselines import apply_approval, plan_approval
from fuzzmark.baselines.models import NEW
from fuzzmark.baselines.store import baseline_path
from fuzzmark.compare import PASS
from fuzzmark.mobile import MobileCaptureArtifact, MobileRunResult
from fuzzmark.report import NO_BASELINE, render_report


VIEWPORT = "iPhone-17e_iOS-26-5"


def _solid(path: Path, color: tuple[int, int, int]) -> Path:
    img = np.full((40, 60, 3), color, dtype=np.uint8)
    cv2.imwrite(str(path), img)
    return path


def _mobile_result(captures_dir: Path) -> MobileRunResult:
    vp_dir = captures_dir / VIEWPORT
    vp_dir.mkdir(parents=True, exist_ok=True)
    return MobileRunResult(
        test_name="mobile-demo",
        device_udid="UDID-0",
        device_name="iPhone 17e",
        runtime="iOS-26.5",
        bundle_id="com.example.app",
        viewport=VIEWPORT,
        captures=[
            MobileCaptureArtifact(
                name="home",
                step_index=2,
                screenshot_path=str(_solid(vp_dir / "home.png", (10, 20, 30))),
                viewport=VIEWPORT,
            ),
            MobileCaptureArtifact(
                name="detail",
                step_index=5,
                screenshot_path=str(_solid(vp_dir / "detail.png", (200, 100, 50))),
                viewport=VIEWPORT,
            ),
        ],
    )


def test_render_report_groups_mobile_captures_under_viewport(tmp_path: Path) -> None:
    result = _mobile_result(tmp_path / "shots").to_dict()
    report = render_report(result, tmp_path / "report")
    # Every capture inherits the device viewport tag.
    assert {e.viewport for e in report.entries} == {VIEWPORT}
    assert {e.verdict for e in report.entries} == {NO_BASELINE}
    html = Path(report.index_path).read_text(encoding="utf-8")
    # Viewport label surfaces in the grouped report header.
    assert VIEWPORT in html


def test_render_report_resolves_baselines_nested_under_viewport(tmp_path: Path) -> None:
    result = _mobile_result(tmp_path / "shots").to_dict()
    baselines = tmp_path / "baselines"
    # Same content as the captures → all pass.
    (baselines / VIEWPORT).mkdir(parents=True)
    _solid(baselines / VIEWPORT / "home.png", (10, 20, 30))
    _solid(baselines / VIEWPORT / "detail.png", (200, 100, 50))

    report = render_report(result, tmp_path / "report", baselines_dir=baselines)
    assert {e.verdict for e in report.entries} == {PASS}


def test_plan_and_apply_approval_writes_baselines_under_viewport(tmp_path: Path) -> None:
    result = _mobile_result(tmp_path / "shots").to_dict()
    baselines = tmp_path / "baselines"

    plan = plan_approval(result, baselines)
    targets = sorted(Path(item.target_path) for item in plan.approvals)
    assert targets == [
        baseline_path(baselines, "detail", viewport=VIEWPORT),
        baseline_path(baselines, "home", viewport=VIEWPORT),
    ]
    assert {item.action for item in plan.approvals} == {NEW}

    approval = apply_approval(plan)
    assert len(approval.written) == 2
    for item in approval.written:
        assert Path(item.target_path).is_file()
        # All baselines for this mobile run live under the device viewport dir.
        assert Path(item.target_path).parent.name == VIEWPORT
