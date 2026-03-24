"""Base page object with shared navigation and utility methods."""

from __future__ import annotations

from playwright.sync_api import Page


class BasePage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def navigate_to(self, label: str) -> None:
        """Click a sidebar nav button by its text label."""
        self.page.get_by_role("button", name=label, exact=True).click()

    def get_health_status(self) -> str:
        """Read the API health status text from the sidebar footer."""
        return self.page.locator("nav span").last.inner_text()

    def wait_for_heading(self, text: str) -> None:
        """Wait for an h1 heading containing the given text."""
        self.page.locator(f"h1:has-text('{text}')").wait_for(timeout=10000)

    def get_active_nav_text(self) -> str:
        """Return the text of the currently active nav button."""
        return self.page.locator("nav button.font-medium").inner_text()
