"""Browser-driven tests for `fuzzmark session` capture and replay.

Skipped unless `pytest --run-browser` is passed. Uses a tiny in-process HTTP
server so the browser is talking to a real http:// origin — file:// URLs can't
carry cookies, and storage_state round-trips need a real origin to bind to.
"""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
from pathlib import Path
from typing import Generator

import pytest

from fuzzmark.capture import capture_page
from fuzzmark.driver import CAPTURE, VISIT, FlowStep, Test, run_flow
from fuzzmark.sessions import capture_session

pytestmark = pytest.mark.browser


_LOGIN_HTML = """<!doctype html>
<html><body>
<script>
document.cookie = "auth=yes; path=/";
window.location.href = "/done.html";
</script>
</body></html>
"""

_DONE_HTML = "<!doctype html><html><body><h1>done</h1></body></html>"

_PROTECTED_HTML = """<!doctype html>
<html><body>
<h1>Status</h1>
<p id="s">?</p>
<script>
document.getElementById("s").textContent =
  document.cookie.indexOf("auth=yes") >= 0 ? "LOGGED IN" : "ANON";
</script>
</body></html>
"""


@pytest.fixture
def localhost_site(tmp_path_factory: pytest.TempPathFactory) -> Generator[str, None, None]:
    site_dir = tmp_path_factory.mktemp("auth-site")
    (site_dir / "login.html").write_text(_LOGIN_HTML, encoding="utf-8")
    (site_dir / "done.html").write_text(_DONE_HTML, encoding="utf-8")
    (site_dir / "protected.html").write_text(_PROTECTED_HTML, encoding="utf-8")

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(site_dir), **kwargs)

        def log_message(self, *_args, **_kwargs) -> None:  # silence stderr
            return

    server = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _capture_session_for(site: str, out_path: Path) -> None:
    capture_session(
        f"{site}/login.html",
        out_path,
        wait_for_url=r".*/done\.html$",
        timeout_s=30,
        headless=True,
    )


def test_capture_session_writes_auth_cookie(
    tmp_path: Path, localhost_site: str
) -> None:
    session_path = tmp_path / "sess.json"
    _capture_session_for(localhost_site, session_path)

    assert session_path.exists() and session_path.stat().st_size > 0
    data = json.loads(session_path.read_text(encoding="utf-8"))
    assert isinstance(data.get("cookies"), list)
    auth_cookies = [c for c in data["cookies"] if c.get("name") == "auth"]
    assert auth_cookies, f"auth cookie missing from {data['cookies']!r}"
    assert auth_cookies[0]["value"] == "yes"


def test_capture_session_result_summary(
    tmp_path: Path, localhost_site: str
) -> None:
    session_path = tmp_path / "sess.json"
    result = capture_session(
        f"{localhost_site}/login.html",
        session_path,
        wait_for_url=r".*/done\.html$",
        timeout_s=30,
        headless=True,
    )
    assert result.closed_by == "url-match"
    assert result.final_url.endswith("/done.html")
    assert result.cookies_count >= 1


def test_capture_page_with_session_differs_from_anon(
    tmp_path: Path, localhost_site: str
) -> None:
    """The protected page renders different pixels when the auth cookie is replayed."""
    session_path = tmp_path / "sess.json"
    _capture_session_for(localhost_site, session_path)

    auth_png = tmp_path / "auth.png"
    anon_png = tmp_path / "anon.png"
    capture_page(
        f"{localhost_site}/protected.html",
        auth_png,
        headless=True,
        session=str(session_path),
    )
    capture_page(f"{localhost_site}/protected.html", anon_png, headless=True)

    assert auth_png.read_bytes() != anon_png.read_bytes()


def test_run_flow_uses_test_session_field(
    tmp_path: Path, localhost_site: str
) -> None:
    """`Test.session` is replayed into the driver's per-viewport context."""
    session_path = tmp_path / "sess.json"
    _capture_session_for(localhost_site, session_path)

    auth_test = Test(
        name="protected-auth",
        flow=[
            FlowStep(kind=VISIT, url=f"{localhost_site}/protected.html"),
            FlowStep(kind=CAPTURE, name="snap"),
        ],
        session=str(session_path),
    )
    anon_test = Test(
        name="protected-anon",
        flow=[
            FlowStep(kind=VISIT, url=f"{localhost_site}/protected.html"),
            FlowStep(kind=CAPTURE, name="snap"),
        ],
    )

    auth_out = run_flow(auth_test, tmp_path / "auth")
    anon_out = run_flow(anon_test, tmp_path / "anon")

    assert (
        Path(auth_out.captures[0].screenshot_path).read_bytes()
        != Path(anon_out.captures[0].screenshot_path).read_bytes()
    )
