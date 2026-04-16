# Orchestration Prompt — Portal UI: Partners Actions + Onboard Compare-Rules Lean View

## Context

Two UI defects to fix on the portal, plus Playwright coverage:

1. **Partners page (`#partners`)** — `View Rules` and `Delete` action buttons sit
   in the rightmost column. Click `View Rules` today → lands on the Rules page
   `overview` tab (no partner selected). User must then click through `Partner`
   tab and pick the partner from a dropdown.
2. **Onboard wizard StepRules (`#onboard` → Configure Rules)** — seeds **every**
   schema field. Required fields come through as `hard`, all optional fields
   get auto-classified as `soft`. Result: hundreds of rows, most of them noise.
   User wants a lean view of only hard / soft / inherited rows, and wants to
   add rules explicitly via a modal.

Companion file: `instructions/portal_ui_partners_compare_rules_tasks.md` —
contains the full task list (T1-T6), decisions table, and recon pointers.
Read it first; this prompt coordinates execution.

## Goal

- Partners table: `Actions` column becomes leftmost. `View Rules` deep-links to
  the Rules page with the partner tab active and that profile pre-selected.
- Onboard Compare-rules: render only classified rows (hard explicit, soft user-
  added, inherited from tier). Add `+ Add Rule` modal with tier selector
  (universal / transaction / partner) that writes to disk immediately on Add.
- Playwright headed coverage for new behaviors + regression on existing specs.

## Constraints

- Follow `CLAUDE.md` strictly: minimal diffs, match existing patterns, type
  hints on all new TS, no refactoring outside the changed areas.
- Data-driven. Segment and element dropdowns must come from
  `api.ruleFieldOptions(...)` or the in-memory `wizard.x12Schema` / `wizard.columns`.
  No hardcoded segment allowlists.
- No new npm dependencies.
- No backend changes. All APIs already exist (`api.compareUpdateRules`,
  `api.ruleUpdateTransaction`, `api.ruleUpdateUniversal`).
- Do not touch `Effective View` tab.
- Do not migrate pre-existing partner YAMLs. Only affect newly-seeded rules.

## Plan — 6 steps

### Step 1 — Recon (read, don't write)

Skim and confirm structure of:

- `portal/ui/src/App.tsx` — navigation / hash routing / `Page` type.
- `portal/ui/src/pages/TradingPartners.tsx` — current table layout, action
  handlers, `onNavigate` usage.
- `portal/ui/src/pages/Rules.tsx` — `selectedPartner` state, `partner` tab render,
  `normRule` normalizer, `compareUpdateRules` wiring.
- `portal/ui/src/pages/Onboard.tsx` — `StepRules` (line ~1298), rule seeding
  (lines ~1320-1378), `updateRule` helper (~1380), `groupedRules` memo (~1384),
  existing inherited-row styling (if any) from prior tier-inheritance work.
- `portal/ui/src/api.ts` — signatures of `compareUpdateRules`,
  `ruleUpdateTransaction`, `ruleUpdateUniversal`, `ruleFieldOptions`,
  `ruleTransaction`, `ruleUniversal`.
- `portal/ui/tests/onboard-x12-855.spec.ts` — helpers to reuse
  (`navigateTo855Schema`, `cleanupProfile`, `TEST_PROFILE`, `PROJECT_ROOT`).
- `portal/ui/playwright.config.ts` — baseURL + headless default.

Confirm: `_global_855.yaml` exists in `config/compare_rules/` (it was created in
the prior orchestration `onboard_x12_tier_inheritance_orchestration_prompt.md`).
If missing, Test C / Test D will have no inherited rows — **stop and report**,
do not re-create silently.

### Step 2 — Task T1: move Partners actions to leftmost column

File: `portal/ui/src/pages/TradingPartners.tsx`.

1. Reorder both `<thead>` and `<tbody>` so `Actions` is the first column. Match
   the existing `px-3 py-2.5` cell padding and drop `text-right` /
   `whitespace-nowrap` from the old actions `<td>` (they made sense when it was
   rightmost; leftmost should align with `Name` styling).
2. Keep both buttons (`View Rules` and `Delete`) together in the single leftmost
   cell; whitespace them with the existing `mr-3` pattern.
3. **Do not yet** change the `View Rules` onClick — Step 3 rewires the
   navigation contract first.

Run `npm run build` after this step to catch any accidental JSX breakage.

### Step 3 — Task T2: deep-link plumbing

Files: `portal/ui/src/App.tsx`, `portal/ui/src/pages/Rules.tsx`,
`portal/ui/src/pages/TradingPartners.tsx`.

Current `onNavigate: (page: string) => void` has no way to pass context. The
minimal extension:

1. **`App.tsx`**:
   - Extend the prop signature passed into page components to
     `onNavigate: (page: string, params?: Record<string, string>) => void`.
   - Add `const [navParams, setNavParams] = useState<Record<string, string>>({})`.
   - When `onNavigate(p, params)` is called with params, do:
     - `setPage(p as Page)`
     - `setNavParams(params ?? {})`
     - Update the URL hash to `#<page>?k=v&k=v` using `URLSearchParams`.
   - Update `getInitialPage()` and the `hashchange` listener to split on `?` and
     parse the query-string portion into `navParams`.
   - Pass `initialParams={navParams}` as a prop to `RulesPage` (only that page
     needs it for now — keep the surface area small).
