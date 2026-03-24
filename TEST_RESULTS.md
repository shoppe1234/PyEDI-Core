# PyEDI-Core Test Results

**Date:** 2026-03-24
**Run:** Full suite after Tier 2 completion
**Result:** **143 / 143 PASSED** (86 unit, 57 integration)

---

## Test Suite Summary

| Category | Count | Marker |
|----------|-------|--------|
| Unit tests | 86 | `pytest -m unit` |
| Integration tests | 57 | `pytest -m integration` |
| **Total** | **143** | `pytest` |

## Test Execution

**Command:**
```bash
pytest tests/ -v --tb=short
```

**Output:**
```
143 passed, 1 warning in 1.23s
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
| `integration/test_user_supplied_data.py` | 3 | integration | YAML-driven regression tests with real files |

## User-Supplied Test Cases

| # | Name | Input File | Expected Output | Status |
|---|------|------------|-----------------|--------|
| 1 | UnivT701 Demo Invoice CSV | `inputs/UnivT701_small.csv` | `expected_outputs/UnivT701_small.json` | PASS |
| 2 | MarginEdge 810 Text File | `inputs/NA_810_MARGINEDGE_20260129.txt` | `expected_outputs/NA_810_MARGINEDGE_20260129.json` | PASS |
| 3 | x12 Data Comparison | `inputs/200220261215033.dat` | `expected_outputs/200220261215033.json` | PASS (with non-fatal discrepancies) |

## Review Fixes Validated

All Tier 1 (9 criticals) and Tier 2 fixes have regression tests:

- **C3:** Manifest TOCTOU race — `test_read_manifest_missing_file_no_error`, `test_read_manifest_race_condition`
- **C4:** Error handler missing source — `test_handle_failure_missing_source_no_sidecar`, `test_handle_failure_existing_file_creates_sidecar`
- **W3:** Typed exception hierarchy — `test_exception_hierarchy`, `test_exception_stage_attributes`
- **W55/W56:** Integration test fix + conftest fixtures — autouse singleton resets active
