# PyEDI Portal — UI Design Specification

**Date:** 2026-03-26
**Status:** Living document. Every item tagged `[EXISTS]` or `[SPEC]` to distinguish implementation from specification.

---

## 1. Overview and Scope

This is the dedicated portal UI design specification for the PyEDI Portal (`./portal/`). It is the single source of truth for all portal UI decisions — design tokens, component inventory, page wireframes, user flows, accessibility, and responsive behavior.

**What this document is:** A synthesis of portal UI specifications scattered across 11 source documents, reconciled against the actual implementation.

**What this document is not:** Not a backend architecture doc (see `instructions/pyedi_portal_plan.md`), not an execution guide (see `instructions/portal_orchestration_prompt.md`), not a system specification (see `SPECIFICATION.md`).

### Source Document Cross-Reference

| # | Document | Portal UI Contribution |
|---|----------|----------------------|
| S1 | `instructions/pyedi_portal_plan.md` | ASCII wireframes (4 pages), endpoint tables, tech stack, 7 invariants |
| S2 | `instructions/portal_orchestration_prompt.md` | Phase gates, execution rules |
| S3 | `instructions/compare_orchestration_prompt.md` | Compare page spec, 9 compare endpoints, rules editor |
| S4 | `instructions/compare_integration_plan.md` | Compare engine integration details |
| S5 | `PROJECT_INTENT.md` | Portal parity requirement, target users |
| S6 | `SPECIFICATION.md` | REST API contracts, concurrency model |
| S7 | `sqlLiteReport.md` | 10 gaps with portal implications (error discovery, reclassification, reporting) |
| S8 | `TODO.md` | Open portal items (react-router, file upload, manifest page, auth, config editing) |
| S9 | `README.md` | Architecture tree, project assessment |
| S10 | `REVIEW_REPORT.md` | Bevager refactoring, build status |
| S11 | `BeveragerTaskList.md` | First trading partner onboarding flow |

### Target Users (source: S5)

- **Operations teams** — processing batch EDI files, reviewing results, triaging failures
- **Integration engineers** — onboarding new trading partners, validating DSL schemas, tuning compare rules
- **Developers** — inspecting configuration, running test harnesses, debugging pipeline output

---

## 2. Architecture Summary (sources: S1, S6, `package.json`, `App.tsx`)

### Tech Stack

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Framework | React | 19.2.4 | S1 planned React 18 — implementation uses 19 |
| Language | TypeScript | 5.9.3 | |
| Styling | Tailwind CSS | 4.2.2 | CSS-based config (`@import "tailwindcss"`), no `tailwind.config.js` |
| Bundler | Vite | 8.0.1 | `@tailwindcss/vite` plugin |
| Linting | ESLint | 9.39.4 | With `react-hooks` and `react-refresh` plugins |

### Layout `[EXISTS]`

```
+------------------+--------------------------------------------+
|  Sidebar (w-56)  |  Main Content (flex-1, overflow-auto, p-6) |
|  bg-gray-900     |  bg-gray-50                                |
|  text-gray-200   |                                            |
|                  |  <Page Component />                        |
|  [Logo]          |                                            |
|  [Nav Items]     |                                            |
|                  |                                            |
|  [Health Status] |                                            |
+------------------+--------------------------------------------+
```

- **Sidebar:** Fixed `w-56`, dark theme. Logo ("PyEDI Portal"), 6 nav buttons, health indicator at bottom.
- **Main:** `flex-1 overflow-auto p-6` on `bg-gray-50`. Conditional page rendering via `useState<Page>`.
- **Routing:** Manual `useState<Page>` — no `react-router-dom`. No URL-based navigation, no deep linking, no browser back/forward. `[SPEC]` react-router-dom replacement is tracked in `TODO.md`.
- **API Client:** `api.ts` with 21 methods wrapping `fetch()`. All responses typed as `any`. No TanStack Query or SWR.

### Notable Absences vs Plan (S1)

| Planned | Actual | Impact |
|---------|--------|--------|
| `react-router-dom` | `useState<Page>` | No deep links, browser history broken |
| TanStack Query | Raw `fetch` + `useState` | No caching, no background refetch, no loading/error states |
| Typed API responses | All `any` | No IDE autocomplete, no compile-time safety |
| `src/components/` directory | Components inline in page files | No reuse, duplication |

---

## 3. Design Tokens and Visual Language (sources: all `.tsx` files)

Extracted from actual Tailwind class usage across all portal files. These are the canonical values.

### Colors

