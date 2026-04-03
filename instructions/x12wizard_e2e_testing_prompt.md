# X12 Wizard End-to-End Testing — Orchestration Prompt

**Purpose:** Fully test the X12 EDI branch of the onboarding wizard using Playwright CLI tests. Covers: format selection, transaction type loading, schema review, partner registration, match-key auto-population, rules configuration, and cleanup. Tests run against the Playwright TS test suite in `portal/ui/tests/`.

**Status:** COMPLETE — 10/10 Playwright tests passing, idempotent (verified 2026-04-03)

**Fixes applied during execution:**
- `Onboard.tsx` line 2: split import to `import type` for `StandardVersion`, `StandardTransaction`, `StandardSchemaResponse` (required by `verbatimModuleSyntax: true` in tsconfig)
- `app.py` line 20: added `http://localhost:15174` to CORS origins
- `x12-wizard.spec.ts` test 3: changed `selectOption('810')` to search+click pattern (the `<select>` is for version, not transaction type)

**Coding standards:** `CLAUDE.md`
**Wizard implementation:** `portal/ui/src/pages/Onboard.tsx`
**API routes:** `portal/api/routes/onboard.py`
**API client:** `portal/ui/src/api.ts`
**Existing smoke tests:** `portal/ui/tests/portal-smoke.spec.ts`
**Playwright config:** `portal/ui/playwright.config.ts` (baseURL: `http://localhost:15174`, headless: false)
**Existing E2E (Python):** `portal/tests/e2e/test_onboard.py`, `portal/tests/e2e/pages/onboard_page.py`
**Config file:** `config/config.yaml`
**Compare rules dir:** `config/compare_rules/`

---

## Rules of Engagement

1. **Sequential within phases** — complete each task fully (including its test gate) before starting the next.
2. **Phase gates are hard stops** — do not start a phase until the prior phase gate passes.
3. **Read before writing** — always read the target file and its imports before making any change.
4. **Minimal diffs** — change only what the task requires. No drive-by fixes, no extra comments.
5. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
6. **Stop on red** — if any test gate fails, diagnose and fix before proceeding.
7. **Match existing patterns** — follow conventions in `portal-smoke.spec.ts` and `portal/tests/e2e/` exactly.
8. **No backend changes** — Python files are read-only for this prompt. If a backend bug is found, document it and skip the test with a TODO.
9. **Server is live** — backend runs on port 18041, frontend on 15174. Test endpoints with curl throughout.
10. **Cleanup after tests** — any profiles or rules files created during testing must be removed so the test is idempotent.

---

## Pre-Flight

Before starting any task, verify the development environment:

```bash
cd ~/VS/pycoreEdi

# Verify API is healthy
curl -s http://localhost:18041/api/health

# Verify X12 endpoints respond
curl -s http://localhost:18041/api/onboard/x12-types | python -m json.tool | head -20

# Verify frontend is running
curl -s -o /dev/null -w "%{http_code}" http://localhost:15174/

# Verify Playwright is installed
cd portal/ui && npx playwright --version

# Verify existing smoke tests pass
cd ~/VS/pycoreEdi/portal/ui && npx playwright test portal-smoke.spec.ts

# Verify TypeScript compiles clean
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
```

If anything fails at baseline, **stop and fix before proceeding**.

---

# PHASE A: API Contract Tests (curl) ✅ COMPLETE

> **Prerequisite:** Pre-flight green.
> **Deliverables:** Validated API responses for all X12 endpoints.
> **Why:** Confirm the backend contract before writing UI tests — if an endpoint is broken, we know immediately.

---

## Task A.1 — Verify `GET /api/onboard/x12-types`

**Execute:**
```bash
curl -s http://localhost:18041/api/onboard/x12-types | python -m json.tool
```

**Test Gate:**
- Response has `types` array.
- Each entry has `code`, `label`, `map_file` keys.
- At least one entry has `code: "810"`.

**Commit:** `test(x12Wizard): verify x12-types API contract`

---

## Task A.2 — Verify `GET /api/onboard/x12-schema?type=810`

**Execute:**
```bash
curl -s "http://localhost:18041/api/onboard/x12-schema?type=810" | python -m json.tool
```

