"""Validate page object."""

from __future__ import annotations

from .base_page import BasePage


class ValidatePage(BasePage):
    def navigate(self) -> None:
        self.navigate_to("Validate")
        self.wait_for_heading("Schema Validation")

    def fill_dsl_path(self, path: str) -> None:
        self.page.get_by_placeholder("DSL file path").fill(path)

    def fill_sample_path(self, path: str) -> None:
        self.page.get_by_placeholder("Sample file path").fill(path)

    def click_validate(self) -> None:
        self.page.locator("main").get_by_role("button", name="Validate").click()

    def is_validate_disabled(self) -> bool:
        return self.page.locator("main").get_by_role("button", name="Validate").is_disabled()

    def wait_for_result(self) -> None:
        self.page.get_by_text("Compilation Summary").wait_for(timeout=20000)

    def has_schema_columns(self) -> bool:
        return self.page.get_by_text("Schema Columns").is_visible()

    def has_coverage_section(self) -> bool:
        return self.page.get_by_text("Coverage").is_visible()