| Token | Tailwind Class | Usage |
|-------|---------------|-------|
| **Surface / Primary** | `bg-gray-900` | Sidebar background |
| **Surface / Main** | `bg-gray-50` | Main content background |
| **Surface / Card** | `bg-white` | Cards, panels, tables |
| **Surface / Table Header** | `bg-gray-50` | Table header rows, section headers |
| **Text / Primary** | `text-gray-900` | Body text |
| **Text / Secondary** | `text-gray-500` | Labels, metadata, section headers |
| **Text / Muted** | `text-gray-400` | Placeholders, empty states |
| **Text / Sidebar** | `text-gray-200` | Sidebar nav text |
| **Text / Brand** | `text-white` | Sidebar logo, active nav |
| **Interactive / Primary** | `bg-blue-600` | Primary action buttons |
| **Interactive / Primary Hover** | `bg-blue-700` | Button hover state |
| **Interactive / Confirm** | `bg-green-600` | Save/confirm buttons |
| **Interactive / Selected** | `bg-blue-50` | Selected table rows |
| **Interactive / Disabled** | `opacity-50` | Disabled buttons |
| **Status / Success** | `bg-green-100 text-green-800` | SUCCESS, MATCH, PASS badges |
| **Status / Success Text** | `text-green-600` | Success stat values, match counts |
| **Status / Error** | `bg-red-100 text-red-800` | FAILED, MISMATCH, FAIL, hard badges |
| **Status / Error Text** | `text-red-600` | Failed stat values, mismatch counts |
| **Status / Warning** | `bg-yellow-100 text-yellow-800` | SKIPPED, WARN, UNMATCHED, soft badges |
| **Status / Warning Text** | `text-yellow-600` | Skipped/warned stat values |
| **Status / Neutral** | `bg-gray-100 text-gray-600` | ignore badges, unknown status fallback |
| **Danger / Banner** | `bg-red-50 border-red-200 text-red-700` | Error messages |
| **Warning / Banner** | `bg-yellow-50 text-yellow-800` | Type warnings |

### Typography

| Token | Tailwind Classes | Usage |
|-------|-----------------|-------|
| **Page Title** | `text-2xl font-bold` | H1 on each page |
| **Section Header** | `font-semibold text-sm text-gray-500 uppercase` | Panel headers |
| **Card Title** | `font-semibold mb-2` | Card section headers |
| **Body** | `text-sm` | Default text size |
| **Label** | `text-xs text-gray-500` | Form labels, metadata |
| **Monospace** | `font-mono text-xs` | Filenames, field names, code values |
| **Stat Value** | `text-3xl font-bold` | Dashboard stat cards |
| **Stat Value (small)** | `text-xl font-bold` | Test results summary |
| **Brand** | `text-lg font-bold tracking-tight text-white` | Sidebar logo |

### Spacing

| Token | Tailwind Class | Usage |
|-------|---------------|-------|
| **Card Padding** | `p-4` | Card/panel internal padding |
| **Main Padding** | `p-6` | Main content area |
| **Section Margin** | `mb-4` | Between page sections |
| **Grid Gap** | `gap-4` | Grid and flex gaps |
| **Table Cell** | `px-3 py-2` or `px-2 py-1` | Table padding |
| **Badge Padding** | `px-2 py-0.5` | Status badges |
| **Button Padding** | `px-4 py-1.5` | Action buttons |

### Surfaces

| Token | Tailwind Classes | Usage |
|-------|-----------------|-------|
| **Card** | `bg-white rounded-lg shadow` | All content panels |
| **Badge** | `rounded text-xs font-medium` | Status indicators |
| **Input** | `border rounded px-3 py-1.5 text-sm` | Text inputs, selects |
| **Button / Primary** | `bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50` | Primary actions |
| **Button / Secondary** | `border border-gray-300 rounded text-sm hover:bg-gray-50` | Secondary actions |
| **Table Row** | `border-t` | Row separator |
| **Table Row / Active** | `cursor-pointer hover:bg-blue-50` | Clickable rows |

---

## 4. Component Inventory (sources: all `.tsx` files, S1)

### Existing Components `[EXISTS]`

