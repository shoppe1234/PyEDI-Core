"""Dashboard page object."""

from __future__ import annotations

from .base_page import BasePage


class DashboardPage(BasePage):
    def navigate(self) -> None:
        self.navigate_to("Dashboard")
        self.wait_for_heading("Dashboard")

    def has_stat_cards(self) -> bool:
        """Check that at least one stat card label is visible."""
        return self.page.get_by_text("Total Processed").is_visible()

    def has_recent_processing(self) -> bool:
        return self.page.get_by_text("Recent Processing").is_visible()
