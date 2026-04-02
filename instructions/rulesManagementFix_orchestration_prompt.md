# Rules Management Fix — Orchestration Prompt (Playwright Verification)

**Purpose:** Verify every fix from `instructions/rulesManagementFix.md` by creating Playwright E2E tests, running them, and fixing any implementation issues found. Tests use the existing Python/pytest-playwright harness with Page Object Model pattern.

**Codebase context:**
- Project root: `pycoreEdi/`
- Portal API: `portal/api/app.py` (FastAPI, serves React SPA)
- Portal UI: `portal/ui/src/` (React/TypeScript/Tailwind)
- E2E tests: `portal/tests/e2e/` (Python, pytest-playwright, sync API)
- Page objects: `portal/tests/e2e/pages/` (inherit `BasePage`)
- Conftest: `portal/tests/e2e/conftest.py` (server lifecycle on port 8321, fixtures)
- Coding standards: see `CLAUDE.md`
- Task list: `instructions/rulesManagementFix.md`

**Implementation files under test:**
- `portal/ui/src/pages/Rules.tsx` — Tasks 2a, 2b, 2c
- `portal/ui/src/pages/Onboard.tsx` — Task 1

---

## Rules of Engagement

1. **Sequential within phases** — complete each task fully (including its test gate) before starting the next.
2. **Read before writing** — always read the target file and its imports before making any change.
3. **Minimal diffs** — change only what the task requires. No drive-by fixes.
4. **One commit per phase** — after each phase gate passes, commit with a descriptive message.
5. **Stop on red** — if any test fails, diagnose and fix the *implementation code* first. Do not weaken the test to make it pass.
6. **Match existing patterns** — new page objects and test files must follow the exact conventions in `portal/tests/e2e/pages/base_page.py` and `portal/tests/e2e/test_compare.py`.
7. **No new dependencies** — use only `playwright.sync_api`, `pytest`, and what's already in conftest.

---

## Pre-Flight

Before starting any task:

```bash
# 1. Verify TypeScript compiles cleanly
cd portal/ui && npx tsc --noEmit

# 2. Build frontend (tests serve from dist/)
cd portal/ui && npm run build

# 3. Run existing E2E suite to confirm green baseline
cd pycoreEdi && pytest portal/tests/e2e/ -v --tb=short 2>&1 | tail -30

# 4. Verify the two implementation files exist and have the expected changes
grep -n "createPortal" portal/ui/src/pages/Rules.tsx          # Task 2a — portal dropdown
grep -n "previousValue" portal/ui/src/pages/Rules.tsx          # Task 2b — revert on blur
grep -n "cancelUniversal\|cancelTransaction\|cancelPartner" portal/ui/src/pages/Rules.tsx  # Task 2c — cancel handlers
grep -n "required" portal/ui/src/pages/Onboard.tsx             # Task 1 — required indicators
```

If any pre-flight check fails, **stop and resolve before proceeding**.

---

# PHASE A: Page Objects

> **Prerequisite:** Green baseline E2E suite.
> **Deliverables:** `rules_page.py` and `onboard_page.py` in `portal/tests/e2e/pages/`.

---

## Task A1: Create `rules_page.py`

**Investigate:**
```bash
# Read the existing page object pattern
cat portal/tests/e2e/pages/base_page.py

# Read Rules.tsx to understand DOM structure, selectors, tab labels
# Focus on: tab buttons, FieldCombobox inputs, Cancel/Save buttons, table structure
cat portal/ui/src/pages/Rules.tsx | head -100
```

**Execute:**

Create `portal/tests/e2e/pages/rules_page.py` with this Page Object:

```python
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
        # Cancel is next to Save; find the group
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
        # Check if it's the empty state
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
        # Portal dropdown has fixed positioning and z-index 9999
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
```

**Test Gate:**
```bash
# Verify file exists and imports cleanly
python -c "from portal.tests.e2e.pages.rules_page import RulesPage; print('OK')"
```

---

## Task A2: Create `onboard_page.py`

**Investigate:**
```bash
# Read Onboard.tsx to understand the wizard steps and DOM structure
# Focus on: step labels, required asterisks, Input components, Register button, Next button, helper text
cat portal/ui/src/pages/Onboard.tsx | head -60
```

**Execute:**

Create `portal/tests/e2e/pages/onboard_page.py`:

```python
"""Page object for the Onboard Wizard page."""

from __future__ import annotations

from playwright.sync_api import Page

from .base_page import BasePage


class OnboardPage(BasePage):
    """Encapsulates selectors and actions for the Onboard Wizard."""

    def navigate(self) -> None:
        self.navigate_to("Onboard")
        self.wait_for_heading("Onboard")

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
```

**Test Gate:**
```bash
python -c "from portal.tests.e2e.pages.onboard_page import OnboardPage; print('OK')"
```

---

## Phase A Gate

- [ ] `rules_page.py` imports cleanly
- [ ] `onboard_page.py` imports cleanly
- [ ] Existing E2E tests still pass: `pytest portal/tests/e2e/ -v --tb=short`

