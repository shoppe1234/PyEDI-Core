# Tier 2 — Remaining Tasks

**Source:** `REVIEW_REPORT.md` (2026-03-17 code review)
**Status:** Open — all Tier 1 and partial Tier 2 items already resolved

---

## Task 1: W8 — Remove dead code: `_setup_file_output()` in logger.py

**File:** `pyedi_core/core/logger.py` lines 115-130
**Issue:** `_setup_file_output()` is defined but never called anywhere in the codebase. File logging is dead code.

**Steps:**
1. Read `logger.py` and all files that import it
2. Confirm `_setup_file_output()` has zero call sites (grep codebase)
3. Remove the method and any `ObservabilityConfig` fields used only by it
4. Run tests to verify nothing breaks

**Status:** [x] Complete — `_setup_file_output()` already removed; cleaned up orphaned `_get_log_level()` and `log_file` config key

---

## Task 2: W20 — Remove dead code: `default_value` block in schema.py

**File:** `pyedi_core/core/schema.py` lines 117-127
**Issue:** The `default_value` branch can never execute due to a prior condition that always returns first. This is unreachable dead code.

**Steps:**
1. Read `schema.py` around lines 117-127 and understand the control flow
2. Confirm the block is unreachable (trace the conditions above it)
3. Remove the dead block
4. Run tests to verify nothing breaks

**Status:** [x] Complete — no unreachable `default_value` block found in `schema_compiler.py`; either already removed in prior fixes or review line numbers were stale

---

## Task 3: W54 — Apply pytest markers to all tests

**Issue:** Pytest markers (`unit`, `integration`, `scale`) are registered but never applied to any test functions or classes.

**Steps:**
1. Read `pyproject.toml` to confirm marker definitions
2. Inventory all test files under `tests/`
3. For each test file, assign the appropriate marker:
   - `unit` — isolated, no I/O, no pipeline
   - `integration` — hits real files, pipeline, or multi-module paths
   - `scale` — load/stress/concurrency tests
4. Apply `@pytest.mark.X` decorators to each test class or function
5. Verify markers work: `pytest -m unit`, `pytest -m integration`

**Status:** [x] Complete — all test classes already have `@pytest.mark.unit` or `@pytest.mark.integration` decorators; 86 unit + 57 integration = 143 total, 0 unknown marker warnings

---

## Task 4: W45 — Fix triple-duplicated columns in `gfs_ca_810_map.yaml`

**File:** `pyedi_core/schemas/mappings/gfs_ca_810_map.yaml` (~640 lines)
**Issue:** Columns are copy-pasted three times, making the file ~3x longer than it should be and causing duplicate mapping keys.

**Steps:**
1. Read the file and identify the duplication boundaries
2. Determine the canonical set of columns (first occurrence)
3. Remove the two duplicate blocks
4. Validate the resulting YAML parses cleanly
5. Run any tests that exercise this mapping to confirm no regressions

**Status:** [x] Complete — NOT a bug. DSL source defines 3 record types (Header/Details/Summary) sharing 42 columns. `schema.columns` already deduplicated (42 unique). Mapping sections correctly reflect the 3 record types with appropriate source path prefixes.

---

## Task 5: W46 — Fix triple-duplicated columns in `test_map.yaml`

**File:** `pyedi_core/schemas/mappings/test_map.yaml`
**Issue:** Same triple-duplication copy-paste bug as `gfs_ca_810_map.yaml` (W45). Columns appear three times.

**Steps:**
1. Read the file and identify the duplication boundaries
2. Determine the canonical set of columns (first occurrence)
3. Remove the two duplicate blocks
4. Validate the resulting YAML parses cleanly
5. Run tests that reference `test_map.yaml` to confirm no regressions

> **Note:** W48 (consolidating `gfs_ca_810_map.yaml` and `test_map.yaml` as near-duplicates) is a separate Tier 3 decision — do not merge them here, just deduplicate within each file.

**Status:** [x] Complete — `test_map.yaml` does not exist in the codebase. References in test files create it inline via `tmp_path`. File was either already deleted or never committed.

---

## Task 6: W47 — Resolve empty shell `gfsGenericOut810FF.yaml`

**File:** `pyedi_core/schemas/mappings/gfsGenericOut810FF.yaml`
**Issue:** The file exists but all mappings are empty — it is a non-functional placeholder.

**Steps:**
1. Read the file to confirm it is empty/stub
2. Check if anything in the codebase references this file by name (grep for `gfsGenericOut810FF`)
3. Decide (with user input if needed): populate with real mappings, or delete and remove references
4. If populating: determine correct output mapping based on existing schemas
5. If deleting: remove the file and any config/registry entries pointing to it
6. Run tests to confirm no regressions

**Status:** [x] Complete — deleted `gfsGenericOut810FF.yaml` and its `.meta.json`. Empty stale artifact from 2026-02-21; config uses `gfs_ca_810_map.yaml` instead. Zero runtime references.
