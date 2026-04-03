# Tier 3 & Tier 4 — Remaining Tasks

**Source:** `REVIEW_REPORT.md` (2026-03-17 code review), updated 2026-04-03
**Baseline (at time of review):** 143 tests (86 unit, 57 integration). **Current:** 205 tests (127 unit, 71 integration), 0 failures. **Playwright E2E:** 10 tests (x12-wizard.spec.ts), all passing (2026-04-03)
**Prerequisites:** Tiers 1 and 2 complete

---

## Tier 3: Cleanup & Documentation

### Task 1: Delete 3 redundant root scripts

**Files to delete:**
- `generate_expected.py` (41 lines) — absorbed by `pyedi test --generate-expected`
- `verify_environment.py` (32 lines) — absorbed by `pyedi test --verify`
- `verify_structure.py` (46 lines) — absorbed by `pyedi test --verify`

**Rationale:** The `pyedi test` CLI subcommand (`pyedi_core/test_harness.py`) now provides all functionality these scripts offered. Zero imports from elsewhere in the codebase.

**Steps:**
1. Grep codebase for any imports or references to these filenames (expect: zero in code)
2. Delete all 3 files
3. Verify `pyedi test --verify` still works as replacement
4. Run full test suite

**Status:** [x] Complete

---

### Task 2: Delete 3 stale doc files

**Files to delete:**
- `AGENTIC_IDE_TEST_PROMPT.md` (368 lines) — stale workflow prompt, superseded by actual test harness
- `PROJECT_BRIEF.md` (0 lines) — empty placeholder
- `PyEDI_Core_Testing_Specification-user-supplied-v1.md` (1,844 lines) — v1.0 superseded by v1.2

**Files to keep (do NOT delete):**
- `SPECIFICATION.md` — historical reference
- `PyEDI_Core_Testing_Specification-user-supplied.md` — active v1.2

**Steps:**
1. Grep for references to these filenames in code/config (expect: zero)
2. Delete all 3 files
3. Run full test suite

**Status:** [x] Complete

---

### Task 3: Delete stale `rules/200220261215033.yaml` + root `rules/` dir

**File:** `rules/200220261215033.yaml` (7 lines)
**Issue:** Empty 810 mapping stub (no columns, no mappings). The pipeline's `_rules_dir` glob (`pipeline.py` line 522-523) picks up `./rules/*.yaml` as a fallback. The `_matches_mapping()` method (line 534-544) matches on transaction_type substring in filename — this stub has `transaction_type: "810"` which could false-match any file with "810" in its name.

**Steps:**
1. Read the file to confirm it's an empty stub
2. Verify the root `rules/` dir contains only this one file
3. Delete the file
4. Delete the `rules/` directory if now empty
5. Run full test suite (especially x12 integration tests)

**Status:** [x] Complete

---

### Task 4: Standardize YAML quoting conventions

**Issue:** 11 YAML files across the project use mixed quoting styles:
- `pyedi_core/rules/*.yaml` — single quotes for string values (`'810_INVOICE'`)
- `schemas/compiled/*.yaml` — unquoted values (`810_INVOICE`)
- `config/config.yaml` — mixed single-quoted and unquoted
- `tests/user_supplied/metadata.yaml` — double-quoted strings

**Proposed convention:**
- Single quotes for values YAML might misinterpret (numeric-looking: `'810'`, booleans, special chars)
- No quotes for plain unambiguous strings (`CSV`, `INFO`, `console`)
- Double quotes only when escape sequences are needed
- Single-quoted delimiters (`','`, `'|'`)

**Risk:** Changing `'810'` (string) to `810` (integer) would break transaction registry lookups. Each file must be validated: parse before and after, compare dicts are identical.

**Steps:**
1. For each of the 11 YAML files:
   a. Parse with `yaml.safe_load()` and save the result
   b. Apply quoting convention changes
   c. Parse again and compare — must be identical
   d. If types change, keep the original quoting for that value
2. Run full test suite

**Decision point:** This is low-value cosmetic work with type-coercion risk. May be skipped if user prefers.

**YAML files in scope:**
- `config/config.yaml`
- `pyedi_core/rules/cxml_850_map.yaml`
- `pyedi_core/rules/default_x12_map.yaml`
- `pyedi_core/rules/gfs_810_map.yaml`
- `pyedi_core/rules/gfs_850_map.yaml`
- `pyedi_core/rules/gfs_856_map.yaml`
- `pyedi_core/rules/gfs_csv_map.yaml`
- `schemas/compiled/margin_edge_810_map.yaml`
- `schemas/compiled/gfs_ca_810_map.yaml`
- `tests/user_supplied/metadata.yaml`

