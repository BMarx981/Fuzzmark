"""Shared pytest hooks and fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-browser",
        action="store_true",
        default=False,
        help="Run tests marked `browser` (requires a Playwright Chromium install).",
    )
    parser.addoption(
        "--run-sim",
        action="store_true",
        default=False,
        help="Run tests marked `simulator` (requires Xcode + iOS Simulator on macOS).",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    skips: list[tuple[str, pytest.MarkDecorator]] = []
    if not config.getoption("--run-browser"):
        skips.append(("browser", pytest.mark.skip(reason="needs --run-browser")))
    if not config.getoption("--run-sim"):
        skips.append(("simulator", pytest.mark.skip(reason="needs --run-sim")))
    if not skips:
        return
    for item in items:
        for keyword, marker in skips:
            if keyword in item.keywords:
                item.add_marker(marker)


@pytest.fixture(scope="session")
def fixture_form_url() -> str:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "form.html"
    assert path.exists(), f"fixture missing: {path}"
    return path.as_uri()


@pytest.fixture(scope="session")
def fixture_site_url() -> str:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "site" / "index.html"
    assert path.exists(), f"fixture missing: {path}"
    return path.as_uri()


@pytest.fixture(scope="session")
def fixture_components_url() -> str:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "components.html"
    assert path.exists(), f"fixture missing: {path}"
    return path.as_uri()


@pytest.fixture(scope="session")
def fixture_components_reveal_url() -> str:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "components_reveal.html"
    assert path.exists(), f"fixture missing: {path}"
    return path.as_uri()


@pytest.fixture(scope="session")
def fixture_ctas_url() -> str:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "ctas.html"
    assert path.exists(), f"fixture missing: {path}"
    return path.as_uri()


@pytest.fixture(scope="session")
def fixture_wizard_url() -> str:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "wizard.html"
    assert path.exists(), f"fixture missing: {path}"
    return path.as_uri()
