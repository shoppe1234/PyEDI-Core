# PyEDI Portal — Orchestration Prompt

**Purpose:** Execute all tasks from `instructions/pyedi_portal_plan.md` sequentially across four phases, with built-in verification after each task. Each phase has a gate — do not advance to the next phase until the gate passes.

**Codebase context:**
- Python project: `pyedi_core/` (EDI/CSV/XML processing pipeline)
- Tests: `tests/` (pytest — 143+ baseline: 86 unit, 57 integration)
- Coding standards: see `CLAUDE.md` (read before writing, minimal diffs, match patterns, type hints, explicit error handling)
- Plan document: `instructions/pyedi_portal_plan.md` (architecture, endpoint specs, page layouts)
- Prior tiers complete: Tiers 1-4 (2026-03-17 through 2026-03-24)

---

## Rules of Engagement

1. **Sequential within phases** — complete each task fully (including its test gate) before starting the next task within a phase.
2. **Phase gates are hard stops** — do not start Phase B until Phase A gate passes. Do not start Phase C until Phase B gate passes.
3. **Read before writing** — always read the target file and its imports before making any change.
4. **Minimal diffs** — change only what the task requires. No drive-by fixes, no opportunistic refactoring.
5. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
6. **Stop on red** — if any test gate fails, diagnose and fix before proceeding. Do not skip.
7. **No business logic in API or UI layers** — Phase B endpoints are thin wrappers. Phase C renders data. All logic stays in `pyedi_core/`.
8. **CLI must still work standalone** — at no point should the portal be required for `pyedi run`, `pyedi test`, or `pyedi validate` to function.

---

## Pre-Flight

Before starting any task:

```bash
# Verify clean baseline — all existing tests must pass
pytest tests/ -v --tb=short 2>&1 | tail -20

# Capture baseline test count for comparison
pytest tests/ -v --tb=short 2>&1 | grep -E "passed|failed|error"

# Verify pyedi CLI is functional
python -m pyedi_core.main test --verify

# Confirm project structure
ls pyedi_core/core/schema_compiler.py pyedi_core/pipeline.py pyedi_core/main.py pyedi_core/__init__.py
```

If any tests fail at baseline, **stop and fix them first** — do not begin new work on a red suite.

---

# PHASE A: Backend Engine

> **Prerequisite:** Green test suite.
> **Deliverables:** Compiler bug fixes, `parse_dsl_file()` helper, `validator.py` module, `validate` CLI subcommand, validator tests.
> **Duration:** 6 tasks.

---

## Task A1: Fix Bug 1 — Type loss in `_compile_to_yaml()` dedup

**Investigate:**
```bash
# Read the target function
# Focus on _compile_to_yaml() lines 120-242 and the dedup block at lines 233-240

# Read both DSL files to understand the field types declared
# gfsGenericOut810FF.txt — Header has String fields, Details has Decimal/Integer
# tpm810SourceFF.txt — Header has String + Decimal, Detail has Decimal

# Read compiled output to confirm the bug
# schemas/compiled/gfs_ca_810_map.yaml — expect all types are "string" (the bug)
```

**Root Cause:** `_compile_to_yaml()` dedup block (lines 233-240) keeps the **first occurrence** by name. When Header (all `String`) is parsed before Details (`Decimal`), the Header's `string` type wins for shared field names.

**Execute:**
1. Read `pyedi_core/core/schema_compiler.py` — locate the dedup block at lines 233-240
2. Replace the dedup logic with type-specificity-aware dedup:
   - When a field name appears multiple times with different types, keep the most specific type
   - Specificity order: `float` > `integer` > `date` > `boolean` > `string`
   - Implementation: build a dict keyed by `col['name']`, for each duplicate compare types and keep the winner
3. Do NOT change any other part of `_compile_to_yaml()`

**Test Gate:**
```bash
# Existing tests still pass
pytest tests/test_core.py -v --tb=short -k "schema or compile"

# Verify the fix works on the real DSL
python -c "
from pyedi_core.core.schema_compiler import _parse_dsl_record, _compile_to_yaml
import re

with open('schemas/source/gfsGenericOut810FF.txt', 'r') as f:
    content = f.read()

delimiter = ','
delim_match = re.search(r'delimiter\s*=\s*[\'\"](.*?)[\'\"]', content)
if delim_match:
    delimiter = delim_match.group(1)

record_matches = []
start_pattern = re.compile(r'def\s+record\s+\w+\s*\{')
search_pos = 0
while True:
    match = start_pattern.search(content, search_pos)
    if not match:
        break
    start_idx = match.start()
    brace_count = 0
    end_idx = -1
    for i in range(match.end() - 1, len(content)):
        if content[i] == '{':
            brace_count += 1
        elif content[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break
    if end_idx != -1:
        record_matches.append(content[start_idx:end_idx])
        search_pos = end_idx
    else:
        break

record_defs = [_parse_dsl_record(m) for m in record_matches]
yaml_map = _compile_to_yaml(record_defs, 'gfsGenericOut810FF.txt', delimiter)

# Check that Decimal fields compiled as float, not string
cols = {c['name']: c['type'] for c in yaml_map['schema']['columns']}
assert cols.get('CaseSize') == 'float', f'CaseSize is {cols.get(\"CaseSize\")} — expected float'
assert cols.get('CasePrice') == 'float', f'CasePrice is {cols.get(\"CasePrice\")} — expected float'
print('BUG 1 FIX VERIFIED: Decimal fields compile as float')
"

# Full suite
pytest tests/ -v --tb=short
```

