"""Browser-driven tests for the capture module.

Skipped unless `pytest --run-browser` is passed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fuzzmark.capture import capture_page

pytestmark = pytest.mark.browser


def test_captures_full_page_screenshot(tmp_path: Path, fixture_form_url: str) -> None:
    out = tmp_path / "shot.png"
    result = capture_page(fixture_form_url, out)

    assert out.exists()
    assert out.stat().st_size > 0
    assert result.screenshot_path == str(out)
    assert result.full_page is True
    assert (result.viewport_width, result.viewport_height) == (1280, 800)


def test_clean_page_records_no_errors(tmp_path: Path, fixture_form_url: str) -> None:
    result = capture_page(fixture_form_url, tmp_path / "shot.png")

    assert result.console_errors == []
    assert result.page_errors == []
    assert result.failed_requests == []
    assert result.has_errors is False


def test_viewport_only_mode_is_selectable(tmp_path: Path, fixture_form_url: str) -> None:
    result = capture_page(
        fixture_form_url, tmp_path / "shot.png", full_page=False, viewport=(640, 480)
    )

    assert result.full_page is False
    assert (result.viewport_width, result.viewport_height) == (640, 480)


def test_repeated_captures_are_byte_stable(tmp_path: Path, fixture_form_url: str) -> None:
    """The MVP diff DoD depends on this: identical input → identical capture."""
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    capture_page(fixture_form_url, a)
    capture_page(fixture_form_url, b)
    assert a.read_bytes() == b.read_bytes()


def test_page_error_is_collected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.html"
    bad.write_text(
        "<!doctype html><html><body><script>throw new Error('boom');</script></body></html>",
        encoding="utf-8",
    )
    result = capture_page(bad.as_uri(), tmp_path / "shot.png")

    assert any("boom" in err for err in result.page_errors)
    assert result.has_errors is True


def test_console_error_is_collected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.html"
    bad.write_text(
        "<!doctype html><html><body><script>console.error('oops');</script></body></html>",
        encoding="utf-8",
    )
    result = capture_page(bad.as_uri(), tmp_path / "shot.png")

    assert any(m.level == "error" and "oops" in m.text for m in result.console_errors)
