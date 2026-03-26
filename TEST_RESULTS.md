# PyEDI-Core Test Results

**Date:** 2026-03-26
**Run:** Full suite after Bevager 810 end-to-end compare workflow + code refactoring
**Result:** **221 / 221 PASSED**, 1 warning

---

## Test Suite Summary

| Category | Count | Command |
|----------|-------|---------|
| Unit tests | ~110 | `pytest -m unit` |
| Integration tests | ~82 | `pytest -m integration` |
| Portal API tests | 5 | `pytest portal/tests/test_compare_api.py` |
| E2E browser tests | 29 | `pytest portal/tests/e2e/ --headed` |
| **Total** | **221** | |

## Test Execution

**Command:**
```bash
pytest tests/ -v --tb=short                       # 187 passed
pytest portal/tests/test_compare_api.py -v        #   5 passed
pytest portal/tests/e2e/ --headed --slowmo=200 -v #  29 passed
```

**Output:**
```
187 passed, 1 warning in 6.96s    (engine tests)
  5 passed in 2.11s               (portal compare API tests)
 29 passed in 110.78s             (E2E browser tests, headed mode)
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
| `portal/tests/e2e/test_navigation.py` | 4 | e2e | sidebar nav, health indicator, active highlighting |
| `portal/tests/e2e/test_dashboard.py` | 2 | e2e | stat cards, page rendering |
| `portal/tests/e2e/test_validate.py` | 4 | e2e | DSL validation by path, schema columns, disabled state |
| `portal/tests/e2e/test_pipeline.py` | 1 | e2e | page loads |
| `portal/tests/e2e/test_tests.py` | 2 | e2e | case listing, run harness |
| `portal/tests/e2e/test_config.py` | 2 | e2e | JSON display, expected keys |
| `portal/tests/e2e/test_compare.py` | 14 | e2e | full compare workflow: profiles, run, pairs, diffs, rules, export |

## User-Supplied Test Cases

| # | Name | Input File | Expected Output | Status |
|---|------|------------|-----------------|--------|
| 1 | UnivT701 Demo Invoice CSV | `inputs/UnivT701_small.csv` | `expected_outputs/UnivT701_small.json` | PASS |
| 2 | MarginEdge 810 Text File | `inputs/NA_810_MARGINEDGE_20260129.txt` | `expected_outputs/NA_810_MARGINEDGE_20260129.json` | PASS |
| 3 | x12 Data Comparison | `inputs/200220261215033.dat` | `expected_outputs/200220261215033.json` | PASS (with non-fatal discrepancies) |

## Bevager Refactoring Validated (2026-03-26)

- **Delimiter auto-detection** — `csv_handler.py` `_detect_delimiter()` correctly identifies `|` delimiter for bevager flat files. No hardcoded delimiter.
- **Split-by-key output** — `write_split()` produces 1 JSON per InvoiceID. 22 unique invoices across 2 input files → 22 JSON files per directory.
- **Flat file compare** — `_compare_flat_dict()` compares `{header, lines, summary}` JSON structure with positional line matching.
- **Crosswalk overrides** — `field_crosswalk` table with `amount_variance` correctly overrides YAML rules at runtime. Taxes field with 50.0 variance validated.
- **Scaffold rules** — `scaffold.py` generates bevager_810 compare rules YAML with correct numeric flags from compiled schema.
- **End-to-end bevager run** — 22 pairs compared, 660 diffs recorded in SQLite, CSV export generated (`reports/compare/compare_run_33.csv`).

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
