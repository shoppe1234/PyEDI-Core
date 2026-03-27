"""Page object for the Onboard Wizard page."""

from __future__ import annotations

from playwright.sync_api import Page

from .base_page import BasePage


class OnboardPage(BasePage):
    """Encapsulates selectors and actions for the Onboard Wizard."""

    def navigate(self) -> None:
        self.navigate_to("Onboard")
        self.wait_for_heading("Onboard Trading Partner")

    # ── Step 1: Import & Compile ──

    def get_current_step_title(self) -> str:
        """Get the title of the currently visible card."""
        return self.page.locator("h2").first.inner_text()

    # ── Step 2: Register Partner ──

    def click_step_indicator(self, step_number: int) -> None:
        """Click a step indicator in the stepper bar (1-indexed)."""
        self.page.locator(f".flex.items-center >> nth={step_number - 1}").click()

    def get_required_asterisks(self) -> int:
        """Count the red asterisk (*) indicators on the current form."""
        return self.page.locator("label span.text-red-500").count()

    def has_required_footnote(self) -> bool:
        """Check for the '* Required' footnote text."""
        return self.page.locator("text=Required").first.is_visible()

    def get_next_button(self):
        """Return the 'Next: Configure Rules' button locator."""
        return self.page.locator("button:has-text('Next: Configure Rules')")

    def is_next_button_disabled(self) -> bool:
        return self.get_next_button().is_disabled()

    def has_next_button_helper_text(self) -> bool:
        """Check for helper text explaining why Next is disabled."""
        return self.page.locator("text=Register your partner above before proceeding").is_visible()

    def get_register_button(self):
        """Return the 'Register' button locator."""
        return self.page.get_by_role("button", name="Register", exact=True)

    def is_register_button_disabled(self) -> bool:
        return self.get_register_button().is_disabled()

    # ── Form fields ──

    def fill_profile_name(self, name: str) -> None:
        self.page.locator("input[placeholder='bevager_810']").fill(name)

    def fill_trading_partner(self, name: str) -> None:
        self.page.locator("input[placeholder='Bevager']").fill(name)

    def fill_transaction_type(self, txn_type: str) -> None:
        self.page.locator("input[placeholder='810']").fill(txn_type)