| Component | File | Props | Notes |
|-----------|------|-------|-------|
| **StatCard** | Dashboard.tsx | `{ label: string, value: number, color?: string }` | 4-card grid for manifest stats |
| **StatusBadge** (Pipeline) | Pipeline.tsx | `{ status: string }` | Handles: SUCCESS, FAILED, fallback to gray |
| **StatusBadge** (Tests) | Tests.tsx | `{ status: string }` | Inline, not extracted. Handles: PASS, FAIL, fallback to yellow |
| **StatusBadge** (Compare) | Compare.tsx | `{ status: string }` | Record-based color map. Handles: MATCH, MISMATCH, UNMATCHED, hard, soft, ignore |
| **SummaryCard** | Validate.tsx | `{ result: any }` | Compilation summary (transaction type, path, columns, records) |
| **TypeWarnings** | Validate.tsx | `{ warnings: any[] }` | Yellow banner with type mismatch list |
| **CoverageCard** | Validate.tsx | `{ coverage: any }` | Progress bar + source/target field counts |
| **ColumnsTable** | Validate.tsx | `{ columns: any[] }` | Scrollable table with name, type, DSL type, record, OK |
| **ErrorBanner** | Compare.tsx (inline) | — | Red `bg-red-50 border-red-200` with dismiss button. Pattern repeated in Validate.tsx without dismiss. |

**Key finding:** `StatusBadge` is defined 3 separate times with different color maps. This is the most urgent extraction candidate. A canonical shared component should handle all 12 status strings: SUCCESS, FAILED, SKIPPED, PASS, FAIL, WARN, MATCH, MISMATCH, UNMATCHED, hard, soft, ignore.

### Planned Components `[SPEC]`

| Component | Source | Description |
|-----------|--------|-------------|
| **CollapsiblePanel** | S1 | Expandable panel for YAML preview, DSL source, error details |
| **DataTable** (sortable) | S1 | Reusable sortable table with column headers |
| **FileUpload** (drag-and-drop) | S1 | Drag-and-drop upload zone. Currently raw `<input type="file">` |
| **JsonPreview** (syntax-highlighted) | S1 | Syntax-highlighted JSON viewer. Currently raw `<pre>` |
| **Shared StatusBadge** | This spec | Unified color map, extracted to `src/components/StatusBadge.tsx` |
| **Shared ErrorBanner** | This spec | Dismissable error display with consistent styling |

---

## 5. Page Specifications (sources: S1, S3, S7, S8, all page `.tsx` files)

### 5.1 Dashboard `[EXISTS]`

**Data Sources:** `api.manifestStats()`, `api.manifestEntries(10)`

**Wireframe:**

```
+------------------------------------------------------------------+
| Dashboard                                                         |
+------------------------------------------------------------------+
| +------------+ +------------+ +------------+ +------------+       |
| | Total      | | Success    | | Failed     | | Skipped    |       |
| |   247      | |   203      | |    12      | |    32      |       |
| +------------+ +------------+ +------------+ +------------+       |
|                                                                   |
| +--------------------------------------------------------------+ |
| | Recent Processing                                             | |
| +--------------------------------------------------------------+ |
| | invoice_batch.csv                          SUCCESS             | |
| | PO_850_001.x12                             FAILED              | |
| | vendor_xml.xml                             SUCCESS             | |
| | ...                                                            | |
| +--------------------------------------------------------------+ |
+------------------------------------------------------------------+
```

**Missing:**
- No error rate trend or time-series chart
- No link from recent entries to Pipeline detail
- Empty state when manifest has no entries

### 5.2 Validate `[EXISTS]`

**Data Sources:** `api.validate()`, `api.validateUpload()`

**Wireframe:**

```
+------------------------------------------------------------------+
| Schema Validation                                                 |
+------------------------------------------------------------------+
| +--------------------------------------------------------------+ |
| | BY PATH                                                       | |
| | [DSL file path___________] [Sample file path (optional)____]  | |
| |                                                                | |
| | OR UPLOAD                                                      | |
| | [Choose file...] [Choose file...]                              | |
| |                                                                | |
| | [Validate]                                                     | |
| +--------------------------------------------------------------+ |
|                                                                   |
| +--------------------------------------------------------------+ |
| | Compilation Summary                                            | |
| | Transaction Type: 810   |  Compiled To: schemas/compiled/...   | |
| | Columns: 18             |  Records: Header, Details, Summary   | |
| +--------------------------------------------------------------+ |
|                                                                   |
| +--------------------------------------------------------------+ |
| | Type Warnings (3)                                  [yellow bg] | |
| | CaseSize (Details): Decimal -> string                          | |
| | CasePrice (Details): Decimal -> string                         | |
| +--------------------------------------------------------------+ |
|                                                                   |
| +--------------------------------------------------------------+ |
| | Coverage                                                       | |
| | [=============================------] 78.5%                    | |
| | Source: 14/18 mapped  |  Target: 11/14 populated               | |
| +--------------------------------------------------------------+ |
|                                                                   |
| +--------------------------------------------------------------+ |
| | Schema Columns                                     [scrollable]| |
| | Name          | Type    | DSL Type | Record  | OK              | |
| | InvoiceID     | integer | Integer  | Header  | check           | |
| | InvoiceDate   | string  | String   | Header  | check           | |
| | ...                                                             | |
| +--------------------------------------------------------------+ |
+------------------------------------------------------------------+
```

