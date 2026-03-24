"""E2E tests for sidebar navigation and health indicator."""

from __future__ import annotations

from playwright.sync_api import Page

from .pages.base_page import BasePage


def test_initial_page_is_dashboard(page: Page, base_url: str) -> None:
    page.goto(base_url)
    bp = BasePage(page)
    bp.wait_for_heading("Dashboard")
    assert bp.get_active_nav_text() == "Dashboard"


def test_navigate_all_pages(page: Page, base_url: str) -> None:
    page.goto(base_url)
    bp = BasePage(page)

    pages = {
        "Dashboard": "Dashboard",
        "Validate": "Schema Validation",
        "Pipeline": "Pipeline Results",
        "Tests": "Test Harness",
        "Compare": "Compare",
        "Config": "Configuration",
    }
    for nav_label, heading in pages.items():
        bp.navigate_to(nav_label)
        bp.wait_for_heading(heading)


def test_health_indicator_shows_ok(page: Page, base_url: str) -> None:
    page.goto(base_url)
    bp = BasePage(page)
    page.wait_for_timeout(2000)  # allow health fetch
    assert bp.get_health_status() == "ok"


def test_active_nav_highlighting(page: Page, base_url: str) -> None:
    page.goto(base_url)
    bp = BasePage(page)
    bp.navigate_to("Compare")
    bp.wait_for_heading("Compare")
    assert bp.get_active_nav_text() == "Compare"
    bp.navigate_to("Config")
    bp.wait_for_heading("Configuration")
    assert bp.get_active_nav_text() == "Config"
