"""Compare page object — most complex page with profile selection, run history, diffs, rules editor."""

from __future__ import annotations

from playwright.sync_api import Page

from .base_page import BasePage


class ComparePage(BasePage):
    def navigate(self) -> None:
        self.navigate_to("Compare")
        self.wait_for_heading("Compare")

    # --- Form ---

    def select_profile(self, name: str) -> None:
        self.page.locator("select").select_option(value=name)

    def get_profile_options(self) -> list[str]:
        """Return all option values in the profile dropdown."""
        return self.page.locator("select option").all_inner_texts()

    def fill_source_dir(self, path: str) -> None:
        self.page.get_by_placeholder("/path/to/source").fill(path)

    def fill_target_dir(self, path: str) -> None:
        self.page.get_by_placeholder("/path/to/target").fill(path)

    def click_run(self) -> None:
        self.page.get_by_role("button", name="Run Comparison").click()

    def is_run_disabled(self) -> bool:
        return self.page.get_by_role("button", name="Run Comparison").is_disabled()

    def has_profile_detail(self) -> bool:
        """Check if the profile description info box is visible."""
        return self.page.locator(".bg-gray-50.rounded.p-2").is_visible()

    # --- Run History ---

    def wait_for_run_history(self) -> None:
        self.page.get_by_text("Run History").wait_for(timeout=10000)

    def get_run_row_count(self) -> int:
        """Count rows in the run history table body."""
        self.page.wait_for_timeout(500)  # allow table to populate
        return self.page.locator("text=Run History").locator("..").locator("table tbody tr").count()

    def click_run_row(self, index: int = 0) -> None:
        self.page.locator("text=Run History").locator("..").locator("table tbody tr").nth(index).click()

    # --- Pairs ---

    def wait_for_pairs(self) -> None:
        self.page.get_by_text("Pairs").first.wait_for(timeout=10000)

    def get_pair_row_count(self) -> int:
        # Pairs table is in the card after "Run #X — Pairs"
        return self.page.locator("text=Pairs").locator("..").locator("..").locator("table tbody tr").count()

    def filter_pairs(self, status: str) -> None:
        """Click a status filter button (All, MATCH, MISMATCH, UNMATCHED)."""
        self.page.get_by_role("button", name=status, exact=True).click()
        self.page.wait_for_timeout(500)

    def click_pair_row(self, index: int = 0) -> None:
        """Click a pair row (only works on non-MATCH rows)."""
        rows = self.page.locator("text=Pairs").locator("..").locator("..").locator("table tbody tr")
        rows.nth(index).click()

    def has_status_badge(self, status: str) -> bool:
        return self.page.get_by_text(status, exact=True).first.is_visible()

    # --- Diffs ---

    def wait_for_diffs(self) -> None:
        self.page.get_by_text("Diffs").first.wait_for(timeout=10000)

    def get_diff_row_count(self) -> int:
        return self.page.locator("text=Diffs").locator("..").locator("table tbody tr").count()

    # --- Rules Editor ---

    def open_rules_editor(self) -> None:
        self.page.get_by_role("button", name="Edit Rules").click()
        self.page.locator("textarea").wait_for(timeout=5000)

    def get_rules_text(self) -> str:
        return self.page.locator("textarea").input_value()

    def set_rules_text(self, text: str) -> None:
        self.page.locator("textarea").fill(text)

    def save_rules(self) -> None:
        self.page.get_by_role("button", name="Save Rules").click()
        self.page.wait_for_timeout(1000)

    def close_rules_editor(self) -> None:
        # Click the "x Close" button in the rules header
        self.page.locator("text=Close").click()

    def is_rules_editor_visible(self) -> bool:
        return self.page.locator("textarea").is_visible()

    # --- Export ---

    def has_export_link(self) -> bool:
        return self.page.get_by_text("Export CSV").is_visible()
