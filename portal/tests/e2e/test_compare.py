"""E2E tests for the Compare page — most thorough coverage."""

from __future__ import annotations

import json

from playwright.sync_api import Page

from .pages.compare_page import ComparePage


def test_profiles_load_in_dropdown(page: Page, base_url: str) -> None:
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()
    page.wait_for_timeout(1000)
    options = cp.get_profile_options()
    assert "810_invoice" in options
    assert "csv_generic" in options


def test_run_button_disabled_until_form_filled(
    page: Page, base_url: str, compare_test_data: dict[str, str],
) -> None:
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()
    assert cp.is_run_disabled()

    cp.select_profile("810_invoice")
    assert cp.is_run_disabled()

    cp.fill_source_dir(compare_test_data["source_dir"])
    cp.fill_target_dir(compare_test_data["target_dir"])
    assert not cp.is_run_disabled()


def test_profile_detail_shows_on_select(page: Page, base_url: str) -> None:
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()
    cp.select_profile("810_invoice")
    page.wait_for_timeout(500)
    assert cp.has_profile_detail()


def test_run_comparison_e2e(
    page: Page, base_url: str, compare_test_data: dict[str, str],
) -> None:
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()
    cp.select_profile("810_invoice")
    cp.fill_source_dir(compare_test_data["source_dir"])
    cp.fill_target_dir(compare_test_data["target_dir"])
    cp.click_run()
    page.wait_for_timeout(3000)
    assert cp.get_run_row_count() >= 1


def test_run_history_table_populated(
    page: Page, base_url: str, compare_test_data: dict[str, str],
) -> None:
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()

    # Run a comparison first
    cp.select_profile("810_invoice")
    cp.fill_source_dir(compare_test_data["source_dir"])
    cp.fill_target_dir(compare_test_data["target_dir"])
    cp.click_run()
    page.wait_for_timeout(3000)

    cp.wait_for_run_history()
    assert cp.get_run_row_count() >= 1


def test_click_run_shows_pairs(
    page: Page, base_url: str, compare_test_data: dict[str, str],
) -> None:
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()

    cp.select_profile("810_invoice")
    cp.fill_source_dir(compare_test_data["source_dir"])
    cp.fill_target_dir(compare_test_data["target_dir"])
    cp.click_run()
    page.wait_for_timeout(3000)

    cp.click_run_row(0)
    cp.wait_for_pairs()
    assert cp.get_pair_row_count() >= 1


def test_filter_pairs_by_status(
    page: Page, base_url: str, compare_test_data: dict[str, str],
) -> None:
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()

    cp.select_profile("810_invoice")
    cp.fill_source_dir(compare_test_data["source_dir"])
    cp.fill_target_dir(compare_test_data["target_dir"])
    cp.click_run()
    page.wait_for_timeout(3000)

    cp.click_run_row(0)
    cp.wait_for_pairs()

    all_count = cp.get_pair_row_count()
    cp.filter_pairs("MISMATCH")
    mismatch_count = cp.get_pair_row_count()
    assert mismatch_count <= all_count

    cp.filter_pairs("All")
    assert cp.get_pair_row_count() == all_count


def test_click_mismatch_pair_shows_diffs(
    page: Page, base_url: str, compare_test_data: dict[str, str],
) -> None:
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()

    cp.select_profile("810_invoice")
    cp.fill_source_dir(compare_test_data["source_dir"])
    cp.fill_target_dir(compare_test_data["target_dir"])
    cp.click_run()
    page.wait_for_timeout(3000)

    cp.click_run_row(0)
    cp.wait_for_pairs()

    # Filter to MISMATCH and click first row
    cp.filter_pairs("MISMATCH")
    page.wait_for_timeout(500)
    if cp.get_pair_row_count() > 0:
        cp.click_pair_row(0)
        cp.wait_for_diffs()
        assert cp.get_diff_row_count() >= 1


def test_unmatched_pair_status(
    page: Page, base_url: str, compare_test_data: dict[str, str],
) -> None:
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()

    cp.select_profile("810_invoice")
    cp.fill_source_dir(compare_test_data["source_dir"])
    cp.fill_target_dir(compare_test_data["target_dir"])
    cp.click_run()
    page.wait_for_timeout(3000)

    cp.click_run_row(0)
    cp.wait_for_pairs()

    cp.filter_pairs("UNMATCHED")
    page.wait_for_timeout(500)
    assert cp.has_status_badge("UNMATCHED")


def test_export_csv_link_appears(
    page: Page, base_url: str, compare_test_data: dict[str, str],
) -> None:
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()

    cp.select_profile("810_invoice")
    cp.fill_source_dir(compare_test_data["source_dir"])
    cp.fill_target_dir(compare_test_data["target_dir"])
    cp.click_run()
    page.wait_for_timeout(3000)

    cp.click_run_row(0)
    page.wait_for_timeout(500)
    assert cp.has_export_link()


def test_edit_rules_opens_editor(page: Page, base_url: str) -> None:
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()
    cp.select_profile("810_invoice")
    page.wait_for_timeout(500)
    cp.open_rules_editor()
    text = cp.get_rules_text()
    assert "classification" in text
    assert "ignore" in text


def test_save_rules_round_trip(page: Page, base_url: str) -> None:
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()
    cp.select_profile("810_invoice")
    page.wait_for_timeout(500)
    cp.open_rules_editor()

    original = cp.get_rules_text()
    rules = json.loads(original)

    # Modify — add a test ignore entry
    rules["ignore"].append({"segment": "TEST", "field": "TEST01", "reason": "e2e test"})
    cp.set_rules_text(json.dumps(rules, indent=2))
    cp.save_rules()

    # Reload and verify
    cp.close_rules_editor()
    page.wait_for_timeout(500)
    cp.open_rules_editor()
    updated = cp.get_rules_text()
    assert "e2e test" in updated

    # Restore original
    cp.set_rules_text(original)
    cp.save_rules()


def test_close_rules_editor(page: Page, base_url: str) -> None:
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()
    cp.select_profile("810_invoice")
    page.wait_for_timeout(500)
    cp.open_rules_editor()
    assert cp.is_rules_editor_visible()
    cp.close_rules_editor()
    page.wait_for_timeout(500)
    assert not cp.is_rules_editor_visible()


def test_full_workflow(
    page: Page, base_url: str, compare_test_data: dict[str, str],
) -> None:
    """End-to-end: select profile, run comparison, view diffs, check rules editor."""
    page.goto(base_url)
    cp = ComparePage(page)
    cp.navigate()

    # 1. Select profile and run
    cp.select_profile("810_invoice")
    assert cp.has_profile_detail()
    cp.fill_source_dir(compare_test_data["source_dir"])
    cp.fill_target_dir(compare_test_data["target_dir"])
    cp.click_run()
    page.wait_for_timeout(3000)

    # 2. Verify run history
    assert cp.get_run_row_count() >= 1

    # 3. Click run, view pairs
    cp.click_run_row(0)
    cp.wait_for_pairs()
    total_pairs = cp.get_pair_row_count()
    assert total_pairs >= 3  # 1 match + 1 mismatch + 1 unmatched

    # 4. Filter to mismatches
    cp.filter_pairs("MISMATCH")
    page.wait_for_timeout(500)

    # 5. Click mismatch pair, view diffs
    if cp.get_pair_row_count() > 0:
        cp.click_pair_row(0)
        cp.wait_for_diffs()
        assert cp.get_diff_row_count() >= 1

    # 6. Check export link
    assert cp.has_export_link()

    # 7. Open rules editor
    cp.open_rules_editor()
    assert "classification" in cp.get_rules_text()
    cp.close_rules_editor()