**Commit:** `fix(compiler): prefer most specific type during column deduplication`

---

## Task A2: Fix Bug 2 — fieldIdentifier collision in `_compile_to_yaml()`

**Investigate:**
```bash
# Line 162 of schema_compiler.py:
#   yaml_map["schema"]["records"][record_def["fieldIdentifier"]] = []
# This overwrites when multiple records share the same fieldIdentifier value.

# gfsGenericOut810FF.txt has Header, Details, Summary all with fieldIdentifier value = "0"
# This causes records{} to be empty or contain only the last record's fields.

# The CSV handler (csv_handler.py line 109) uses records[record_id] for positional column mapping.
# Merging different record types under one key breaks positional mapping.
```

**Execute:**
1. Read `pyedi_core/core/schema_compiler.py` — locate line 161-168 (the fieldIdentifier block)
2. Change the logic so that when a fieldIdentifier value is already in `records{}`:
   - Use the **record name** (e.g., `"Header"`, `"Details"`) as the key instead
   - This preserves distinct column lists per record type for positional parsing
3. The first record with a given fieldIdentifier still uses the fieldIdentifier as key (backward compatible for non-colliding DSLs like `tpm810SourceFF.txt`)
4. Do NOT modify `csv_handler.py` — the handler already iterates `records[record_id]` generically

**Test Gate:**
```bash
# Existing tests still pass
pytest tests/test_core.py -v --tb=short -k "schema or compile"

# Verify the fix on the colliding DSL
python -c "
from pyedi_core.core.schema_compiler import _parse_dsl_record, _compile_to_yaml
import re

with open('schemas/source/gfsGenericOut810FF.txt', 'r') as f:
    content = f.read()

delimiter = ','
delim_match = re.search(r'delimiter\s*=\s*[\'\"](.*?)[\'\"]', content)
if delim_match:
    delimiter = delim_match.group(1)

record_matches = []
start_pattern = re.compile(r'def\s+record\s+\w+\s*\{')
search_pos = 0
while True:
    match = start_pattern.search(content, search_pos)
    if not match:
        break
    start_idx = match.start()
    brace_count = 0
    end_idx = -1
    for i in range(match.end() - 1, len(content)):
        if content[i] == '{':
            brace_count += 1
        elif content[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break
    if end_idx != -1:
        record_matches.append(content[start_idx:end_idx])
        search_pos = end_idx
    else:
        break

record_defs = [_parse_dsl_record(m) for m in record_matches]
yaml_map = _compile_to_yaml(record_defs, 'gfsGenericOut810FF.txt', delimiter)

records = yaml_map['schema']['records']
assert len(records) > 0, f'records is empty — collision not handled'
print(f'Record keys: {list(records.keys())}')
for k, v in records.items():
    print(f'  {k}: {len(v)} fields')
print('BUG 2 FIX VERIFIED: fieldIdentifier collision produces distinct record keys')
"

# Verify non-colliding DSL still works (tpm810SourceFF uses distinct HDR/DTL/etc.)
python -c "
from pyedi_core.core.schema_compiler import _parse_dsl_record, _compile_to_yaml
import re

with open('tpm810SourceFF.txt', 'r') as f:
    content = f.read()

delimiter = '|'
delim_match = re.search(r'delimiter\s*=\s*[\'\"](.*?)[\'\"]', content)
if delim_match:
    delimiter = delim_match.group(1)

record_matches = []
start_pattern = re.compile(r'def\s+record\s+\w+\s*\{')
search_pos = 0
while True:
    match = start_pattern.search(content, search_pos)
    if not match:
        break
    start_idx = match.start()
    brace_count = 0
    end_idx = -1
    for i in range(match.end() - 1, len(content)):
        if content[i] == '{':
            brace_count += 1
        elif content[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break
    if end_idx != -1:
        record_matches.append(content[start_idx:end_idx])
        search_pos = end_idx
    else:
        break

record_defs = [_parse_dsl_record(m) for m in record_matches]
yaml_map = _compile_to_yaml(record_defs, 'tpm810SourceFF.txt', delimiter)

records = yaml_map['schema']['records']
assert 'HDR' in records, f'HDR not found — keys: {list(records.keys())}'
assert 'DTL' in records, f'DTL not found — keys: {list(records.keys())}'
print(f'Non-colliding DSL still works. Keys: {list(records.keys())}')
"

# Full suite
pytest tests/ -v --tb=short
```

