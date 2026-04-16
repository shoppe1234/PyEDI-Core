# Orchestration Prompt — Fix X12 Onboard "Everything Mandatory" Bug

## Context

Portal Onboard wizard (`http://localhost:15174/#onboard`) currently treats every
segment and every element of an X12 transaction (reproduced with 4010 855) as
mandatory / hard-error. Two root causes in `portal/ui/src/pages/Onboard.tsx`:

- **Bug 1** — Line 627-628: label "Required Segments" renders `schema.segments`,
  which is built by `convertStandardSchema` (line 333-373) by pushing **every**
  segment in `std.areas` regardless of `min_occurs`. Cardinality never consulted.
- **Bug 2** — Line 1257-1268: `StepRules` seeds every `RuleRow` with
  `severity: 'hard'` unconditionally. No derivation from element / segment
  `min_occurs`. Also, `X12Field` (see `portal/ui/src/api.ts:33-43`) does not
  carry `min_occurs` at all — `convertStandardSchema` drops it at line 357-361.

Backend (`pyedi_core/standards_parser.py` `_parse_cardinality`, line 101-108)
and API response (`portal/api/routes/onboard.py:289-294`) correctly expose
`min_occurs` / `max_occurs`. Fix is purely frontend.

Git history: `Onboard.tsx` last modified 2026-04-03. No commits in last 48h
touch this path. This is a pre-existing defect, not a 24h regression.

## Constraints

- Follow `CLAUDE.md` coding standards strictly (minimal diff, match existing
  patterns, type hints where applicable, no refactoring, no new patterns).
- Data-driven — no hardcoded segment/element lists. Derive severity from
  `min_occurs` only.
- X12 semantics: `min_occurs >= 1` → Mandatory → `severity: 'hard'`;
  `min_occurs == 0` → Optional → `severity: 'soft'`.
- An element is only "hard" if **both** its containing segment is required
  **and** the element itself is required (`seg.min_occurs >= 1 && elem.min_occurs >= 1`).

## Plan — 4 Steps

### Step 1 — Extend `X12Field` interface

File: `portal/ui/src/api.ts`

Add two optional numeric fields to the `X12Field` type:

- `min_occurs?: number` — the element's own min_occurs
- `seg_min_occurs?: number` — the parent segment's min_occurs

Do not change any other types. Do not change anything that currently consumes
`X12Field` elsewhere (they remain valid because the fields are optional).

### Step 2 — Populate cardinality in `convertStandardSchema`

File: `portal/ui/src/pages/Onboard.tsx`, function `convertStandardSchema`
(line 333-373).

- Build a `segMinOccurs: Record<string, number>` map from `std.areas` by
  walking every `SegmentRef` (including nested `children`) and recording
  `ref.min_occurs` keyed by segment code. If a segment appears multiple times,
  keep the max (effectively: required if any occurrence is required).
- Change the `segments` list so it includes **only** segment codes whose
  `segMinOccurs >= 1`. Preserve declaration order (do not sort).
- When emitting `X12Field` rows (line 357-361), set:
  - `min_occurs: elem.min_occurs`
  - `seg_min_occurs: segMinOccurs[segCode] ?? 0`

Do not change the `fields` ordering or any other shape. All previously-emitted
fields continue to appear (the fields table still shows everything — only the
"Required Segments" string shrinks).

### Step 3 — Verify "Required Segments" render

File: `portal/ui/src/pages/Onboard.tsx`, line 627-628.

No code change expected — the existing `{schema.segments.join(', ')}` now
reflects the filtered list from Step 2. Confirm the label still reads
"Required Segments".

### Step 4 — Derive `severity` in `StepRules`

File: `portal/ui/src/pages/Onboard.tsx`, `StepRules` effect (line 1257-1268).

Replace the hardcoded `severity: 'hard'` in the `.map` callback with:

```ts
severity:
  (f.min_occurs ?? 0) >= 1 && (f.seg_min_occurs ?? 0) >= 1 ? 'hard' : 'soft',
```

Leave the catch-all row (line 1270) at `severity: 'hard'` — unchanged.

Do not touch the flat-file branch (line 1275+) — only the X12 seed path.

## Testing & Confirmation

After all four code changes:

1. **Typecheck / build** — from `portal/ui/`:
   ```
   npm run build
   ```
   Must pass with zero TypeScript errors.

2. **Start dev servers** (two terminals):
   - API: from repo root, launch the portal API on `:18042` per
     `project_portal_architecture.md` (2-port dev setup).
   - UI: `cd portal/ui && npm run dev` (Vite on `:15174`).

3. **Playwright CLI headed smoke test** — required confirmation step.

   From repo root run:
   ```
   npx playwright test --headed --project=chromium
   ```
   if a Playwright suite exists under `portal/ui/` or `tests/e2e/`. If no
   suite exists, create a minimal ad-hoc script at
   `portal/ui/tests/onboard-x12-855.spec.ts` that:

   - Navigates to `http://localhost:15174/#onboard`
   - Selects standard X12, version 4010, transaction `855`
   - Clicks "Review Schema"
   - Asserts the "Required Segments" `<dd>` text includes `ST, BAK, PO1, CTT, SE`
     (all `min_occurs >= 1` in the stock 004010/855 schema) and does **NOT**
     include `CUR, REF, PER, TAX, FOB, CTP, PAM, CSH, SAC, ITD, DIS, INC, DTM,
     LDT, SI, PID, MEA, PWK, PKG, TD1, TD5, TD3, TD4, MAN, TXI, CTB, N9, MSG,
     N1, N2, N3, N4, NX2, ADV, MTX, PO3, PO4, IT8, SDQ, AMT` (all optional at
     the root level).
   - Advances to Step 3 "Configure Rules" and asserts that at least one rule
     row in an optional segment (e.g. `CUR`, `PER`, `N9`) has
     `severity === 'soft'`, and that mandatory-segment/mandatory-element rows
     (e.g. `ST01`, `BAK01`, `BAK02`, `PO101`, `CTT01`, `SE01`) have
     `severity === 'hard'`.

   Run with `--headed` so the reviewer can visually confirm the wizard
   renders correctly:
   ```
   npx playwright test portal/ui/tests/onboard-x12-855.spec.ts --headed --project=chromium
   ```

   Must pass. Screenshot or video trace is saved to `test-results/` on pass
   and on failure.

4. **Manual cross-check** — with the UI still running headed, load a second
   transaction known to have different required-segment sets (e.g. 4010 810,
   4010 850) and eyeball that the "Required Segments" list differs per
   transaction and is no longer the full segment enumeration.

5. **Regression** — from `portal/ui/` run the existing unit test suite if
   present:
   ```
   npm test
   ```
   Must not introduce any new failures.

## Deliverables

- Minimal diff across exactly two files: `portal/ui/src/api.ts` and
  `portal/ui/src/pages/Onboard.tsx`.
- Playwright spec file (new) at `portal/ui/tests/onboard-x12-855.spec.ts`
  **only if** no existing equivalent suite is present.
- No changes to backend, no changes to `pyedi_core/`, no changes to schema
  data files.
- Commit only after all four steps pass the Playwright `--headed` run.
