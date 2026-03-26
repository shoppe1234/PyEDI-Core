# PyEDI-Core Test Results

**Date:** 2026-03-26
**Run:** Full suite after SQLite comparator parity + portal UI integration + matcher fix
**Result:** **187 engine tests PASSED** (10 warnings), portal API + E2E tests separate

---

## Test Suite Summary

| Category | Count | Command |
|----------|-------|---------|
| Engine tests (unit + integration) | 187 | `pytest tests/ -v --tb=short` |
| Portal API tests | 5 | `pytest portal/tests/test_compare_api.py` |
| E2E browser tests | 29 | `pytest portal/tests/e2e/ --headed` |
| **Total** | **221** | |

## Test Execution

**Command:**
```bash
pytest tests/ -v --tb=short                       # 187 passed, 10 warnings
pytest portal/tests/test_compare_api.py -v        #   5 passed
pytest portal/tests/e2e/ --headed --slowmo=200 -v #  29 passed
```

**Output:**
```
187 passed, 10 warnings in 2.73s  (engine tests)
  5 passed in 2.11s               (portal compare API tests)
 29 passed in 110.78s             (E2E browser tests, headed mode)
```

Warnings are non-fatal: x12 integration test metadata key discrepancies and structlog format_exc_info deprecation.

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

- **Delimiter auto-detection** — `csv_handler.py` `_detect_delimiter()` correctly identifies `|` delimiter for bevager flat files.
- **Split-by-key output** — `write_split()` produces 1 JSON per InvoiceID.
- **Flat file compare** — `_compare_flat_dict()` compares `{header, lines, summary}` JSON structure with positional line matching.
- **Crosswalk overrides** — `field_crosswalk` table with `amount_variance` correctly overrides YAML rules at runtime.
- **Scaffold rules** — `scaffold.py` generates compare rules YAML with correct numeric flags from compiled schema.
- **Bidirectional matcher** — `pair_transactions()` now detects both source-only and target-only unmatched pairs. Previously only source-only were detected.

## SQLite Comparator Parity Validated (2026-03-26)

All 11 improvement tasks from `sqlLiteReport.md` implemented and passing:
- **Error discovery** — `error_discovery` table, auto-detection during compare runs, CLI + portal workflow.
- **Reclassification** — Re-evaluate diffs without re-running file pairing. CLI `--reclassify-run` + portal button.
- **Trading partner context** — `trading_partner`, `transaction_type` columns on compare_runs.
- **Pre-seeded crosswalk** — Scaffold seeds crosswalk from rules YAML.
- **Segment column on crosswalk** — `(profile, segment, field_name)` uniqueness.
- **Enriched CSV export** — 15 columns with metadata header block.
- **Summary statistics** — Severity/segment/field breakdowns + top errors.
- **855/860 profiles** — New compare rules for PO Ack and PO Change.
- **Run comparison view** — Diff two runs to see new/resolved/changed errors.

## Portal UI Integration Validated (2026-03-26)

All portal UI features build clean (`npm run build` passes):
- 5 new API methods in `api.ts`
- Runs/Discoveries tab toggle
- Reclassify button + `re:N` badge
- Summary statistics panel with inline bar charts
- Run diff via checkbox selection
- Discoveries panel with apply workflow
- State cleanup for tab switching and edge cases

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
