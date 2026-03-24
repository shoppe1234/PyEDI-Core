"""E2E tests for the Config page."""

from __future__ import annotations

from playwright.sync_api import Page

from .pages.config_page import ConfigPage


def test_config_displays_json(page: Page, base_url: str) -> None:
    page.goto(base_url)
    cp = ConfigPage(page)
    cp.navigate()
    page.wait_for_timeout(1000)
    assert cp.has_config_json()


def test_config_contains_expected_keys(page: Page, base_url: str) -> None:
    page.goto(base_url)
    cp = ConfigPage(page)
    cp.navigate()
    page.wait_for_timeout(1000)
    text = cp.get_config_text()
    assert "system" in text
    assert "directories" in text
    assert "compare" in text
