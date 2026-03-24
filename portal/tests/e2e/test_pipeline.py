"""E2E tests for the Pipeline page."""

from __future__ import annotations

from playwright.sync_api import Page

from .pages.pipeline_page import PipelinePage


def test_pipeline_page_loads(page: Page, base_url: str) -> None:
    page.goto(base_url)
    pp = PipelinePage(page)
    pp.navigate()
    page.wait_for_timeout(1000)
    assert pp.has_content()