**Commit:**
```bash
git add portal/tests/e2e/pages/rules_page.py portal/tests/e2e/pages/onboard_page.py
git commit -m "test(e2e): add RulesPage and OnboardPage page objects for rules management fix verification"
```

---

# PHASE B: E2E Test Files

> **Prerequisite:** Phase A gate passes.
> **Deliverables:** `test_rules.py` and `test_onboard.py` in `portal/tests/e2e/`.

---

## Task B1: Create `test_rules.py`

**Execute:**

Create `portal/tests/e2e/test_rules.py` with the following tests. Each test maps to a specific task list item.

```python
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
```

**Test Gate:**
```bash
python -c "import ast; ast.parse(open('portal/tests/e2e/test_rules.py').read()); print('Syntax OK')"
```

---

## Task B2: Create `test_onboard.py`

**Execute:**

Create `portal/tests/e2e/test_onboard.py`:

```python
"""E2E tests for Onboard Wizard — verifies rulesManagementFix.md Task 1."""

from __future__ import annotations

from playwright.sync_api import Page

from .pages.onboard_page import OnboardPage


# ── Task 1: Required field indicators ──


def test_required_asterisks_visible(page: Page, base_url: str, dsl_path: str) -> None:
    """Task 1: Required fields (Profile Name, Trading Partner, Transaction Type) show red asterisks."""
    page.goto(base_url)
    op = OnboardPage(page)
    op.navigate()

    # Step 1 — Import & Compile: we need to compile a DSL to reach Step 2
    # Fill the DSL path and compile
    page.locator("input[placeholder*='path']").first.fill(dsl_path)
    page.locator("button:has-text('Compile')").click()
    page.wait_for_timeout(3000)

    # Advance to Step 2 — Register Partner
    page.locator("button:has-text('Next')").first.click()
    page.wait_for_timeout(1000)

    # Verify exactly 3 required asterisks
    asterisk_count = op.get_required_asterisks()
    assert asterisk_count == 3, (
        f"Expected 3 required field asterisks (Profile Name, Trading Partner, Transaction Type), "
        f"got {asterisk_count}"
    )


def test_required_footnote_visible(page: Page, base_url: str, dsl_path: str) -> None:
    """Task 1: '* Required' footnote is visible on the Register Partner form."""
    page.goto(base_url)
    op = OnboardPage(page)
    op.navigate()

    page.locator("input[placeholder*='path']").first.fill(dsl_path)
    page.locator("button:has-text('Compile')").click()
    page.wait_for_timeout(3000)
    page.locator("button:has-text('Next')").first.click()
    page.wait_for_timeout(1000)

    assert op.has_required_footnote(), "'* Required' footnote not visible on Register Partner step"


def test_next_button_disabled_with_helper_text(page: Page, base_url: str, dsl_path: str) -> None:
    """Task 1: 'Next: Configure Rules' is disabled and shows helper text before registration."""
    page.goto(base_url)
    op = OnboardPage(page)
    op.navigate()

    page.locator("input[placeholder*='path']").first.fill(dsl_path)
    page.locator("button:has-text('Compile')").click()
    page.wait_for_timeout(3000)
    page.locator("button:has-text('Next')").first.click()
    page.wait_for_timeout(1000)

    # Next button should be disabled
    assert op.is_next_button_disabled(), "Next: Configure Rules should be disabled before registration"

    # Helper text should be visible
    assert op.has_next_button_helper_text(), (
        "Helper text 'Register your partner above before proceeding' not visible"
    )


def test_register_button_disabled_without_required_fields(page: Page, base_url: str, dsl_path: str) -> None:
    """Task 1: Register button is disabled when required fields are empty."""
    page.goto(base_url)
    op = OnboardPage(page)
    op.navigate()

    page.locator("input[placeholder*='path']").first.fill(dsl_path)
    page.locator("button:has-text('Compile')").click()
    page.wait_for_timeout(3000)
    page.locator("button:has-text('Next')").first.click()
    page.wait_for_timeout(1000)

    # Clear profile name (it may be auto-suggested)
    page.locator("input[placeholder='bevager_810']").fill("")
    page.wait_for_timeout(200)

    assert op.is_register_button_disabled(), "Register button should be disabled with empty required fields"


def test_register_button_enables_with_required_fields(page: Page, base_url: str, dsl_path: str) -> None:
    """Task 1: Register button enables once all required fields are filled."""
    page.goto(base_url)
    op = OnboardPage(page)
    op.navigate()

    page.locator("input[placeholder*='path']").first.fill(dsl_path)
    page.locator("button:has-text('Compile')").click()
    page.wait_for_timeout(3000)
    page.locator("button:has-text('Next')").first.click()
    page.wait_for_timeout(1000)

    op.fill_profile_name("e2e_test_profile")
    op.fill_trading_partner("E2E Partner")
    op.fill_transaction_type("810")
    page.wait_for_timeout(300)

    assert not op.is_register_button_disabled(), "Register button should be enabled with all required fields filled"
```

