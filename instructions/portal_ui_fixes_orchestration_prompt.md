# Portal UI Fixes — Orchestration Prompt (v2)

> **Purpose:** Fix portal UI issues spanning backend path resolution, frontend routing, styling, infographic navigation, and Rules page functionality. Execute tasks sequentially, then run a Playwright verification loop until all checks pass.

---

## Pre-Flight

1. `cd portal/ui && npm install`
2. Ensure `@playwright/test` is a local devDependency:
   ```bash
   npm ls @playwright/test || npm install --save-dev @playwright/test
   ```
3. Start Vite dev server: `npm run dev` (background, port 5173)
4. Start backend API **from the project root** (critical for path resolution):
   ```bash
   cd /path/to/pycoreEdi && python -m uvicorn portal.api.main:app --port 8000
   ```
5. Verify both are up:
   ```bash
   curl -s http://localhost:5173/ | head -1    # should return HTML
   curl -s http://localhost:8000/api/health     # should return {"status":"ok"}
   ```

---

## Task 1: Fix Backend Path Resolution (root cause of 404s)

**Problem:** `GET /api/compare/profiles/{name}/rules` returns HTTP 404:
```
{"detail":"[Errno 2] No such file or directory: 'config/compare_rules/bevager_810.yaml'"}
```

**Root cause:** `compare.py` loads `profile.rules_file` from config (a relative path like `config/compare_rules/bevager_810.yaml`) and passes it directly to `load_rules()`. The `load_rules()` function calls `open(rules_path)` which resolves relative to the Python process CWD — not the project root. The rules.py tier routes work fine because they use the absolute `_RULES_DIR` constant, but compare.py doesn't apply the same resolution.

**File:** `portal/api/routes/compare.py`

**Implementation:**

1. Find the `_PROJECT_ROOT` constant (near line 44):
   ```python
   _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
   ```

2. Add a helper function after the constants:
   ```python
   def _resolve_rules_path(relative_path: str) -> str:
       """Resolve a relative rules_file path against the project root."""
       p = Path(relative_path)
       if p.is_absolute():
           return str(p)
       return str(_PROJECT_ROOT / p)
   ```

3. In `get_rules()` (the `GET /profiles/{name}/rules` handler), change:
   ```python
   # BEFORE:
   rules = load_rules(profile.rules_file)
   # AFTER:
   rules = load_rules(_resolve_rules_path(profile.rules_file))
   ```

4. In `update_rules()` (the `PUT /profiles/{name}/rules` handler), change:
   ```python
   # BEFORE:
   with open(profile.rules_file, "w", encoding="utf-8") as f:
   # AFTER:
   with open(_resolve_rules_path(profile.rules_file), "w", encoding="utf-8") as f:
   ```

5. In the `get_rules()` response dict, add `amount_variance` (currently missing):
   ```python
   # BEFORE:
   classification = [
       {
           "segment": r.segment,
           "field": r.field,
           "severity": r.severity,
           "ignore_case": r.ignore_case,
           "numeric": r.numeric,
           "conditional_qualifier": r.conditional_qualifier,
       }
       for r in rules.classification
   ]
   # AFTER:
   classification = [
       {
           "segment": r.segment,
           "field": r.field,
           "severity": r.severity,
           "ignore_case": r.ignore_case,
           "numeric": r.numeric,
           "conditional_qualifier": r.conditional_qualifier,
           "amount_variance": r.amount_variance,
       }
       for r in rules.classification
   ]
   ```

**File:** `portal/api/routes/rules.py`

6. In `get_effective()`, resolve the rules_dir to an absolute path:
   ```python
   # BEFORE (around line 211):
   rules_dir = os.path.dirname(profile.rules_file) if profile.rules_file else _RULES_DIR
   tiered = load_tiered_rules(rules_dir, profile.transaction_type, profile.rules_file)
   # AFTER:
   if profile.rules_file:
       abs_rules_file = str(Path(profile.rules_file) if Path(profile.rules_file).is_absolute() else _PROJECT_ROOT / profile.rules_file)
       rules_dir = os.path.dirname(abs_rules_file)
   else:
       abs_rules_file = ""
       rules_dir = _RULES_DIR
   tiered = load_tiered_rules(rules_dir, profile.transaction_type, abs_rules_file)
   ```

**File:** `pyedi_core/comparator/rules.py`