**Commit:** `fix(compiler): handle fieldIdentifier collisions using record name as fallback key`

---

## Task A3: Extract `parse_dsl_file()` helper in `schema_compiler.py`

**Investigate:**
```bash
# Read compile_dsl() — lines 245-400
# Lines 337-378 contain the DSL parsing logic:
#   read file → regex delimiter → brace-count record blocks → _parse_dsl_record each
# This logic needs to be reusable by the validator without triggering file writes.
```

**Execute:**
1. Read `pyedi_core/core/schema_compiler.py` — identify lines 337-378 (the parsing block inside `compile_dsl()`)
2. Extract into a new public function `parse_dsl_file(source_file: str) -> Tuple[List[Dict[str, Any]], str]`
3. Place it above `compile_dsl()` in the file
4. Refactor `compile_dsl()` to call `parse_dsl_file()` instead of the inline parsing logic
5. Verify: `compile_dsl()` produces identical output before and after — this is a pure refactor

**Test Gate:**
```bash
# Existing tests
pytest tests/test_core.py -v --tb=short -k "schema or compile"

# Verify the new function is importable and works
python -c "
from pyedi_core.core.schema_compiler import parse_dsl_file
record_defs, delimiter = parse_dsl_file('tpm810SourceFF.txt')
print(f'Records: {len(record_defs)}, Delimiter: \"{delimiter}\"')
for r in record_defs:
    print(f'  {r[\"name\"]}: {len(r[\"fields\"])} fields (type: {r[\"type\"]})')
"

# Verify compile_dsl still works end-to-end
python -c "
from pyedi_core.core.schema_compiler import compile_dsl
import tempfile, os
tmp = tempfile.mkdtemp()
result = compile_dsl('tpm810SourceFF.txt', compiled_dir=tmp)
print(f'transaction_type: {result[\"transaction_type\"]}')
print(f'columns: {len(result[\"schema\"][\"columns\"])}')
# Cleanup
import shutil
shutil.rmtree(tmp)
print('compile_dsl() still works after refactor')
"

# Full suite
pytest tests/ -v --tb=short
```

**Commit:** `refactor(compiler): extract parse_dsl_file() public helper from compile_dsl()`

---

## Task A4: Create `pyedi_core/validator.py`

**Investigate:**
```bash
# Read the plan: instructions/pyedi_portal_plan.md Phase A, Step A3
# Read the detailed spec: instructions/validate_subcommand_plan.md Step 3

# Read files the validator will import:
#   pyedi_core/core/schema_compiler.py — parse_dsl_file, _compile_to_yaml, compute_file_hash
#   pyedi_core/core/mapper.py — load_map, map_data
#   pyedi_core/drivers/csv_handler.py — CSVHandler, set_compiled_yaml_path
```

**Execute:**
1. Read imports: `schema_compiler.py`, `mapper.py`, `csv_handler.py` — understand the functions to call
2. Create `pyedi_core/validator.py` with:
   - Dataclasses: `ColumnInfo`, `TypeWarning`, `FieldTrace`, `CoverageReport`, `ValidationResult`
   - Functions:
     - `validate(dsl_path, sample_path=None, compiled_dir="./schemas/compiled") -> ValidationResult` — orchestrator
     - `compile_and_write(dsl_path, compiled_dir) -> Tuple[Dict, str, List[Dict]]` — parse + compile + write YAML + meta.json
     - `check_type_preservation(record_defs, compiled_yaml) -> List[TypeWarning]` — compare DSL vs compiled types
     - `check_compilation_warnings(record_defs) -> List[str]` — detect fieldIdentifier collisions etc.
     - `run_sample(compiled_yaml, compiled_yaml_path, sample_path) -> Tuple[Dict, Dict]` — CSVHandler.read + mapper.map_data
     - `compute_coverage(raw_data, mapped_data, compiled_yaml) -> CoverageReport` — mapped/unmapped counts
     - `compute_field_traces(raw_data, mapped_data, compiled_yaml, max_rows=3) -> List[List[FieldTrace]]` — per-row trace
3. All functions must have type hints on signatures
4. All exceptions must be specific (no bare `except`)
5. `compile_and_write` writes YAML via `yaml.dump()` and meta.json with source hash — same format as `compile_dsl()` output

