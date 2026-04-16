# Portal UI — Partners + Onboard/Compare Rules Tasks

Paired with `instructions/portal_ui_partners_compare_rules_orchestration_prompt.md`.
Two UI behavior changes + Playwright coverage. Nothing backend.

## Context snapshot (for the fresh session)

- Partners page: `portal/ui/src/pages/TradingPartners.tsx`
- Rules page: `portal/ui/src/pages/Rules.tsx` (tabs: overview / universal / transaction / partner / effective)
- Onboard wizard StepRules: `portal/ui/src/pages/Onboard.tsx` (X12 branch ~line 1298+, flat-file branch below)
- Router / navigation: `portal/ui/src/App.tsx` (hash-based, `Page` string union, `onNavigate(page)` with no params)
- API client: `portal/ui/src/api.ts` — relevant:
  - `api.compareProfiles()`
  - `api.compareRules(profile)` / `api.compareUpdateRules(profile, {classification, ignore})`
  - `api.ruleTransaction(txnType)` / `api.ruleUpdateTransaction(txnType, {...})`
  - `api.ruleUniversal()` / `api.ruleUpdateUniversal({...})`
  - `api.ruleFieldOptions({format|transaction_type|profile})` → `{segments: [{name, label, fields:[]}]}`
- Playwright config: `portal/ui/playwright.config.ts` (`baseURL: http://localhost:15174`, `headless: false`)
- Existing specs: `portal/ui/tests/onboard-x12-855.spec.ts`, `onboard-multidim-match-key.spec.ts`, `x12-wizard.spec.ts`, `portal-smoke.spec.ts`

## Decisions captured (from clarifying Q&A)

| # | Decision |
|---|----------|
| 1 | Actions become **leftmost column** of Partners table (not sidebar). |
| 2 | **All** existing actions (`View Rules`, `Delete`) move to leftmost column. |
| 3 | `View Rules` deep-links into the **partner-specific rule file editor** (Rules page, `partner` tab, profile pre-selected). |
| 4 | Onboard Compare-rules view **hides non-classified rows entirely** — show only hard, soft, inherited. |
| 5 | Do **not** auto-classify optional fields as soft. Soft is an explicit user classification. |
| 6 | "Add" control = **modal** with segment + element + severity (hard / soft). |
| 7 | Save = **immediate write to YAML on disk** (no staged/draft mode). |
| 8 | Modal lets user pick **which tier** the new rule writes to: universal / transaction / partner. |
| 9 | Playwright **is already wired** (existing config + specs). Do not scaffold from scratch. |
| 10 | Test scope = **new behaviors + regression** on both pages. |
| 11 | File names: `portal_ui_partners_compare_rules_tasks.md` + `..._orchestration_prompt.md`. |
| 12 | **Split** — task list and orchestration prompt are separate files. |

## Task list

### T1 — Partners page: actions to leftmost column with deep-link

File: `portal/ui/src/pages/TradingPartners.tsx`.

1. Reorder `<thead>` so first column is `Actions` (label it `Actions`), followed by the existing columns in their current order (`Name`, `Trading Partner`, `Type`, `Description`, `Rules File`).
2. Reorder `<tbody>` cells to match.
3. Move action-cell text alignment: remove `text-right` and `whitespace-nowrap` from the old actions `<td>` if necessary; use default left alignment on the new leftmost cell (match the styling of the existing leftmost `Name` cell — padding `px-3 py-2.5`).
4. Change the `View Rules` click handler so it does **not** just call `onNavigate('rules')`. It must deep-link such that Rules page opens with:
   - tab = `partner`
   - `selectedPartner` = `p.name`
5. `Delete` behavior unchanged.

### T2 — App-level deep-link plumbing

Files: `portal/ui/src/App.tsx`, `portal/ui/src/pages/Rules.tsx`.

The existing `onNavigate: (page: string) => void` signature has no context channel. Extend it minimally:

1. `App.tsx`: change `onNavigate` prop signature passed into page components to `(page: string, params?: Record<string, string>) => void`. When called with params, App updates the URL hash to `#<page>?k=v&k=v` and stores the params in a new piece of state (`navParams: Record<string, string>`) which it passes into the target page as a prop.
2. `App.tsx` hash parsing: update `getInitialPage` and the `hashchange` listener to split on `?` and parse query-style params.
3. `Rules.tsx`: accept a new optional prop `initialParams?: { tab?: string, partner?: string }`. In a `useEffect`, if `initialParams.tab` is set, call `setTab(initialParams.tab as Tab)`; if `initialParams.partner` is set, call `setSelectedPartner(initialParams.partner)`.
4. `TradingPartners.tsx`: `View Rules` now calls `onNavigate('rules', { tab: 'partner', partner: p.name })`.
5. Other pages that consume `onNavigate` keep working (params optional → backwards-compatible).

### T3 — Onboard/Compare rules view: show only classified rows

File: `portal/ui/src/pages/Onboard.tsx`, `StepRules`, X12 branch (line ~1320-1378) **and** flat-file branch (~1366+).

1. **Seeding change (X12 branch):** in the `rows = schema.fields.map(...)` call, do **not** emit a row for every field. Instead:
   - Emit a row only if `(f.min_occurs ?? 0) >= 1 && (f.seg_min_occurs ?? 0) >= 1` (hard, required at both field + segment level).
   - After the map, still run the tier-inheritance pass: for every tier row whose `segment|field` is **not** already in the seeded set, append it as an `inherited: true` row. (This surfaces inherited rules the partner did not explicitly override; aligns with existing tier-inheritance logic.)
   - Keep the catch-all `{segment:'*', field:'*', severity:'hard', …}` at the end.
   - Do not silently auto-classify anything as soft.