7. In `load_rules()`, add `amount_variance` to FieldRule construction (currently missing):
   ```python
   # BEFORE (around line 35-42):
   classification.append(FieldRule(
       segment=entry["segment"],
       field=entry["field"],
       severity=entry.get("severity", "hard"),
       ignore_case=entry.get("ignore_case", False),
       numeric=entry.get("numeric", False),
       conditional_qualifier=entry.get("conditional_qualifier"),
   ))
   # AFTER:
   classification.append(FieldRule(
       segment=entry["segment"],
       field=entry["field"],
       severity=entry.get("severity", "hard"),
       ignore_case=entry.get("ignore_case", False),
       numeric=entry.get("numeric", False),
       conditional_qualifier=entry.get("conditional_qualifier"),
       amount_variance=entry.get("amount_variance"),
   ))
   ```

**Verify:** Restart the API server, then:
```bash
curl -s http://localhost:8000/api/compare/profiles/bevager_810/rules | python -m json.tool | head -20
# Should return JSON with classification/ignore arrays, NOT a 404
curl -s http://localhost:8000/api/rules/effective/bevager_810 | python -m json.tool | head -20
# Should return rules with tier provenance, NOT empty arrays
```

---

## Task 2: Hash-Based Page Routing (refresh fix)

**File:** `portal/ui/src/App.tsx`

**Problem:** `useState<Page>('dashboard')` resets to dashboard on every page refresh. No URL-based persistence.

**Implementation:**

Read `App.tsx` first. Look for `const [page, setPage] = useState<Page>(...)`. If it already uses `getInitialPage`, skip to verification. Otherwise:

1. Add a helper function **between** the `type Page = ...` line and the `const NAV` array:
   ```typescript
   function getInitialPage(): Page {
     const hash = window.location.hash.replace('#', '')
     const valid: Page[] = ['dashboard','validate','pipeline','tests','compare','rules','config','onboard']
     return valid.includes(hash as Page) ? (hash as Page) : 'dashboard'
   }
   ```

2. Replace `useState<Page>('dashboard')` with:
   ```typescript
   const [page, setPage] = useState<Page>(getInitialPage)
   ```

3. Add two `useEffect` hooks immediately after the existing health-check `useEffect(() => { api.health()... }, [])`:
   ```typescript
   // Sync page state to URL hash
   useEffect(() => {
     window.location.hash = page
   }, [page])

   // Listen for browser back/forward navigation
   useEffect(() => {
     const onHash = () => {
       const h = window.location.hash.replace('#', '')
       const valid: Page[] = ['dashboard','validate','pipeline','tests','compare','rules','config','onboard']
       if (valid.includes(h as Page)) setPage(h as Page)
     }
     window.addEventListener('hashchange', onHash)
     return () => window.removeEventListener('hashchange', onHash)
   }, [])
   ```

**Verify:** Open `http://localhost:5173/#rules`, refresh — should stay on Rules page, not reset to Dashboard.

---

## Task 3: Sidebar Styling (less stark white)

**File:** `portal/ui/src/App.tsx`

**Problem:** Sidebar `<nav>` uses `bg-white` which appears stark/plain against the `bg-gray-50` main content area.

**Implementation:**

Read `App.tsx` and find the `<nav>` element. Apply these exact className changes:

1. On the `<nav>` element, change the background class:
   - **Find:** `bg-white` inside the nav's className string
   - **Replace with:** `bg-gray-50/80`
   - The full className should read: `w-56 bg-gray-50/80 border-r border-gray-200 text-gray-600 flex flex-col`

2. Add a blue gradient accent bar as the **first child** inside `<nav>`, before the heading div:
   ```html
   <div className="h-1 bg-gradient-to-r from-blue-500 to-blue-400" />
   ```

3. Find the heading div containing "PyEDI Portal" and change its text color class:
   - **Find:** `text-gray-900` in that div's className
   - **Replace with:** `text-blue-900`

**Verify:** In browser, sidebar should have a subtle gray tint (not pure white), a thin blue bar at the very top, and a blue-tinted "PyEDI Portal" heading.

---

## Task 4: Infographic Navigation Links (broken clicks)

**Files:**
- `portal/ui/src/components/infographics/WhiteboardTheme.tsx`
- `portal/ui/src/components/infographics/WatercolorTheme.tsx`
- `portal/ui/src/components/infographics/StickyNotesTheme.tsx`
- `portal/ui/src/components/infographics/RetroArcadeTheme.tsx`

**Problem:** SVG arrow/connector elements between workflow step buttons may intercept pointer events, blocking clicks on navigation buttons.

**Implementation (apply to all 4 theme files):**

