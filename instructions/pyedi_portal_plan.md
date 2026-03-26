# PyEDI Portal — Full Operator Web UI + Validate Engine

> **Merged from:** `validate_subcommand_plan.md` (backend engine + compiler fixes) and `autocertify-blueprint.md` (React UI patterns + operator portal intent).

---

## Context

PyEDI-Core is a CLI-first engine. Operators interact via `pyedi run`, `pyedi test`, and (soon) `pyedi validate`. There is no visual interface for inspecting compilation results, reviewing pipeline output, managing configuration, or triaging failures.

The autoCertify project solved a parallel problem: it wrapped a headless certification engine with a React "Mission Control" dashboard. The patterns that transfer are: **workflow cards, step results tables, collapsible data panels, API polling, and report visualization.** The domain-specific pieces (EDI lifecycle state machine, Postgres assertions, db_ops.yaml) do not transfer.

**This document defines a full operator web portal for PyEDI-Core** — a React frontend backed by a thin FastAPI API layer that wraps the existing Python engine.

---

## Goals

1. Fix compiler bugs (type loss + fieldIdentifier collision) — prerequisite for trustworthy validation
2. Add `pyedi validate` CLI subcommand — the engine that powers the Validate page
3. Build a FastAPI API layer wrapping all pyedi operations — Phase 3 of the roadmap
4. Build a React portal at `portal/` with four pages: **Validate, Pipeline, Test Harness, Manifest**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  REACT FRONTEND  (portal/frontend/)                             │
│  Vite + React + TypeScript                                      │
│                                                                  │
│  Pages:                                                          │
│   /validate    — DSL compile, inspect, sample test, field trace │
│   /pipeline    — Process files, view results, triage failures   │
│   /test        — Test harness results, re-run, watch mode       │
│   /manifest    — Processing history, dedup log, search          │
└────────────────────────┬────────────────────────────────────────┘
                         │  HTTP (JSON)
┌────────────────────────▼────────────────────────────────────────┐
│  FASTAPI BACKEND  (portal/api/)                                  │
│  Thin wrapper — no business logic, delegates to pyedi_core       │
│                                                                  │
│  Endpoints:                                                      │
│   POST /api/validate          → validator.validate()            │
│   POST /api/pipeline/run      → pipeline.run()                  │
│   GET  /api/pipeline/results  → read outbound/ + failed/        │
│   POST /api/test/run          → test_harness.run_tests()        │
│   GET  /api/test/results      → read test reports               │
│   GET  /api/manifest          → manifest.read()                 │
│   GET  /api/config            → read config.yaml                │
│   PUT  /api/config/registry   → update csv_schema_registry      │
└────────────────────────┬────────────────────────────────────────┘
                         │  Python imports
