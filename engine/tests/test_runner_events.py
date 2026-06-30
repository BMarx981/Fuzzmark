"""Pure-Python tests for `run_flow`'s event + cancel plumbing.

No browser. Monkeypatches `_run_one_viewport` so we exercise the outer
shell of `run_flow` (the `started` event, the per-viewport loop, cancel
propagation) without standing up Playwright. The browser-driven test in
`test_driver_browser.py` covers the inner emission points (step_started
/ step_finished / capture / console_error / page_error / failed_request).
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from fuzzmark.driver import (
    CAPTURE,
    VISIT,
    FlowStep,
    Test,
    Viewport,
    run_flow,
)
from fuzzmark.driver import runner as runner_mod
from fuzzmark.jobs import JobCancelled


def _flow() -> list[FlowStep]:
    return [
        FlowStep(kind=VISIT, url="about:blank"),
        FlowStep(kind=CAPTURE, name="shot"),
    ]


def _test_no_viewports() -> Test:
    return Test(name="demo", flow=_flow())


def _test_with_viewports() -> Test:
    return Test(
        name="multi",
        flow=_flow(),
        viewports=(
            Viewport(name="phone", width=375, height=667),
            Viewport(name="desktop", width=1280, height=800),
        ),
    )


class _FakeSyncPlaywrightCtx:
    """Stand-in for `sync_playwright()` so `run_flow` doesn't launch Chromium."""

    def __enter__(self):
        class _PW:
            class chromium:
                @staticmethod
                def launch(**_kwargs):
                    class _Browser:
                        def close(self_inner) -> None:
                            pass

                    return _Browser()

        return _PW()

    def __exit__(self, *_exc) -> None:
        return None


@pytest.fixture(autouse=True)
def _stub_playwright(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace `sync_playwright` so `run_flow` runs without a real browser."""
    import playwright.sync_api as pw

    monkeypatch.setattr(
        pw, "sync_playwright", lambda: _FakeSyncPlaywrightCtx(), raising=True
    )


def test_started_event_no_viewports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner_mod, "_run_one_viewport", lambda *a, **kw: None)
    events: list[dict] = []
    run_flow(_test_no_viewports(), tmp_path, on_event=events.append)
    assert events[0] == {
        "event": "started",
        "test_name": "demo",
        "total_steps": 2,
        "viewports": [],
    }


def test_started_event_with_viewports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner_mod, "_run_one_viewport", lambda *a, **kw: None)
    events: list[dict] = []
    run_flow(_test_with_viewports(), tmp_path, on_event=events.append)
    assert events[0] == {
        "event": "started",
        "test_name": "multi",
        "total_steps": 4,
        "viewports": ["phone", "desktop"],
    }


def test_per_viewport_runner_receives_event_and_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen_kwargs: list[dict] = []

    def _spy(*_args, **kwargs):
        cb = kwargs.get("on_event")
        if cb is not None:
            cb({"event": "inner_ping"})
        seen_kwargs.append({"cancel": kwargs.get("cancel")})

    monkeypatch.setattr(runner_mod, "_run_one_viewport", _spy)
    events: list[dict] = []
    cancel = threading.Event()

    run_flow(_test_no_viewports(), tmp_path, on_event=events.append, cancel=cancel)

    assert len(seen_kwargs) == 1
    assert seen_kwargs[0]["cancel"] is cancel
    # Event reaches the outer collector via the same on_event callback.
    assert {"event": "inner_ping"} in events


def test_cancel_propagates_as_jobcancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise_cancel(*_args, **_kwargs):
        raise JobCancelled()

    monkeypatch.setattr(runner_mod, "_run_one_viewport", _raise_cancel)

    with pytest.raises(JobCancelled):
        run_flow(_test_no_viewports(), tmp_path, cancel=threading.Event())


def test_no_event_callback_still_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner_mod, "_run_one_viewport", lambda *a, **kw: None)
    # On the legacy call-site (no on_event / no cancel) run_flow must still return.
    result = run_flow(_test_no_viewports(), tmp_path)
    assert result.test_name == "demo"


class TestHelpers:
    def test_check_cancel_no_op_when_unset(self) -> None:
        runner_mod._check_cancel(None)
        runner_mod._check_cancel(threading.Event())

    def test_check_cancel_raises_when_set(self) -> None:
        evt = threading.Event()
        evt.set()
        with pytest.raises(JobCancelled):
            runner_mod._check_cancel(evt)

    def test_emit_no_op_when_none(self) -> None:
        runner_mod._emit(None, {"event": "ignored"})

    def test_emit_invokes_callback(self) -> None:
        seen: list[dict] = []
        runner_mod._emit(seen.append, {"event": "x"})
        assert seen == [{"event": "x"}]
