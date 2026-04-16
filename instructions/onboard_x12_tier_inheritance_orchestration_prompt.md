# Orchestration Prompt — X12 Onboard: Tier Inheritance for Compare Rules

## Context

Today the X12 onboarding wizard (`Onboard.tsx` `StepRules`) seeds **every** field
of the chosen transaction into the partner-tier rules file (e.g.
`config/compare_rules/<partner>.yaml`). Previously every row was hardcoded
`severity: hard`; that bug was fixed in `instructions/onboard_x12_mandatory_fix_orchestration_prompt.md`
so severity is now derived from `min_occurs`.

The remaining defect: **partner files duplicate every rule already covered by
the transaction tier** (`config/compare_rules/_global_<txn>.yaml`). The 3-tier
resolution (universal → transaction → partner, per
`project_tiered_rules.md`) is defeated because the partner row repeats the
transaction-tier row verbatim. Two consequences:

1. Partner YAML bloat — every onboard creates ~150-row file even when only 2-3
   fields differ from the global default.
2. Drift — when `_global_<txn>.yaml` is updated (e.g. tightening `IT104`),
   already-onboarded partners do **not** pick up the change because their
   duplicate row overrides it.

Goal: in `StepRules`, fetch the transaction tier, mark seeded rows that exactly
match the inherited row as `inherited`, render them visually distinct with an
"Override" affordance, and **omit inherited rows from the saved partner file**.
Editing any cell of an inherited row breaks inheritance (becomes a true
override).

Backend already exposes the tier:
- `GET /api/rules/transaction/<txn_type>` → `api.ruleTransaction(txnType)` in
  `portal/ui/src/api.ts:293`. Returns `{classification: [...], ignore: [...]}`.
  404s if no `_global_<txn>.yaml` exists.

`_global_810.yaml` already exists (~81 lines). Other transactions
(`_global_855.yaml`, etc.) do **not** yet exist — Step 0 below creates the
fixture needed for Step 7 testing.

## Constraints

- Follow `CLAUDE.md` strictly (minimal diff, match existing patterns, type
  hints, no refactoring).
- Data-driven — comparison key derived purely from row fields, no hardcoded
  segment/field allowlist.
- "Inherited" = exact match on **all** of: `segment`, `field`, `severity`,
  `ignore_case`, `numeric`. Any divergence → not inherited.
- Catch-all (`* / *`) row is **never** inherited — always saved.
- If the transaction tier endpoint 404s (no `_global_<txn>.yaml`), fall back to
  current behavior: every seeded row is non-inherited (i.e. saved as today).
- Flat-file (`StepRules` non-X12 branch, line 1275+) is **out of scope** — do
  not touch it.

## Plan — 7 Steps

### Step 0 — Create `_global_855.yaml` fixture

File: `config/compare_rules/_global_855.yaml` (new).

Mirror the structure of `_global_810.yaml` (same key order, same field names).
Seed with these classification rows (855 Purchase Order Acknowledgement —
plausible defaults; not exhaustive):

- `BAK / BAK01` — hard, ignore_case=false, numeric=false (PO ack code)
- `BAK / BAK02` — hard, ignore_case=false, numeric=false (ack type)
- `BAK / BAK03` — hard, ignore_case=true, numeric=false (PO number)
- `PO1 / PO102` — hard, ignore_case=false, numeric=true (qty)
- `PO1 / PO104` — hard, ignore_case=false, numeric=true (unit price)
- `CTT / CTT01` — hard, ignore_case=false, numeric=true (line count)

`ignore:` may be `[]` (universal tier already excludes envelope segments).

Also add a brief header comment matching `_global_810.yaml` style.

### Step 1 — Extend `RuleRow` interface

File: `portal/ui/src/pages/Onboard.tsx`, interface `RuleRow` (line 15-23).

Add **one** optional field:

```ts
inherited?: boolean
```

No other type changes. Existing call sites that omit `inherited` remain valid.

### Step 2 — Fetch tier and mark inherited rows

