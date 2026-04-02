# Trading Partner Onboarding Wizard — Options & Viability

## Problem Statement

Onboarding a new trading partner currently requires 5 manual steps across CLI, YAML files, and config edits (documented in `bevager_orchestration_prompt.md`). The portal UI is solid for reviewing configs and test results, but has no guided workflow for the creation side. We need a wizard that walks a mixed-skill audience through the full lifecycle from DSL import to comparison-ready configuration.

---

## Current State (what exists today)

| Capability | Backend API | Portal UI |
|---|---|---|
| Upload DSL + compile schema | `POST /api/validate/upload` | Validate page (file picker) |
| View compiled columns/types | Response includes columns, types, warnings | Validate page renders results |
| Read config.yaml | `GET /api/config` | Config page (read-only JSON dump) |
| Update csv_schema_registry entry | `PUT /api/config/registry/{name}` | **No UI** |
| Read compare rules | `GET /api/compare/profiles/{name}/rules` | Compare page (rules editor) |
| Write compare rules | `PUT /api/compare/profiles/{name}/rules` | Compare page (JSON editor) |
| Create new compare profile | **No API** | **No UI** |
| Create new csv_schema_registry entry | **No API** | **No UI** |

**Key gap:** No API endpoint to _create_ a new `csv_schema_registry` entry or a new `compare.profiles` entry. The PUT endpoint only updates existing entries.

---

## Recommended Approach: 3-Step Wizard on New "Onboard" Tab

A dedicated `Onboard` page with a horizontal stepper (Step 1 / 2 / 3) that carries state forward. Each step has a clear deliverable and validation gate before proceeding.

### Step 1: Import & Compile DSL

**What the user does:**
- Upload a DSL `.txt` file (reuse existing `validateUpload` infrastructure) OR enter a server-side path
- Optionally upload a sample data file for coverage analysis
- Click "Compile" — sees the compiled schema columns, types, type warnings inline
- Review and confirm the compilation looks correct

**What happens behind the scenes:**
- Calls existing `POST /api/validate/upload` (or `/validate` for path mode)
- Returns `ValidateResponse` with columns, types, transaction_type, compiled_yaml_path
- The compiled YAML is already written to `schemas/compiled/` by the validator

**Deliverable:** Compiled schema YAML on disk. Column metadata carried forward to Step 2.

**New backend work:** None — reuses existing validate endpoint. Minor enhancement: return the compiled schema's `compiled_yaml_path` as an absolute path so Step 2 can reference it.

---

### Step 2: Register Trading Partner

**What the user does:**
- Fill in a form with:
  - **Profile name** (e.g., `bevager_810`) — auto-suggested from DSL filename
  - **Trading partner** (e.g., `Bevager`) — free text
  - **Transaction type** (e.g., `810`) — dropdown or free text, pre-filled from Step 1's compiled schema
  - **Inbound directory** — text input for the data file directory path
  - **Match key** — either `json_path` (e.g., `header.InvoiceID`) with a dropdown of fields from Step 1's column list, or `segment`/`field` for X12
  - **Description** — free text
- Click "Register" — confirmation badge shows success

**What happens behind the scenes:**
- **New API endpoint:** `POST /api/config/register-partner` that:
  1. Adds entry to `csv_schema_registry` in `config.yaml`
  2. Adds entry to `compare.profiles` in `config.yaml`
  3. Creates a skeleton rules YAML file at `config/compare_rules/{profile_name}.yaml`
  4. Returns the created profile + rules file path

**Deliverable:** Config entries written, skeleton rules file created. Column metadata + profile name carried forward to Step 3.

**New backend work:** One new endpoint. Writes to `config.yaml` and creates rules file.

---

### Step 3: Configure Compare Rules

**What the user does:**
- See an **auto-generated rules grid** based on compiled schema columns:
  - Each row = one field from the schema
  - Columns: Field Name | Type (from DSL) | Severity (dropdown: hard/soft/ignore) | Numeric (checkbox, pre-checked for float/integer) | Ignore Case (checkbox) | Amount Variance (number input, shown only for numeric)
  - **Auto-defaults:** `float`/`integer` fields → `numeric: true, severity: hard`. `String` fields → `severity: hard`. A `*/*` default row at the bottom.