**Implemented vs Plan (S1):**

| S1 Feature | Status | Notes |
|------------|--------|-------|
| Path-based validation | `[EXISTS]` | |
| File upload | `[EXISTS]` | Raw `<input type="file">`, not drag-and-drop |
| Compilation summary | `[EXISTS]` | |
| Type warnings | `[EXISTS]` | |
| Coverage bar | `[EXISTS]` | Only shown when sample file provided |
| Columns table | `[EXISTS]` | |
| Collapsible YAML preview | `[SPEC]` | Not built |
| Collapsible DSL source preview | `[SPEC]` | Not built |
| Field trace table | `[SPEC]` | Not built — S1 specified first 3 rows with expand |

### 5.3 Pipeline `[PARTIAL]`

**Data Sources:** `api.pipelineResults()`

**Wireframe (current):**

```
+------------------------------------------------------------------+
| Pipeline Results                                                  |
+------------------------------------------------------------------+
| +--------------------------------------------------------------+ |
| | File                     | Status      | Modified             | |
| +--------------------------------------------------------------+ |
| | invoice_batch.csv        | [SUCCESS]   | 3/26/2026 8:00 AM    | |
| | PO_850_001.x12           | [FAILED]    | 3/26/2026 7:45 AM    | |
| | ...                                                            | |
| +--------------------------------------------------------------+ |
+------------------------------------------------------------------+
```

**Wireframe (planned — S1):**

```
+------------------------------------------------------------------+
| Pipeline                                                          |
+------------------------------------------------------------------+
| +--------------------------------------------------------------+ |
| | [Upload File(s)] [x Dry Run] [ Process ]                      | |
| +--------------------------------------------------------------+ |
|                                                                   |
| +--------------------------------------------------------------+ |
| | Recent Results                             [auto-refresh 10s] | |
| | File         | Status      | Type | Time   | Actions          | |
| | invoice.csv  | [SUCCESS]   | CSV  | 120ms  | [View]           | |
| | PO_850.x12   | [FAILED]    | X12  | 45ms   | [Triage]         | |
| +--------------------------------------------------------------+ |
|                                                                   |
| +--------------------------------------------------------------+ |
| | Failure Detail (expanded from [Triage])                        | |
| | Stage: VALIDATION  | Error: Missing required field             | |
| | Correlation ID: abc-123                                        | |
| | [> error.json]  [> Source File]                                | |
| +--------------------------------------------------------------+ |
|                                                                   |
| | Batch Summary: 10 total | 8 success | 1 failed | 1 skipped    | |
+------------------------------------------------------------------+
```

**Missing:**

| Feature | Source | Status |
|---------|--------|--------|
| File upload (drag-and-drop) | S1, S8 | `[SPEC]` — backend `POST /api/pipeline/upload` exists, UI not wired |
| Dry-run toggle | S1 | `[SPEC]` |
| Pipeline run trigger | S1 | `[SPEC]` — `api.pipelineRun()` exists but no UI button |
| Failure triage detail | S1 | `[SPEC]` |
| Auto-refresh polling | S1 | `[SPEC]` |
| Batch summary row | S1 | `[SPEC]` |
| Processing time column | S1 | `[SPEC]` |
| Transaction type column | S1 | `[SPEC]` |

### 5.4 Tests `[EXISTS]`

**Data Sources:** `api.testCases()`, `api.testRun()`

**Wireframe:**

```
+------------------------------------------------------------------+
| Test Harness                                      [Run Tests]     |
+------------------------------------------------------------------+
| +--------------------------------------------------------------+ |
| | Total      | Passed      | Failed      | Warned               | |
| |   9        |   8         |   0         |   1                  | |
| +--------------------------------------------------------------+ |
|                                                                   |
| | [PASS] UnivT701 Demo Invoice CSV                               |
| | [PASS] MarginEdge 810 Text File                                |
| | [WARN] x12 Data Comparison (non-fatal discrepancies)           |
| | ...                                                            |
|                                                                   |
| +--------------------------------------------------------------+ |
| | Test Cases (9)                                                 | |
| | UnivT701 Demo Invoice CSV                                     | |
| |   inputs/UnivT701_small.csv                                   | |
| | ...                                                            | |
| +--------------------------------------------------------------+ |
+------------------------------------------------------------------+
```

**Missing:**

