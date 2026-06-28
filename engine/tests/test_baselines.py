"""Pure tests for the baseline approval flow.

No browser; on-disk fixtures live in `tmp_path` only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fuzzmark.baselines import (
    NEW,
    UPDATED,
    apply_approval,
    baseline_path,
    existing_baselines,
    plan_approval,
)


def _write_png(path: Path, content: bytes = b"\x89PNG\r\n\x1a\n<capture>") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _run_result(tmp_path: Path, *names: str, test_name: str = "demo") -> dict:
    captures = []
    for idx, name in enumerate(names):
        src = _write_png(tmp_path / "captures" / f"{name}.png", f"<{name}>".encode())
        captures.append(
            {"name": name, "step_index": idx, "screenshot_path": str(src)}
        )
    return {"test_name": test_name, "captures": captures}


class TestStore:
    def test_baseline_path_uses_png(self, tmp_path: Path) -> None:
        assert baseline_path(tmp_path, "home") == tmp_path / "home.png"

    def test_existing_baselines_lists_png_stems(self, tmp_path: Path) -> None:
        _write_png(tmp_path / "a.png")
        _write_png(tmp_path / "b.png")
        (tmp_path / "notes.txt").write_text("ignored")
        assert existing_baselines(tmp_path) == {"a", "b"}

    def test_existing_baselines_handles_missing_dir(self, tmp_path: Path) -> None:
        assert existing_baselines(tmp_path / "nope") == set()

    def test_baseline_path_nests_under_viewport(self, tmp_path: Path) -> None:
        assert (
            baseline_path(tmp_path, "home", viewport="mobile")
            == tmp_path / "mobile" / "home.png"
        )

    def test_existing_baselines_scoped_to_viewport(self, tmp_path: Path) -> None:
        _write_png(tmp_path / "flat.png")
        _write_png(tmp_path / "mobile" / "a.png")
        _write_png(tmp_path / "mobile" / "b.png")
        _write_png(tmp_path / "desktop" / "a.png")
        assert existing_baselines(tmp_path) == {"flat"}
        assert existing_baselines(tmp_path, viewport="mobile") == {"a", "b"}
        assert existing_baselines(tmp_path, viewport="desktop") == {"a"}
        assert existing_baselines(tmp_path, viewport="missing") == set()


class TestPlan:
    def test_plans_every_capture_when_no_filter(self, tmp_path: Path) -> None:
        run = _run_result(tmp_path, "home", "checkout")
        plan = plan_approval(run, tmp_path / "baselines")
        names = [a.capture_name for a in plan.approvals]
        assert names == ["home", "checkout"]
        assert all(a.action == NEW for a in plan.approvals)
        assert plan.skipped == []

    def test_filter_includes_only_named_captures(self, tmp_path: Path) -> None:
        run = _run_result(tmp_path, "home", "checkout", "thanks")
        plan = plan_approval(run, tmp_path / "baselines", capture_names=["home", "thanks"])
        names = [a.capture_name for a in plan.approvals]
        assert names == ["home", "thanks"]
        reasons = {(s.capture_name, s.reason) for s in plan.skipped}
        assert reasons == {("checkout", "not-selected")}

    def test_filter_records_unknown_names(self, tmp_path: Path) -> None:
        run = _run_result(tmp_path, "home")
        plan = plan_approval(run, tmp_path / "baselines", capture_names=["home", "ghost"])
        reasons = {(s.capture_name, s.reason) for s in plan.skipped}
        assert reasons == {("ghost", "unknown")}

    def test_existing_baseline_marks_action_updated(self, tmp_path: Path) -> None:
        base = tmp_path / "baselines"
        _write_png(base / "home.png", b"<old>")
        run = _run_result(tmp_path, "home", "checkout")
        plan = plan_approval(run, base)
        by_name = {a.capture_name: a.action for a in plan.approvals}
        assert by_name == {"home": UPDATED, "checkout": NEW}

    def test_skips_capture_with_missing_source_file(self, tmp_path: Path) -> None:
        run = {
            "test_name": "demo",
            "captures": [
                {
                    "name": "home",
                    "step_index": 0,
                    "screenshot_path": str(tmp_path / "missing.png"),
                }
            ],
        }
        plan = plan_approval(run, tmp_path / "baselines")
        assert plan.approvals == []
        reasons = {(s.capture_name, s.reason) for s in plan.skipped}
        assert reasons == {("home", "source-not-found")}

    def test_target_path_lives_under_baselines_dir(self, tmp_path: Path) -> None:
        run = _run_result(tmp_path, "home")
        base = tmp_path / "baselines"
        plan = plan_approval(run, base)
        assert plan.approvals[0].target_path == str(base / "home.png")


class TestApply:
    def test_writes_baseline_files(self, tmp_path: Path) -> None:
        run = _run_result(tmp_path, "home", "checkout")
        base = tmp_path / "baselines"
        plan = plan_approval(run, base)
        result = apply_approval(plan)

        assert result.dry_run is False
        assert {a.capture_name for a in result.written} == {"home", "checkout"}
        assert (base / "home.png").read_bytes() == b"<home>"
        assert (base / "checkout.png").read_bytes() == b"<checkout>"

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        run = _run_result(tmp_path, "home")
        base = tmp_path / "baselines"
        plan = plan_approval(run, base)
        result = apply_approval(plan, dry_run=True)

        assert result.dry_run is True
        assert len(result.written) == 1
        assert not (base / "home.png").exists()

    def test_overwrites_existing_baseline(self, tmp_path: Path) -> None:
        base = tmp_path / "baselines"
        _write_png(base / "home.png", b"<old>")
        run = _run_result(tmp_path, "home")
        result = apply_approval(plan_approval(run, base))

        assert (base / "home.png").read_bytes() == b"<home>"
        assert result.written[0].action == UPDATED

    def test_creates_baselines_dir_if_missing(self, tmp_path: Path) -> None:
        run = _run_result(tmp_path, "home")
        base = tmp_path / "fresh" / "baselines"
        apply_approval(plan_approval(run, base))
        assert (base / "home.png").exists()

    def test_carries_skipped_through_to_result(self, tmp_path: Path) -> None:
        run = _run_result(tmp_path, "home", "checkout")
        plan = plan_approval(run, tmp_path / "baselines", capture_names=["home"])
        result = apply_approval(plan)
        reasons = {(s.capture_name, s.reason) for s in result.skipped}
        assert reasons == {("checkout", "not-selected")}


class TestViewports:
    def _viewport_run(self, tmp_path: Path) -> dict:
        captures = []
        for idx, (name, vp) in enumerate(
            [("home", "desktop"), ("home", "mobile"), ("checkout", "desktop")]
        ):
            src = _write_png(
                tmp_path / "shots" / vp / f"{name}.png",
                f"<{vp}-{name}>".encode(),
            )
            captures.append(
                {
                    "name": name,
                    "step_index": idx,
                    "screenshot_path": str(src),
                    "viewport": vp,
                }
            )
        return {"test_name": "demo", "captures": captures}

    def test_plan_targets_are_viewport_nested(self, tmp_path: Path) -> None:
        run = self._viewport_run(tmp_path)
        base = tmp_path / "baselines"
        plan = plan_approval(run, base)

        targets = {
            (a.capture_name, Path(a.target_path).relative_to(base).as_posix())
            for a in plan.approvals
        }
        assert targets == {
            ("home", "desktop/home.png"),
            ("home", "mobile/home.png"),
            ("checkout", "desktop/checkout.png"),
        }
        assert all(a.action == NEW for a in plan.approvals)

    def test_apply_writes_per_viewport_files(self, tmp_path: Path) -> None:
        run = self._viewport_run(tmp_path)
        base = tmp_path / "baselines"
        apply_approval(plan_approval(run, base))

        assert (base / "desktop" / "home.png").read_bytes() == b"<desktop-home>"
        assert (base / "mobile" / "home.png").read_bytes() == b"<mobile-home>"
        assert (base / "desktop" / "checkout.png").read_bytes() == b"<desktop-checkout>"

    def test_per_viewport_update_action_is_independent(self, tmp_path: Path) -> None:
        run = self._viewport_run(tmp_path)
        base = tmp_path / "baselines"
        _write_png(base / "desktop" / "home.png", b"<old>")
        plan = plan_approval(run, base)

        by_target = {
            Path(a.target_path).relative_to(base).as_posix(): a.action
            for a in plan.approvals
        }
        assert by_target["desktop/home.png"] == UPDATED
        assert by_target["mobile/home.png"] == NEW

    def test_name_filter_matches_across_viewports(self, tmp_path: Path) -> None:
        run = self._viewport_run(tmp_path)
        plan = plan_approval(
            run, tmp_path / "baselines", capture_names=["home"]
        )
        assert {a.capture_name for a in plan.approvals} == {"home"}
        assert len(plan.approvals) == 2  # home @ desktop and home @ mobile