**Test Gate:**
```bash
# Smoke test: compile-only validation
python -c "
from pyedi_core.validator import validate
result = validate('tpm810SourceFF.txt')
print(f'DSL: {result.dsl_path}')
print(f'Compiled to: {result.compiled_yaml_path}')
print(f'Columns: {len(result.columns)}')
print(f'Type warnings: {len(result.type_warnings)}')
print(f'Compilation warnings: {len(result.compilation_warnings)}')
print(f'Records: {list(result.records.keys())}')
"

# Smoke test: validate with sample file
python -c "
from pyedi_core.validator import validate
result = validate('tpm810SourceFF.txt', sample_path='tests/user_supplied/inputs/NA_810_MARGINEDGE_20260129.txt')
print(f'Sample rows: {result.sample_row_count}')
print(f'Coverage: {result.coverage.coverage_pct:.1f}%')
print(f'Unmapped: {result.coverage.source_fields_unmapped[:3]}')
print(f'Field traces: {len(result.field_traces)} rows')
if result.field_traces:
    print(f'First trace row has {len(result.field_traces[0])} fields')
"

# Full suite
pytest tests/ -v --tb=short
```

**Commit:** `feat(validator): add pyedi_core/validator.py with compile, trace, and coverage`

---

## Task A5: Add `validate` subcommand to `main.py`

**Investigate:**
```bash
# Read main.py — understand the subparser pattern (run, test)
# Read test_harness.py — understand _handle_test as the model to follow
```

**Execute:**
1. Read `pyedi_core/main.py`
2. Add `validate` subparser after `test_parser`:
   - `--dsl` (required) — path to DSL .txt file
   - `--sample` — optional path to sample data file
   - `--json` — output JSON instead of report
   - `--verbose` / `-v` — show all field traces
   - `--output-dir` — compiled YAML output directory (default: `./schemas/compiled`)
3. Add dispatch: `if parsed.command == "validate": return _handle_validate(parsed)`
4. Add `_handle_validate(parsed) -> int` — calls `validator.validate()`, dispatches to print functions
5. Add `_print_validate_report(result, verbose)` — human-readable console output matching the format in `validate_subcommand_plan.md` Step 4
6. Add `_print_validate_json(result)` — JSON via `dataclasses.asdict()` + `json.dumps()`
7. Handle `--dsl` argument added to top-level parser too for backward compat (same pattern as run args)

**Test Gate:**
```bash
# CLI help works
python -m pyedi_core.main validate --help

# Compile-only
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt

# With sample
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt --sample tests/user_supplied/inputs/NA_810_MARGINEDGE_20260129.txt

# JSON output
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt --json

# GFS DSL (previously broken by type loss bug)
python -m pyedi_core.main validate --dsl schemas/source/gfsGenericOut810FF.txt

# Existing CLI still works
python -m pyedi_core.main test --verify
python -m pyedi_core.main --help

# Full suite
pytest tests/ -v --tb=short
```

**Commit:** `feat(cli): add pyedi validate subcommand with report and JSON output`

---

## Task A6: Add `tests/test_validator.py` + update `__init__.py`

**Execute:**
1. Create `tests/test_validator.py` with:
   - `test_compile_and_write_produces_yaml` — DSL compiles, file written, YAML has schema + mapping
   - `test_type_preservation_correct_tpm` — tpm810 Decimal→float, Integer→integer preserved
   - `test_type_preservation_fixed_gfs` — gfs Decimal→float after bug fix
   - `test_fieldidentifier_collision_handled` — gfs records{} is non-empty
   - `test_run_sample_produces_traces` — DSL + sample → field_traces has 3 rows
   - `test_coverage_report_counts` — coverage percentages correct
   - `test_validate_missing_dsl` — FileNotFoundError for nonexistent DSL
   - `test_validate_json_serializable` — ValidationResult serializes to JSON
   - Apply `@pytest.mark.unit` or `@pytest.mark.integration` markers appropriately
   - Use `tmp_path` fixture for compiled output to avoid polluting `schemas/compiled/`
2. Update `pyedi_core/__init__.py` — add `from .validator import validate` and `"validate"` to `__all__`

**Test Gate:**
```bash
# New tests pass
pytest tests/test_validator.py -v --tb=short

# Full suite — expect baseline + new tests (152+)
pytest tests/ -v --tb=short

# Verify export
python -c "from pyedi_core import validate; print('validate imported OK')"
```

**Commit:** `test(validator): add unit and integration tests for validator module`

---

## PHASE A GATE

**All of these must pass before starting Phase B:**

```bash
# 1. Full test suite green
pytest tests/ -v --tb=short

# 2. Validate CLI works end-to-end on both DSLs
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt
python -m pyedi_core.main validate --dsl schemas/source/gfsGenericOut810FF.txt

# 3. Validate with sample works
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt --sample tests/user_supplied/inputs/NA_810_MARGINEDGE_20260129.txt

# 4. JSON output works
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt --json | python -m json.tool > /dev/null

# 5. Existing CLI unchanged
python -m pyedi_core.main test --verify

# 6. Show commits
git log --oneline -6
```