┌────────────────────────▼────────────────────────────────────────┐
│  PYEDI_CORE ENGINE  (pyedi_core/)                                │
│  Pipeline, Validator, Test Harness, Manifest, Drivers            │
│  No changes to core engine — API layer is additive only          │
└──────────────────────────────────────────────────────────────────┘
```

---

## What Transfers from autoCertify (and What Doesn't)

| autoCertify Layer | Transfers? | PyEDI Equivalent |
|---|---|---|
| React UI — workflow cards grid | **YES** | Validation history cards, pipeline batch cards |
| React UI — step results table (id, label, status badge, duration) | **YES** | Field trace table, pipeline results table, test case results |
| React UI — collapsible data panel | **YES** | DSL source preview, compiled YAML preview, sample data preview |
| React UI — API polling pattern | **YES** | Poll `/api/pipeline/results` during batch processing |
| Report generator (markdown) | **YES (adapted)** | Validation reports written to `reports/` for history |
| CLI runner flags | **YES** | Already exists in `pyedi_core/main.py` |
| YAML Workflow Engine (step sequencing, stored_vars) | **NO** | PyEDI has no step-chaining concept — each operation is independent |
| Fixture files (X12 4010 lifecycle) | **NO** | PyEDI uses `tests/user_supplied/` for test data |
| Lifecycle Engine (state machine) | **NO** | PyEDI is stateless transformation, not lifecycle tracking |
| Database assertions (db_ops.yaml, Postgres) | **NO** | PyEDI validates via JSON comparison, not SQL assertions |
| CERT-prefix isolation | **NO** | PyEDI uses manifest dedup, not prefix-based cleanup |
| Headed/Headless dual mode (Playwright) | **NO** | PyEDI has no browser automation |

---

## Phase A: Backend Engine (Steps 1-6 from validate_subcommand_plan.md)

These steps are unchanged from the validate plan. They must be completed first — the API layer wraps them.

### Step A1: Fix compiler bugs in `schema_compiler.py`

**Bug 1 — Type loss:** Deduplication at lines 233-240 keeps first occurrence by name. Header (all `String`) overwrites Detail (`Decimal`/`Integer`). Fix: prefer most specific type during dedup (`float` > `integer` > `date` > `boolean` > `string`).

**Bug 2 — fieldIdentifier collision:** Line 162 overwrites `records[fid]` when multiple records share the same fieldIdentifier value. Fix: when collision detected, fall back to record name as key instead of fieldIdentifier value.

### Step A2: Extract `parse_dsl_file()` in `schema_compiler.py`

Extract lines 337-381 (file read → delimiter regex → brace-count → `_parse_dsl_record`) into a public function. Refactor `compile_dsl()` to call it. No behavior change.

### Step A3: Create `pyedi_core/validator.py`

New module with: `validate()`, `compile_and_write()`, `check_type_preservation()`, `check_compilation_warnings()`, `run_sample()`, `compute_coverage()`, `compute_field_traces()`. Returns `ValidationResult` dataclass.

### Step A4: Add `validate` subcommand to `main.py`

`pyedi validate --dsl <path> [--sample <path>] [--json] [--verbose] [--output-dir <dir>]`

### Step A5: Add `tests/test_validator.py`

Unit + integration tests for the validator module.

### Step A6: Update `__init__.py` exports

---

## Phase B: FastAPI API Layer

**Location:** `portal/api/`

### Directory structure

```
portal/
├── api/
│   ├── __init__.py
│   ├── app.py              # FastAPI app factory, CORS, lifespan
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── validate.py     # /api/validate endpoints
│   │   ├── pipeline.py     # /api/pipeline endpoints
│   │   ├── test.py         # /api/test endpoints
│   │   ├── manifest.py     # /api/manifest endpoints
│   │   └── config.py       # /api/config endpoints
│   └── models.py           # Pydantic request/response models
├── frontend/               # (Phase C)
└── pyproject.toml          # portal package definition
```

### Endpoint Specifications

#### Validate Endpoints

| Method | Path | Request | Response | Wraps |
|---|---|---|---|---|
| `POST` | `/api/validate` | `{dsl_path: str, sample_path?: str, output_dir?: str}` | `ValidationResult` as JSON | `validator.validate()` |
| `POST` | `/api/validate/upload` | multipart: DSL file + optional sample file | Same as above | Saves uploads to temp dir, calls `validator.validate()` |
| `GET` | `/api/validate/history` | query: `?limit=20` | List of past validation results | Reads from `reports/validate/` |

#### Pipeline Endpoints

| Method | Path | Request | Response | Wraps |
|---|---|---|---|---|
| `POST` | `/api/pipeline/run` | `{file?: str, files?: List[str], dry_run?: bool}` | `PipelineResult` or `List[PipelineResult]` | `pipeline.run()` |
| `POST` | `/api/pipeline/upload` | multipart: file(s) to process | Same as above | Saves to inbound dir, runs pipeline |
| `GET` | `/api/pipeline/results` | query: `?status=FAILED&limit=50` | List of recent results | Reads outbound/ + failed/ |
| `GET` | `/api/pipeline/results/{correlation_id}` | — | Single result detail + error.json if failed | Reads specific output + sidecar |

#### Test Harness Endpoints

| Method | Path | Request | Response | Wraps |
|---|---|---|---|---|
| `POST` | `/api/test/run` | `{metadata_path?: str, verbose?: bool}` | Test run results (pass/fail/warn per case) | `test_harness.run_tests()` |
| `GET` | `/api/test/cases` | — | List of test cases from metadata.yaml | Reads metadata.yaml |
| `POST` | `/api/test/generate-expected` | — | Generation results | `test_harness.generate_expected()` |
| `GET` | `/api/test/verify` | — | Environment verification results | `test_harness.verify()` |

#### Manifest Endpoints

| Method | Path | Request | Response | Wraps |
|---|---|---|---|---|
| `GET` | `/api/manifest` | query: `?status=FAILED&search=filename` | Manifest entries | Reads `.processed` file |
| `GET` | `/api/manifest/stats` | — | `{total, success, failed, skipped}` | Aggregates from `.processed` |

#### Config Endpoints

| Method | Path | Request | Response | Wraps |
|---|---|---|---|---|
| `GET` | `/api/config` | — | Full config.yaml as JSON | Reads config.yaml |
| `GET` | `/api/config/registry` | — | `transaction_registry` + `csv_schema_registry` | Subset of config |
| `PUT` | `/api/config/registry/{entry_name}` | `CsvSchemaEntry` body | Updated entry | Writes to config.yaml |

### Key Design Decisions

- **No business logic in the API layer.** Every endpoint is a thin wrapper that calls existing `pyedi_core` functions and returns their output as JSON. The FastAPI layer does: request validation (Pydantic), file upload handling, CORS, and response serialization. Nothing else.
- **File upload endpoints** save uploaded files to a temp directory, pass the path to the engine, and clean up after. This enables the React UI to work without direct filesystem access.
- **Config write endpoints** are the only mutation path. They write to `config.yaml` and require explicit user action. No auto-mutation.
- **CORS** configured for `localhost:5173` (Vite dev) and the production origin.

### Dependencies

Add to `portal/pyproject.toml`:
```
fastapi>=0.110
uvicorn>=0.27
python-multipart>=0.0.9    # for file uploads
```

These align with the Phase 3 roadmap in `SPECIFICATION.md`.

---

## Phase C: React Frontend

**Location:** `portal/frontend/`

### Tech Stack

| Tool | Purpose |
|---|---|
| Vite | Build tool + dev server |
| React 18 | UI framework |
| TypeScript | Type safety |
| Tailwind CSS | Utility-first styling |
| React Router | Client-side routing |
| TanStack Query (React Query) | Server state management, polling, caching |

### Directory Structure

```
portal/frontend/
├── src/
│   ├── main.tsx                    # App entry
│   ├── App.tsx                     # Router + layout
│   ├── api/
│   │   └── client.ts              # Typed fetch wrapper for all /api/* endpoints
│   ├── components/
│   │   ├── Layout.tsx             # Shell: sidebar nav + content area
│   │   ├── StatusBadge.tsx        # SUCCESS/FAILED/SKIPPED/WARN badges
│   │   ├── CollapsiblePanel.tsx   # Reusable expand/collapse panel (from autoCertify pattern)
│   │   ├── DataTable.tsx          # Sortable table component
│   │   ├── FileUpload.tsx         # Drag-and-drop file upload
│   │   └── JsonPreview.tsx        # Syntax-highlighted JSON viewer
│   ├── pages/
│   │   ├── Validate.tsx           # DSL validation page
│   │   ├── Pipeline.tsx           # File processing page
│   │   ├── TestHarness.tsx        # Test results page
│   │   └── Manifest.tsx           # Processing history page
│   └── types/
│       └── api.ts                 # TypeScript types matching Pydantic models
├── index.html
├── tailwind.config.js
├── tsconfig.json
├── vite.config.ts
└── package.json
```

### Page Specifications

---

#### Page 1: Validate (`/validate`)

**Purpose:** The DSL compilation and mapping verification workflow, visualized.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  [Upload DSL File]  or  [Select Existing: ▼ tpm810SourceFF.txt] │
│  [Upload Sample File (optional)]                                 │
│  [ Validate ]                                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  === Compilation Report ===                                      │
│  ┌──────────────────────┐                                       │
│  │ Source: tpm810...txt  │  Transaction: 810_INVOICE             │
│  │ Compiled: margin_...  │  Delimiter: "|"                      │
│  │ Records: 3            │  Columns: 45                         │
│  └──────────────────────┘                                       │
│                                                                  │
│  === Schema Columns ===  (sortable table)                       │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Name                    │ Type   │ DSL Type │ Status   │     │
│  │ RecordId                │ string │ String   │ ✓ OK     │     │
│  │ HDRInvoiceTotalNet...   │ float  │ Decimal  │ ✓ OK     │     │
│  │ CaseSize                │ string │ Decimal  │ ✗ LOST   │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  === Type Warnings ===  (collapsible, red highlight)            │
│  === Record Definitions ===  (collapsible)                      │
│                                                                  │
│  ─── Sample Results (only if sample file provided) ───          │
│                                                                  │
│  === Mapping Coverage ===                                        │
│  ┌──────────────┐  Source: 45 total, 41 mapped (91.1%)          │
│  │  ████████░░  │  Target: 45 total, 41 populated               │
│  │  91.1%       │  Unmapped: [field1, field2, ...]              │
│  └──────────────┘                                               │
│                                                                  │
│  === Field Trace ===  (first 3 rows, expandable)                │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Row 1 (HDR)                                            │     │
│  │  Target           ← Source           = Value           │     │
│  │  RecordId         ← RecordId         = "HDR"          │     │
│  │  HDRInvoiceNumber ← HDRInvoiceNumber = "INV-001"      │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  [▼ Compiled YAML Preview]  (collapsible, syntax highlighted)   │
│  [▼ DSL Source Preview]     (collapsible)                       │
└─────────────────────────────────────────────────────────────────┘
```