2. **`Rules.tsx`**:
   - Add optional prop `initialParams?: { tab?: string; partner?: string }`.
   - In a `useEffect` watching `initialParams`, call `setTab(...)` and
     `setSelectedPartner(...)` if provided. Guard against invalid `tab` values
     (only accept the union of `Tab`).
3. **`TradingPartners.tsx`**:
   - Change `View Rules` click to
     `onNavigate('rules', { tab: 'partner', partner: p.name })`.

Compatibility: all other pages continue calling `onNavigate(page)` with no
second arg — TS `params?` keeps them valid.

Run `npm run build`. Must be zero errors.

### Step 4 — Task T3: Onboard Compare-rules lean seeding

File: `portal/ui/src/pages/Onboard.tsx`, `StepRules`.

**X12 branch (~line 1320-1364):**

1. Change the `schema.fields.map(...)` into a filter + map. Only emit a row
   when `(f.min_occurs ?? 0) >= 1 && (f.seg_min_occurs ?? 0) >= 1`. These are
   the hard / required rows.
2. After the filter+map produces `seededRows`, keep the existing tier-inheritance
   code path but extend it: iterate `tierClassification`, and for every tier row
   whose `segment|field` is **not** in the seeded set, append a row with
   `inherited: true` and the tier row's severity / flags. This surfaces
   inherited soft/hard rules that the partner has not overridden.
3. Keep the catch-all `{segment:'*', field:'*', severity:'hard', …}` append at
   the end. Catch-all is never inherited.
4. Delete the current behavior where optional fields default to
   `severity: 'soft'`. Optional fields must simply not appear unless the user
   adds them via the Step-5 modal.

**Flat-file branch (~line 1366+):**

The template from `api.onboardRulesTemplate(...)` does not expose a field-level
`min_occurs`. For flat-file:

- Filter rows where `severity === 'hard'` OR `tierMap` has an entry matching
  the row.
- If that filter is too aggressive (API returns no severity on seed, everything
  becomes hard by default), **stop and report** — do not guess. Flat-file may
  need backend plumbing before this task is feasible.

**Empty-state helper** — if `rules.length <= 1` (only catch-all), render above
the grouped table:

```tsx
<div className="mb-4 px-4 py-3 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-700">
  No required or inherited rules for this transaction. Use <strong>+ Add Rule</strong> to classify elements.
</div>
```

### Step 5 — Task T4: Add-rule modal

File: `portal/ui/src/pages/Onboard.tsx`, `StepRules`.

1. Add a `+ Add Rule` button in the same toolbar row as the existing rule-search
   input. Match button styling to existing `text-blue-600` / `px-3 py-1.5`
   patterns.
2. Modal component:
   - Local state: `modalOpen`, `modalTier ('universal'|'transaction'|'partner')`,
     `modalSegment`, `modalElement`, `modalSeverity`, `modalIgnoreCase`,
     `modalNumeric`, `modalError`, `modalSaving`.
   - Tier radio: three options. Label transaction with txn code, partner with
     profile name.
   - Segment dropdown: if `wizard.formatMode === 'x12'`, derive unique segments
     from `wizard.x12Schema.fields.map(f => f.source.split('.')[0])`. For
     flat-file, fall back to `wizard.columns.map(c => c.record_name || '*')`.
   - Element dropdown: depends on `modalSegment`. X12: filter
     `wizard.x12Schema.fields` by `source.startsWith(modalSegment + '.')` then
     `.map(f => f.name)`. Flat-file: filter `wizard.columns` by `record_name`.
   - Severity radio: `hard` / `soft` only. No `ignore`.
3. On `Add` click:
   - Build the rule object: `{segment, field, severity, ignore_case, numeric}`.
   - Tier = `partner`:
     - `setRules(prev => [...prev, newRule])` (local only; Save Rules persists).
   - Tier = `transaction`:
     - `await api.ruleTransaction(txnType)` → current
     - Append new rule to `classification`
     - `await api.ruleUpdateTransaction(txnType, {classification, ignore})`
     - On success, also add to local `rules` with `inherited: true` so the row
       renders with the inherited styling already in place.
   - Tier = `universal`:
     - Same pattern with `api.ruleUniversal()` and `api.ruleUpdateUniversal`.
   - On error: set `modalError`, do not close.
   - On success: close modal, reset fields.
4. Modal markup: match the existing inline modal pattern. If none exists in
   `Onboard.tsx` or `Rules.tsx`, use a simple `<div className="fixed inset-0
   bg-black/40 z-50 flex items-center justify-center">` backdrop + centered
   `<div className="bg-white rounded-lg shadow-lg p-6 w-[420px]">`. No portal
   needed.

### Step 6 — Task T5 + T6: build + Playwright

