"""Pipeline page object."""

from __future__ import annotations

from .base_page import BasePage


class PipelinePage(BasePage):
    def navigate(self) -> None:
        self.navigate_to("Pipeline")
        self.wait_for_heading("Pipeline Results")

    def has_content(self) -> bool:
        """Check the page loaded — either a table or empty message."""
        return (
            self.page.locator("table").is_visible()
            or self.page.get_by_text("No results").is_visible()
        )