**Data flow:** File upload → `POST /api/validate/upload` → backend calls `validator.validate()` → returns `ValidationResult` JSON → React renders all sections.

**Patterns from autoCertify applied:**
- Collapsible data panels (DSL source, compiled YAML, field traces)
- Status badges on each column row (OK / LOST)
- Step results table pattern for field traces

---

#### Page 2: Pipeline (`/pipeline`)

**Purpose:** Process files through the pyedi pipeline and review results.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  [Upload File(s)]  [☐ Dry Run]  [ Process ]                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  === Recent Results ===  (auto-refresh every 10s)               │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ File              │ Status  │ Type │ Time  │ Actions   │     │
│  │ invoice_001.csv   │ SUCCESS │ 810  │ 42ms  │ [View]    │     │
│  │ PO_850.x12        │ FAILED  │ 850  │ 15ms  │ [Triage]  │     │
│  │ vendor.xml         │ SKIPPED │ —    │ 2ms   │ [Details] │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  === Failure Detail ===  (shown when [Triage] clicked)          │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Stage: TRANSFORMATION                                  │     │
│  │ Error: No mapping rules found for file: PO_850.x12    │     │
│  │ Correlation ID: abc-123-def                            │     │
│  │ [▼ error.json]  [▼ Source File Preview]                │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  === Batch Summary ===  (for multi-file runs)                   │
│  Total: 15  |  Success: 12  |  Failed: 2  |  Skipped: 1        │
└─────────────────────────────────────────────────────────────────┘
```

**Data flow:** Upload → `POST /api/pipeline/upload` → returns `PipelineResult[]` → render table. Polling `GET /api/pipeline/results` refreshes the recent results list.

**Patterns from autoCertify applied:**
- Step results table (file, status badge, duration)
- Collapsible error detail (equivalent to autoCertify's failed-step JSON response)
- Batch summary counts

---

#### Page 3: Test Harness (`/test`)

**Purpose:** Run and review YAML-driven regression tests.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  [ Run Tests ]  [ Generate Expected ]  [ Verify Environment ]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  === Test Cases ===                                              │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Name                        │ Status │ Details         │     │
│  │ UnivT701 Demo Invoice CSV   │ PASS   │ 0 discrepancies│     │
│  │ MarginEdge 810 Text File    │ PASS   │ 0 discrepancies│     │
│  │ cXML 850 Purchase Order     │ PASS   │ 0 discrepancies│     │
│  │ Malformed X12 - failure     │ PASS   │ expected FAILED │     │
│  │ Unmapped CSV - failure      │ FAIL   │ wrong stage    │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  === Environment Verify ===  (collapsible)                      │
│  Python 3.10.x  |  badx12 ✓  |  pandas ✓  |  structlog ✓      │
│                                                                  │
│  Summary: 5 total  |  4 passed  |  1 failed  |  0 warnings     │
└─────────────────────────────────────────────────────────────────┘
```

