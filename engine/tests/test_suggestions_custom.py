"""Tests for user-extensible suggestion tables (Phase 4 spec §5.3).

Pure: no browser, no I/O beyond temp JSON files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fuzzmark.extractor import Field, Validation
from fuzzmark.suggestions import (
    CustomTablesError,
    FORMAT_INVALID,
    FORMAT_VALID,
    SECURITY,
    Suggestion,
    load_custom_tables,
    merge_tables,
    suggest,
)


def _field(*, type: str = "text", selector: str = "#x") -> Field:
    return Field(
        selector=selector,
        kind="input",
        type=type,
        name=None,
        id=None,
        label=None,
        validation=Validation(),
        options=[],
    )


def _write(tmp_path: Path, payload: dict) -> str:
    path = tmp_path / "tables.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


class TestLoad:
    def test_extend_parses_rows_into_suggestions(self, tmp_path):
        spec = load_custom_tables(
            _write(
                tmp_path,
                {
                    "tables": {
                        "email": {
                            "extend": [
                                {"category": "format-valid", "value": "ceo@acme.com", "label": "CEO"}
                            ]
                        }
                    }
                },
            )
        )
        assert spec == {"email": {"extend": (Suggestion(FORMAT_VALID, "ceo@acme.com", "CEO"),)}}

    def test_replace_drops_the_built_in(self, tmp_path):
        spec = load_custom_tables(
            _write(
                tmp_path,
                {
                    "tables": {
                        "color": {
                            "replace": [
                                {"category": "format-valid", "value": "#003366", "label": "brand"}
                            ]
                        }
                    }
                },
            )
        )
        assert "replace" in spec["color"]
        assert spec["color"]["replace"][0].value == "#003366"

    def test_top_level_tables_key_is_optional(self, tmp_path):
        spec = load_custom_tables(
            _write(
                tmp_path,
                {
                    "ssn": {
                        "extend": [
                            {"category": "format-valid", "value": "555-55-5555", "label": "test"}
                        ]
                    }
                },
            )
        )
        assert "ssn" in spec

    def test_unknown_category_is_rejected(self, tmp_path):
        with pytest.raises(CustomTablesError, match="unknown category"):
            load_custom_tables(
                _write(
                    tmp_path,
                    {
                        "tables": {
                            "email": {
                                "extend": [
                                    {"category": "made-up", "value": "x", "label": "y"}
                                ]
                            }
                        }
                    },
                )
            )

    def test_missing_required_keys_is_rejected(self, tmp_path):
        with pytest.raises(CustomTablesError, match="missing required keys"):
            load_custom_tables(
                _write(
                    tmp_path,
                    {"tables": {"email": {"extend": [{"category": "format-valid"}]}}},
                )
            )

    def test_unknown_mode_is_rejected(self, tmp_path):
        with pytest.raises(CustomTablesError, match="unknown keys"):
            load_custom_tables(
                _write(tmp_path, {"tables": {"email": {"append": []}}})
            )

    def test_empty_spec_is_rejected(self, tmp_path):
        with pytest.raises(CustomTablesError, match="extend or replace"):
            load_custom_tables(_write(tmp_path, {"tables": {"email": {}}}))


class TestMerge:
    def test_extend_appends_to_built_in(self):
        custom = {"email": {"extend": (Suggestion(FORMAT_VALID, "ceo@acme.com", "CEO"),)}}
        merged = merge_tables(custom)
        assert merged["email"][-1].value == "ceo@acme.com"
        assert any(s.value == "user@example.com" for s in merged["email"])

    def test_replace_drops_built_in(self):
        custom = {"email": {"replace": (Suggestion(FORMAT_VALID, "only@acme.com", "only"),)}}
        merged = merge_tables(custom)
        assert merged["email"] == (Suggestion(FORMAT_VALID, "only@acme.com", "only"),)

    def test_extend_creates_table_for_new_type(self):
        custom = {"ssn": {"extend": (Suggestion(FORMAT_VALID, "555-55-5555", "test SSN"),)}}
        merged = merge_tables(custom)
        assert merged["ssn"] == (Suggestion(FORMAT_VALID, "555-55-5555", "test SSN"),)

    def test_replace_plus_extend_concatenates(self):
        custom = {
            "color": {
                "replace": (Suggestion(FORMAT_VALID, "#000", "black"),),
                "extend": (Suggestion(FORMAT_INVALID, "garbage", "bad"),),
            }
        }
        merged = merge_tables(custom)
        assert [s.value for s in merged["color"]] == ["#000", "garbage"]


class TestSuggestUsesCustom:
    def test_custom_table_reaches_suggest(self):
        custom = {"email": {"extend": (Suggestion(FORMAT_VALID, "ceo@acme.com", "CEO"),)}}
        merged = merge_tables(custom)
        values = [s.value for s in suggest(_field(type="email"), tables=merged)]
        assert "ceo@acme.com" in values
        assert "user@example.com" in values

    def test_replace_hides_built_in_rows(self):
        custom = {"email": {"replace": (Suggestion(FORMAT_VALID, "only@acme.com", "only"),)}}
        merged = merge_tables(custom)
        values = [s.value for s in suggest(_field(type="email"), tables=merged)]
        assert "only@acme.com" in values
        assert "user@example.com" not in values

    def test_new_type_routes_to_user_table(self):
        custom = {"ssn": {"extend": (Suggestion(FORMAT_VALID, "555-55-5555", "test SSN"),)}}
        merged = merge_tables(custom)
        values = [s.value for s in suggest(_field(type="ssn"), tables=merged)]
        assert "555-55-5555" in values
        assert "Quick brown fox" not in values

    def test_unknown_type_without_custom_still_falls_back_to_text(self):
        values = [s.value for s in suggest(_field(type="not-a-real-type"))]
        assert any("script" in v.lower() for v in values)

    def test_default_call_path_unchanged(self):
        values_default = [s.value for s in suggest(_field(type="email"))]
        values_none = [s.value for s in suggest(_field(type="email"), tables=None)]
        assert values_default == values_none
