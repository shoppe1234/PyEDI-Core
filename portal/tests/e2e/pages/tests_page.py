"""Tests page object."""

from __future__ import annotations

from .base_page import BasePage


class TestsPage(BasePage):
    def navigate(self) -> None:
        self.navigate_to("Tests")
        self.wait_for_heading("Test Harness")

    def has_test_cases(self) -> bool:
        return self.page.get_by_text("Test Cases").is_visible()

    def click_run_tests(self) -> None:
        self.page.get_by_role("button", name="Run Tests").click()

    def wait_for_results(self) -> None:
        """Wait for summary stats to appear after running tests."""
        self.page.get_by_text("Passed").wait_for(timeout=30000)

    def get_total(self) -> str:
        """Return the total count text from the summary."""
        return self.page.locator("text=Total").locator("..").locator(".text-xl, .text-3xl").first.inner_text()