**Data flow:** Button click → `POST /api/test/run` → returns results → render table.

**Patterns from autoCertify applied:**
- Workflow cards with check counts and pass/fail tallies
- Check ID + label + status badge table (maps directly to test case results)

---

#### Page 4: Manifest (`/manifest`)

**Purpose:** View processing history, search, filter, and review dedup status.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  [Search: ________]  [Filter: All ▼]  Stats: 247 total         │
│                                        │ 210 success │ 35 fail │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  === Processing History ===                                      │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Hash (short) │ Filename          │ Timestamp  │ Status │     │
│  │ a088ec...    │ invoice_001.csv   │ 2026-03-24 │ SUCCESS│     │
│  │ 567494...    │ PO_850.x12        │ 2026-03-24 │ FAILED │     │
│  │ ...          │ ...               │ ...        │ ...    │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  Showing 1-50 of 247  [ < ] [ > ]                               │
└─────────────────────────────────────────────────────────────────┘
```

**Data flow:** `GET /api/manifest?status=&search=&offset=&limit=` → paginated results.

---

## Phase D: Wiring and Dev Experience

### Dev Workflow

```bash
# Terminal 1: API server
cd portal && uvicorn api.app:app --reload --port 8000

# Terminal 2: React dev server
cd portal/frontend && npm run dev    # Vite on :5173, proxies /api to :8000

