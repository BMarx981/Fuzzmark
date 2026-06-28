"""Unit tests for the rule-based suggestion engine.

Pure: no browser, no I/O. Builds `Field` objects directly so the engine can be
exercised independently of the extractor.
"""

from __future__ import annotations

from fuzzmark.extractor import Field, Option, Validation
from fuzzmark.suggestions import (
    BOUNDARY,
    CATEGORIES,
    EMPTY,
    FORMAT_INVALID,
    FORMAT_VALID,
    I18N,
    SECURITY,
    TYPE_SPECIFIC,
    suggest,
    suggest_all,
)
from fuzzmark.suggestions.tables import TYPE_TABLES


def _field(
    *,
    kind: str = "input",
    type: str | None = "text",
    selector: str = "#x",
    required: bool = False,
    minlength: int | None = None,
    maxlength: int | None = None,
    min: str | None = None,
    max: str | None = None,
    pattern: str | None = None,
    options: list[Option] | None = None,
) -> Field:
    return Field(
        selector=selector,
        kind=kind,
        type=type,
        name=None,
        id=None,
        label=None,
        validation=Validation(
            required=required,
            minlength=minlength,
            maxlength=maxlength,
            min=min,
            max=max,
            pattern=pattern,
        ),
        options=options or [],
    )


def _categories(suggestions) -> set[str]:
    return {s.category for s in suggestions}


def _values(suggestions) -> list[str]:
    return [s.value for s in suggestions]


class TestEmptyRequired:
    def test_required_field_gets_empty_and_whitespace(self):
        s = suggest(_field(required=True))
        empties = [x for x in s if x.category == EMPTY]
        assert any(x.value == "" for x in empties)
        assert any(x.value.strip() == "" and x.value != "" for x in empties)

    def test_non_required_field_skips_empty_category(self):
        s = suggest(_field(required=False))
        assert not any(x.category == EMPTY for x in s)


class TestLengthBoundary:
    def test_maxlength_emits_at_and_over(self):
        s = suggest(_field(type="text", maxlength=5))
        vals = _values([x for x in s if x.category == BOUNDARY])
        assert "a" * 5 in vals
        assert "a" * 6 in vals

    def test_minlength_emits_under_and_at(self):
        s = suggest(_field(type="text", minlength=3))
        vals = _values([x for x in s if x.category == BOUNDARY])
        assert "a" * 2 in vals
        assert "a" * 3 in vals


class TestNumericBoundary:
    def test_number_field_emits_min_max_boundaries(self):
        s = suggest(_field(type="number", min="16", max="120"))
        boundary_vals = _values([x for x in s if x.category == BOUNDARY])
        assert "15" in boundary_vals
        assert "16" in boundary_vals
        assert "120" in boundary_vals
        assert "121" in boundary_vals

    def test_number_field_does_not_use_length_boundary(self):
        s = suggest(_field(type="number", min="0", max="9", maxlength=5))
        boundary_vals = _values([x for x in s if x.category == BOUNDARY])
        assert "aaaaa" not in boundary_vals


class TestTypeRoutes:
    def test_email_has_format_valid_and_invalid(self):
        s = suggest(_field(type="email"))
        cats = _categories(s)
        assert FORMAT_VALID in cats
        assert FORMAT_INVALID in cats

    def test_tel_includes_security_payloads(self):
        s = suggest(_field(type="tel"))
        assert SECURITY in _categories(s)

    def test_unknown_type_falls_back_to_text(self):
        s = suggest(_field(type="madeuptype"))
        assert SECURITY in _categories(s)

    def test_textarea_includes_multiline(self):
        s = suggest(_field(kind="textarea", type=None))
        assert any("\n" in x.value for x in s)


