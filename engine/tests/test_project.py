"""Pure-Python tests for the project module.

No browser. Verifies the project file loader, init helper, and path resolution.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fuzzmark.project import (
    Project,
    ProjectError,
    ProjectViewport,
    init_project,
    load_project,
    parse_project,
)


def _minimal() -> dict:
    return {"name": "demo", "base_url": "http://localhost:8000/"}


def _write(path: Path, raw: dict | str) -> Path:
    path.write_text(
        raw if isinstance(raw, str) else json.dumps(raw), encoding="utf-8"
    )
    return path


class TestParseProject:
    def test_minimal_project(self, tmp_path: Path) -> None:
        proj = parse_project(_minimal(), source_dir=tmp_path)
        assert proj.name == "demo"
        assert proj.base_url == "http://localhost:8000/"
        assert proj.viewports == ()
        assert proj.tests == ()
        assert proj.session is None

    def test_top_level_must_be_object(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectError, match="JSON object"):
            parse_project([], source_dir=tmp_path)  # type: ignore[arg-type]

    def test_requires_name(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectError, match="name"):
            parse_project({"base_url": "x"}, source_dir=tmp_path)
        with pytest.raises(ProjectError, match="name"):
            parse_project({"name": "  ", "base_url": "x"}, source_dir=tmp_path)

    def test_requires_base_url(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectError, match="base_url"):
            parse_project({"name": "d"}, source_dir=tmp_path)
        with pytest.raises(ProjectError, match="base_url"):
            parse_project(
                {"name": "d", "base_url": "  "}, source_dir=tmp_path
            )

    def test_optional_paths(self, tmp_path: Path) -> None:
        raw = _minimal() | {
            "session": "auth.json",
            "tables": "tables.json",
            "scan": "scan.json",
            "baselines": "baselines",
        }
        proj = parse_project(raw, source_dir=tmp_path)
        assert proj.session == "auth.json"
        assert proj.tables == "tables.json"
        assert proj.scan == "scan.json"
        assert proj.baselines == "baselines"

    @pytest.mark.parametrize("key", ["session", "tables", "scan", "baselines"])
    def test_optional_path_rejects_blank(self, tmp_path: Path, key: str) -> None:
        with pytest.raises(ProjectError, match=key):
            parse_project(_minimal() | {key: "   "}, source_dir=tmp_path)

    @pytest.mark.parametrize("key", ["session", "tables", "scan", "baselines"])
    def test_optional_path_rejects_non_string(
        self, tmp_path: Path, key: str
    ) -> None:
        with pytest.raises(ProjectError, match=key):
            parse_project(_minimal() | {key: 42}, source_dir=tmp_path)


class TestParseTests:
    def test_default_empty(self, tmp_path: Path) -> None:
        assert parse_project(_minimal(), source_dir=tmp_path).tests == ()

    def test_string_list(self, tmp_path: Path) -> None:
        raw = _minimal() | {"tests": ["tests/a.json", "tests/b.json"]}
        proj = parse_project(raw, source_dir=tmp_path)
        assert proj.tests == ("tests/a.json", "tests/b.json")

    def test_rejects_non_list(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectError, match="tests"):
            parse_project(_minimal() | {"tests": "tests/a.json"}, source_dir=tmp_path)

    def test_rejects_blank_entry(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectError, match=r"tests\[1\]"):
            parse_project(
                _minimal() | {"tests": ["ok.json", "  "]}, source_dir=tmp_path
            )

    def test_rejects_duplicates(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectError, match="duplicate"):
            parse_project(
                _minimal() | {"tests": ["a.json", "a.json"]}, source_dir=tmp_path
            )


class TestParseViewports:
    def test_default_empty(self, tmp_path: Path) -> None:
        assert parse_project(_minimal(), source_dir=tmp_path).viewports == ()

    def test_parses(self, tmp_path: Path) -> None:
        raw = _minimal() | {
            "viewports": [
                {"name": "desktop", "width": 1280, "height": 800},
                {"name": "mobile", "width": 375, "height": 667},
            ]
        }
        proj = parse_project(raw, source_dir=tmp_path)
        assert proj.viewports == (
            ProjectViewport("desktop", 1280, 800),
            ProjectViewport("mobile", 375, 667),
        )

    def test_rejects_empty_list(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectError, match="non-empty"):
            parse_project(_minimal() | {"viewports": []}, source_dir=tmp_path)

    def test_rejects_duplicate_names(self, tmp_path: Path) -> None:
        raw = _minimal() | {
            "viewports": [
                {"name": "desktop", "width": 1280, "height": 800},
                {"name": "desktop", "width": 1920, "height": 1080},
            ]
        }
        with pytest.raises(ProjectError, match="unique"):
            parse_project(raw, source_dir=tmp_path)

    def test_rejects_non_positive(self, tmp_path: Path) -> None:
        raw = _minimal() | {
            "viewports": [{"name": "x", "width": 0, "height": 100}]
        }
        with pytest.raises(ProjectError, match="positive"):
            parse_project(raw, source_dir=tmp_path)

    def test_rejects_missing_dim(self, tmp_path: Path) -> None:
        raw = _minimal() | {"viewports": [{"name": "x", "width": 100}]}
        with pytest.raises(ProjectError, match="height"):
            parse_project(raw, source_dir=tmp_path)


class TestPathResolution:
    def test_relative_resolves_against_source_dir(self, tmp_path: Path) -> None:
        raw = _minimal() | {"session": "auth.json", "baselines": "out/base"}
        proj = parse_project(raw, source_dir=tmp_path)
        assert proj.session_resolved == (tmp_path / "auth.json").resolve()
        assert proj.baselines_resolved == (tmp_path / "out/base").resolve()

    def test_absolute_kept_as_is(self, tmp_path: Path) -> None:
        absolute = str(tmp_path / "elsewhere.json")
        raw = _minimal() | {"session": absolute}
        proj = parse_project(raw, source_dir=tmp_path / "subdir")
        assert proj.session_resolved == Path(absolute)

    def test_none_when_unset(self, tmp_path: Path) -> None:
        proj = parse_project(_minimal(), source_dir=tmp_path)
        assert proj.session_resolved is None
        assert proj.tables_resolved is None
        assert proj.scan_resolved is None
        assert proj.baselines_resolved is None
        assert proj.tests_resolved == ()

    def test_tests_resolved(self, tmp_path: Path) -> None:
        raw = _minimal() | {"tests": ["a.json", "nested/b.json"]}
        proj = parse_project(raw, source_dir=tmp_path)
        assert proj.tests_resolved == (
            (tmp_path / "a.json").resolve(),
            (tmp_path / "nested/b.json").resolve(),
        )


class TestRoundTrip:
    def test_to_dict_drops_unset_optionals(self, tmp_path: Path) -> None:
        proj = parse_project(_minimal(), source_dir=tmp_path)
        assert proj.to_dict() == _minimal()

    def test_to_dict_includes_everything_set(self, tmp_path: Path) -> None:
        raw = _minimal() | {
            "viewports": [{"name": "d", "width": 100, "height": 200}],
            "session": "auth.json",
            "tables": "t.json",
            "scan": "s.json",
            "baselines": "b",
            "tests": ["a.json"],
        }
        proj = parse_project(raw, source_dir=tmp_path)
        assert proj.to_dict() == raw

    def test_parse_round_trip(self, tmp_path: Path) -> None:
        raw = _minimal() | {
            "viewports": [{"name": "d", "width": 100, "height": 200}],
            "tests": ["a.json"],
        }
        proj = parse_project(raw, source_dir=tmp_path)
        again = parse_project(proj.to_dict(), source_dir=tmp_path)
        assert again == proj


class TestLoadProject:
    def test_loads_from_disk(self, tmp_path: Path) -> None:
        path = _write(tmp_path / "p.json", _minimal())
        proj = load_project(path)
        assert proj.name == "demo"
        assert proj.source_dir == tmp_path

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectError, match="not found"):
            load_project(tmp_path / "nope.json")

    def test_invalid_json(self, tmp_path: Path) -> None:
        _write(tmp_path / "p.json", "{not-json")
        with pytest.raises(ProjectError, match="not valid JSON"):
            load_project(tmp_path / "p.json")

    def test_source_dir_drives_resolution(self, tmp_path: Path) -> None:
        path = _write(tmp_path / "p.json", _minimal() | {"baselines": "b"})
        proj = load_project(path)
        assert proj.baselines_resolved == (tmp_path / "b").resolve()


class TestInitProject:
    def test_writes_starter_file(self, tmp_path: Path) -> None:
        path = tmp_path / "p.json"
        proj = init_project(path, name="demo", base_url="http://localhost:8000/")
        assert path.exists()
        roundtripped = load_project(path)
        assert roundtripped.name == proj.name == "demo"
        assert roundtripped.base_url == "http://localhost:8000/"

    def test_writes_viewports(self, tmp_path: Path) -> None:
        path = tmp_path / "p.json"
        init_project(
            path,
            name="demo",
            base_url="http://x/",
            viewports=(ProjectViewport("desktop", 1280, 800),),
        )
        loaded = load_project(path)
        assert loaded.viewports == (ProjectViewport("desktop", 1280, 800),)

    def test_refuses_to_overwrite(self, tmp_path: Path) -> None:
        path = tmp_path / "p.json"
        path.write_text("existing", encoding="utf-8")
        with pytest.raises(ProjectError, match="overwrite"):
            init_project(path, name="d", base_url="http://x/")

    def test_force_overwrites(self, tmp_path: Path) -> None:
        path = tmp_path / "p.json"
        path.write_text("existing", encoding="utf-8")
        init_project(path, name="d", base_url="http://x/", overwrite=True)
        assert load_project(path).name == "d"

    def test_rejects_blank_name(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectError, match="name"):
            init_project(tmp_path / "p.json", name="  ", base_url="http://x/")

    def test_rejects_blank_base_url(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectError, match="base_url"):
            init_project(tmp_path / "p.json", name="d", base_url="")

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "deep" / "p.json"
        init_project(path, name="d", base_url="http://x/")
        assert path.exists()
