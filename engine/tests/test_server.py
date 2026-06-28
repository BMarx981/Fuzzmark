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

from fuzzmark.driver import CaptureArtifact, RunResult
from fuzzmark.extractor import Field, Option, Validation
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


class TestPagesRoute:
    def _project_with_scan(self, tmp_path: Path) -> str:
        path = str(tmp_path / "project.json")
        dispatch(
            "POST",
            "/api/projects/init",
            {"path": path, "name": "demo", "base_url": "http://example.test/"},
        )
        site_map = {
            "base_url": "http://example.test/",
            "bounds": {},
            "page_count": 2,
            "skipped_count": 0,
            "pages": [
                {
                    "url": "http://example.test/",
                    "depth": 0,
                    "parent_url": None,
                    "title": "Home",
                    "links": [],
                    "error": None,
                },
                {
                    "url": "http://example.test/about",
                    "depth": 1,
                    "parent_url": "http://example.test/",
                    "title": "About",
                    "links": [],
                    "error": None,
                },
            ],
            "skipped": [],
        }
        dispatch(
            "POST",
            "/api/projects/scan/save",
            {"path": path, "site_map": site_map},
        )
        return path

    def test_returns_pages_from_saved_scan(self, tmp_path: Path) -> None:
        path = self._project_with_scan(tmp_path)
        body = dispatch("POST", "/api/projects/pages", {"path": path})
        assert body["base_url"] == "http://example.test/"
        assert [p["url"] for p in body["pages"]] == [
            "http://example.test/",
            "http://example.test/about",
        ]
        assert body["pages"][0]["title"] == "Home"

    def test_requires_saved_scan(self, tmp_path: Path) -> None:
        path = str(tmp_path / "project.json")
        dispatch(
            "POST",
            "/api/projects/init",
            {"path": path, "name": "demo", "base_url": "http://x/"},
        )
        with pytest.raises(RouteError) as excinfo:
            dispatch("POST", "/api/projects/pages", {"path": path})
        assert excinfo.value.status == 400
        assert "scan" in excinfo.value.message


class TestExtractRoute:
    def _init_project(self, tmp_path: Path) -> str:
        path = str(tmp_path / "project.json")
        dispatch(
            "POST",
            "/api/projects/init",
            {"path": path, "name": "demo", "base_url": "http://x/"},
        )
        return path

    def test_extract_uses_session_and_returns_field_dicts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = self._init_project(tmp_path)
        captured: dict = {}

        def fake_extract(url, *, session=None):
            captured["url"] = url
            captured["session"] = session
            return [
                Field(
                    selector="#email",
                    kind="input",
                    type="email",
                    name="email",
                    id="email",
                    label="Email",
                    validation=Validation(required=True, maxlength=64),
                    options=[],
                )
            ]

        monkeypatch.setattr(server_routes, "_extract_fields", fake_extract)
        body = dispatch(
            "POST",
            "/api/projects/extract",
            {"path": path, "url": "http://x/login"},
        )
        assert captured["url"] == "http://x/login"
        assert captured["session"] is None
        assert body["url"] == "http://x/login"
        assert len(body["fields"]) == 1
        f = body["fields"][0]
        assert f["selector"] == "#email"
        assert f["validation"]["required"] is True
        assert f["validation"]["maxlength"] == 64