1. Find every SVG or `<span>` element that renders **between** workflow step buttons — the connector elements inside `{i < WORKFLOW_STEPS.length - 1 && ( ... )}` blocks. Add `pointer-events-none` to each element's className. Preserve any existing className.

   - **WhiteboardTheme:** The `<svg width="36" height="24" ...>` connector — add `pointer-events-none` to its className
   - **WatercolorTheme:** The `<svg width="32" height="20" ...>` connector — add `pointer-events-none` to its className
   - **StickyNotesTheme:** The yarn SVG layer already has `pointer-events-none` (no change needed for connectors)
   - **RetroArcadeTheme:** The `<span>` with `>>` text — add `pointer-events-none` to its className

2. Add `data-testid={`nav-${step.pageKey}`}` attribute to each **workflow step** `<button>` element (the ones with `onClick={() => onNavigate?.(step.pageKey)}`).

3. Add `data-testid={`tip-${tip.pageKey}`}` attribute to each **quick tip** `<button>` element.

**Verify:** On Dashboard, click each workflow step button (Validate, Onboard, Compare, Rules, Pipeline) — each should navigate to the corresponding page. Check URL hash changes.

---

## Task 5: Partner Rules Visibility & Error Surfacing

**File:** `portal/ui/src/pages/Rules.tsx`

**Problem:** When the API returns a 404 for partner rules (now fixed in Task 1), the error is silently swallowed. When profiles are empty, there's no user feedback.

**Implementation:**

1. In the `partner` rules `useEffect` catch block (the one that calls `api.compareRules(selectedPartner)`), add `setError(e.message)`:
   ```typescript
   .catch(e => {
     setPartnerRules([])
     setPartnerIgnores([])
     setError(e.message)  // ADD THIS LINE
   })
   ```

2. Same fix for the `transaction` rules `useEffect` catch block (the one that calls `api.ruleTransaction(selectedTxn)`):
   ```typescript
   .catch(e => {
     setTxnRules([])
     setTxnIgnores([])
     setError(e.message)  // ADD THIS LINE
   })
   ```

3. In the Partner tab section, after the `</select>` closing tag and its parent `</div>`, add an empty-state warning:
   ```typescript
   {profiles.length === 0 && (
     <p className="text-sm text-amber-600 mt-2">
       No profiles loaded — verify the API is running and check the error banner above.
     </p>
   )}
   ```

**Verify:** Rules -> Partner tab should show 9 profiles in dropdown. Select "bevager_810" -> rules grid should appear with classification rules (requires Task 1 to be complete). If API is offline, amber warning should appear.

---

## Task 6: Conditional Qualifier & Amount Variance Columns in RulesGrid

**File:** `portal/ui/src/pages/Rules.tsx`

**Problem:** `ClassificationRule` interface has `conditional_qualifier` and `amount_variance` fields, and `normRule` preserves them, but the `RulesGrid` table has no columns for them.

**Implementation — RulesGrid table headers:**

Find the `<thead>` inside the `RulesGrid` function's Classification Rules table. After the "Ignore Case" `<th>` and before the action `<th>` (the `{!readOnly && <th>}` one), add:
```html
<th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Cond. Qualifier</th>
<th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Amt Variance</th>
```

**Implementation — Empty-state colspan:**

Find the empty-state `<tr>` inside the same table (the one with "No classification rules"). Update the colSpan:
- FROM: `colSpan={readOnly ? 5 : 6}`
- TO: `colSpan={readOnly ? 7 : 8}`

**Implementation — Rule row cells:**

Inside the `rules.map()` row rendering, after the ignore_case `<td>` and before the `{!readOnly && (` delete button `<td>`, add:

```tsx
<td className="px-3 py-2">
  {readOnly ? (
    <span className="font-mono text-xs">{r.conditional_qualifier || '-'}</span>
  ) : (
    <FieldCombobox
      value={r.conditional_qualifier || ''}
      options={fieldNames}
      onChange={v => updateRule(i, { conditional_qualifier: v || null })}
      placeholder="e.g. IT108"
    />
  )}
</td>
<td className="px-3 py-2">
  {readOnly ? (
    <span className="font-mono text-xs">{r.amount_variance != null ? r.amount_variance : '-'}</span>
  ) : (
    <input
      type="number"
      step="0.01"
      min="0"
      value={r.amount_variance ?? ''}
      onChange={e => updateRule(i, { amount_variance: e.target.value ? parseFloat(e.target.value) : null })}
      className="w-20 px-2 py-1 border border-gray-200 rounded text-xs font-mono focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none"
      placeholder="0.00"
    />
  )}
</td>
```

**Implementation — Effective View table:**

Find the effective rules `<table>` (inside the `tab === 'effective'` block). In its `<thead>`, after the "Ignore Case" `<th>` and before the "Tier" `<th>`, add:
```html
<th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Cond. Qualifier</th>
<th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Amt Variance</th>
```