**Checklist:**
- [ ] 0 test failures
- [ ] Compiler type loss fixed (gfs Decimal→float)
- [ ] Compiler fieldIdentifier collision fixed (gfs records{} non-empty)
- [ ] `parse_dsl_file()` extracted and used by both `compile_dsl()` and validator
- [ ] `pyedi validate` CLI works with `--dsl`, `--sample`, `--json`, `--verbose`
- [ ] `from pyedi_core import validate` works
- [ ] 6 clean commits

---

# PHASE B: FastAPI API Layer

> **Prerequisite:** Phase A gate passed.
> **Deliverables:** `portal/` directory with FastAPI app, route modules for validate/pipeline/test/manifest/config.
> **Duration:** 7 tasks.

---

## Task B1: Scaffold `portal/` directory + FastAPI app factory

**Execute:**
1. Create directory structure:
   ```
   portal/
   ├── api/
   │   ├── __init__.py
   │   ├── app.py
   │   ├── models.py
   │   └── routes/
   │       └── __init__.py
   └── pyproject.toml
   ```
2. `portal/pyproject.toml`: define package with dependencies `fastapi>=0.110`, `uvicorn>=0.27`, `python-multipart>=0.0.9`, and `pyedi-core` (local editable)
3. `portal/api/app.py`: FastAPI app factory with CORS middleware (origins: `localhost:5173`, `localhost:3000`), health endpoint `GET /api/health → {"status": "ok"}`
4. `pip install -e ./portal`

**Test Gate:**
```bash
# App starts
timeout 5 uvicorn portal.api.app:app --port 8000 || true

# Health check
uvicorn portal.api.app:app --port 8000 &
sleep 2
curl -s http://localhost:8000/api/health
kill %1 2>/dev/null

# Existing tests still pass
pytest tests/ -v --tb=short
```

**Commit:** `feat(portal): scaffold FastAPI app with CORS and health endpoint`

---

## Task B2: Pydantic models (`portal/api/models.py`)

**Execute:**
1. Read `pyedi_core/validator.py` dataclasses — mirror them as Pydantic models for the API
2. Read `pyedi_core/pipeline.py` `PipelineResult` — mirror for pipeline responses
3. Create request/response models:
   - `ValidateRequest(dsl_path, sample_path?, output_dir?)`
   - `ValidateResponse` — mirrors `ValidationResult`
   - `PipelineRunRequest(file?, files?, dry_run?)`
   - `PipelineResponse` — mirrors `PipelineResult`
   - `TestRunRequest(metadata_path?, verbose?)`
   - `TestCaseResult(name, status, details)`
   - `TestRunResponse(total, passed, failed, warned, cases: List[TestCaseResult])`
   - `ManifestEntry(hash, filename, timestamp, status)`
   - `ManifestStatsResponse(total, success, failed, skipped)`
   - `ConfigResponse` — full config as dict

**Test Gate:**
```bash
# Models import without error
python -c "from portal.api.models import ValidateRequest, PipelineRunRequest, ManifestEntry; print('Models OK')"
```

**Commit:** `feat(portal): add Pydantic request/response models`

---

## Task B3: Validate routes (`portal/api/routes/validate.py`)

**Execute:**
1. Create `portal/api/routes/validate.py` with a FastAPI `APIRouter(prefix="/api/validate")`
2. Endpoints:
   - `POST /api/validate` — accepts `ValidateRequest` JSON, calls `validator.validate()`, returns `ValidateResponse`
   - `POST /api/validate/upload` — accepts multipart (DSL file + optional sample file), saves to temp dir, calls `validator.validate()`, cleans up temp files in `finally`
   - `GET /api/validate/history` — reads validation reports from `reports/validate/` (create dir if needed), returns list
3. Register router in `app.py`
4. All endpoints call `pyedi_core` functions — no business logic in the route

**Test Gate:**
```bash
# Start server
uvicorn portal.api.app:app --port 8000 &
sleep 2

# Test path-based validate
curl -s -X POST http://localhost:8000/api/validate \
  -H "Content-Type: application/json" \
  -d '{"dsl_path":"tpm810SourceFF.txt"}' | python -m json.tool | head -20

# Test file upload validate
curl -s -X POST http://localhost:8000/api/validate/upload \
  -F "dsl_file=@tpm810SourceFF.txt" | python -m json.tool | head -20

# Test history (may be empty)
curl -s http://localhost:8000/api/validate/history | python -m json.tool

kill %1 2>/dev/null

# Existing tests
pytest tests/ -v --tb=short
```

**Commit:** `feat(portal): add /api/validate endpoints`

---

## Task B4: Pipeline routes (`portal/api/routes/pipeline.py`)

**Execute:**
1. Create `portal/api/routes/pipeline.py` with `APIRouter(prefix="/api/pipeline")`
2. Endpoints:
   - `POST /api/pipeline/run` — accepts `PipelineRunRequest`, calls `Pipeline(config_path).run()`, returns `PipelineResponse` or list
   - `POST /api/pipeline/upload` — multipart file(s), saves to appropriate inbound dir, runs pipeline
   - `GET /api/pipeline/results` — reads `outbound/` for SUCCESS, `failed/` for FAILED, returns list with query filters `?status=&limit=`
   - `GET /api/pipeline/results/{correlation_id}` — reads specific output JSON + error.json sidecar
