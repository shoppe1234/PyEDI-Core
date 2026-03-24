"""E2E tests for the Dashboard page."""

from __future__ import annotations

from playwright.sync_api import Page

from .pages.dashboard_page import DashboardPage


def test_dashboard_loads_stats(page: Page, base_url: str) -> None:
    page.goto(base_url)
    dp = DashboardPage(page)
    dp.navigate()
    page.wait_for_timeout(1000)
    assert dp.has_stat_cards()


def test_dashboard_page_renders(page: Page, base_url: str) -> None:
    """Dashboard page renders without errors (recent processing may be empty)."""
    page.goto(base_url)
    dp = DashboardPage(page)
    dp.navigate()
    page.wait_for_timeout(1000)
    # Page loaded successfully if heading is visible
    dp.wait_for_heading("Dashboard")