In the effective rules `<tbody>` row, after the ignore_case `<td>` and before the Tier `<td>`, add:
```html
<td className="px-3 py-2 font-mono text-xs">{r.conditional_qualifier || '-'}</td>
<td className="px-3 py-2 font-mono text-xs">{r.amount_variance != null ? r.amount_variance : '-'}</td>
```

**Verify:** Rules -> Universal tab -> "+ Add Rule" -> Cond. Qualifier dropdown should show field options -> Amt Variance input should accept numbers.

---

## RALPH Verification Loop

After implementing all 6 tasks, run this review loop. Repeat until all checks pass.

### Round 1: Type Check & Audit

1. Run `cd portal/ui && npx tsc --noEmit` — must produce zero errors
2. Read each modified file end-to-end, verify no syntax errors, no missing imports, no broken JSX
3. Restart the backend API (required after Task 1 backend changes)

### Round 2: Playwright Automated Checks

Create a file `portal/ui/e2e-verify.spec.ts` with the following content, then run it with `cd portal/ui && npx playwright test e2e-verify.spec.ts --reporter=list`:

```typescript
import { test, expect } from '@playwright/test'

const BASE = 'http://localhost:5173'

test.describe('Portal UI Fixes Verification', () => {

  test('CHECK 1 — Hash routing: refresh preserves page', async ({ page }) => {
    await page.goto(`${BASE}/#rules`)
    await page.waitForTimeout(1000)
    const heading = page.locator('text=Rules Management')
    await expect(heading).toBeVisible()

    // Refresh and verify page persists
    await page.reload()
    await page.waitForTimeout(1000)
    expect(new URL(page.url()).hash).toBe('#rules')
    await expect(heading).toBeVisible()

    // Click sidebar Compare, verify hash changes
    await page.locator('nav button', { hasText: 'Compare' }).click()
    await page.waitForTimeout(500)
    expect(new URL(page.url()).hash).toBe('#compare')

    // Browser back should return to rules
    await page.goBack()
    await page.waitForTimeout(500)
    expect(new URL(page.url()).hash).toBe('#rules')
  })

  test('CHECK 2 — Sidebar styling: not stark white', async ({ page }) => {
    await page.goto(BASE)
    await page.waitForTimeout(1000)
    const nav = page.locator('nav').first()
    const navClasses = await nav.getAttribute('class') || ''

    // Must NOT have bg-white
    expect(navClasses).not.toContain('bg-white')
    // Must have bg-gray-50 (the /80 opacity variant)
    expect(navClasses).toContain('bg-gray-50')

    // Blue gradient bar must be visible
    const gradientBar = nav.locator('div').first()
    const gradientClasses = await gradientBar.getAttribute('class') || ''
    expect(gradientClasses).toContain('bg-gradient-to-r')

    // Heading must have blue color
    const headingDiv = nav.locator('div', { hasText: 'PyEDI Portal' })
    const headingClasses = await headingDiv.getAttribute('class') || ''
    expect(headingClasses).toContain('text-blue-900')
  })

  test('CHECK 3 — Infographic nav: data-testid present and clickable', async ({ page }) => {
    await page.goto(`${BASE}/#dashboard`)
    await page.waitForTimeout(2000)

    // Verify data-testid attributes exist
    const navRules = page.locator('[data-testid="nav-rules"]')
    await expect(navRules.first()).toBeVisible()

    // Click and verify navigation
    await navRules.first().click()
    await page.waitForTimeout(500)
    expect(new URL(page.url()).hash).toBe('#rules')

    // Go back, try validate
    await page.goto(`${BASE}/#dashboard`)
    await page.waitForTimeout(2000)
    const navValidate = page.locator('[data-testid="nav-validate"]')
    await navValidate.first().click()
    await page.waitForTimeout(500)
    expect(new URL(page.url()).hash).toBe('#validate')
  })

  test('CHECK 4 — Backend rules: no 404 on partner rules', async ({ page }) => {
    // Direct API check: profiles endpoint
    const profilesResp = await page.request.get('http://localhost:8000/api/compare/profiles')
    expect(profilesResp.status()).toBe(200)
    const profiles = await profilesResp.json()
    expect(profiles.length).toBeGreaterThan(0)

    // Direct API check: partner rules for first profile must NOT 404
    const name = profiles[0].name
    const rulesResp = await page.request.get(`http://localhost:8000/api/compare/profiles/${name}/rules`)
    expect(rulesResp.status()).toBe(200)
    const rulesData = await rulesResp.json()
    expect(rulesData).toHaveProperty('classification')
    expect(rulesData).toHaveProperty('ignore')

    // Direct API check: effective rules must return rules (not empty)
    const effectiveResp = await page.request.get(`http://localhost:8000/api/rules/effective/${name}`)
    expect(effectiveResp.status()).toBe(200)
  })

  test('CHECK 5 — Partner rules UI: dropdown populated, rules grid appears', async ({ page }) => {
    await page.goto(`${BASE}/#rules`)
    await page.waitForTimeout(1000)

    // Click Partner tab
    const partnerTab = page.locator('button', { hasText: 'Partner' })
    await partnerTab.click()
    await page.waitForTimeout(1000)

    // Dropdown should have profile options (more than just "Select profile...")
    const select = page.locator('select').last()
    const options = await select.locator('option').count()
    expect(options).toBeGreaterThan(1)

    // Select a profile and verify grid appears
    await select.selectOption({ index: 1 })
    await page.waitForTimeout(1500)

    // Either rules grid table OR the success/info banner should be visible
    const table = page.locator('table')
    const hasTable = await table.first().isVisible().catch(() => false)
    expect(hasTable).toBe(true)
  })

  test('CHECK 6 — Cond. Qualifier & Amt Variance columns', async ({ page }) => {
    await page.goto(`${BASE}/#rules`)
    await page.waitForTimeout(1000)

    // Click Universal tab
    await page.locator('button', { hasText: 'Universal' }).click()
    await page.waitForTimeout(1000)

    // Column headers must exist
    const condHeader = page.locator('th', { hasText: 'Cond. Qualifier' })
    const amtHeader = page.locator('th', { hasText: 'Amt Variance' })
    await expect(condHeader.first()).toBeVisible()
    await expect(amtHeader.first()).toBeVisible()

    // Add a rule and verify input fields
    const addBtn = page.locator('button', { hasText: '+ Add Rule' })
    if (await addBtn.isVisible()) {
      await addBtn.click()
      await page.waitForTimeout(500)
      const numberInput = page.locator('input[type="number"][placeholder="0.00"]')
      await expect(numberInput.first()).toBeVisible()
    }

    // Check Effective View tab columns after selecting a profile
    await page.locator('button', { hasText: 'Effective View' }).click()
    await page.waitForTimeout(500)
    const select = page.locator('select')
    const optCount = await select.locator('option').count()
    if (optCount > 1) {
      await select.selectOption({ index: 1 })
      await page.waitForTimeout(1500)
      // If effective rules loaded, new columns should appear
      const effCondHeader = page.locator('th', { hasText: 'Cond. Qualifier' })
      const effAmtHeader = page.locator('th', { hasText: 'Amt Variance' })
      const effCondCount = await effCondHeader.count()
      const effAmtCount = await effAmtHeader.count()
      // These are visible only when effectiveRules.length > 0
      console.log(`  Effective Cond. Qualifier headers: ${effCondCount}`)
      console.log(`  Effective Amt Variance headers: ${effAmtCount}`)
    }
  })
})
```

Run:
```bash
cd portal/ui && npx playwright test e2e-verify.spec.ts --reporter=list
```

### Round 3: Fix Any Failures
- For each failed check, identify root cause and fix
- Re-run only the failed checks
- Repeat until all 6 checks pass

### Round 4: Final Lint & Type Check
- `cd portal/ui && npx tsc --noEmit` — zero errors
- Visual spot-check in browser: navigate through all pages, verify no regressions
- Clean up: remove `e2e-verify.spec.ts` if desired

---

## Files Modified Summary

| File | Tasks |
|------|-------|
| `portal/api/routes/compare.py` | 1 (path resolution, amount_variance in response) |
| `portal/api/routes/rules.py` | 1 (effective rules absolute path resolution) |
| `pyedi_core/comparator/rules.py` | 1 (load amount_variance from YAML) |
| `portal/ui/src/App.tsx` | 2 (hash routing), 3 (sidebar styling) |
| `portal/ui/src/pages/Rules.tsx` | 5 (error surfacing), 6 (new columns) |
| `portal/ui/src/components/infographics/WhiteboardTheme.tsx` | 4 (pointer-events, data-testid) |
| `portal/ui/src/components/infographics/WatercolorTheme.tsx` | 4 (pointer-events, data-testid) |
| `portal/ui/src/components/infographics/StickyNotesTheme.tsx` | 4 (data-testid only) |
| `portal/ui/src/components/infographics/RetroArcadeTheme.tsx` | 4 (pointer-events, data-testid) |