3. Register router in `app.py`

**Test Gate:**
```bash
uvicorn portal.api.app:app --port 8000 &
sleep 2

# Test results listing (may be empty or populated from prior runs)
curl -s http://localhost:8000/api/pipeline/results | python -m json.tool | head -10

kill %1 2>/dev/null

pytest tests/ -v --tb=short
```

**Commit:** `feat(portal): add /api/pipeline endpoints`

---

## Task B5: Test harness routes (`portal/api/routes/test.py`)

**Execute:**
1. Create `portal/api/routes/test.py` with `APIRouter(prefix="/api/test")`
2. Endpoints:
   - `POST /api/test/run` — calls `test_harness.run_tests()`, captures output, returns structured results
   - `GET /api/test/cases` — reads `tests/user_supplied/metadata.yaml`, returns list of test cases
   - `POST /api/test/generate-expected` — calls `test_harness.generate_expected()`, returns results
   - `GET /api/test/verify` — calls `test_harness.verify()`, returns env check results
3. **Important:** `test_harness.run_tests()` currently prints to stdout and returns an int. You may need to refactor it to return structured data, OR capture stdout. Prefer: add an optional `return_results=True` parameter to `run_tests()` that returns a list of result dicts instead of printing. This is a minimal change to `test_harness.py`.
4. Register router in `app.py`

**Test Gate:**
```bash
uvicorn portal.api.app:app --port 8000 &
sleep 2

# Test cases listing
curl -s http://localhost:8000/api/test/cases | python -m json.tool

# Verify environment
curl -s http://localhost:8000/api/test/verify | python -m json.tool

kill %1 2>/dev/null

pytest tests/ -v --tb=short
```

**Commit:** `feat(portal): add /api/test endpoints`

---

## Task B6: Manifest + Config routes

**Execute:**
1. Create `portal/api/routes/manifest.py` with `APIRouter(prefix="/api/manifest")`
   - `GET /api/manifest` — reads `.processed` file, parses lines, filters by `?status=&search=`, paginates by `?offset=&limit=`
   - `GET /api/manifest/stats` — aggregates counts by status
2. Create `portal/api/routes/config.py` with `APIRouter(prefix="/api/config")`
   - `GET /api/config` — reads `config/config.yaml`, returns as JSON
   - `GET /api/config/registry` — returns `transaction_registry` + `csv_schema_registry` subset
   - `PUT /api/config/registry/{entry_name}` — updates a `csv_schema_registry` entry in `config.yaml`
3. Register both routers in `app.py`

**Test Gate:**
```bash
uvicorn portal.api.app:app --port 8000 &
sleep 2

# Manifest stats
curl -s http://localhost:8000/api/manifest/stats | python -m json.tool

# Config
curl -s http://localhost:8000/api/config | python -m json.tool | head -20

# Registry
curl -s http://localhost:8000/api/config/registry | python -m json.tool

kill %1 2>/dev/null

pytest tests/ -v --tb=short
```

**Commit:** `feat(portal): add /api/manifest and /api/config endpoints`

---

## Task B7: API integration tests

**Execute:**
1. Create `portal/tests/test_api.py` (or `tests/test_api.py`):
   - Use `httpx.AsyncClient` with FastAPI `TestClient` pattern
   - `test_health` — GET /api/health returns 200
   - `test_validate_path` — POST /api/validate with dsl_path returns valid result
   - `test_validate_upload` — POST /api/validate/upload with file returns valid result
   - `test_pipeline_results` — GET /api/pipeline/results returns 200
   - `test_test_cases` — GET /api/test/cases returns list
   - `test_manifest_stats` — GET /api/manifest/stats returns counts
   - `test_config` — GET /api/config returns YAML-parseable dict

**Test Gate:**
```bash
# API tests
pytest portal/tests/test_api.py -v --tb=short || pytest tests/test_api.py -v --tb=short

# Full engine suite still green
pytest tests/ -v --tb=short
```

**Commit:** `test(portal): add API integration tests`

---

## PHASE B GATE

```bash
# 1. All engine tests green
pytest tests/ -v --tb=short

# 2. All API tests green
pytest portal/tests/ -v --tb=short 2>/dev/null || pytest tests/test_api.py -v --tb=short

# 3. Server starts and all endpoints respond
uvicorn portal.api.app:app --port 8000 &
sleep 2
curl -sf http://localhost:8000/api/health
curl -sf http://localhost:8000/api/manifest/stats
curl -sf http://localhost:8000/api/config
curl -sf http://localhost:8000/api/test/cases
curl -sf -X POST http://localhost:8000/api/validate -H "Content-Type: application/json" -d '{"dsl_path":"tpm810SourceFF.txt"}' > /dev/null
kill %1 2>/dev/null

# 4. CLI still standalone
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt --json > /dev/null

# 5. Show commits
git log --oneline -7
```