2. **Seeding change (flat-file branch):** apply the analogous filter. The template from `api.onboardRulesTemplate` currently returns all columns; filter to rows where `severity === 'hard'` OR the row matches an inherited tier rule. (If the flat-file template API does not indicate required vs optional, document that as a gap in the orchestration prompt — do not guess.)
3. **Grouped render:** the existing `groupedRules` memo already groups by `record_name`. It will naturally show only the filtered rows. No render changes needed.
4. **Empty state:** if after filtering there is exactly one row (the catch-all), the grouped view will look empty. Add a brief neutral-styled helper above the table when `rules.length <= 1`: "No required or inherited rules for this transaction. Use **+ Add Rule** to classify elements."

### T4 — Add-rule modal with tier selector

File: `portal/ui/src/pages/Onboard.tsx`, `StepRules`.

1. Add a `+ Add Rule` button near the existing rule-search input (top of the rules table). Button opens a modal.
2. Modal fields:
   - **Tier** — radio group: `universal` / `transaction (<txnType>)` / `partner (<profileName>)`. Default `partner`.
   - **Segment** — dropdown populated from `wizard.x12Schema.fields` (unique segment codes) or from `wizard.columns` in flat-file mode.
   - **Element** — dropdown scoped to the selected segment; empty until segment chosen.
   - **Severity** — radio group: `hard` / `soft`. Default `hard`. (No `ignore` here — that belongs to the ignore list.)
   - `ignore_case` checkbox, default off.
   - `numeric` checkbox, default off.
3. Modal actions: `Cancel` / `Add`.
4. On `Add`:
   - If tier = `partner`: append to local `rules` state as a non-inherited row. It will be persisted on the existing `Save Rules` click via `api.compareUpdateRules`.
   - If tier = `transaction`: call `api.ruleTransaction(txnType)` to fetch current tier rules, append the new rule, then `api.ruleUpdateTransaction(txnType, {classification, ignore})` to persist immediately. On success, also seed the row into local `rules` as `inherited: true` so it renders consistently with other tier-inherited rows.
   - If tier = `universal`: same pattern with `api.ruleUniversal()` + `api.ruleUpdateUniversal(...)`. Also seed locally as `inherited: true`.
   - Close modal on success; surface error text inside the modal on failure; do not close on error.
5. Do **not** add a new npm dependency. Use the same inline modal pattern already present elsewhere in `Onboard.tsx` or `Rules.tsx` (plain `<div>` with backdrop + fixed positioning). Match existing class styles (`rounded-lg`, `shadow`, `bg-white`).

### T5 — Typecheck + build

```
cd portal/ui
npm run build
```

Must pass with zero TypeScript errors.

### T6 — Playwright headed coverage

File: **new** `portal/ui/tests/portal-ui-partners-compare-rules.spec.ts`.

Required tests (all must run headed per existing config default):

**Test A — Partners actions leftmost and deep-link**
1. `page.goto('/#partners')`.
2. Assert the first `<th>` text is `Actions`.
3. Click the `View Rules` button on the first row.
4. Assert URL hash starts with `#rules` and contains `partner=`.
5. Assert the Rules page `Partner` tab is active (visible heading `Partner Rules`).
6. Assert the partner selector `<select>` has a non-empty value matching the partner from step 3.

**Test B — Partners Delete action remains functional (regression)**
1. Navigate to `#partners`.
2. Seed a throwaway profile via a python helper (same pattern as `onboard-x12-855.spec.ts` `cleanupProfile`, but reversed — create it).
3. Click `Delete` on that row (accept the `window.confirm` dialog with `page.on('dialog', d => d.accept())`).
4. Assert the row is gone.
5. Cleanup in `afterEach`.

**Test C — Onboard compare rules hides non-classified, shows inherited**
1. Navigate through the X12 855 onboard flow (reuse `navigateTo855Schema` helper pattern from `onboard-x12-855.spec.ts`).
2. Register partner, advance to StepRules.
3. Assert the rules table does **not** contain an optional element (e.g. `CUR02` or any `REF` child) rendered with `severity: soft` from auto-classification.
4. Assert at least one inherited row is visible (expect `_global_855.yaml` seeds like `BAK01`).

**Test D — Add-rule modal writes to the selected tier**
1. From StepRules, click `+ Add Rule`.
2. In the modal, choose tier `partner`, segment (e.g. `PO1`), element `PO103`, severity `soft`, click `Add`.
3. Assert the row appears in the table with severity `soft`.
4. Click `Save Rules`, then inspect `config/compare_rules/<profile>.yaml` on disk — the new row must be present.
5. Second modal pass: choose tier `transaction`, segment `BAK`, element `BAK05`, severity `hard`, `Add`. Assert `_global_855.yaml` on disk contains `BAK05` after the modal closes.
6. Cleanup both files in `afterEach`.

**Test E — Regression: existing 855 severity test still passes**
- Run `portal/ui/tests/onboard-x12-855.spec.ts` — all four tests must still pass. The new filter (hide non-classified) may affect any test that asserts a specific soft row's presence; if a breakage occurs, the orchestration must either update the test to match new behavior or revert-and-flag.

Run commands:

```
cd portal/ui
npx playwright test tests/portal-ui-partners-compare-rules.spec.ts --headed
npx playwright test tests/onboard-x12-855.spec.ts --headed
npx playwright test tests/x12-wizard.spec.ts
```

All must be green before commit.

## Out of scope

- Backend (`portal/api/`, `pyedi_core/`) — no changes.
- `Effective View` tab on Rules page.
- Ignore list editing via the Onboard modal (classification only).
- Migration of already-onboarded partner YAMLs.
- New npm dependencies.
- Styling overhauls beyond what's required to reorder columns.