class TestSuggestRoute:
    def _init_project(self, tmp_path: Path) -> str:
        path = str(tmp_path / "project.json")
        dispatch(
            "POST",
            "/api/projects/init",
            {"path": path, "name": "demo", "base_url": "http://x/"},
        )
        return path

    def test_suggests_for_extracted_fields(self, tmp_path: Path) -> None:
        path = self._init_project(tmp_path)
        fields = [
            Field(
                selector="#email",
                kind="input",
                type="email",
                name="email",
                id="email",
                label="Email",
                validation=Validation(required=True),
            ).to_dict(),
            Field(
                selector="#country",
                kind="select",
                type=None,
                name="country",
                id="country",
                label="Country",
                validation=Validation(),
                options=[Option(value="us", label="USA"), Option(value="ca", label="Canada")],
            ).to_dict(),
        ]
        body = dispatch(
            "POST",
            "/api/projects/suggest",
            {"path": path, "fields": fields},
        )
        sug = body["suggestions"]
        assert "#email" in sug and "#country" in sug
        email_categories = {s["category"] for s in sug["#email"]}
        assert "empty" in email_categories
        country_values = [s["value"] for s in sug["#country"]]
        assert "us" in country_values
        assert "ca" in country_values

    def test_honors_project_custom_tables(self, tmp_path: Path) -> None:
        path = str(tmp_path / "project.json")
        tables_path = tmp_path / "tables.json"
        tables_path.write_text(
            json.dumps(
                {
                    "tables": {
                        "email": {
                            "extend": [
                                {
                                    "category": "format-valid",
                                    "value": "ceo@acme.com",
                                    "label": "CEO",
                                }
                            ]
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        dispatch(
            "POST",
            "/api/projects/init",
            {"path": path, "name": "d", "base_url": "http://x/"},
        )
        Path(path).write_text(
            json.dumps(
                {"name": "d", "base_url": "http://x/", "tables": "tables.json"}
            ),
            encoding="utf-8",
        )
        body = dispatch(
            "POST",
            "/api/projects/suggest",
            {
                "path": path,
                "fields": [
                    Field(
                        selector="#email",
                        kind="input",
                        type="email",
                        name=None,
                        id=None,
                        label=None,
                        validation=Validation(),
                    ).to_dict()
                ],
            },
        )
        values = [s["value"] for s in body["suggestions"]["#email"]]
        assert "ceo@acme.com" in values

    def test_rejects_non_list_fields(self, tmp_path: Path) -> None:
        path = self._init_project(tmp_path)
        with pytest.raises(RouteError) as excinfo:
            dispatch(
                "POST",
                "/api/projects/suggest",
                {"path": path, "fields": "nope"},
            )
        assert excinfo.value.status == 400


class TestTestsSaveRoute:
    def _init_project(self, tmp_path: Path) -> str:
        path = str(tmp_path / "project.json")
        dispatch(
            "POST",
            "/api/projects/init",
            {"path": path, "name": "demo", "base_url": "http://x/"},
        )
        return path

    def _valid_test(self) -> dict:
        return {
            "name": "smoke",
            "flow": [
                {"kind": "visit", "url": "http://x/"},
                {"kind": "fill", "selector": "#email", "value": "a@b.co"},
                {"kind": "capture", "name": "after-fill"},
            ],
        }

    def test_writes_file_and_links_to_project(self, tmp_path: Path) -> None:
        path = self._init_project(tmp_path)
        body = dispatch(
            "POST",
            "/api/projects/tests/save",
            {"path": path, "test": self._valid_test()},
        )
        assert body["tests"] == ["tests/smoke.json"]
        written = tmp_path / "tests" / "smoke.json"
        assert written.exists()
        on_disk = json.loads(written.read_text(encoding="utf-8"))
        assert on_disk["name"] == "smoke"
        assert on_disk["flow"][0]["kind"] == "visit"

    def test_custom_filename(self, tmp_path: Path) -> None:
        path = self._init_project(tmp_path)
        body = dispatch(
            "POST",
            "/api/projects/tests/save",
            {
                "path": path,
                "test": self._valid_test(),
                "filename": "flows/login.json",
            },
        )
        assert body["tests"] == ["flows/login.json"]
        assert (tmp_path / "flows" / "login.json").exists()

    def test_refuses_overwrite_without_force(self, tmp_path: Path) -> None:
        path = self._init_project(tmp_path)
        dispatch(
            "POST",
            "/api/projects/tests/save",
            {"path": path, "test": self._valid_test()},
        )
        with pytest.raises(RouteError) as excinfo:
            dispatch(
                "POST",
                "/api/projects/tests/save",
                {"path": path, "test": self._valid_test()},
            )
        assert excinfo.value.status == 400

    def test_rejects_path_escape(self, tmp_path: Path) -> None:
        path = self._init_project(tmp_path)
        with pytest.raises(RouteError) as excinfo:
            dispatch(
                "POST",
                "/api/projects/tests/save",
                {
                    "path": path,
                    "test": self._valid_test(),
                    "filename": "../escape.json",
                },
            )
        assert excinfo.value.status == 400

    def test_rejects_invalid_test_body(self, tmp_path: Path) -> None:
        path = self._init_project(tmp_path)
        with pytest.raises(RouteError) as excinfo:
            dispatch(
                "POST",
                "/api/projects/tests/save",
                {"path": path, "test": {"name": "x", "flow": []}},
            )
        assert excinfo.value.status == 400


class TestTestsRunRoute:
    def _project_with_test(self, tmp_path: Path) -> tuple[str, str]:
        path = str(tmp_path / "project.json")
        dispatch(
            "POST",
            "/api/projects/init",
            {
                "path": path,
                "name": "demo",
                "base_url": "http://x/",
                "viewports": [
                    {"name": "desktop", "width": 1024, "height": 768}
                ],
            },
        )
        body = dispatch(
            "POST",
            "/api/projects/tests/save",
            {
                "path": path,
                "test": {
                    "name": "smoke",
                    "flow": [
                        {"kind": "visit", "url": "http://x/"},
                        {"kind": "capture", "name": "home"},
                    ],
                },
            },
        )
        return path, body["tests"][0]

    def _stub_run(self, captured: dict, run_dir_capture: dict) -> object:
        def fake(test, output_dir, *, viewport, headless, session):
            captured["test_name"] = test.name
            captured["viewport"] = viewport
            captured["headless"] = headless
            captured["session"] = session
            run_dir_capture["dir"] = Path(output_dir)
            screenshot = Path(output_dir) / "home.png"
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            screenshot.write_bytes(b"\x89PNG\r\n\x1a\n")
            return RunResult(
                test_name=test.name,
                captures=[
                    CaptureArtifact(
                        name="home",
                        step_index=1,
                        screenshot_path=str(screenshot),
                    )
                ],
            )

        return fake

    def test_runs_test_and_writes_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path, test_rel = self._project_with_test(tmp_path)
        captured: dict = {}
        run_dir_capture: dict = {}
        monkeypatch.setattr(
            server_routes, "_run_flow", self._stub_run(captured, run_dir_capture)
        )

        body = dispatch(
            "POST",
            "/api/projects/tests/run",
            {"path": path, "test": test_rel},
        )

        assert captured["test_name"] == "smoke"
        assert captured["viewport"] == (1024, 768)
        assert captured["headless"] is True
        assert captured["session"] is None
        assert run_dir_capture["dir"] == tmp_path / "runs" / "smoke"
        assert body["result"]["test_name"] == "smoke"
        assert body["result"]["captures"][0]["name"] == "home"
        assert body["run_dir"] == str((tmp_path / "runs" / "smoke").resolve())
        result_path = Path(body["result_path"])
        assert result_path.exists()
        on_disk = json.loads(result_path.read_text(encoding="utf-8"))
        assert on_disk["test_name"] == "smoke"

    def test_honors_headed_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path, test_rel = self._project_with_test(tmp_path)
        captured: dict = {}
        monkeypatch.setattr(
            server_routes, "_run_flow", self._stub_run(captured, {})
        )

        dispatch(
            "POST",
            "/api/projects/tests/run",
            {"path": path, "test": test_rel, "headed": True},
        )
        assert captured["headless"] is False

    def test_rejects_test_outside_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path, _ = self._project_with_test(tmp_path)
        outside = tmp_path.parent / "elsewhere.json"

        def fail(*_a, **_kw):
            raise AssertionError("run should not start when test path is rejected")

        monkeypatch.setattr(server_routes, "_run_flow", fail)
        with pytest.raises(RouteError) as excinfo:
            dispatch(
                "POST",
                "/api/projects/tests/run",
                {"path": path, "test": str(outside)},
            )
        assert excinfo.value.status == 400

    def test_rejects_missing_test_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path, _ = self._project_with_test(tmp_path)

        def fail(*_a, **_kw):
            raise AssertionError("run should not start when test file is missing")

        monkeypatch.setattr(server_routes, "_run_flow", fail)
        with pytest.raises(RouteError) as excinfo:
            dispatch(
                "POST",
                "/api/projects/tests/run",
                {"path": path, "test": "tests/nope.json"},
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