| Feature | Source | Status |
|---------|--------|--------|
| Generate Expected button | S1 | `[SPEC]` — `api.testRun()` exists but no Generate Expected UI |
| Verify Environment button | S1 | `[SPEC]` — `api.testVerify()` exists but no UI button |
| Environment details panel | S1 | `[SPEC]` |

### 5.5 Compare `[EXISTS]`

**Data Sources:** `api.compareProfiles()`, `api.compareRun()`, `api.compareRuns()`, `api.comparePairs()`, `api.compareDiffs()`, `api.compareRules()`, `api.compareUpdateRules()`, `api.compareExportUrl()`

**Wireframe:**

```
+------------------------------------------------------------------+
| Compare                                                           |
+------------------------------------------------------------------+
| +--------------------------------------------------------------+ |
| | NEW COMPARISON                                                 | |
| | Profile [Select...v] Source Dir [________] Target Dir [______] | |
| |                                                                | |
| | bevager_810 - Bevager 810 Invoice flat file comparison         | |
| | Match: json_path:header.InvoiceID | Qualifiers: none           | |
| |                                                                | |
| | [Run Comparison] [Edit Rules] [Export CSV]                     | |
| +--------------------------------------------------------------+ |
|                                                                   |
| +--------------------------------------------------------------+ |
| | RULES: bevager_810                                     [x]    | |
| | +----------------------------------------------------------+ | |
| | | {                                                         | | |
| | |   "classification": [...],                                | | |
| | |   "ignore": [...]                                         | | |
| | | }                                                         | | |
| | +----------------------------------------------------------+ | |
| | [Save Rules]                                                   | |
| +--------------------------------------------------------------+ |
|                                                                   |
| +--------------------------------------------------------------+ |
| | RUN HISTORY                                                    | |
| | Run # | Date              | Profile      | Pairs | M | D | U | |
| | 34    | 2026-03-26T16:19  | bevager_810  | 22    | 2 |20 | 0 | |
| | 33    | 2026-03-26T16:18  | bevager_810  | 22    | 2 |20 | 0 | |
| +--------------------------------------------------------------+ |
|                                                                   |
| +--------------------------------------------------------------+ |
| | RUN #34 -- PAIRS                   [All][MATCH][MISMATCH][UN] | |
| | Source File         | Target File       | Value    | St | Diffs| |
| | InvoiceID_903..json | InvoiceID_903.json| 9033..   | MM | 14   | |
| | InvoiceID_200..json | InvoiceID_200.json| 2003..   | MA |  0   | |
| +--------------------------------------------------------------+ |
|                                                                   |
| +--------------------------------------------------------------+ |
| | DIFFS -- 9033674514                                            | |
| | Segment  | Field    | Severity | Source     | Target | Desc   | |
| | line_0   | DueDate  | [hard]   | 04/24/2026 | nan    | Con... | |
| | line_0   | Taxes    | [hard]   | 2.03       | 0      | Con... | |
| +--------------------------------------------------------------+ |
+------------------------------------------------------------------+
```

**This page had no wireframe in any prior spec document.** The above is the first formal wireframe, based on the actual implementation. The compare page was added via S3/S4, not the original portal plan (S1).

### 5.6 Config `[PARTIAL]`

**Data Sources:** `api.config()`

**Wireframe (current):**

```
+------------------------------------------------------------------+
| Configuration                                                     |
+------------------------------------------------------------------+
| +--------------------------------------------------------------+ |
| | {                                                              | |
| |   "system": { ... },                                          | |
| |   "observability": { ... },                                   | |
| |   "directories": { ... },                                     | |
| |   "transaction_registry": { ... },                            | |
| |   "csv_schema_registry": { ... },                             | |
| |   "compare": { ... }                                          | |
| | }                                                              | |
| +--------------------------------------------------------------+ |
+------------------------------------------------------------------+
```

**Missing:**

| Feature | Source | Status |
|---------|--------|--------|
| Structured display by section | S1 | `[SPEC]` — currently raw JSON dump |
| Inline editing for csv_schema_registry | S8 | `[SPEC]` — `PUT /api/config/registry/{entry_name}` exists |
| Syntax-highlighted JSON | S1 | `[SPEC]` — currently raw `<pre>` |

---

## 6. User Flow Diagrams (sources: S1, S3, S7, S11)

### 6.1 Validate Workflow

