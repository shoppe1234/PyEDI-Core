# autoCertify — Architecture Blueprint & Reuse Guide

> **Purpose:** Holistic reference for how autoCertify is built, where each piece lives, what is
> domain-specific vs. reusable infrastructure, and how to prompt-orchestrate an equivalent system
> for a new project that has lifecycles and data transformation.

---

## Table of Contents

1. [Philosophy](#1-philosophy)
2. [Layer Map](#2-layer-map)
3. [End-to-End Data Flow](#3-end-to-end-data-flow)
4. [Layer-by-Layer Detail](#4-layer-by-layer-detail)
   - 4A. Fixture Files
   - 4B. YAML Workflow Engine
   - 4C. API Endpoint (Ingest / Transform)
   - 4D. Lifecycle Engine
   - 4E. Database Assertions
   - 4F. CLI Runner
   - 4G. Report Generator
   - 4H. React UI (Mission Control)
5. [Specialization Map — What to Change for a New Project](#5-specialization-map)
6. [Invariants to Carry Forward](#6-invariants-to-carry-forward)
7. [Prompt Orchestration — Building This for a New Project](#7-prompt-orchestration)

---

## 1. Philosophy

autoCertify is a **headless-first, YAML-driven certification harness**. It proves that a system
behaves correctly end-to-end — not by mocking, but by exercising the real API, the real database,
and the real state machine with controlled test data.

Four core principles:

| Principle | What it means in practice |
|-----------|--------------------------|
| **No mocks** | Every step hits the live API. Fixtures are real documents. DB is real Postgres. |
| **YAML is the brain** | Workflows, assertions, and parameters live in YAML — not in Python test code. |
| **CERT-prefix isolation** | All test data uses a known prefix. Cleanup targets only that prefix — never production data. |
| **Dual-mode** | Headed (Playwright browser visible) for humans debugging. Headless for agent-bots and CI. |

---

## 2. Layer Map

```
┌─────────────────────────────────────────────────────────────────┐
│  ORCHESTRATION                                                   │
│  scripts/run_certification.sh  ←  Mission Control UI (F3)       │
│  tastecli CLI (--yaml-dir autoCertify/yaml)                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  YAML WORKFLOW ENGINE  (tastecli/scenarios/yaml_engine.py)       │
│  Reads workflow YAML → executes steps in order                   │
│  Two step types: edi_ingest  |  db                              │
└──────────┬──────────────────────────────────┬───────────────────┘
           │                                  │
┌──────────▼──────────┐             ┌─────────▼──────────────────┐
│  FIXTURE FILES       │             │  DB OPS (db_ops.yaml)       │
│  autoCertify/        │             │  cleanup_* mutations        │
│  fixtures/           │             │  assert_* assertions        │
│  *.edi (X12 4010)    │             │  Direct Postgres SQL        │
└──────────┬──────────┘             └────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│  API ENDPOINT   POST /api/v1/edi/ingest  (portals/api.py)        │
│  Parse X12 envelope → resolve trading partner → dedup check      │
│  Extract PO#, qty, N1 → build payload → call lifecycle engine    │
└──────────┬──────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│  LIFECYCLE ENGINE  (lifecycle_engine/)                           │
│  on_document_processed() — state machine transition              │
│  Writes po_lifecycle, lifecycle_events, lifecycle_violations     │
└──────────────────────────────────────────────────────────────────┘
           │ results flow back up
┌──────────▼──────────────────────────────────────────────────────┐
│  REPORTS  autoCertify/reports/{date}_{workflow}.md               │
│  REACT UI  mission-control/frontend/src/pages/AutoCertify.tsx    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. End-to-End Data Flow

```
1.  CLI invocation
    python -m tastecli --yaml-dir autoCertify/yaml --workflow edi_lifecycle

2.  YamlEngine loads workflow YAML
    Merges global.yaml scope + db_ops.yaml ops + workflow steps

3.  For each step (type: edi_ingest):
    a. Load raw fixture from autoCertify/fixtures/{path}
    b. Interpolate YAML variables into fixture if needed
    c. POST {"raw_x12": "...", "source_label": "..."} to /api/v1/edi/ingest
    d. Endpoint parses ISA/GS envelope, resolves partner, dedup-checks
    e. Extracts PO number, quantity, N1 qualifiers from raw X12
    f. Calls lifecycle_engine.on_document_processed() via psycopg2
    g. Queries po_lifecycle + violations tables for post-state
    h. Returns JSON: {status, po_number, prior_state, new_state, violations, human_message, quantities}
    i. YamlEngine validates response against expect_* fields in step
    j. Stores named fields in stored_vars for later steps

4.  For each step (type: db):
    a. Resolve operation name → SQL template from db_ops.yaml
    b. Bind parameters from step, stored_vars, global scope
    c. Mutations (cleanup_*, seed_*): execute, no result check
    d. Assertions (assert_*): execute, compare actual vs. expected
    e. Fail immediately on mismatch (no retry)

5.  After all steps:
    a. Emit NDJSON events: step_pass / step_fail
    b. If --report: write autoCertify/reports/{date}_{workflow}.md
    c. If --gh-issue and failures: create GitHub issue with report body

6.  Mission Control dashboard polls reports/ and /api/runs for display
```

---

## 4. Layer-by-Layer Detail

### 4A. Fixture Files

**Location:** `autoCertify/fixtures/`

**Structure:**
```
fixtures/
├── happy_path/          # Normal flow
│   ├── 850_stock_po.edi
│   ├── 855_po_ack.edi
│   ├── 856_asn.edi
│   └── 810_invoice.edi
├── change_order/        # PO change flow
│   ├── 860_po_change.edi
│   └── 865_po_change_ack.edi
└── violations/          # Error scenarios
    ├── qty_exceed.edi
    ├── terminal_reentry.edi
    ├── duplicate_isa.edi
    └── no_prior_po.edi
```

**Key conventions:**
- All test PO numbers use the `CERT` prefix (e.g., `CERT00001`) — matches `po_prefix` in global.yaml
- Sender/receiver IDs are synthetic: `CERTRETAILER` / `CERTSUPPLIER`
- X12 4010 format: ISA 106-char fixed-width, element delimiter `*`, segment terminator `~`
- Control numbers increment across fixtures in a workflow (ISA 000000001, 000000002, ...)

**Specialized:** Everything here is domain-specific. For a new project replace with your document format (JSON payloads, CSV rows, XML messages, etc.).

---

### 4B. YAML Workflow Engine

**Location:** `tastecli/scenarios/yaml_engine.py`

**Inputs:** Three YAML layers merged at runtime:
```
global.yaml          ← base scope (partner IDs, slugs, prefixes)
db_ops.yaml          ← named operations (SQL templates)
workflows/{name}.yaml ← ordered step list
```

**Step types currently supported:**
| type | what it does |
|------|-------------|
| `edi_ingest` | POST fixture to ingest endpoint, validate JSON response |
| `db` | run named SQL op from db_ops.yaml, optionally assert result |

**Workflow YAML anatomy:**
```yaml
workflow:
  id: edi_lifecycle
  name: "EDI Lifecycle — Happy Path"
  checks: 11

journey:
  - id: CERT-LC-01
    label: "Ingest 850 PO"
    type: edi_ingest
    fixture: happy_path/850_stock_po.edi
    expect_status: processed
    expect_new_state: po_originated
    store:
      po_number: po_number        # stores response field into named var

  - id: CERT-LC-02
    label: "Cleanup before test"
    type: db
    op: cleanup_lifecycle_events
    params:
      po_number: "{po_number}"    # interpolated from stored_vars

  - id: CERT-LC-05
    label: "Assert PO state = po_acknowledged"
    type: db
    op: assert_po_state
    params:
      po_number: "{po_number}"
      expected_state: po_acknowledged
```

**Specialized:** The `type` enum and the `_run_*` handler methods are the extension points. Adding a new document type means adding a new `type` value and a corresponding handler.

---

### 4C. API Endpoint (Ingest / Transform)

**Location:** `portals/api.py` — `POST /api/v1/edi/ingest`

**Responsibilities:**
1. Parse the envelope (sender, receiver, control number, transaction set ID)
2. Resolve trading partner from routing rules
3. Deduplicate by ISA control number (log to `edi_interchange_log`)
4. Extract business keys from the document body (PO number, quantity, N1 qualifiers)
5. Build a minimal payload for the lifecycle engine
6. Call the lifecycle engine synchronously
7. Query post-transition state and any violations
8. Build a human-readable error message if violations exist
9. Return a structured JSON response

**Helper functions (all private, in-file):**
- `_extract_po_from_x12()` — reads BEG/BAK/PRF/BIG segments
- `_extract_qty_from_x12()` — reads PO1/ACK/SN1/IT1 segments
- `_extract_n1_from_x12()` — reads N1 qualifier loops
- `_build_human_message()` — converts violation codes to plain English

**Response contract:**
```json
{
  "status": "processed|violation|duplicate|error|unrouted",
  "po_number": "CERT00001",
  "prior_state": "po_originated",
  "new_state": "po_acknowledged",
  "is_terminal": false,
  "violations": [],
  "human_message": "PO CERT00001 acknowledged successfully.",
  "correlation_id": "uuid",
  "success": true,
  "envelope": { "sender_id": "...", "receiver_id": "...", "transaction_set_id": "855", "isa_control_number": "000000002" },
  "quantities": { "ordered": 20.0, "accepted": 20.0, "shipped": null, "invoiced": null }
}
```

**Specialized:** The X12 parsing helpers are EDI-specific. For a new project replace with your document parsers. The response contract shape is the stable interface the YAML engine validates against — keep it.

---

### 4D. Lifecycle Engine

**Location:** `lifecycle_engine/`

**Entry point:** `on_document_processed(payload, conn)` — called synchronously from the API endpoint with an open psycopg2 connection.

**What it does:**
- Reads the current state from `po_lifecycle`
- Validates the transition (is this document valid from the current state?)
- Writes the new state to `po_lifecycle`
- Appends an event row to `lifecycle_events` (INSERT-ONLY)
- Appends violation rows to `lifecycle_violations` if rules are broken

**Tables written:**
| Table | Role |
|-------|------|
| `po_lifecycle` | Current state per PO |
| `lifecycle_events` | Append-only audit log |
| `lifecycle_violations` | Violation records (quantity mismatch, terminal reentry, etc.) |
| `edi_interchange_log` | Dedup log keyed on ISA control number |

**Specialized:** The state machine transitions and violation rules are domain-specific. For a new project replace the transition table and violation checks with your business rules.

---

### 4E. Database Assertions

**Location:** `autoCertify/yaml/db_ops.yaml`

**Pattern:** Named SQL operations with typed parameters. The YAML engine binds params and executes.

```yaml
ops:
  assert_po_state:
    sql: |
      SELECT current_state FROM po_lifecycle
      WHERE po_number = :po_number
    assert:
      field: current_state
      equals: :expected_state

  assert_quantity_chain:
    sql: |
      SELECT ordered_qty, accepted_qty, shipped_qty, invoiced_qty
      FROM po_lifecycle WHERE po_number = :po_number
    assert:
      ordered_qty: :expected_ordered
      accepted_qty: :expected_accepted
```

**Specialized:** Every SQL query here is project-specific. For a new project define assertions against your schema.

---

### 4F. CLI Runner

**Location:** `tastecli/cli.py` + `autoCertify/scripts/run_certification.sh`

**Key flags:**
```bash
python -m tastecli \
  --yaml-dir autoCertify/yaml \   # points to YAML definitions
  --workflow edi_lifecycle \       # which workflow to run
  --headless \                     # no browser window (CI mode)
  --report                         # write markdown report to reports/
```

**Shell wrapper** (`run_certification.sh`) adds:
- `--gh-issue` flag: create GitHub issue on failure
- `--full` flag: run all 5 workflows in sequence
- Timestamped report filenames

**Specialized:** Only the `--yaml-dir` path changes per project. The CLI infrastructure is reusable.

---

### 4G. Report Generator

**Location:** `tastecli/cli.py` (report section) + `autoCertify/reports/`

**Output format:** Markdown with:
- Workflow name, date, total checks
- Pass/fail table per check ID
- Full JSON response for any failed step
- Summary counts at top

**Used by:** Mission Control backend (`mission-control/api/parsers.py`) to surface pass/fail counts in the React UI.

**Specialized:** Report template is reusable. Only the check IDs and field names differ.

---

### 4H. React UI (Mission Control)

**Location:** `mission-control/frontend/src/pages/AutoCertify.tsx`

**What it renders:**
- Workflow cards grid (5 workflows, check count, pass/fail tally from latest report)
- EDI state machine pipeline per workflow (e.g., `850 PO → 855 Ack → 856 ASN → 810 Invoice`)
- Step results table: check ID, label, status badge, duration
- Collapsible "Test Data" panel: workflow parameters + fixture file content preview

**Data sources:**
- `GET /api/cert/workflows` — workflow metadata + latest report tallies
- `GET /api/cert/workflows/{variant}/fixtures` — fixture file content
- `GET /api/runs?harness=cert` — run history (polled every 30s)

**Trigger:** F3 hotkey in Mission Control Layout.tsx

**Specialized:** The state machine pipeline visualization and fixture preview are EDI-specific. For a new project replace with your document types and transformation steps.

---

## 5. Specialization Map

This table shows exactly what to change when adapting autoCertify to a new project.

| Layer | File(s) | What is generic (keep) | What is specialized (replace) |
|-------|---------|------------------------|-------------------------------|
| **Fixture files** | `autoCertify/fixtures/` | Directory structure (happy_path/, violations/) | X12 format → your document format |
| **Global config** | `yaml/global.yaml` | Variable interpolation mechanism | partner IDs, slugs, prefixes, document version |
| **Workflow YAML** | `yaml/workflows/*.yaml` | Step ordering, store/expect fields, check IDs | Step types, fixture paths, expected states |
| **DB ops** | `yaml/db_ops.yaml` | Named-op + param-binding pattern | SQL queries → your schema |
| **YAML engine** | `tastecli/scenarios/yaml_engine.py` | Step dispatch loop, stored_vars, pass/fail tracking | `_run_edi_ingest()` → `_run_{your_step_type}()` |
| **API endpoint** | `portals/api.py` | Response contract shape, correlation ID, dedup pattern | X12 parsing helpers → your document parsers |
| **Lifecycle engine** | `lifecycle_engine/` | Transition + violation pattern, INSERT-ONLY events | State names, transition rules, violation types |
| **DB assertions** | `db_ops.yaml assert_* ops` | Assert-by-field pattern | Table names, column names, business invariants |
| **CLI flags** | `tastecli/cli.py` | `--yaml-dir`, `--workflow`, `--headless`, `--report` | Nothing — fully reusable |
| **React UI** | `AutoCertify.tsx` | Workflow cards grid, step table, collapsible test data | Pipeline diagram labels, fixture preview format |
| **Reports** | `autoCertify/reports/` | Markdown structure, NDJSON event format | Check ID prefixes, field names in tables |

### The three things that define a new project's certification suite

1. **Your fixture corpus** — the real documents that exercise your system (JSON, XML, CSV, etc.)
2. **Your workflow YAMLs** — the ordered sequence of steps + assertions that prove correctness
3. **Your db_ops.yaml** — the SQL assertions that confirm your schema ends up in the right state

Everything else (CLI, report generator, React UI, YAML engine dispatch) is infrastructure you carry forward unchanged.

---

## 6. Invariants to Carry Forward

These are not EDI-specific — they apply to any certification harness built on this pattern.

| Invariant | Rule |
|-----------|------|
| **Test data isolation** | All test records use a known prefix. Cleanup ops target only that prefix. Never touch production data. |
| **No mocks** | The certification harness tests the real API, real DB, real engine. Mocks defeat the purpose. |
| **YAML is the source of truth** | Business logic (what states are valid, what quantities must match) lives in YAML — not scattered across Python. |
| **INSERT-ONLY audit log** | The events table is append-only. Assertions read it; nothing deletes from it during a test run. |
| **Cleanup before, assert after** | Each workflow starts with cleanup steps to ensure a known baseline. Assertions come only after ingest steps. |
| **Fail fast** | The first assertion mismatch stops the workflow. No partial passes that hide downstream failures. |
| **Idempotent cleanup** | Cleanup ops use `WHERE po_number LIKE 'CERT%'` (or equivalent). Running cleanup twice is safe. |

---

## 7. Prompt Orchestration

Use the following prompts verbatim (or adapt them) to build an equivalent certification harness for a new project. Each prompt is scoped to one step — do not combine them.

---

### Phase 0 — Scope the domain

```
I want to build a YAML-driven certification harness for [PROJECT NAME].

The system has:
- A [document type] ingest API at [endpoint]
- A lifecycle / state machine with states: [list states]
- Data transformation steps: [describe what changes]
- A Postgres schema with tables: [list tables]

Before writing any code, confirm my understanding:
1. What is the document format (JSON / XML / CSV / X12)?
2. What is the primary key on every table?
3. What constitutes a "violation" in this domain?
4. What is the test data prefix I should use to isolate certification records?

Ask one clarifying question at a time. Do not write code until I confirm.
```

---

### Phase 1 — Fixture corpus

```
Create the fixture corpus for [PROJECT NAME] certification.

Directory: [project]/fixtures/
Subdirectories: happy_path/, violations/, [other scenarios]

For each fixture:
- Use the test prefix [PREFIX] for all primary keys
- Use synthetic sender/receiver IDs: [TEST_SENDER] / [TEST_RECEIVER]
- Show the first fixture file in full before writing the rest

Do not create the YAML workflows yet. Only fixtures.
```

---

### Phase 2 — global.yaml

```
Create [project]/yaml/global.yaml.

It must define:
- partner_id: "[test partner]"
- primary_key_prefix: "[PREFIX]"
- sender_id / receiver_id: "[TEST_SENDER]" / "[TEST_RECEIVER]"
- Any other base scope variables needed by all workflows

Do not create workflow files yet.
```

---

### Phase 3 — db_ops.yaml

```
Create [project]/yaml/db_ops.yaml.

Define named SQL operations for:
Mutations (cleanup_*):
- cleanup_[table]: DELETE FROM [table] WHERE [pk] LIKE '[PREFIX]%'
- [repeat for each table written by the lifecycle engine]

Assertions (assert_*):
- assert_[entity]_state: SELECT current_state FROM [table] WHERE [pk] = :pk_value
- assert_[quantity_field]: SELECT [field] FROM [table] WHERE [pk] = :pk_value
- [any domain-specific assertions]

Each op must have: sql, params list, and for assertions: assert.field + assert.equals.

Do not create workflow YAMLs yet.
```

---

### Phase 4 — Happy path workflow

```
Create [project]/yaml/workflows/[name]_lifecycle.yaml.

This is the happy path: one complete successful journey through all lifecycle states.

Workflow structure:
- id: [name]_lifecycle
- checks: [count]

Journey steps in order:
1. Cleanup step (type: db, op: cleanup_*)
2. Ingest step for first document (type: [your_type], fixture: happy_path/[file])
   - expect_status: processed
   - expect_new_state: [first state]
   - store: { [pk_field]: [pk_field] }
3. Assert state step (type: db, op: assert_[entity]_state)
4. Ingest step for second document...
[continue for each document in the lifecycle]

Use check IDs: [PREFIX]-LC-01, [PREFIX]-LC-02, ...

Do not create violation workflows yet.
```

---

### Phase 5 — Violation workflows

```
Create [project]/yaml/workflows/[name]_violations.yaml.

Each step tests one error scenario:
- [violation type 1]: expect_status: violation, expect_violation_type: [type]
- [violation type 2]: ...
- [duplicate scenario]: expect_status: duplicate

Use check IDs: [PREFIX]-VL-01, [PREFIX]-VL-02, ...

Before each violation test, include a cleanup step to reset state.
```

---

### Phase 6 — YAML engine step handler

```
I need to add a new step type "[your_type]" to tastecli/scenarios/yaml_engine.py.

Read the file first. Then add:

def _run_[your_type](self, step: dict, scope: dict) -> StepResult:
    """
    Handles steps of type '[your_type]'.
    Loads fixture from [project]/fixtures/{step['fixture']}.
    POSTs to {scope['base_url']}{step.get('endpoint', '/api/v1/[your_endpoint]')}.
    Validates response against expect_* fields in step.
    Stores named fields from response into self.stored_vars.
    """

Match the exact pattern of _run_edi_ingest(). Minimal diff — do not refactor surrounding code.
```

---

### Phase 7 — API endpoint

```
Read portals/api.py before writing anything.

Add endpoint: POST /api/v1/[your_path]/ingest

Responsibilities:
1. Parse [document format] envelope: extract sender, receiver, control number, document type
2. Resolve trading partner from [routing table]
3. Deduplicate by control number (log to [interchange_log table])
4. Extract primary key ([pk_field]) from document body using _extract_[pk]_from_[format]()
5. Extract [quantity/amount/other fields] using _extract_[field]_from_[format]()
6. Call [lifecycle engine entry point](payload, conn) synchronously
7. Query post-transition state from [lifecycle table]
8. Build human_message if violations exist using _build_human_message()
9. Return JSON matching this contract:
   { status, [pk_field], prior_state, new_state, is_terminal, violations, human_message, success, envelope }

Do not modify any existing endpoint signatures. Add after line [N].
One function at a time — write _extract_[pk]_from_[format]() first, wait for confirmation.
```

---

### Phase 8 — React UI component

```
Read mission-control/frontend/src/pages/AutoCertify.tsx before writing.

Create mission-control/frontend/src/pages/[YourCert].tsx modeled on AutoCertify.tsx.

Replace:
- "EDI state machine pipeline" visualization → "[Your domain] transformation pipeline"
- Fixture file preview → [your document format] preview
- Check ID prefix CERT- → [YOUR_PREFIX]-
- Workflow variant names → [your workflow names]

Keep identical:
- Workflow cards grid layout
- Step results table (id, label, status badge, duration)
- Collapsible test data panel structure
- API polling pattern (GET /api/cert/workflows, GET /api/runs?harness=cert)

Do not modify AutoCertify.tsx. Only create the new file.
```

---

### Phase 9 — Wire up and smoke test

```
I want to run the new certification suite end-to-end.

1. Start backends: bash scripts/restart_backends.sh
2. Run the happy path workflow in headed mode:
   python -m tastecli --yaml-dir [project]/yaml --workflow [name]_lifecycle
3. If it fails, show me the full step output. Do not guess at a fix — show me the error and ask.
4. Once happy path passes, run violations:
   python -m tastecli --yaml-dir [project]/yaml --workflow [name]_violations
5. Generate a report:
   python -m tastecli --yaml-dir [project]/yaml --workflow [name]_lifecycle --report

Run one workflow at a time. Stop at the first failure and wait for my input.
```

---

### Phase 10 — Full certification run script

```
Create [project]/scripts/run_certification.sh modeled on autoCertify/scripts/run_certification.sh.

It must:
- Accept --headless, --report, --gh-issue, --full flags
- Default to headed mode (no --headless) when flag is absent
- Run workflows in order: [lifecycle, change_order_or_equivalent, violations, duplicates, full]
- With --full: run all workflows and aggregate pass/fail counts
- With --gh-issue and failures: create a GitHub issue with label "[your-project],regression"
- Name reports: [project]/reports/{date}_{workflow}.md

Do not copy the script. Write it fresh from scratch targeting [project]/yaml.
```

---

*This document lives at `instructions/autocertify-blueprint.md`. It is a reference, not a runnable artifact.*
