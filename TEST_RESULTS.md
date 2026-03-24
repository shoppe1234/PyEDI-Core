# PyEDI-Core Test Results

**Date:** 2026-03-24
**Run:** Full suite after Compare engine build (Phase D-E complete)
**Result:** **192 / 192 PASSED**, 1 warning

---

## Test Suite Summary

| Category | Count | Marker |
|----------|-------|--------|
| Unit tests | ~110 | `pytest -m unit` |
| Integration tests | ~82 | `pytest -m integration` |
| **Total** | **192** | `pytest tests/ + pytest portal/tests/` |

## Test Execution

**Command:**
```bash
pytest tests/ -v --tb=short          # 187 passed
pytest portal/tests/ -v --tb=short   #   5 passed
```

**Output:**
```
187 passed, 1 warning in 7.18s   (engine tests)
  5 passed in 2.11s              (portal compare API tests)
```

The single warning is a non-fatal discrepancy in the x12 integration test (unexpected metadata keys `_transaction_type`, `_is_unmapped`, `_map_file` in actual output).

## Test Files

| File | Tests | Marker | Scope |
|------|-------|--------|-------|
| `test_core.py` | 36 | unit | logger, manifest, error_handler, schema_compiler, mapper, pipeline |
| `test_core_extended.py` | 24 | unit | extended coverage of all core modules |
| `test_drivers.py` | 56 | integration | CSV, X12, XML handlers; pipeline integration; failure paths |
| `test_harness.py` | 13 | unit + integration | compare_outputs, run_tests, verify, generate_expected, CLI wiring |
| `test_main.py` | 11 | unit | main() CLI entry point, _print_result |
| `test_validator.py` | 9 | unit + integration | validator module: compile, type preservation, coverage, traces |
| `test_comparator.py` | 22 | unit + integration | compare engine: models, rules, matcher, engine, store, full pipeline |
| `test_api.py` | 7 | integration | portal API: health, validate, pipeline, test, manifest, config |
| `integration/test_user_supplied_data.py` | 9 | integration | YAML-driven regression tests with real files |
| `portal/tests/test_compare_api.py` | 5 | integration | compare API: profiles, run+query, export, rules read/write |

## User-Supplied Test Cases

| # | Name | Input File | Expected Output | Status |
|---|------|------------|-----------------|--------|
| 1 | UnivT701 Demo Invoice CSV | `inputs/UnivT701_small.csv` | `expected_outputs/UnivT701_small.json` | PASS |
| 2 | MarginEdge 810 Text File | `inputs/NA_810_MARGINEDGE_20260129.txt` | `expected_outputs/NA_810_MARGINEDGE_20260129.json` | PASS |
| 3 | x12 Data Comparison | `inputs/200220261215033.dat` | `expected_outputs/200220261215033.json` | PASS (with non-fatal discrepancies) |

## Compiler Bug Fixes Validated (2026-03-24)

- **Type loss fix** — `_compile_to_yaml()` dedup now keeps most-specific type. GFS DSL `CaseSize`/`CasePrice` compile as `float` (was `string`).
- **fieldIdentifier collision fix** — GFS DSL records with shared `fieldIdentifier="0"` now produce distinct keys (`0`, `Details`, `Summary`).
- Both fixes covered by `test_validator.py::TestTypePreservation` and `test_validator.py::TestFieldIdentifierCollision`.

## Review Fixes Validated (2026-03-17)

All Tier 1 (9 criticals) and Tier 2 fixes have regression tests:

- **C3:** Manifest TOCTOU race — `test_read_manifest_missing_file_no_error`, `test_read_manifest_race_condition`
- **C4:** Error handler missing source — `test_handle_failure_missing_source_no_sidecar`, `test_handle_failure_existing_file_creates_sidecar`
- **W3:** Typed exception hierarchy — `test_exception_hierarchy`, `test_exception_stage_attributes`
- **W55/W56:** Integration test fix + conftest fixtures — autouse singleton resets active