```
[Select DSL source]          [Optionally select sample file]
   |-- By path: enter path       |-- By path: enter path
   |-- By upload: choose file    |-- By upload: choose file
   v                             v
[Click "Validate"] -----> API: POST /api/validate or /api/validate/upload
   |
   v
[View Compilation Summary] -- transaction type, compiled path, column count
   |
   +-- [Inspect Type Warnings] -- fields with type mismatches (yellow)
   |
   +-- [View Coverage] -- coverage %, source/target field counts (if sample)
   |
   +-- [Browse Columns Table] -- scrollable, sortable by name/type/record
```

### 6.2 Pipeline Workflow `[SPEC]`

```
[Upload file(s)]       [Toggle dry-run]
   |                      |
   v                      v
[Click "Process"] -----> API: POST /api/pipeline/run or /upload
   |
   v
[View Results Table] -- auto-refresh every 10s
   |
   +-- SUCCESS: view output path
   |
   +-- FAILED: [Click "Triage"]
         |
         v
       [View Failure Detail] -- stage, error, correlation ID
         |
         +-- [Expand error.json]
         +-- [View source file]
```

### 6.3 Compare Workflow

```
[Select Profile] -----> [Enter Source + Target directories]
   |
   v
[Click "Run Comparison"] -----> API: POST /api/compare/run
   |
   v
[View in Run History] -----> [Click run row to load pairs]
   |
   v
[Browse Pairs] -- filter by [All] [MATCH] [MISMATCH] [UNMATCHED]
   |
   +-- MATCH: no action
   |
   +-- MISMATCH/UNMATCHED: [Click pair to load diffs]
         |
         v
       [View Field-Level Diffs] -- segment, field, severity, source vs target
   |
   +-- [Edit Rules] -- load rules JSON, edit, save
   |
   +-- [Export CSV] -- download run as CSV report
```

### 6.4 Trading Partner Onboarding (source: S11)

```
[Compile DSL schema]
   pyedi validate --dsl <path>
   |
   v
[Register in config.yaml]
   csv_schema_registry + compare.profiles entries
   |
   v
[Create compare rules YAML]
   OR: pyedi scaffold-rules --schema <compiled.yaml>
   |
   v
[Process control files]
   pyedi run --file <control.txt> --split-key InvoiceID --output-dir outbound/control
   |
   v
[Process test files]
   pyedi run --file <test.txt> --split-key InvoiceID --output-dir outbound/test
   |
   v
[Run comparison]
   pyedi compare --profile <name> --source-dir outbound/control --target-dir outbound/test
   |
   v
[Review diffs] -- tune rules, adjust severity, set amount_variance in crosswalk
   |
   v
[Re-run comparison] -- verify rule changes produce expected results
```

### 6.5 Error Discovery Workflow `[SPEC]` (source: S7, Gap G1)

```
[Run comparison] -- diffs generated using wildcard (*,*) fallback
   |
   v
[System detects unclassified fields] -- (segment, field) combos not in rules
   |
   v
[View Discoveries] -- table: segment, field, source value, target value, suggested severity
   |
   v
[Review each discovery]
   +-- Accept: promote to classification rule
   +-- Modify: change severity before promoting
   +-- Dismiss: mark as reviewed, no action
   |
   v
[Reclassify existing run] -- re-evaluate diffs with updated rules (no re-pairing)
```

---

## 7. Responsive and Mobile Specification `[SPEC]`

### Current State

No responsive behavior. The sidebar is fixed at `w-56`. Grid layouts use `grid-cols-4` and `grid-cols-2` with no breakpoint variants. Tables have no horizontal scroll wrappers at narrow viewports.

### Minimum Supported Viewport

**768px (tablet).** This is an operator tool used at desks and on tablets, not a consumer mobile app.

### Breakpoint Behavior

| Breakpoint | Sidebar | StatCard Grid | Tables | Compare Panels |
|-----------|---------|---------------|--------|----------------|
| `lg` (1024px+) | Full width (w-56), text labels | `grid-cols-4` | Full columns | Side-by-side where applicable |
| `md` (768-1023px) | Icons only (w-14), tooltips on hover | `grid-cols-2` | Full columns, horizontal scroll if needed | Stacked vertically |
| `sm` (<768px) | Hamburger menu (hidden by default) | `grid-cols-1` | Horizontal scroll wrapper | Stacked vertically |

### Specific Adaptations

- **Sidebar collapse:** At `<md`, sidebar collapses to icon-only rail (w-14). Nav items show icon + tooltip on hover. Logo collapses to icon. Health indicator shows dot only.
- **StatCard grid:** Dashboard `grid-cols-4` becomes `md:grid-cols-2 sm:grid-cols-1`.
- **Data tables:** Wrap all `<table>` elements in `<div className="overflow-x-auto">`. Tables already exist in scrollable containers on Validate page (`overflow-auto max-h-96`) but Pipeline, Tests, and Compare tables do not.
- **Compare page:** The multi-step layout (form + history + pairs + diffs) stacks vertically at all breakpoints (already does). No side-by-side panel layout needed.
- **Input groups:** Validate and Compare forms use `flex gap-2` for side-by-side inputs. At `<md`, switch to `flex-col`.
- **Button groups:** Stack vertically at `<sm`.