File: `portal/ui/src/pages/Onboard.tsx`, `StepRules` X12 branch (line 1255+).

After building `rows` from `wizard.x12Schema.fields.map(...)` but before the
catch-all `rows.push(...)`:

1. Try to fetch transaction-tier rules:
   ```ts
   let tierClassification: any[] = []
   try {
     const tier = await api.ruleTransaction(wizard.transactionType)
     tierClassification = tier.classification || []
   } catch {
     // 404 = no tier file; treat all rows as new
   }
   ```
   You will need to convert the `useEffect` callback to handle this async work
   — wrap in an `async` IIFE inside the effect, matching the pattern already
   used elsewhere in the file (search for `(async () => {` if uncertain;
   otherwise `.then()` chain is acceptable as long as state updates happen
   inside).

2. Build a lookup keyed by `segment|field` from the tier classification, then
   set `inherited: true` on every seeded row whose `segment`, `field`,
   `severity`, `ignore_case`, and `numeric` **all** match the tier entry. Any
   mismatch → leave `inherited` unset (treated as non-inherited).

3. The catch-all row appended after the loop must NOT be marked inherited.

### Step 3 — Break inheritance on edit

File: `portal/ui/src/pages/Onboard.tsx`, `updateRule` function (line ~1289+).

Modify so that any patch coming in clears inheritance:

```ts
const updateRule = (idx: number, patch: Partial<RuleRow>) => {
  setRules(rs => rs.map((r, i) => (i === idx ? { ...r, ...patch, inherited: false } : r)))
}
```

(Locate the existing implementation; preserve its update mechanism but inject
`inherited: false` into the merged row.)

### Step 4 — UI: badge + Override button

File: `portal/ui/src/pages/Onboard.tsx`, the rules table render inside
`StepRules`.

For each rendered row:

- If `row.inherited === true`: apply `text-gray-400` (or matching dim style
  already used in the codebase — search for existing inherited/disabled row
  styling first) to the row, render a small badge after the field name reading
  `inherited from _global_<txn>.yaml` (substitute `wizard.transactionType`),
  and add a button with text `Override` that calls
  `updateRule(idx, {})` (passing an empty patch; the modified `updateRule`
  from Step 3 still flips `inherited` to false).
- Otherwise: render exactly as today (no styling change, no badge, no button).

Do NOT change column count or table structure. Badge + button live inside an
existing cell (preferably the field-name cell). Match existing badge/button
class patterns from elsewhere in `Onboard.tsx` (e.g. `text-xs`,
`text-indigo-600`, `border rounded`).

### Step 5 — Save filter

File: `portal/ui/src/pages/Onboard.tsx`, the "Save Rules" submit handler in
`StepRules` (search for `compareUpdateRules` or the function bound to the
"Save Rules" button).

Before sending the payload, filter:

```ts
const classification = rules
  .filter(r => r.inherited !== true)
  .map(({ inherited, ...rest }) => rest)
```

Strip the `inherited` key from the payload (it is a UI-only flag, not part of
the persisted schema). Send `classification` as today.

If after filtering the classification is empty (all rows inherited and user
saved without overriding anything), the partner YAML must still be created
with at least the catch-all row so backend tier resolution can find it. (The
catch-all is non-inherited per Step 0/2, so it survives the filter — no extra
work needed.) Confirm by inspection.

### Step 6 — Typecheck

From `portal/ui/`:
```
npm run build
```
Must pass with zero TypeScript errors (the `wizard` unused-param fix from the
prior orchestration is already in place).

### Step 7 — Playwright headed E2E

Extend `portal/ui/tests/onboard-x12-855.spec.ts` (created by the prior
orchestration). Add **two** new tests inside the existing
`test.describe('X12 855 Required Segments + Severity', ...)` block:

#### Test A — Inherited rows render badge and dim styling