# Terminal 3: Engine (still works standalone)
pyedi validate --dsl tpm810SourceFF.txt --sample data.txt
```

### Vite Proxy Config

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

### Startup Script

```bash
# portal/dev.sh
#!/bin/bash
uvicorn portal.api.app:app --reload --port 8000 &
cd portal/frontend && npm run dev
```

---

## Files Summary

### Phase A (Backend Engine)

| File | Action |
|---|---|
| `pyedi_core/core/schema_compiler.py` | Fix 2 bugs + extract `parse_dsl_file()` |
| `pyedi_core/validator.py` | **NEW** — validation logic |
| `pyedi_core/main.py` | Add `validate` subparser |
| `pyedi_core/__init__.py` | Add validator export |
| `tests/test_validator.py` | **NEW** — validator tests |

### Phase B (FastAPI API)

| File | Action |
|---|---|
| `portal/api/__init__.py` | Package init |
| `portal/api/app.py` | **NEW** — FastAPI app factory |
| `portal/api/models.py` | **NEW** — Pydantic request/response models |
| `portal/api/routes/validate.py` | **NEW** — /api/validate endpoints |
| `portal/api/routes/pipeline.py` | **NEW** — /api/pipeline endpoints |
| `portal/api/routes/test.py` | **NEW** — /api/test endpoints |
| `portal/api/routes/manifest.py` | **NEW** — /api/manifest endpoints |
| `portal/api/routes/config.py` | **NEW** — /api/config endpoints |
| `portal/pyproject.toml` | **NEW** — portal package with fastapi/uvicorn deps |

### Phase C (React Frontend)

| File | Action |
|---|---|
| `portal/frontend/package.json` | **NEW** — React + Vite + Tailwind + React Query |
| `portal/frontend/src/App.tsx` | **NEW** — Router + Layout |
| `portal/frontend/src/api/client.ts` | **NEW** — Typed API client |
| `portal/frontend/src/components/Layout.tsx` | **NEW** — Sidebar shell |
| `portal/frontend/src/components/StatusBadge.tsx` | **NEW** — Status badges |
| `portal/frontend/src/components/CollapsiblePanel.tsx` | **NEW** — Expand/collapse |
| `portal/frontend/src/components/DataTable.tsx` | **NEW** — Sortable table |
| `portal/frontend/src/components/FileUpload.tsx` | **NEW** — Drag-and-drop upload |
| `portal/frontend/src/components/JsonPreview.tsx` | **NEW** — JSON viewer |
| `portal/frontend/src/pages/Validate.tsx` | **NEW** — DSL validation page |
| `portal/frontend/src/pages/Pipeline.tsx` | **NEW** — File processing page |
| `portal/frontend/src/pages/TestHarness.tsx` | **NEW** — Test results page |
| `portal/frontend/src/pages/Manifest.tsx` | **NEW** — Processing history page |

---

## Execution Order

1. **Phase A** — Backend engine (compiler fixes + validator + CLI). Must complete first.
2. **Phase B** — FastAPI API layer. Wraps Phase A outputs. Can be built incrementally per route file.
3. **Phase C** — React frontend. Built page by page. Validate page first (most complex, validates the API contract), then Pipeline, Test, Manifest.
4. **Phase D** — Wiring, dev scripts, documentation.

Within Phase C, build order:
1. Shared components (`Layout`, `StatusBadge`, `CollapsiblePanel`, `DataTable`, `FileUpload`, `JsonPreview`)
2. API client (`client.ts` + `types/api.ts`)
3. Validate page (most complex — proves the full stack)
4. Pipeline page
5. Test Harness page
6. Manifest page

---

## Verification

### Phase A
1. `pytest` — all existing + new tests pass
2. `pyedi validate --dsl tpm810SourceFF.txt` — correct report
3. `pyedi validate --dsl tpm810SourceFF.txt --sample tests/user_supplied/inputs/NA_810_MARGINEDGE_20260129.txt` — coverage + traces

### Phase B
4. `uvicorn portal.api.app:app` starts without error
5. `curl -X POST localhost:8000/api/validate -d '{"dsl_path":"tpm810SourceFF.txt"}'` returns ValidationResult JSON
6. `curl localhost:8000/api/manifest` returns manifest entries

### Phase C
7. `cd portal/frontend && npm run dev` starts Vite
8. Navigate to `/validate`, upload DSL, see compilation report
9. Upload DSL + sample, see field traces and coverage chart
10. Navigate to `/pipeline`, upload a CSV, see PipelineResult
11. Navigate to `/test`, click Run Tests, see pass/fail table
12. Navigate to `/manifest`, see processing history with search/filter

---

## Invariants (Carried from autoCertify Blueprint)

| Invariant | PyEDI Application |
|---|---|
| **No business logic in the UI layer** | React renders data from the API. All transformation/validation logic stays in `pyedi_core/`. |
| **API is a thin wrapper** | FastAPI endpoints call existing Python functions. No logic duplication. |
| **YAML is the source of truth** | Mapping rules, schema definitions, and test cases live in YAML — not in React state or API code. |
| **CLI still works standalone** | The portal is additive. `pyedi run`, `pyedi test`, `pyedi validate` work identically without the portal running. |
| **Fail fast, show everything** | Validation and pipeline errors surface in full detail (stage, error, correlation ID). No silent swallowing. |

---

*This document lives at `instructions/pyedi_portal_plan.md`. It is an instruction artifact, not a runnable file.*