**Status:** [x] Skipped — user decision (added to TODO for future consideration)

---

## Tier 4: Test Coverage Expansion

### Task 5: Add cXML fixture + integration test (W53)

**Issue:** `TestCxmlParsing` in `tests/test_drivers.py` has 5 unit tests with inline XML strings but no real cXML fixture file and no integration test through the pipeline.

**Steps:**
1. Read `pyedi_core/rules/cxml_850_map.yaml` to understand expected mapping paths
2. Read `pyedi_core/drivers/xml_handler.py` cXML detection (lines 87-100) and parsing (lines 131-177)
3. Verify transaction registry path resolution: `config.yaml` references `./rules/cxml_850_map.yaml` but actual file is at `pyedi_core/rules/cxml_850_map.yaml` — check how pipeline resolves this
4. Create a realistic cXML 850 Purchase Order fixture at `tests/user_supplied/inputs/cxml_850_sample.cxml`:
   - Proper cXML envelope with Header/From/To
   - OrderRequest with OrderRequestHeader (orderID, orderDate)
   - 2-3 OrderRequestLine items with ItemID, Quantity, UnitPrice
   - Fields matching `cxml_850_map.yaml` source paths
5. Add test case to `tests/user_supplied/metadata.yaml` with `should_succeed: true` and `target_inbound_dir`
6. Generate expected output baseline
7. Run full test suite — expect 144+ passed

**Key concern:** The integration test `else` branch (line 71) only handles `transaction_type == 'x12'`. cXML tests need `target_inbound_dir` to go through the pipeline path, or the test code needs extending.

**Status:** [x] Complete

---

### Task 6: Add `should_succeed: false` failure-path test cases (W57)

**Issue:** The integration test at `tests/integration/test_user_supplied_data.py` supports `should_succeed: false` with `expected_error_stage` validation (lines 116-129), but all 3 existing test cases use `should_succeed: true`.

**Steps:**
1. Read the failure code path in `test_user_supplied_data.py` lines 116-129 carefully:
   - Line 117 references `result.status` — `result` is only assigned in the `if target_inbound_dir:` branch
   - Failure tests MUST set `target_inbound_dir` to go through the pipeline
   - `dry_run` must be `false` for error.json to be written to `./failed/`
2. Create 2-3 failure-inducing input files under `tests/user_supplied/inputs/`:
   - `malformed_x12.dat` — X12-like file with corrupted ISA/missing envelope
   - `unmapped_csv.csv` — valid CSV placed in directory with no matching `csv_schema_registry` entry
3. Add entries to `tests/user_supplied/metadata.yaml`:
   - Each with `should_succeed: false`, `expected_error_stage`, and `target_inbound_dir`
4. Run full test suite — expect 145+ passed
5. Clean up: ensure failure tests don't leave artifacts in `./failed/` (add cleanup in test's `finally` block or conftest)

**Status:** [x] Complete

---

### Task 7: Add concurrent batch processing stress test (W26)

**Issue:** `TestPipelineBatchProcessing` in `tests/test_drivers.py` has 6 tests but all use unrecognized file types (.xyz, .abc) that immediately fail. No test exercises concurrent successful processing or thread safety.

**Steps:**
1. Read `pipeline.py` `_process_batch()` (lines 371-446) — ThreadPoolExecutor, manifest dedup, future collection
2. Read `manifest.py` locking mechanism (`threading.Lock` at line 21)
3. Add new test class `TestPipelineConcurrency` in `tests/test_drivers.py`:
   - **Test 1 — Thread isolation:** Create 5+ CSV files in separate tmp subdirectories with matching schema registry entries. Process via `pipeline.run(files=[...])`. Verify unique correlation_ids, no cross-contamination, all results present.
   - **Test 2 — Manifest thread safety:** Process multiple files concurrently with `dry_run=False` and shared manifest path. Verify manifest contains exactly one entry per file, no corruption.
   - **Test 3 — Exception isolation:** Mix valid and invalid files. Verify failures in some threads don't affect others.
4. Run full test suite — expect 148+ passed

**Status:** [x] Complete
