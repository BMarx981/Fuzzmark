"""Interactively capture a logged-in browser session to a `storage_state` file.

A headed Chromium window opens at `login_url`. The user logs in by hand; the
function waits until the page navigates away from the login URL (or matches an
explicit `wait_for_url` pattern) and then writes the resulting storage state to
`out_path`. No stdin prompting — the trigger is always a browser navigation or
the supplied timeout.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class SessionCaptureResult:
    """Summary of a successful session capture."""

    path: str
    start_url: str
    final_url: str
    closed_by: str
    cookies_count: int
    origins_count: int

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "start_url": self.start_url,
            "final_url": self.final_url,
            "closed_by": self.closed_by,
            "cookies_count": self.cookies_count,
            "origins_count": self.origins_count,
        }


def capture_session(
    login_url: str,
    out_path: str | Path,
    *,
    wait_for_url: Optional[str] = None,
    timeout_s: float = 300.0,
    headless: bool = False,
    viewport: tuple[int, int] = (1280, 800),
    wait_until: str = "networkidle",
) -> SessionCaptureResult:
    """Open `login_url` in a headed browser, wait for login, save storage state.

    Args:
        login_url: The login page URL to open.
        out_path: Where to write the JSON storage-state file.
        wait_for_url: Optional regex; when set, capture saves once `page.url`
            matches it. When unset, capture saves on the first navigation away
            from `login_url` (as resolved by the browser).
        timeout_s: Hard cap on how long to wait for the trigger navigation.
        headless: Headless mode. Default False since interactive login needs a
            visible window; tests pass True with an automated wait_for_url.
        viewport: Window viewport size.
        wait_until: Playwright load state for the initial navigation.
    """
    from playwright.sync_api import sync_playwright

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    width, height = viewport
    timeout_ms = int(timeout_s * 1000)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        try:
            page.goto(login_url, wait_until=wait_until, timeout=timeout_ms)
            start_url = page.url

            if wait_for_url is not None:
                pattern = re.compile(wait_for_url)
                page.wait_for_url(pattern, timeout=timeout_ms)
                closed_by = "url-match"
            else:
                page.wait_for_url(
                    lambda u: u != start_url, timeout=timeout_ms
                )
                closed_by = "navigation"

            final_url = page.url
            state = context.storage_state(path=str(out))
        finally:
            context.close()
            browser.close()

    cookies = state.get("cookies") if isinstance(state, dict) else None
    origins = state.get("origins") if isinstance(state, dict) else None
    return SessionCaptureResult(
        path=str(out),
        start_url=start_url,
        final_url=final_url,
        closed_by=closed_by,
        cookies_count=len(cookies or []),
        origins_count=len(origins or []),
    )
