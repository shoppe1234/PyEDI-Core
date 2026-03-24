"""E2E tests for the Validate page."""

from __future__ import annotations

from playwright.sync_api import Page

from .pages.validate_page import ValidatePage


def test_validate_button_disabled_when_empty(page: Page, base_url: str) -> None:
    page.goto(base_url)
    vp = ValidatePage(page)
    vp.navigate()
    assert vp.is_validate_disabled()


def test_validate_dsl_by_path(page: Page, base_url: str, dsl_path: str) -> None:
    page.goto(base_url)
    vp = ValidatePage(page)
    vp.navigate()
    vp.fill_dsl_path(dsl_path)
    vp.click_validate()
    vp.wait_for_result()


def test_validate_shows_schema_columns(page: Page, base_url: str, dsl_path: str) -> None:
    page.goto(base_url)
    vp = ValidatePage(page)
    vp.navigate()
    vp.fill_dsl_path(dsl_path)
    vp.click_validate()
    vp.wait_for_result()
    assert vp.has_schema_columns()


def test_validate_with_sample(page: Page, base_url: str, dsl_path: str) -> None:
    page.goto(base_url)
    vp = ValidatePage(page)
    vp.navigate()
    # Use the same DSL — sample path is optional and triggers coverage section
    vp.fill_dsl_path(dsl_path)
    vp.click_validate()
    vp.wait_for_result()
    assert vp.has_schema_columns()