**Checklist:**
- [ ] 0 test failures (engine + API)
- [ ] All 5 route modules registered and responding
- [ ] File upload endpoints work
- [ ] Manifest parses `.processed` file correctly
- [ ] Config read/write works
- [ ] CLI still standalone (no portal dependency)
- [ ] 7 clean commits

---

# PHASE C: React Frontend

> **Prerequisite:** Phase B gate passed.
> **Deliverables:** React app at `portal/frontend/` with 4 pages.
> **Duration:** 8 tasks.

---

## Task C1: Scaffold React + Vite + Tailwind project

**Execute:**
```bash
cd portal
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install react-router-dom @tanstack/react-query
```

1. Configure Tailwind in `tailwind.config.js` (content paths: `./src/**/*.{ts,tsx}`)
2. Add `@tailwind` directives to `src/index.css`
3. Configure Vite proxy in `vite.config.ts`: `/api` → `http://localhost:8000`
4. Verify dev server starts: `npm run dev`

**Test Gate:**
```bash
cd portal/frontend && npm run build
# Build succeeds with 0 errors
```

**Commit:** `feat(portal): scaffold React + Vite + Tailwind frontend`

---

## Task C2: Shared components + types + API client

**Execute:**
1. `src/types/api.ts` — TypeScript interfaces matching `portal/api/models.py` Pydantic models
2. `src/api/client.ts` — typed fetch functions for every endpoint (reusable across pages)
3. `src/components/Layout.tsx` — sidebar with nav links to `/validate`, `/pipeline`, `/test`, `/manifest` + content area
4. `src/components/StatusBadge.tsx` — colored badges for SUCCESS (green), FAILED (red), SKIPPED (gray), WARN (yellow), PASS (green)
5. `src/components/CollapsiblePanel.tsx` — title + toggle + animated content reveal
6. `src/components/DataTable.tsx` — sortable, typed table component
7. `src/components/FileUpload.tsx` — drag-and-drop zone with file type filter
8. `src/components/JsonPreview.tsx` — `<pre>` with syntax highlighting (use simple CSS, no heavy library)
9. `src/App.tsx` — React Router setup with Layout wrapper and route definitions

**Test Gate:**
```bash
cd portal/frontend && npm run build
# Build succeeds, no type errors
```

**Commit:** `feat(portal): add shared components, API client, and routing`

---

## Task C3: Validate page (`/validate`)

**Execute:**
1. Create `src/pages/Validate.tsx` — see layout spec in `pyedi_portal_plan.md` Page 1
2. Sections:
   - File upload form (DSL + optional sample)
   - Compilation report summary card
   - Schema columns table with StatusBadge per row (OK / LOST)
   - Type warnings section (collapsible, red)
   - Record definitions section (collapsible)
   - Mapping coverage with progress bar (only with sample)
   - Field trace table — first 3 rows (expandable)
   - Collapsible panels for compiled YAML preview and DSL source preview
3. Use `@tanstack/react-query` `useMutation` for the POST /api/validate/upload call
4. Loading states, error states, empty states all handled

**Test Gate:**
```bash
cd portal/frontend && npm run build

# Manual: start both servers
# Terminal 1: uvicorn portal.api.app:app --reload --port 8000
# Terminal 2: cd portal/frontend && npm run dev
# Navigate to http://localhost:5173/validate
# Upload tpm810SourceFF.txt → see compilation report
# Upload tpm810SourceFF.txt + NA_810_MARGINEDGE_20260129.txt → see field traces + coverage
```

**Commit:** `feat(portal): add Validate page with DSL compilation and mapping trace`

---

## Task C4: Pipeline page (`/pipeline`)

**Execute:**
1. Create `src/pages/Pipeline.tsx` — see layout spec in `pyedi_portal_plan.md` Page 2
2. Sections:
   - File upload form with dry-run checkbox
   - Results table (file, status badge, type, time, actions)
   - Failure detail panel (stage, error, correlation ID, collapsible error.json)
   - Batch summary counts
3. Use `useQuery` to poll `GET /api/pipeline/results` every 10 seconds
4. Use `useMutation` for `POST /api/pipeline/upload`

**Test Gate:**
```bash
cd portal/frontend && npm run build
# Manual: navigate to /pipeline, upload a CSV, see result
```

**Commit:** `feat(portal): add Pipeline page with file processing and triage`

---

## Task C5: Test Harness page (`/test`)

**Execute:**
1. Create `src/pages/TestHarness.tsx` — see layout spec in `pyedi_portal_plan.md` Page 3
2. Sections:
   - Action buttons: Run Tests, Generate Expected, Verify Environment
   - Test cases table (name, status badge, details)
   - Environment verify section (collapsible)
   - Summary counts
