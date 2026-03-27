"""Page object for the Rules Management page."""

from __future__ import annotations

from playwright.sync_api import Page, Locator

from .base_page import BasePage


class RulesPage(BasePage):
    """Encapsulates selectors and actions for the Rules Management page."""

    def navigate(self) -> None:
        self.navigate_to("Rules")
        self.wait_for_heading("Rules Management")

    # ── Tab navigation ──

    def click_tab(self, label: str) -> None:
        """Click a tab button by its visible text (Overview, Universal, Transaction, Partner, Effective View)."""
        self.page.get_by_role("button", name=label, exact=True).click()

    def get_active_tab(self) -> str:
        """Return the text of the currently active tab (has border-blue-600 class)."""
        return self.page.locator("button.border-blue-600").inner_text()

    # ── Universal tab ──

    def click_save_universal(self) -> None:
        self.page.locator("button:has-text('Save')").first.click()

    def click_cancel_universal(self) -> None:
        self.page.locator("button:has-text('Cancel')").first.click()

    def get_universal_success_message(self) -> str:
        return self.page.locator("text=Universal rules saved successfully").inner_text()

    # ── Transaction tab ──

    def select_transaction_type(self, txn_type: str) -> None:
        self.page.locator("select").first.select_option(txn_type)

    def click_save_transaction(self) -> None:
        self.page.locator("button:has-text('Save')").last.click()

    def click_cancel_transaction(self) -> None:
        self.page.locator("button:has-text('Cancel')").first.click()

    # ── Partner tab ──

    def select_partner_profile(self, profile_name: str) -> None:
        self.page.locator("select").first.select_option(profile_name)

    def click_save_partner(self) -> None:
        self.page.locator("button:has-text('Save')").last.click()

    def click_cancel_partner(self) -> None:
        self.page.locator("button:has-text('Cancel')").first.click()

    # ── Cancel button presence ──

    def has_cancel_button(self) -> bool:
        return self.page.locator("button:has-text('Cancel')").count() > 0

    # ── Classification rules grid ──

    def get_classification_rule_count(self) -> int:
        """Count rows in the classification rules table (exclude header and empty-state row)."""
        rows = self.page.locator("table").first.locator("tbody tr")
        if rows.count() == 1:
            text = rows.first.inner_text()
            if "No classification rules" in text:
                return 0
        return rows.count()

    def add_rule(self) -> None:
        self.page.locator("button:has-text('+ Add Rule')").click()

    # ── FieldCombobox interactions ──

    def get_field_combobox_inputs(self) -> Locator:
        """Return all FieldCombobox input elements (font-mono text-xs inputs in the grid)."""
        return self.page.locator("table input.font-mono")

    def click_first_field_input(self) -> None:
        self.get_field_combobox_inputs().first.click()

    def get_first_field_value(self) -> str:
        return self.get_field_combobox_inputs().first.input_value()

    def clear_first_field(self) -> None:
        inp = self.get_field_combobox_inputs().first
        inp.click()
        inp.fill("")

    def blur_first_field(self) -> None:
        """Move focus away from the first field input."""
        self.page.locator("h2").first.click()

    def is_dropdown_portal_in_body(self) -> bool:
        """Check that the dropdown menu renders as a direct child of <body> (portal)."""
        return self.page.locator("body > div.max-h-48.overflow-auto").count() > 0

    def get_dropdown_option_count(self) -> int:
        """Count visible options in the portal dropdown."""
        return self.page.locator("body > div.max-h-48 button").count()

    def is_dropdown_visible(self) -> bool:
        """Check if the portal dropdown is currently visible."""
        return self.page.locator("body > div.max-h-48").is_visible()

    # ── Severity dropdown ──

    def get_first_severity_value(self) -> str:
        return self.page.locator("table select").first.input_value()

    def set_first_severity(self, value: str) -> None:
        self.page.locator("table select").first.select_option(value)
