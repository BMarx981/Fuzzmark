"""Execute a `Test` flow in a real Playwright session.

One browser launch per run. If the test declares viewports, the flow runs once
per viewport in its own context; otherwise it runs once at the runner's default
viewport (legacy single-viewport behavior). Screenshots from `capture` steps
land at `<out>/<viewport>/<step>.png` when viewports are configured, or flat
`<out>/<step>.png` when not.
"""

from __future__ import annotations

from pathlib import Path

from ..capture import ConsoleMessage, FailedRequest
from ..compare import MaskRegion
from .models import (
    CAPTURE,
    CLICK,
    FILL,
    INTERACT,
    SELECT_OPTION,
    SUBMIT,
    VISIT,
    CaptureArtifact,
    FlowStep,
    RunResult,
    Test,
    Viewport,
)


_CONSOLE_LEVELS_TRACKED = {"error", "warning"}


def run_flow(
    test: Test,
    output_dir: str | Path,
    *,
    viewport: tuple[int, int] = (1280, 800),
    wait_until: str = "networkidle",
    timeout_ms: int = 15000,
    headless: bool = True,
) -> RunResult:
    """Drive `test` against a fresh browser and return a `RunResult`.

    When the test declares `viewports`, the flow runs once per viewport in its
    own context; the `viewport` argument is ignored in that case. When the test
    declares none, the flow runs once at the supplied `viewport` and capture
    artifacts are untagged.
    """
    from playwright.sync_api import sync_playwright

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    viewports: tuple[Viewport, ...] = test.viewports or (
        Viewport(name="", width=viewport[0], height=viewport[1]),
    )
    tag_with_viewport = bool(test.viewports)

    console_errors: list[ConsoleMessage] = []
    page_errors: list[str] = []
    failed_requests: list[FailedRequest] = []
    captures: list[CaptureArtifact] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        try:
            for vp in viewports:
                vp_out = out_dir / vp.name if tag_with_viewport else out_dir
                vp_out.mkdir(parents=True, exist_ok=True)
                _run_one_viewport(
                    browser,
                    test,
                    vp,
                    vp_out,
                    captures,
                    console_errors,
                    page_errors,
                    failed_requests,
                    tag_with_viewport=tag_with_viewport,
                    wait_until=wait_until,
                    timeout_ms=timeout_ms,
                )
        finally:
            browser.close()

    return RunResult(
        test_name=test.name,
        captures=captures,
        console_errors=console_errors,
        page_errors=page_errors,
        failed_requests=failed_requests,
    )


def _run_one_viewport(
    browser,
    test: Test,
    vp: Viewport,
    out_dir: Path,
    captures: list[CaptureArtifact],
    console_errors: list[ConsoleMessage],
    page_errors: list[str],
    failed_requests: list[FailedRequest],
    *,
    tag_with_viewport: bool,
    wait_until: str,
    timeout_ms: int,
) -> None:
    context = browser.new_context(viewport={"width": vp.width, "height": vp.height})
    page = context.new_page()

    def _on_console(msg) -> None:
        if msg.type in _CONSOLE_LEVELS_TRACKED:
            console_errors.append(ConsoleMessage(level=msg.type, text=msg.text))

    def _on_pageerror(exc) -> None:
        page_errors.append(str(exc))

    def _on_requestfailed(request) -> None:
        failure = request.failure or ""
        failed_requests.append(
            FailedRequest(
                url=request.url,
                method=request.method,
                failure=failure or None,
            )
        )

    def _on_response(response) -> None:
        if response.status >= 400:
            failed_requests.append(
                FailedRequest(
                    url=response.url,
                    method=response.request.method,
                    status=response.status,
                )
            )

    page.on("console", _on_console)
    page.on("pageerror", _on_pageerror)
    page.on("requestfailed", _on_requestfailed)
    page.on("response", _on_response)

    viewport_tag = vp.name if tag_with_viewport else None
    try:
        for idx, step in enumerate(test.flow):
            _execute_step(
                page,
                step,
                idx,
                out_dir,
                captures,
                viewport_tag=viewport_tag,
                wait_until=wait_until,
                timeout_ms=timeout_ms,
            )
    finally:
        context.close()


def _execute_step(
    page,
    step: FlowStep,
    idx: int,
    out_dir: Path,
    captures: list[CaptureArtifact],
    *,
    viewport_tag: str | None,
    wait_until: str,
    timeout_ms: int,
) -> None:
    if step.kind == VISIT:
        page.goto(step.url, wait_until=wait_until, timeout=timeout_ms)
        return

    if step.kind == FILL:
        page.locator(step.selector).fill(step.value or "", timeout=timeout_ms)
        return

    if step.kind == INTERACT:
        locator = page.locator(step.selector)
        if step.action == CLICK:
            locator.click(timeout=timeout_ms)
        elif step.action == SELECT_OPTION:
            locator.select_option(step.value, timeout=timeout_ms)
        else:
            getattr(locator, step.action)(timeout=timeout_ms)
        return

    if step.kind == SUBMIT:
        page.locator(step.selector).click(timeout=timeout_ms)
        try:
            page.wait_for_load_state(wait_until, timeout=timeout_ms)
        except Exception:
            pass
        return

    if step.kind == CAPTURE:
        path = out_dir / f"{step.name}.png"
        page.screenshot(path=str(path), full_page=step.full_page)
        masks = tuple(step.mask_regions) + tuple(
            _resolve_selector_masks(page, step.mask_selectors, timeout_ms=timeout_ms)
        )
        captures.append(
            CaptureArtifact(
                name=step.name,
                step_index=idx,
                screenshot_path=str(path),
                masks=masks,
                viewport=viewport_tag,
            )
        )
        return

    raise AssertionError(f"unreachable: unknown step kind {step.kind!r}")


def _resolve_selector_masks(
    page, selectors: tuple[str, ...], *, timeout_ms: int
) -> list[MaskRegion]:
    """Resolve each selector to bounding boxes for every matching element.

    Missing matches are silently skipped — a selector that resolves to nothing
    contributes no masks but does not fail the capture, because the page may
    legitimately render the volatile region only on some paths.
    """
    regions: list[MaskRegion] = []
    for selector in selectors:
        locator = page.locator(selector)
        try:
            count = locator.count()
        except Exception:
            continue
        for i in range(count):
            try:
                box = locator.nth(i).bounding_box(timeout=timeout_ms)
            except Exception:
                box = None
            if not box:
                continue
            width = int(round(box["width"]))
            height = int(round(box["height"]))
            if width <= 0 or height <= 0:
                continue
            regions.append(
                MaskRegion(
                    x=int(round(box["x"])),
                    y=int(round(box["y"])),
                    width=width,
                    height=height,
                    source=selector,
                )
            )
    return regions