3. Use `useMutation` for POST endpoints, `useQuery` for GET

**Test Gate:**
```bash
cd portal/frontend && npm run build
# Manual: navigate to /test, click Run Tests, see results
```

**Commit:** `feat(portal): add Test Harness page`

---

## Task C6: Manifest page (`/manifest`)

**Execute:**
1. Create `src/pages/Manifest.tsx` — see layout spec in `pyedi_portal_plan.md` Page 4
2. Sections:
   - Search input + status filter dropdown + stats summary
   - Processing history table (hash, filename, timestamp, status badge)
   - Pagination controls
3. Use `useQuery` with query params for `GET /api/manifest`

**Test Gate:**
```bash
cd portal/frontend && npm run build
# Manual: navigate to /manifest, see processing history
```

**Commit:** `feat(portal): add Manifest page with search and pagination`

---

## Task C7: Dev experience wiring

**Execute:**
1. Create `portal/dev.sh`:
   ```bash
   #!/bin/bash
   echo "Starting PyEDI Portal..."
   uvicorn portal.api.app:app --reload --port 8000 &
   API_PID=$!
   cd portal/frontend && npm run dev &
   VITE_PID=$!
   trap "kill $API_PID $VITE_PID 2>/dev/null" EXIT
   wait
   ```
2. Make executable: `chmod +x portal/dev.sh`
3. Update `portal/frontend/vite.config.ts` — ensure proxy is correct
4. Verify both servers start with one command

**Test Gate:**
```bash
bash portal/dev.sh &
sleep 5
curl -sf http://localhost:8000/api/health
curl -sf http://localhost:5173/ > /dev/null
kill %1 2>/dev/null
```

**Commit:** `feat(portal): add dev startup script`

---

## Task C8: Frontend build verification

**Execute:**
1. `cd portal/frontend && npm run build` — verify production build succeeds
2. Check for TypeScript errors: `npx tsc --noEmit`
3. Verify no unused imports or dead code warnings

**Test Gate:**
```bash
cd portal/frontend
npm run build
npx tsc --noEmit
echo "Frontend build clean"
```

**Commit:** `chore(portal): verify clean production build`

---

## PHASE C GATE

```bash
# 1. Frontend builds
cd portal/frontend && npm run build

# 2. No TypeScript errors
cd portal/frontend && npx tsc --noEmit

# 3. Backend tests green
pytest tests/ -v --tb=short

# 4. API tests green
pytest portal/tests/ -v --tb=short 2>/dev/null || pytest tests/test_api.py -v --tb=short

# 5. Dev script works
bash portal/dev.sh &
sleep 5
curl -sf http://localhost:8000/api/health
curl -sf http://localhost:5173/ > /dev/null
kill %1 2>/dev/null

# 6. CLI still standalone
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt --json > /dev/null
python -m pyedi_core.main test --verify
```

**Checklist:**
- [ ] Frontend production build succeeds with 0 errors
- [ ] No TypeScript errors
- [ ] All 4 pages render (Validate, Pipeline, Test, Manifest)
- [ ] File upload works on Validate and Pipeline pages
- [ ] All backend tests still green
- [ ] CLI still standalone
- [ ] Dev script starts both servers
- [ ] 8 clean commits

---

# POST-FLIGHT

After all phases complete:

```bash
# Final full verification
pytest tests/ -v --tb=short
pytest portal/tests/ -v --tb=short 2>/dev/null || true
cd portal/frontend && npm run build && npx tsc --noEmit
cd ../..

# CLI standalone
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt
python -m pyedi_core.main test --verify

# API standalone
timeout 5 uvicorn portal.api.app:app --port 8000 || true

# Show all commits
git log --oneline -21

# Show project structure
find portal/ -type f -name "*.py" -o -name "*.tsx" -o -name "*.ts" | head -30
```

**Final checklist:**
- [ ] Phase A: 6 commits — compiler fixes + validator + CLI + tests
- [ ] Phase B: 7 commits — FastAPI app + 5 route modules + API tests
- [ ] Phase C: 8 commits — scaffold + components + 4 pages + dev script + build verify
- [ ] 0 test failures across all suites
- [ ] CLI works without portal
- [ ] Portal works without modifying pyedi_core behavior
- [ ] `pyedi validate` produces correct reports for both DSL files
- [ ] React Validate page renders compilation report with field traces

---

## Resumption Protocol

If execution is interrupted mid-task:
1. Identify the last successful commit: `git log --oneline -5`
2. Determine which phase/task to resume from
3. Run the **pre-flight** check for the current phase:
   - Phase A: `pytest tests/ -v --tb=short`
   - Phase B: pre-flight + `uvicorn portal.api.app:app --port 8000` starts
   - Phase C: pre-flight + `cd portal/frontend && npm run build` succeeds
4. Resume from the current task's **Investigate** step
