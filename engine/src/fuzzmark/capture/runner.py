"""Drive a page and capture a screenshot plus runtime error signals."""

from __future__ import annotations

from pathlib import Path

from .result import CaptureResult, ConsoleMessage, FailedRequest


_CONSOLE_LEVELS_TRACKED = {"error", "warning"}


def capture_page(
    url: str,
    screenshot_path: str | Path,
    *,
    viewport: tuple[int, int] = (1280, 800),
    full_page: bool = True,
    wait_until: str = "networkidle",
    timeout_ms: int = 15000,
    headless: bool = True,
) -> CaptureResult:
    """Load `url`, save a screenshot to `screenshot_path`, and collect error signals.

    Args:
        url: The page to load.
        screenshot_path: Where the PNG is written. Parent directory must exist.
        viewport: `(width, height)` in CSS pixels.
        full_page: If True, capture the full scrollable page; otherwise the viewport only.
        wait_until: Playwright load-state to wait for before screenshotting.
        timeout_ms: Hard cap on the navigation step.
        headless: Run the browser headless.

    Returns:
        A populated `CaptureResult`.
    """
    from playwright.sync_api import sync_playwright

    path = Path(screenshot_path)
    width, height = viewport

    console_errors: list[ConsoleMessage] = []
    page_errors: list[str] = []
    failed_requests: list[FailedRequest] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": width, "height": height})
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

        try:
            page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            page.screenshot(path=str(path), full_page=full_page)
        finally:
            context.close()
            browser.close()

    return CaptureResult(
        url=url,
        screenshot_path=str(path),
        viewport_width=width,
        viewport_height=height,
        full_page=full_page,
        console_errors=console_errors,
        page_errors=page_errors,
        failed_requests=failed_requests,
    )