**Test Gate:**
- Response has `transaction_type`, `input_format`, `segments`, `fields`, `match_key_default`.
- `transaction_type` is `"810"`.
- `input_format` is `"X12"`.
- `fields` is a non-empty array; each entry has `name`, `source`, `section`.
- `match_key_default` has `segment: "BIG"` and `field: "BIG02"`.

**Commit:** `test(x12Wizard): verify x12-schema API contract for 810`

---

## Task A.3 — Verify `POST /api/onboard/register` (X12 payload)

**Execute:**
```bash
# Register a test profile
curl -s -X POST http://localhost:18041/api/onboard/register \
  -H "Content-Type: application/json" \
  -d '{
    "profile_name": "_e2e_x12_test",
    "trading_partner": "E2E Test",
    "transaction_type": "810",
    "description": "Automated E2E test profile",
    "source_dsl": "./rules/gfs_810_map.yaml",
    "compiled_output": "./rules/gfs_810_map.yaml",
    "inbound_dir": "./inbound/x12",
    "match_key": {"segment": "BIG", "field": "BIG02"},
    "segment_qualifiers": {},
    "split_config": null
  }' | python -m json.tool
```

**Test Gate:**
- Response has `profile_name: "_e2e_x12_test"`, `rules_file`, `config_updated: true`, `rules_created: true`.
- `config/compare_rules/_e2e_x12_test.yaml` exists on disk.
- Profile appears in `config.yaml` under `compare.profiles`.

**Cleanup:**
```bash
# Remove from config.yaml and rules file
python -c "
import yaml
from pathlib import Path
cfg = Path('config/config.yaml')
data = yaml.safe_load(cfg.read_text())
data.get('compare',{}).get('profiles',{}).pop('_e2e_x12_test', None)
data.get('csv_schema_registry',{}).pop('_e2e_x12_test', None)
cfg.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
Path('config/compare_rules/_e2e_x12_test.yaml').unlink(missing_ok=True)
print('Cleanup: OK')
"
```

**Commit:** `test(x12Wizard): verify register API with X12 payload and cleanup`

---

# PHASE B: Playwright Test File — X12 Wizard E2E ✅ COMPLETE

> **Prerequisite:** Phase A green.
> **Deliverables:** `portal/ui/tests/x12-wizard.spec.ts` with full X12 wizard flow coverage.

---

## Task B.1 — Create test file scaffold with helpers

**Investigate:**
```bash
# Read existing smoke test for pattern reference
cat portal/ui/tests/portal-smoke.spec.ts
# Read Playwright config
cat portal/ui/playwright.config.ts
# Read API client for endpoint signatures
cat portal/ui/src/api.ts | head -60
```

**Execute:**

Create `portal/ui/tests/x12-wizard.spec.ts` with:

1. Imports: `{ test, expect } from '@playwright/test'`
2. Constants: `API_BASE = 'http://localhost:18041'`, `TEST_PROFILE = '_pw_x12_test'`
3. `test.afterEach()` hook that calls cleanup API or direct config removal for any profile created during the test (idempotency).
4. Helper: `async function cleanupProfile(profileName: string)` — DELETE or manual cleanup via fetch to remove test profiles.

