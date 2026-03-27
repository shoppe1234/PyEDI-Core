"""E2E tests for Onboard Wizard — verifies rulesManagementFix.md Task 1."""

from __future__ import annotations

from playwright.sync_api import Page

from .pages.onboard_page import OnboardPage


def _compile_and_advance(page: Page, op: OnboardPage, dsl_path: str) -> None:
    """Navigate to Onboard, compile DSL, advance to Step 2."""
    op.navigate()

    # Step 1: fill DSL path and compile
    page.locator("input[placeholder='testingData/Batch1/bevager810FF.txt']").fill(dsl_path)
    page.locator("button:has-text('Compile')").click()
    page.wait_for_timeout(3000)

    # Advance to Step 2
    page.locator("button:has-text('Next: Register Partner')").click()
    page.wait_for_timeout(1000)


# ── Task 1: Required field indicators ──


def test_required_asterisks_visible(page: Page, base_url: str, dsl_path: str) -> None:
    """Task 1: Required fields (Profile Name, Trading Partner, Transaction Type) show red asterisks."""
    page.goto(base_url)
    op = OnboardPage(page)
    _compile_and_advance(page, op, dsl_path)

    asterisk_count = op.get_required_asterisks()
    assert asterisk_count == 3, (
        f"Expected 3 required field asterisks (Profile Name, Trading Partner, Transaction Type), "
        f"got {asterisk_count}"
    )


def test_required_footnote_visible(page: Page, base_url: str, dsl_path: str) -> None:
    """Task 1: '* Required' footnote is visible on the Register Partner form."""
    page.goto(base_url)
    op = OnboardPage(page)
    _compile_and_advance(page, op, dsl_path)

    assert op.has_required_footnote(), "'* Required' footnote not visible on Register Partner step"


def test_next_button_disabled_with_helper_text(page: Page, base_url: str, dsl_path: str) -> None:
    """Task 1: 'Next: Configure Rules' is disabled and shows helper text before registration."""
    page.goto(base_url)
    op = OnboardPage(page)
    _compile_and_advance(page, op, dsl_path)

    assert op.is_next_button_disabled(), "Next: Configure Rules should be disabled before registration"
    assert op.has_next_button_helper_text(), (
        "Helper text 'Register your partner above before proceeding' not visible"
    )


def test_register_button_disabled_without_required_fields(page: Page, base_url: str, dsl_path: str) -> None:
    """Task 1: Register button is disabled when required fields are empty."""
    page.goto(base_url)
    op = OnboardPage(page)
    _compile_and_advance(page, op, dsl_path)

    # Clear all fields to ensure Register is disabled
    page.locator("input[placeholder='bevager_810']").fill("")
    page.locator("input[placeholder='Bevager']").fill("")
    page.locator("input[placeholder='810']").fill("")
    page.wait_for_timeout(200)

    assert op.is_register_button_disabled(), "Register button should be disabled with empty required fields"


def test_register_button_enables_with_required_fields(page: Page, base_url: str, dsl_path: str) -> None:
    """Task 1: Register button enables once all required fields are filled."""
    page.goto(base_url)
    op = OnboardPage(page)
    _compile_and_advance(page, op, dsl_path)

    op.fill_profile_name("e2e_test_profile")
    op.fill_trading_partner("E2E Partner")
    op.fill_transaction_type("810")
    page.wait_for_timeout(300)

    assert not op.is_register_button_disabled(), "Register button should be enabled with all required fields filled"
