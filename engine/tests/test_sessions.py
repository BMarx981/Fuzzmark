"""Pure-Python tests for the sessions module and Test JSON `session` field.

No browser. Verifies the storage_state validator and the loader integration.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fuzzmark.driver import parse_test
from fuzzmark.sessions import SessionError, validate_session


def _empty_state() -> dict:
    return {"cookies": [], "origins": []}


def _write(path: Path, raw: dict | str) -> Path:
    path.write_text(
        raw if isinstance(raw, str) else json.dumps(raw), encoding="utf-8"
    )
    return path


class TestValidateSession:
    def test_accepts_minimal_state(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "s.json", _empty_state())
        state = validate_session(p)
        assert state["cookies"] == []
        assert state["origins"] == []

    def test_missing_file_errors(self, tmp_path: Path) -> None:
        with pytest.raises(SessionError, match="not found"):
            validate_session(tmp_path / "nope.json")

    def test_invalid_json_errors(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "s.json", "{not-json")
        with pytest.raises(SessionError, match="not valid JSON"):
            validate_session(p)

    def test_top_level_must_be_object(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "s.json", "[]")
        with pytest.raises(SessionError, match="JSON object"):
            validate_session(p)

    def test_requires_cookies_and_origins_lists(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "s.json", {"cookies": []})
        with pytest.raises(SessionError, match="cookies"):
            validate_session(p)
        p = _write(tmp_path / "s.json", {"cookies": "x", "origins": []})
        with pytest.raises(SessionError, match="cookies"):
            validate_session(p)


def _minimal() -> dict:
    return {
        "name": "auth-flow",
        "flow": [
            {"kind": "visit", "url": "about:blank"},
            {"kind": "capture", "name": "shot"},
        ],
    }


class TestTestSessionField:
    def test_default_is_none(self) -> None:
        assert parse_test(_minimal()).session is None

    def test_string_path_loaded(self) -> None:
        raw = _minimal() | {"session": "/tmp/auth.json"}
        assert parse_test(raw).session == "/tmp/auth.json"

    def test_round_trip_includes_session(self) -> None:
        raw = _minimal() | {"session": "auth.json"}
        test = parse_test(raw)
        assert parse_test(test.to_dict()).session == "auth.json"

    def test_round_trip_omits_session_when_unset(self) -> None:
        test = parse_test(_minimal())
        assert "session" not in test.to_dict()

    def test_empty_string_rejected(self) -> None:
        raw = _minimal() | {"session": "   "}
        with pytest.raises(ValueError, match="session"):
            parse_test(raw)

    def test_non_string_rejected(self) -> None:
        raw = _minimal() | {"session": 42}
        with pytest.raises(ValueError, match="session"):
            parse_test(raw)