1. **Build**:
   ```
   cd portal/ui
   npm run build
   ```
   Zero TS errors.

2. **Dev server check**:
   ```
   curl http://localhost:18041/api/health
   curl http://localhost:15174/
   ```
   If not up: `bash portal/dev.sh` in another shell.

3. **New spec**: create `portal/ui/tests/portal-ui-partners-compare-rules.spec.ts`.
   Reuse helpers from `onboard-x12-855.spec.ts`:
   - `TEST_PROFILE`, `PROJECT_ROOT`, `cleanupProfile`, `navigateTo855Schema`.
   - Import these locally (copy-paste if needed; do not refactor the existing
     spec to extract — out of scope).

   Implement tests A-D from the task list:

   - **A** — Partners actions leftmost + deep-link. Requires at least one
     existing profile. If none exist in dev, seed one via
     `api.profileCreate` or the same python-helper pattern used for cleanup,
     then clean up in `afterEach`.
   - **B** — Delete action regression. Create a throwaway profile, delete via
     the UI, assert the row disappears.
   - **C** — Onboard compare rules shows only hard + inherited, no auto-soft.
     After reaching StepRules for 855: assert no `<tr>` contains `CUR02` with
     severity `soft` (that was the old auto-classification). Assert `BAK01`
     inherited row is visible.
   - **D** — Add-rule modal writes to disk.
     - Partner tier add: modal → segment `PO1`, element `PO103`, severity
       `soft`, `Add`. Row appears in table. Click `Save Rules`. Wait for
       success. Read `config/compare_rules/<TEST_PROFILE>.yaml` and assert
       `field: PO103` appears.
     - Transaction tier add: modal → tier `transaction`, segment `BAK`,
       element `BAK05`, severity `hard`, `Add`. Read
       `config/compare_rules/_global_855.yaml` and assert `field: BAK05`
       appears (write happened on `Add`, not on Save Rules).
     - `afterEach`: strip the `BAK05` row from `_global_855.yaml` (small python
       helper, same pattern as `cleanupProfile`) and delete the partner yaml.

4. **Regression runs** — all must pass:
   ```
   npx playwright test tests/portal-ui-partners-compare-rules.spec.ts --headed
   npx playwright test tests/onboard-x12-855.spec.ts --headed
   npx playwright test tests/onboard-multidim-match-key.spec.ts --headed
   npx playwright test tests/x12-wizard.spec.ts
   npx playwright test tests/portal-smoke.spec.ts
   ```

   If an existing spec breaks due to the lean-seeding change (e.g. a test
   asserted the presence of an auto-classified soft row), **report the
   failure and the exact assertion before patching** — do not silently
   rewrite existing assertions.

## Testing & confirmation checklist

Before declaring done:

- [ ] `npm run build` passes with zero TS errors.
- [ ] `#partners` — leftmost column is `Actions`. Click `View Rules` →
      `#rules?tab=partner&partner=<name>`, partner tab active, correct profile
      pre-selected.
- [ ] `#partners` — `Delete` still works with confirm dialog.
- [ ] `#onboard` → 855 → Configure Rules — table renders only required +
      inherited rows. No `CUR02`-style optional rows visible until user adds
      them.
- [ ] `+ Add Rule` modal opens, tier radio has three options, segment/element
      dropdowns populate from schema.
- [ ] Partner-tier add appears in table, persists on `Save Rules`.
- [ ] Transaction-tier add writes to `_global_<txn>.yaml` immediately on
      modal `Add` click.
- [ ] Universal-tier add writes to universal YAML immediately.
- [ ] All Playwright suites listed above pass.

## Deliverables

- `portal/ui/src/pages/TradingPartners.tsx` — column reorder + deep-link.
- `portal/ui/src/App.tsx` — `onNavigate(page, params?)` + hash query parsing.
- `portal/ui/src/pages/Rules.tsx` — `initialParams` prop + useEffect seeding.
- `portal/ui/src/pages/Onboard.tsx` — lean seeding + `+ Add Rule` modal + tier
  writes.
- `portal/ui/tests/portal-ui-partners-compare-rules.spec.ts` — new spec.
- No backend changes. No new deps.
- Commit only after build + all Playwright suites are green.

## Known open questions (flag before coding if blocking)

1. Flat-file seeding: `api.onboardRulesTemplate` may not surface
   required/optional info. If Step 4 flat-file branch cannot filter cleanly,
   stop and ask whether to (a) leave flat-file seeding unchanged for now or
   (b) treat every seeded row as required.
2. Deep-link hash format — decision above uses `#rules?tab=partner&partner=X`.
   If a different router convention is preferred, flag before implementing
   Step 3.
3. Modal placement — the task list assumes a local inline modal. If the
   codebase already has a shared Modal component not found during recon, use
   that instead and note the deviation.

## Out of scope

- Backend routes / `pyedi_core` changes.
- `Effective View` tab changes.
- Ignore-list editing via the new modal (classification only).
- Visual redesign of Rules page `partner` tab.
- Migration of existing partner YAMLs.
