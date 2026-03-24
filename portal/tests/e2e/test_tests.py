"""E2E tests for the Tests page."""

from __future__ import annotations

from playwright.sync_api import Page

from .pages.tests_page import TestsPage


def test_cases_listed(page: Page, base_url: str) -> None:
    page.goto(base_url)
    tp = TestsPage(page)
    tp.navigate()
    page.wait_for_timeout(1000)
    assert tp.has_test_cases()


def test_run_tests_shows_results(page: Page, base_url: str) -> None:
    page.goto(base_url)
    tp = TestsPage(page)
    tp.navigate()
    tp.click_run_tests()
    tp.wait_for_results()