```ts
test('Tier rules (BAK01) appear as inherited badge in StepRules', async ({ page }) => {
  // navigate through Steps 0-2 (re-use the helper) and reach StepRules
  // ... copy the navigation+register pattern from the existing severity test ...

  const bakRow = page.locator('tr', { hasText: 'BAK01' }).first()
  await expect(bakRow).toBeVisible()
  await expect(bakRow.getByText(/inherited from _global_855\.yaml/)).toBeVisible()
  await expect(bakRow.getByRole('button', { name: 'Override' })).toBeVisible()
})
```

#### Test B — Save omits inherited rows from partner file

```ts
test('Saved partner YAML omits inherited classification rows', async ({ page }) => {
  // ... full flow through Save Rules ...

  await page.getByRole('button', { name: 'Save Rules' }).click()
  await page.waitForTimeout(3000)
  await expect(page.getByText('Trading Partner Onboarded')).toBeVisible()

  const fs = await import('fs')
  const yaml = await import('js-yaml')  // if available; otherwise text-search
  const path = join(PROJECT_ROOT, 'config', 'compare_rules', `${TEST_PROFILE}.yaml`)
  const body = fs.readFileSync(path, 'utf8')

  // Inherited rows (BAK01, PO102, CTT01 from _global_855.yaml) MUST NOT appear
  expect(body).not.toMatch(/field:\s*BAK01/)
  expect(body).not.toMatch(/field:\s*PO102/)
  expect(body).not.toMatch(/field:\s*CTT01/)

  // Catch-all MUST appear
  expect(body).toMatch(/segment:\s*['"]?\*/)
})
```

If `js-yaml` is not in `portal/ui`'s deps, use plain text/regex assertions on
the raw file body — do **not** add new dependencies.

Run:
```
cd portal/ui
npx playwright test tests/onboard-x12-855.spec.ts --headed
```

All four 855 tests (the two existing + two new) must pass. The screenshot/
trace will land in `portal/ui/test-results/`.

#### Regression — existing 810 suite

```
cd portal/ui
npx playwright test tests/x12-wizard.spec.ts
```

All 10 must still pass. `_global_810.yaml` already exists, so onboarding 810
in the existing tests will now mark some rows inherited — but the existing
assertions check field visibility and severity-option presence, not row
counts in the saved file, so they should remain green. If any test breaks,
report the failure and the assertion involved before patching.

## Testing & Confirmation

Pre-flight (before Step 7):
1. Confirm dev servers are up: `curl http://localhost:18041/api/health` and
   `curl http://localhost:15174/`. If not, start with `bash portal/dev.sh`.
2. Confirm `_global_855.yaml` is reachable through the API:
   ```
   curl http://localhost:18041/api/rules/transaction/855
   ```
   Should return the classification rows from Step 0, not 404.

Post-Step 7:
- All 4 tests in `onboard-x12-855.spec.ts` pass headed.
- All 10 tests in `x12-wizard.spec.ts` pass.
- Manual cross-check: open `http://localhost:15174/#onboard`, walk to
  StepRules for 855, visually confirm BAK01 row is dimmed with the inherited
  badge, click Override, confirm row un-dims and the badge/button disappear.
- Inspect a freshly saved partner YAML and confirm BAK01/PO102/CTT01 are
  absent and the catch-all is present.

## Deliverables

- `config/compare_rules/_global_855.yaml` (new fixture).
- Modified `portal/ui/src/pages/Onboard.tsx` (interface + `StepRules` effect +
  `updateRule` + render + save handler).
- Extended `portal/ui/tests/onboard-x12-855.spec.ts` (+2 tests).
- No backend changes. No new npm dependencies.
- Commit only after build passes and all 14 Playwright tests (4 × 855 + 10 ×
  810) pass headed/headless as appropriate.

## Out of Scope

- Universal-tier (`_universal.yaml`) inheritance — defer; universal currently
  only carries `ignore` rules, not `classification`.
- Flat-file branch of `StepRules`.
- Backend: no changes to `portal/api/routes/`, `pyedi_core/`, schema parser.
- Migration of pre-existing partner YAML files to strip newly-inherited rows.
- Universal/transaction tier authoring UI (Rules page) — separate work.
