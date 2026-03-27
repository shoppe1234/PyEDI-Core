"""E2E tests for Rules Management page — verifies rulesManagementFix.md tasks 2a-2c."""

from __future__ import annotations

from playwright.sync_api import Page

from .pages.rules_page import RulesPage


# ── Task 2c: Cancel buttons exist on all tabs ──


def test_universal_cancel_button_exists(page: Page, base_url: str) -> None:
    """Task 2c: Universal tab has a Cancel button."""
    page.goto(base_url)
    rp = RulesPage(page)
    rp.navigate()
    rp.click_tab("Universal")
    page.wait_for_timeout(1000)
    assert rp.has_cancel_button(), "Cancel button missing on Universal tab"


def test_transaction_cancel_button_exists(page: Page, base_url: str) -> None:
    """Task 2c: Transaction tab has a Cancel button when a type is selected."""
    page.goto(base_url)
    rp = RulesPage(page)
    rp.navigate()
    rp.click_tab("Transaction")
    page.wait_for_timeout(500)
    # Select the first available transaction type
    options = page.locator("select option").all_text_contents()
    txn_types = [o for o in options if o and o != "Select transaction type..."]
    if txn_types:
        rp.select_transaction_type(txn_types[0])
        page.wait_for_timeout(1000)
        assert rp.has_cancel_button(), "Cancel button missing on Transaction tab"


def test_partner_cancel_button_exists(page: Page, base_url: str) -> None:
    """Task 2c: Partner tab has a Cancel button when a profile is selected."""
    page.goto(base_url)
    rp = RulesPage(page)
    rp.navigate()
    rp.click_tab("Partner")
    page.wait_for_timeout(500)
    options = page.locator("select option").all_text_contents()
    profiles = [o for o in options if o and o != "Select profile..."]
    if profiles:
        rp.select_partner_profile(profiles[0])
        page.wait_for_timeout(1000)
        assert rp.has_cancel_button(), "Cancel button missing on Partner tab"


def test_universal_cancel_reverts_changes(page: Page, base_url: str) -> None:
    """Task 2c: Clicking Cancel on Universal tab discards unsaved edits."""
    page.goto(base_url)
    rp = RulesPage(page)
    rp.navigate()
    rp.click_tab("Universal")
    page.wait_for_timeout(1000)

    # Record the initial rule count
    initial_count = rp.get_classification_rule_count()

    # Make a change — add a rule
    rp.add_rule()
    page.wait_for_timeout(300)
    assert rp.get_classification_rule_count() == initial_count + 1, "Rule was not added"

    # Cancel — should revert to original
    rp.click_cancel_universal()
    page.wait_for_timeout(1000)
    assert rp.get_classification_rule_count() == initial_count, "Cancel did not revert added rule"


def test_partner_cancel_reverts_changes(page: Page, base_url: str) -> None:
    """Task 2c: Clicking Cancel on Partner tab discards unsaved edits."""
    page.goto(base_url)
    rp = RulesPage(page)
    rp.navigate()
    rp.click_tab("Partner")
    page.wait_for_timeout(500)

    options = page.locator("select option").all_text_contents()
    profiles = [o for o in options if o and o != "Select profile..."]
    if not profiles:
        return  # Skip if no profiles available

    rp.select_partner_profile(profiles[0])
    page.wait_for_timeout(1000)

    initial_count = rp.get_classification_rule_count()
    rp.add_rule()
    page.wait_for_timeout(300)
    assert rp.get_classification_rule_count() == initial_count + 1

    rp.click_cancel_partner()
    page.wait_for_timeout(1000)
    assert rp.get_classification_rule_count() == initial_count, "Cancel did not revert on Partner tab"


# ── Task 2a: Dropdown renders in portal (not clipped) ──


def test_dropdown_renders_in_body_portal(page: Page, base_url: str) -> None:
    """Task 2a: FieldCombobox dropdown renders via createPortal into document.body."""
    page.goto(base_url)
    rp = RulesPage(page)
    rp.navigate()
    rp.click_tab("Universal")
    page.wait_for_timeout(1000)

    rule_count = rp.get_classification_rule_count()
    if rule_count == 0:
        rp.add_rule()
        page.wait_for_timeout(300)

    # Click a FieldCombobox input to open the dropdown
    rp.click_first_field_input()
    page.wait_for_timeout(500)

    # The dropdown should be a direct child of <body> (portaled out of the table)
    assert rp.is_dropdown_portal_in_body(), (
        "Dropdown did not render as a portal in document.body — "
        "field names may be truncated by parent overflow"
    )


def test_field_dropdown_fully_visible(page: Page, base_url: str) -> None:
    """Task 2a: Dropdown is visible and scrollable with options."""
    page.goto(base_url)
    rp = RulesPage(page)
    rp.navigate()
    rp.click_tab("Universal")
    page.wait_for_timeout(1000)

    rule_count = rp.get_classification_rule_count()
    if rule_count == 0:
        rp.add_rule()
        page.wait_for_timeout(300)

    rp.click_first_field_input()
    page.wait_for_timeout(500)

    assert rp.is_dropdown_visible(), "Dropdown is not visible after clicking field input"
    option_count = rp.get_dropdown_option_count()
    assert option_count > 0, "Dropdown has no options"


# ── Task 2b: Field revert on empty blur ──


def test_field_reverts_on_empty_blur(page: Page, base_url: str) -> None:
    """Task 2b: Clearing a field and blurring reverts to the previous value."""
    page.goto(base_url)
    rp = RulesPage(page)
    rp.navigate()
    rp.click_tab("Universal")
    page.wait_for_timeout(1000)

    rule_count = rp.get_classification_rule_count()
    if rule_count == 0:
        rp.add_rule()
        page.wait_for_timeout(300)

    # Get the current value of the first field
    original_value = rp.get_first_field_value()

    # If empty (new rule), set a value first
    if not original_value:
        inp = rp.get_field_combobox_inputs().first
        inp.click()
        inp.fill("*")
        rp.blur_first_field()
        page.wait_for_timeout(300)
        original_value = rp.get_first_field_value()

    # Now clear and blur — should revert
    rp.clear_first_field()
    page.wait_for_timeout(100)
    rp.blur_first_field()
    page.wait_for_timeout(500)

    restored_value = rp.get_first_field_value()
    assert restored_value == original_value, (
        f"Field did not revert on empty blur: expected '{original_value}', got '{restored_value}'"
    )