**Test Gate:**
```bash
python -c "import ast; ast.parse(open('portal/tests/e2e/test_onboard.py').read()); print('Syntax OK')"
```

---

## Phase B Gate

- [ ] `test_rules.py` parses without syntax errors
- [ ] `test_onboard.py` parses without syntax errors
- [ ] Existing E2E tests still pass

**Commit:**
```bash
git add portal/tests/e2e/test_rules.py portal/tests/e2e/test_onboard.py
git commit -m "test(e2e): add Rules and Onboard wizard E2E tests for rulesManagementFix verification"
```

---

# PHASE C: Run Tests & Fix Implementation

> **Prerequisite:** Phase B gate passes.
> **Goal:** All new tests pass. If any fail, fix the *implementation code* (Rules.tsx / Onboard.tsx), NOT the tests.

---

## Task C1: Build and run the full new test suite

```bash
# Rebuild frontend with latest changes
cd portal/ui && npm run build

# Run only the new test files
pytest portal/tests/e2e/test_rules.py portal/tests/e2e/test_onboard.py -v --tb=long 2>&1

# If all pass, also run the full suite to confirm no regressions
pytest portal/tests/e2e/ -v --tb=short 2>&1 | tail -40
```

## Task C2: Diagnose and fix failures

For each failing test:

1. **Read the failure traceback** — identify which assertion failed and the actual vs expected values.
2. **Read the implementation file** — verify the fix from `rulesManagementFix.md` was applied correctly.
3. **Fix the implementation code** — adjust selectors, logic, or styling in `Rules.tsx` or `Onboard.tsx`.
4. **Rebuild** — `cd portal/ui && npm run build`
5. **Re-run the failing test** — `pytest portal/tests/e2e/test_rules.py::test_name -v --tb=long`
6. **Repeat** until green.

Common failure modes to watch for:

| Symptom | Likely Cause | Fix Location |
|---|---|---|
| Cancel button not found | Button not rendered or wrong text | `Rules.tsx` cancel button JSX |
| Dropdown not in body portal | `createPortal` target wrong | `Rules.tsx` FieldCombobox |
| Field doesn't revert on blur | `previousValue` ref not updated | `Rules.tsx` FieldCombobox `handleBlur` |
| Asterisks not found | `required` prop not passed or `Input` not rendering `*` | `Onboard.tsx` Input component |
| Helper text not visible | Conditional render wrong (checking wrong state) | `Onboard.tsx` near Next button |
| Selector timeout | DOM structure changed, locator doesn't match | Update page object selector |

## Task C3: Verify page object selectors

If selectors fail, update the page objects to match actual DOM. Common selector adjustments:

```bash
# Debug: dump the page HTML for a specific section
# Add to a test temporarily:
#   print(page.locator("body").inner_html())
# Or use Playwright's codegen to discover correct selectors:
npx playwright codegen http://localhost:8321
```

---

## Phase C Gate

- [ ] All `test_rules.py` tests pass
- [ ] All `test_onboard.py` tests pass
- [ ] Full E2E suite passes: `pytest portal/tests/e2e/ -v`
- [ ] TypeScript compiles cleanly: `cd portal/ui && npx tsc --noEmit`

**Final Commit:**
```bash
git add -A
git commit -m "fix(portal): rules management UX fixes — cancel buttons, dropdown portal, field revert, required indicators

Verified by Playwright E2E tests (test_rules.py, test_onboard.py)."
```

---

## Test-to-Task Traceability

| Task | Fix | Test |
|---|---|---|
| 1: Required asterisks | `Onboard.tsx` — `required` prop on Input | `test_required_asterisks_visible` |
| 1: Required footnote | `Onboard.tsx` — `* Required` paragraph | `test_required_footnote_visible` |
| 1: Helper text | `Onboard.tsx` — text below Next button | `test_next_button_disabled_with_helper_text` |
| 2a: Portal dropdown | `Rules.tsx` — `createPortal` in FieldCombobox | `test_dropdown_renders_in_body_portal` |
| 2a: Visible dropdown | `Rules.tsx` — fixed positioning, z-9999 | `test_field_dropdown_fully_visible` |
| 2b: Revert on blur | `Rules.tsx` — `previousValue` ref + `handleBlur` | `test_field_reverts_on_empty_blur` |
| 2c: Universal Cancel | `Rules.tsx` — `cancelUniversal()` + button | `test_universal_cancel_button_exists`, `test_universal_cancel_reverts_changes` |
| 2c: Transaction Cancel | `Rules.tsx` — `cancelTransaction()` + button | `test_transaction_cancel_button_exists` |
| 2c: Partner Cancel | `Rules.tsx` — `cancelPartner()` + button | `test_partner_cancel_button_exists`, `test_partner_cancel_reverts_changes` |

---

## Resumption Protocol

If interrupted mid-execution:

1. Check which phase you're in by looking at committed files
2. Run the phase gate for the last completed phase to confirm green
3. Resume from the next uncompleted task
4. If mid-Phase C with failing tests, re-run `pytest portal/tests/e2e/test_rules.py portal/tests/e2e/test_onboard.py -v` to see current state