- Optionally clone from an existing profile's rules as a starting template
- Edit the grid, then click "Save Rules"
- Final confirmation: "Partner onboarded successfully — ready for comparison"

**What happens behind the scenes:**
- Reads auto-generated skeleton from Step 2 or loads a cloned template
- On save, calls existing `PUT /api/compare/profiles/{name}/rules` to write the YAML

**Deliverable:** Fully configured compare rules. Partner is ready for `pyedi compare`.

**New backend work:** Minor — a new endpoint or query param to list existing profiles' rules as clone templates. The actual save reuses the existing rules PUT endpoint.

---

## Backend API Changes Required

| Endpoint | Method | Purpose | Effort |
|---|---|---|---|
| `/api/config/register-partner` | POST | Create csv_schema_registry + compare profile + skeleton rules | Medium |
| `/api/compare/profiles/{name}/rules-template` | GET | Generate auto-populated rules from compiled schema columns | Low |
| Enhance `/api/validate/upload` | - | Ensure `compiled_yaml_path` is returned as usable reference | Trivial |

---

## Frontend Components

| Component | Purpose |
|---|---|
| `OnboardPage.tsx` | Top-level page with stepper state machine |
| `OnboardStep1.tsx` | DSL upload/compile (reuses Validate page patterns) |
| `OnboardStep2.tsx` | Registration form with pre-filled fields |
| `OnboardStep3.tsx` | Rules grid editor with auto-generation |
| Stepper/progress bar | Visual 1-2-3 indicator with back/next navigation |

---

## Wizard State Flow

```
Step 1 (Compile)                    Step 2 (Register)              Step 3 (Rules)
┌─────────────────┐                ┌──────────────────┐           ┌─────────────────┐
│ Upload DSL file  │───compile───▶│ Profile name      │──register─▶│ Field grid       │
│ + sample (opt)   │               │ Trading partner   │           │ [auto-generated] │
│                  │               │ Transaction type  │           │                  │
│ See: columns,    │               │ Inbound dir       │           │ Severity dropdown │
│ types, warnings  │               │ Match key field   │           │ Numeric checkbox  │
│                  │               │ Description       │           │ Ignore case       │
└─────────────────┘                └──────────────────┘           └─────────────────┘
     carries forward:                   carries forward:              final output:
     - columns[]                        - profile name                - rules YAML saved
     - compiled_yaml_path               - rules_file path             - partner ready
     - transaction_type                 - column metadata
```

---

## Alternative Approaches Considered

### A) Extend Validate Page (rejected)
- Pro: Less navigation, reuses existing page
- Con: Overloads the Validate page purpose. Steps 2-3 have nothing to do with validation. Mixed audience would find it confusing.

### B) Config-file-only (no wizard UI)
- Pro: Zero frontend work — document the YAML edits
- Con: Defeats the purpose. Business users can't do this. Error-prone even for technical users.

### C) Single-page form (no stepper)
- Pro: Simpler component structure
- Con: Too many fields at once for mixed audience. No intermediate validation gates. Can't show compilation results before asking for registration details.

---

## Viability Assessment

| Factor | Rating | Notes |
|---|---|---|
| Backend feasibility | High | One new endpoint. All heavy lifting (DSL parsing, schema compilation, YAML read/write) already exists. |
| Frontend feasibility | High | Stepper pattern is standard React. Step 1 reuses Validate page components. Step 3 reuses Compare rules patterns. |
| Reuse of existing code | ~70% | Validate upload, rules PUT, config read — all exist. Only registration endpoint is new. |
| Risk | Low | Wizard writes the same files that manual CLI steps write. No new data formats or storage. |
| Estimated scope | Medium | ~1 new backend endpoint, 4-5 new React components, updates to App.tsx/api.ts |
