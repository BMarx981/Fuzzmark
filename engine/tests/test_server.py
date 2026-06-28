"""Tests for the local HTTP API.

Both pure unit tests (calling `dispatch` directly) and an end-to-end pass
that binds a server on an ephemeral port and exercises it with urllib.
No browser, no Playwright.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from fuzzmark.scanner import CrawlBounds, Page, SiteMap, SkippedUrl
from fuzzmark.server import RouteError, dispatch, make_server
from fuzzmark.server import routes as server_routes
from fuzzmark.server.app import bound_address


class TestDispatch:
    def test_health_ok(self) -> None:
        body = dispatch("GET", "/api/health", {})
        assert body["ok"] is True
        assert isinstance(body["api_version"], str)

    def test_unknown_route_is_404(self) -> None:
        with pytest.raises(RouteError) as excinfo:
            dispatch("GET", "/api/nope", {})
        assert excinfo.value.status == 404

    def test_load_requires_path(self) -> None:
        with pytest.raises(RouteError) as excinfo:
            dispatch("POST", "/api/projects/load", {})
        assert excinfo.value.status == 400
        assert "path" in excinfo.value.message

    def test_init_then_load(self, tmp_path: Path) -> None:
        path = str(tmp_path / "project.json")
        created = dispatch(
            "POST",
            "/api/projects/init",
            {
                "path": path,
                "name": "demo",
                "base_url": "http://localhost:8000/",
                "viewports": [{"name": "desktop", "width": 1280, "height": 800}],
            },
        )
        assert created["name"] == "demo"
        assert created["viewports"] == [
            {"name": "desktop", "width": 1280, "height": 800}
        ]
        assert created["path"] == str(Path(path).resolve())

        loaded = dispatch("POST", "/api/projects/load", {"path": path})
        assert loaded["base_url"] == "http://localhost:8000/"
        assert loaded["resolved"]["source_dir"] == str(tmp_path.resolve())

    def test_init_refuses_overwrite_without_force(self, tmp_path: Path) -> None:
        path = str(tmp_path / "p.json")
        dispatch(
            "POST",
            "/api/projects/init",
            {"path": path, "name": "x", "base_url": "http://x/"},
        )
        with pytest.raises(RouteError) as excinfo:
            dispatch(
                "POST",
                "/api/projects/init",
                {"path": path, "name": "x", "base_url": "http://x/"},
            )
        assert excinfo.value.status == 400

    def test_init_with_force_overwrites(self, tmp_path: Path) -> None:
        path = str(tmp_path / "p.json")
        dispatch(
            "POST",
            "/api/projects/init",
            {"path": path, "name": "x", "base_url": "http://x/"},
        )
        body = dispatch(
            "POST",
            "/api/projects/init",
            {"path": path, "name": "y", "base_url": "http://y/", "force": True},
        )
        assert body["name"] == "y"
        assert body["base_url"] == "http://y/"

    def test_init_rejects_bad_viewport(self, tmp_path: Path) -> None:
        with pytest.raises(RouteError) as excinfo:
            dispatch(
                "POST",
                "/api/projects/init",
                {
                    "path": str(tmp_path / "p.json"),
                    "name": "x",
                    "base_url": "http://x/",
                    "viewports": [{"name": "", "width": 1, "height": 1}],
                },
            )
        assert excinfo.value.status == 400


class TestScanRoutes:
    def _init_project(self, tmp_path: Path) -> str:
        path = str(tmp_path / "project.json")
        dispatch(
            "POST",
            "/api/projects/init",
            {"path": path, "name": "demo", "base_url": "http://example.test/"},
        )
        return path

    def _stub_crawl(self, captured: dict) -> object:
        def fake(base_url, bounds, *, headless=True, session=None):
            captured["base_url"] = base_url
            captured["bounds"] = bounds
            captured["headless"] = headless
            captured["session"] = session
            return SiteMap(
                base_url=base_url,
                bounds=bounds,
                pages=[
                    Page(url=base_url, depth=0, parent_url=None, title="Home"),
                    Page(
                        url=base_url + "about",
                        depth=1,
                        parent_url=base_url,
                        title="About",
                    ),
                ],
                skipped=[
                    SkippedUrl(
                        url=base_url + "logout",
                        reason="exclude:logout",
                        parent_url=base_url,
                    )
                ],
            )

        return fake

    def test_scan_uses_project_base_url_and_bounds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = self._init_project(tmp_path)
        captured: dict = {}
        monkeypatch.setattr(server_routes, "_crawl", self._stub_crawl(captured))

        body = dispatch(
            "POST",
            "/api/projects/scan",
            {
                "path": path,
                "max_depth": 1,
                "max_pages": 5,
                "ignore_robots": True,
                "allow_cross_origin": True,
                "rate_limit": 0.25,
            },
        )

        assert captured["base_url"] == "http://example.test/"
        bounds = captured["bounds"]
        assert isinstance(bounds, CrawlBounds)
        assert bounds.max_depth == 1
        assert bounds.max_pages == 5
        assert bounds.respect_robots is False
        assert bounds.same_origin is False
        assert bounds.rate_limit_seconds == 0.25
        assert captured["headless"] is True
        assert captured["session"] is None

        site_map = body["site_map"]
        assert site_map["page_count"] == 2
        assert site_map["skipped_count"] == 1
        assert [p["url"] for p in site_map["pages"]] == [
            "http://example.test/",
            "http://example.test/about",
        ]

    def test_scan_requires_project(self, tmp_path: Path) -> None:
        with pytest.raises(RouteError) as excinfo:
            dispatch(
                "POST",
                "/api/projects/scan",
                {"path": str(tmp_path / "missing.json")},
            )
        assert excinfo.value.status == 400

    def test_scan_rejects_bad_bounds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = self._init_project(tmp_path)
        called: dict = {"n": 0}

        def fail_if_called(*_a, **_kw):
            called["n"] += 1
            raise AssertionError("crawl should not run when bounds are invalid")

        monkeypatch.setattr(server_routes, "_crawl", fail_if_called)
        with pytest.raises(RouteError) as excinfo:
            dispatch(
                "POST",
                "/api/projects/scan",
                {"path": path, "max_pages": 0},
            )
        assert excinfo.value.status == 400
        assert called["n"] == 0

    def test_scan_save_writes_file_and_updates_project(
        self, tmp_path: Path
    ) -> None:
        path = self._init_project(tmp_path)
        site_map = {
            "base_url": "http://example.test/",
            "bounds": {},
            "page_count": 1,
            "skipped_count": 0,
            "pages": [
                {
                    "url": "http://example.test/",
                    "depth": 0,
                    "parent_url": None,
                    "title": "Home",
                    "links": [],
                    "error": None,
                }
            ],
            "skipped": [],
        }
        body = dispatch(
            "POST",
            "/api/projects/scan/save",
            {"path": path, "site_map": site_map},
        )
        assert body["scan"] == "scan.json"
        assert body["resolved"]["scan"] == str(
            (tmp_path / "scan.json").resolve()
        )
        on_disk = json.loads(
            (tmp_path / "scan.json").read_text(encoding="utf-8")
        )
        assert on_disk == site_map
        reloaded = dispatch("POST", "/api/projects/load", {"path": path})
        assert reloaded["scan"] == "scan.json"

    def test_scan_save_rejects_non_object_site_map(self, tmp_path: Path) -> None:
        path = self._init_project(tmp_path)
        with pytest.raises(RouteError) as excinfo:
            dispatch(
                "POST",
                "/api/projects/scan/save",
                {"path": path, "site_map": []},
            )
        assert excinfo.value.status == 400

    def test_scan_save_rejects_path_segment_in_filename(
        self, tmp_path: Path
    ) -> None:
        path = self._init_project(tmp_path)
        with pytest.raises(RouteError) as excinfo:
            dispatch(
                "POST",
                "/api/projects/scan/save",
                {"path": path, "site_map": {}, "filename": "nested/scan.json"},
            )
        assert excinfo.value.status == 400


class TestHttpServer:
    def test_end_to_end_health_and_project_lifecycle(self, tmp_path: Path) -> None:
        server = make_server(host="127.0.0.1", port=0)
        host, port = bound_address(server)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://{host}:{port}"

            health = _get_json(f"{base}/api/health")
            assert health["ok"] is True

            project_path = str(tmp_path / "project.json")
            created = _post_json(
                f"{base}/api/projects/init",
                {"path": project_path, "name": "demo", "base_url": "http://x/"},
            )
            assert created["name"] == "demo"

            loaded = _post_json(
                f"{base}/api/projects/load", {"path": project_path}
            )
            assert loaded["base_url"] == "http://x/"

            with pytest.raises(urllib.error.HTTPError) as excinfo:
                _get_json(f"{base}/api/missing")
            assert excinfo.value.code == 404
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_rejects_non_object_body(self, tmp_path: Path) -> None:
        server = make_server(host="127.0.0.1", port=0)
        host, port = bound_address(server)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            req = urllib.request.Request(
                f"http://{host}:{port}/api/projects/load",
                data=b"[]",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with pytest.raises(urllib.error.HTTPError) as excinfo:
                urllib.request.urlopen(req)
            assert excinfo.value.code == 400
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url: str, body: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))