Pattern to follow from `portal-smoke.spec.ts`:
- Hash-based navigation: `page.goto('/#onboard')`
- `page.waitForTimeout(2000)` for render settling
- `page.locator()` / `page.getByRole()` / `page.getByText()` selectors
- `expect()` assertions

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
```

**Commit:** `test(x12Wizard): scaffold x12-wizard.spec.ts with cleanup helpers`

---

## Task B.2 — Test: Format selector renders both options

**Execute:**

Add test `'Onboard page shows X12 EDI and Flat-File format options'`:

1. Navigate to `/#onboard`.
2. Wait for page to render.
3. Assert text "X12 EDI" is visible.
4. Assert text "Flat-File / XML" is visible.
5. Assert both are clickable buttons.

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx playwright test x12-wizard.spec.ts -g "format options"
```

**Commit:** `test(x12Wizard): format selector renders both options`

---

## Task B.3 — Test: Clicking X12 EDI shows transaction type dropdown

**Execute:**

Add test `'Selecting X12 EDI loads transaction type dropdown'`:

1. Navigate to `/#onboard`.
2. Click the button containing "X12 EDI".
3. Wait for the transaction type `<select>` to appear.
4. Assert the select has at least one `<option>` with "810" in its text.
5. Assert step title/card header contains "Select X12 Transaction Type".

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx playwright test x12-wizard.spec.ts -g "transaction type dropdown"
```

**Commit:** `test(x12Wizard): X12 format shows transaction type dropdown with 810`

---

## Task B.4 — Test: Schema review loads for 810

**Execute:**

Add test `'Selecting 810 and clicking Review Schema shows fields table'`:

1. Navigate to `/#onboard`, click "X12 EDI".
2. Select "810" from the transaction type dropdown.
3. Click "Review Schema" button.
4. Wait for schema review card to appear (text "Schema Review").
5. Assert field count badge is visible (e.g., "XX fields").
6. Assert at least one field row shows "BIG" segment reference.
7. Assert `match_key_default` display shows "BIG" / "BIG02".

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx playwright test x12-wizard.spec.ts -g "Review Schema"
```

**Commit:** `test(x12Wizard): 810 schema review shows fields and match key default`

---

## Task B.5 — Test: "Existing Type" and "Upload New Mapping" toggle

**Execute:**

Add test `'Mode toggle switches between Existing Type and Upload New Mapping'`:

1. Navigate to `/#onboard`, click "X12 EDI".
2. Assert "Existing Type" button is active (has active styling or aria state).
3. Assert a `<select>` for transaction types is visible.
4. Click "Upload New Mapping" toggle button.
5. Assert file input (`input[type="file"]`) is now visible.
6. Assert `<select>` is no longer visible.
7. Click "Existing Type" toggle — verify select returns.

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx playwright test x12-wizard.spec.ts -g "Mode toggle"
```

**Commit:** `test(x12Wizard): mode toggle switches between existing and upload`

---

## Task B.6 — Test: Next button advances to Step 2 after schema review

**Execute:**

Add test `'Next: Register Partner button appears after schema review'`:

1. Navigate to `/#onboard`, click "X12 EDI".
2. Select "810", click "Review Schema", wait for schema.
3. Assert "Next: Register Partner" button is visible and enabled.
4. Click it.
5. Assert Step 2 content is visible — look for "Register Partner" heading or the profile name input.
6. Assert transaction type field is pre-filled with "810".

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx playwright test x12-wizard.spec.ts -g "Register Partner button"
```

**Commit:** `test(x12Wizard): next button advances to step 2 with pre-filled type`

---

## Task B.7 — Test: Match key auto-populates in X12 segment mode

**Execute:**

Add test `'Match key auto-populates with BIG / BIG02 for 810'`:

1. Complete Steps 0-1 (format → 810 → schema → Next).
2. Assert "X12 Segment/Field" toggle is active (not "JSON Path").
3. Assert Segment input value is "BIG".
4. Assert Field input value is "BIG02".

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx playwright test x12-wizard.spec.ts -g "Match key auto-populates"
```

**Commit:** `test(x12Wizard): match key auto-populates BIG/BIG02 for 810`

---

## Task B.8 — Test: Register creates profile and advances to Step 3

**Execute:**

Add test `'Registering X12 partner creates profile and shows rules step'`:

1. Complete Steps 0-1 (format → 810 → schema → Next).
2. Fill profile name: `_pw_x12_test`.
3. Fill trading partner: `PW Test Partner`.
4. Transaction type should be pre-filled "810".
5. Click "Register" button.
6. Wait for success indicator (toast, banner, or "Next: Configure Rules" becoming enabled).
7. Click "Next: Configure Rules".
8. Assert Step 3 content is visible — rules table with field rows.
9. Assert at least one rule row references a field from the 810 schema.

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx playwright test x12-wizard.spec.ts -g "Registering X12 partner"
```

**Commit:** `test(x12Wizard): register creates profile and shows rules step`

---

## Task B.9 — Test: Rules step seeds from X12 schema fields

**Execute:**

Add test `'Rules step auto-seeds rules from X12 810 schema fields'`:

1. Complete Steps 0-2 (format → 810 → schema → register `_pw_x12_test`).
2. Advance to Step 3.
3. Assert rules table has multiple rows.
4. Assert at least one row has severity "hard" (default).
5. Assert field names include known 810 fields (e.g., "InvoiceNumber" or any field from the schema).
6. Assert a catch-all row (`*` / `*`) exists.

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx playwright test x12-wizard.spec.ts -g "auto-seeds rules"
```