class TestTypeCoverage:
    """Every HTML5 input type that ships with a curated table.

    Phase 4: full suggestion-category coverage. Each table is asserted to fire
    its expected category set so accidental regressions surface as test failures
    rather than as silently emptier chip menus.
    """

    @staticmethod
    def _cats(input_type: str) -> set[str]:
        return _categories(suggest(_field(type=input_type)))

    def test_url(self):
        cats = self._cats("url")
        assert {FORMAT_VALID, FORMAT_INVALID, SECURITY, TYPE_SPECIFIC} <= cats

    def test_password(self):
        cats = self._cats("password")
        assert {FORMAT_VALID, FORMAT_INVALID, SECURITY, I18N, TYPE_SPECIFIC} <= cats

    def test_date(self):
        cats = self._cats("date")
        assert {FORMAT_VALID, FORMAT_INVALID, TYPE_SPECIFIC} <= cats
        vals = _values(suggest(_field(type="date")))
        assert "2025-02-30" in vals
        assert "2024-02-29" in vals

    def test_time(self):
        cats = self._cats("time")
        assert {FORMAT_VALID, FORMAT_INVALID, TYPE_SPECIFIC} <= cats
        assert "25:00" in _values(suggest(_field(type="time")))

    def test_datetime_local(self):
        cats = self._cats("datetime-local")
        assert {FORMAT_VALID, FORMAT_INVALID, TYPE_SPECIFIC} <= cats

    def test_month(self):
        cats = self._cats("month")
        assert {FORMAT_VALID, FORMAT_INVALID, TYPE_SPECIFIC} <= cats

    def test_week(self):
        cats = self._cats("week")
        assert {FORMAT_VALID, FORMAT_INVALID, TYPE_SPECIFIC} <= cats
        assert "2025-W54" in _values(suggest(_field(type="week")))

    def test_color(self):
        cats = self._cats("color")
        assert {FORMAT_VALID, FORMAT_INVALID, TYPE_SPECIFIC} <= cats
        vals = _values(suggest(_field(type="color")))
        assert "#ff0000" in vals
        assert "rgb(255,0,0)" in vals

    def test_range_uses_numeric_boundaries(self):
        s = suggest(_field(type="range", min="0", max="100"))
        boundary_vals = _values([x for x in s if x.category == BOUNDARY])
        assert "0" in boundary_vals
        assert "100" in boundary_vals
        assert "101" in boundary_vals

    def test_range_does_not_use_length_boundary(self):
        s = suggest(_field(type="range", min="0", max="9", maxlength=5))
        boundary_vals = _values([x for x in s if x.category == BOUNDARY])
        assert "aaaaa" not in boundary_vals

    def test_every_table_only_uses_known_categories(self):
        known = set(CATEGORIES)
        for input_type, table in TYPE_TABLES.items():
            unknown = {s.category for s in table} - known
            assert not unknown, f"{input_type} table uses unknown categories {unknown}"


class TestSelect:
    def test_select_emits_one_format_valid_per_real_option(self):
        opts = [Option("", "Choose"), Option("DE", "Delaware"), Option("MD", "Maryland")]
        s = suggest(_field(kind="select", type=None, options=opts))
        valid = [x for x in s if x.category == FORMAT_VALID]
        assert {x.value for x in valid} == {"DE", "MD"}

    def test_select_emits_placeholder_as_empty(self):
        opts = [Option("", "Choose"), Option("DE", "Delaware")]
        s = suggest(_field(kind="select", type=None, options=opts))
        assert any(x.category == EMPTY and x.value == "" for x in s)

    def test_select_emits_unknown_value_as_format_invalid(self):
        opts = [Option("DE", "Delaware")]
        s = suggest(_field(kind="select", type=None, options=opts))
        assert any(x.category == FORMAT_INVALID for x in s)


class TestDeterminism:
    def test_same_field_yields_identical_output(self):
        f = _field(type="email", required=True, maxlength=120)
        assert [s.to_dict() for s in suggest(f)] == [s.to_dict() for s in suggest(f)]

    def test_no_duplicate_category_value_pairs(self):
        s = suggest(_field(type="email", required=True, maxlength=120))
        pairs = [(x.category, x.value) for x in s]
        assert len(pairs) == len(set(pairs))


class TestFieldRefAttribution:
    def test_each_suggestion_records_selector(self):
        s = suggest(_field(selector="#email", type="email"))
        assert all(x.field_ref == "#email" for x in s)


class TestSuggestAll:
    def test_keys_by_selector(self):
        a = _field(selector="#a", type="text")
        b = _field(selector="#b", type="email")
        out = suggest_all([a, b])
        assert set(out.keys()) == {"#a", "#b"}
        assert all(x.field_ref == "#a" for x in out["#a"])
        assert all(x.field_ref == "#b" for x in out["#b"])