---

## 8. Accessibility Requirements `[SPEC]`

### Target Level

**WCAG 2.1 AA.** Practical for an internal operator tool.

### Current State

| Requirement | Status | Notes |
|-------------|--------|-------|
| Semantic HTML | Partial | `<nav>`, `<button>`, `<table>`, `<h1>` all correct. `<main>` tag not used (is `<main>` element). |
| ARIA labels | Missing | No `aria-label` on nav, inputs, badges, or interactive elements |
| Keyboard navigation | Partial | Nav buttons are focusable (native `<button>`). No visible focus rings. |
| Skip link | Missing | No "Skip to main content" link |
| Color contrast | Borderline | `text-gray-500` (#6B7280) on `bg-white` = 4.6:1 ratio (AA minimum is 4.5:1 for normal text) |
| Status badges | OK | All badges include text labels, not color-only |
| Focus management | Missing | No focus redirect after async operations |
| Screen reader | Untested | No testing with assistive technology |

### Required Additions

1. **`aria-label` attributes:**
   - `<nav aria-label="Main navigation">` on sidebar
   - `aria-label` on all `<input>` elements (currently no labels on file inputs)
   - `aria-label` on status badges for screen readers
   - `aria-label="Dismiss error"` on error banner close buttons

2. **Focus management:**
   - After Validate completes, focus the Compilation Summary heading
   - After Pipeline processes, focus the first result row
   - After Compare runs, focus the new run in history
   - Visible focus rings: add `focus:ring-2 focus:ring-blue-500 focus:ring-offset-2` to all interactive elements

3. **Skip link:**
   - Add `<a href="#main-content" className="sr-only focus:not-sr-only ...">Skip to main content</a>` before sidebar
   - Add `id="main-content"` to `<main>` element

4. **Keyboard shortcuts:** `[SPEC]` — not required for AA, but beneficial:
   - `1-6` to switch pages (when not in a text input)
   - `Escape` to close rules editor, dismiss errors

---

## 9. API-UI Contract (sources: `api.ts`, all page files, backend routes)

### Endpoint Map

| # | Backend Route | api.ts Method | Used By | Notes |
|---|---------------|---------------|---------|-------|
| 1 | `GET /api/health` | `api.health()` | App.tsx | Health indicator |
| 2 | `POST /api/validate` | `api.validate()` | Validate.tsx | Path-based validation |
| 3 | `POST /api/validate/upload` | `api.validateUpload()` | Validate.tsx | File upload validation |
| 4 | `GET /api/validate/history` | — | — | **Backend exists, no api.ts wrapper, no UI** |
| 5 | `POST /api/pipeline/run` | `api.pipelineRun()` | — | **api.ts exists, not used by any page** |
| 6 | `POST /api/pipeline/upload` | — | — | **Backend exists, no api.ts wrapper, no UI** |
| 7 | `GET /api/pipeline/results` | `api.pipelineResults()` | Pipeline.tsx | |
| 8 | `GET /api/pipeline/results/{id}` | — | — | **Backend exists, no api.ts wrapper, no UI** |
| 9 | `POST /api/test/run` | `api.testRun()` | Tests.tsx | |
| 10 | `GET /api/test/cases` | `api.testCases()` | Tests.tsx | |
| 11 | `POST /api/test/generate-expected` | — | — | **Backend exists, no api.ts wrapper, no UI** |
| 12 | `GET /api/test/verify` | `api.testVerify()` | — | **api.ts exists, not used by any page** |
| 13 | `GET /api/manifest` | `api.manifestEntries()` | Dashboard.tsx | |
| 14 | `GET /api/manifest/stats` | `api.manifestStats()` | Dashboard.tsx | |
| 15 | `GET /api/config` | `api.config()` | Config.tsx | |
| 16 | `GET /api/config/registry` | `api.configRegistry()` | — | **api.ts exists, not used by any page** |
| 17 | `PUT /api/config/registry/{name}` | — | — | **Backend exists, no api.ts wrapper, no UI** |
| 18 | `GET /api/compare/profiles` | `api.compareProfiles()` | Compare.tsx | |
| 19 | `POST /api/compare/run` | `api.compareRun()` | Compare.tsx | |
| 20 | `GET /api/compare/runs` | `api.compareRuns()` | Compare.tsx | |
| 21 | `GET /api/compare/runs/{id}` | `api.compareRunDetail()` | — | **api.ts exists, not used by any page** |
| 22 | `GET /api/compare/runs/{id}/pairs` | `api.comparePairs()` | Compare.tsx | |
| 23 | `GET /api/compare/runs/{id}/pairs/{pid}/diffs` | `api.compareDiffs()` | Compare.tsx | |
| 24 | `GET /api/compare/runs/{id}/export` | `api.compareExportUrl()` | Compare.tsx | Returns URL, not fetched |
| 25 | `GET /api/compare/profiles/{name}/rules` | `api.compareRules()` | Compare.tsx | |
| 26 | `PUT /api/compare/profiles/{name}/rules` | `api.compareUpdateRules()` | Compare.tsx | |

### Summary

| Category | Count |
|----------|-------|
| Backend routes total | 26 |
| api.ts methods total | 21 |
| Endpoints fully wired (backend + api.ts + UI) | 14 |
| api.ts methods with no page consumer | 5 (#5, #12, #16, #21, #24 returns URL only) |
| Backend routes with no api.ts wrapper | 5 (#4, #6, #8, #11, #17) |
| All return types typed as `any` | 20 of 21 (only `health` is typed) |

---

## 10. Open Items and Roadmap (sources: S7, S8)

### P1 — High Priority

| Item | Source | Notes |
|------|--------|-------|
| Extract shared `StatusBadge` component | This spec | 3 duplicated definitions with different color maps |
| Add `react-router-dom` routing | S8 | Replace `useState<Page>` with URL-based routing. Enables deep links, browser history. |
| Wire file upload on Pipeline page | S8 | Backend `POST /api/pipeline/upload` exists. Need drag-and-drop UI + trigger button. |
| Wire `api.pipelineRun()` to a UI button | This spec | api.ts method exists, no page uses it. |

### P2 — Medium Priority

| Item | Source | Notes |
|------|--------|-------|
| Build Manifest page | S8 | Backend endpoints exist (`GET /api/manifest`, `/stats`). Need dedicated page with search, filter, pagination. |
| Type API responses | This spec | Replace all `any` return types in api.ts with TypeScript interfaces. |
| Extract shared components directory | S1, this spec | Create `src/components/` with StatusBadge, ErrorBanner, CollapsiblePanel, DataTable, FileUpload. |
| Config editing UI | S8 | Wire `PUT /api/config/registry/{name}` to inline editing on Config page. |
| Wire missing api.ts methods | This spec | Add wrappers for 6 unwired backend endpoints (#4, #6, #8, #11, #17). |
| Add Generate Expected + Verify Environment to Tests page | S1 | Buttons + api.ts methods already exist but not connected. |

### P3 — Low Priority

| Item | Source | Notes |
|------|--------|-------|
| Error discovery portal integration | S7 (G1) | New table, workflow, UI for reviewing unclassified field combos. |
| Reclassification UI | S7 (G2) | "Reclassify" button on run detail — re-evaluate diffs without re-pairing. |
| Summary statistics dashboard | S7 (G8) | Severity/segment/field breakdowns, top errors. |
| Responsive breakpoints | Sec. 7 | Implement sidebar collapse, grid breakpoints, table scroll wrappers. |
| Accessibility remediation | Sec. 8 | ARIA labels, focus management, skip link, visible focus rings. |
| Portal authentication | S8 | Basic auth or API key middleware before exposing outside localhost. |

---

## 11. Design Invariants (sources: S1, S5)

1. **No business logic in React components.** Pages render data from API responses. All processing, validation, and comparison logic lives in `pyedi_core/`. The portal is a thin display layer.

2. **Zero hardcoding.** Display data comes from API calls, never from string literals in React code. Status options, profile names, field lists, column definitions — all from the API. If a value appears in the UI, it was returned by an endpoint.

3. **API is the single data path.** No direct filesystem access from the frontend. No reading config files, manifest files, or SQLite databases from React. Everything goes through FastAPI endpoints.

4. **CLI parity.** Every operation available in the portal is also available via `pyedi` CLI (`pyedi run`, `pyedi test`, `pyedi validate`, `pyedi compare`). The portal is additive — the CLI remains fully functional without the portal running.

5. **Fail fast, show everything.** Errors surface in full detail — stage, correlation ID, exception message. Errors are never swallowed or reduced to generic messages. The error banner pattern (red `bg-red-50`, dismissable) is the standard display mechanism.