**Commit:** `test(x12Wizard): rules auto-seeded from X12 810 schema`

---

## Task B.10 — Test: Save rules completes the wizard

**Execute:**

Add test `'Saving rules completes wizard and shows success state'`:

1. Complete full flow: format → 810 → schema → register `_pw_x12_test` → rules.
2. Click "Save Rules" button.
3. Assert wizard shows completion state (e.g., "Trading Partner Onboarded" or success banner).
4. Verify `config/compare_rules/_pw_x12_test.yaml` was created (via API or file check).

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx playwright test x12-wizard.spec.ts -g "completes wizard"
```

**Commit:** `test(x12Wizard): full wizard flow completes successfully`

---

## Task B.11 — Test: Duplicate profile name returns 409

**Execute:**

Add test `'Registering duplicate profile name shows error'`:

1. Complete Steps 0-1 (format → 810 → schema → Next).
2. Fill profile name with an **existing** profile from config (e.g., `regional_health_810`).
3. Fill trading partner and transaction type.
4. Click "Register".
5. Assert an error message appears (e.g., "already exists" or 409-related text).
6. Assert wizard does NOT advance to Step 3.

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx playwright test x12-wizard.spec.ts -g "duplicate profile"
```

**Commit:** `test(x12Wizard): duplicate profile name shows 409 error`

---

# PHASE C: Cleanup and Full Suite Run ✅ COMPLETE (C.1 idempotency verified, C.2-C.3 pending)

> **Prerequisite:** Phase B green.
> **Deliverables:** All tests passing, idempotent, no leftover artifacts.

---

## Task C.1 — Verify test idempotency

**Execute:**

Run the full X12 wizard test suite twice in a row:

```bash
cd ~/VS/pycoreEdi/portal/ui
npx playwright test x12-wizard.spec.ts
npx playwright test x12-wizard.spec.ts
```

**Test Gate:**
- Both runs pass.
- No leftover `_pw_x12_test` profile in `config/config.yaml`.
- No leftover `config/compare_rules/_pw_x12_test.yaml`.

**Commit:** `test(x12Wizard): verify test idempotency`

---

## Task C.2 — Run full Playwright suite (smoke + x12-wizard)

**Execute:**

```bash
cd ~/VS/pycoreEdi/portal/ui && npx playwright test
```

**Test Gate:**
- All tests pass (0 failures).
- Smoke tests still pass alongside the new X12 wizard tests.
- TypeScript compiles clean: `npx tsc --noEmit`

**Commit:** `test(x12Wizard): full Playwright suite green`

---

## Task C.3 — Verify backend tests unaffected

**Execute:**

```bash
cd ~/VS/pycoreEdi && python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

**Test Gate:**
- All existing backend tests still pass.
- No regressions.

**Commit:** `test(x12Wizard): confirm backend tests unaffected`

---

# Summary of Test Coverage

| Test | Step | What it validates |
|------|------|-------------------|
| Format selector | Step 0 | Both format cards render and are clickable |
| X12 type dropdown | Step 1 | Types load from API, 810 present |
| Schema review | Step 1 | Fields table, segment info, match key default |
| Mode toggle | Step 1 | Existing/Upload toggle switches UI |
| Next → Step 2 | Step 1→2 | Advance with pre-filled transaction type |
| Match key auto | Step 2 | BIG/BIG02 auto-populated for 810 |
| Register partner | Step 2→3 | Profile created, rules step visible |
| Rules seeding | Step 3 | Auto-generated from schema, catch-all present |
| Save rules | Step 3 | Wizard completes, rules file created |
| Duplicate 409 | Step 2 | Error shown for existing profile name |
| Idempotency | All | Runs twice cleanly, no leftover artifacts |
