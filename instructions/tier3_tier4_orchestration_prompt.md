# Tier 3 + Tier 4 Orchestration Prompt — Cleanup & Test Coverage

**Purpose:** Execute all 7 remaining tasks from `instructions/tier3_tier4_remaining_tasks.md` sequentially, with built-in verification after each task.

**Codebase context:**
- Python project: `pyedi_core/` (EDI/CSV/XML processing pipeline)
- Tests: `tests/` (pytest — 143 baseline: 86 unit, 57 integration)
- Coding standards: see `CLAUDE.md` (read before writing, minimal diffs, match patterns, type hints, explicit error handling)
- Prior work: Tiers 1 + 2 complete (2026-03-17 and 2026-03-24)

---

## Rules of Engagement

1. **Sequential execution** — complete each task fully (including its test gate) before starting the next.
2. **Read before writing** — always read the target file and its imports before making any change.
3. **Minimal diffs** — change only what the task requires. No drive-by fixes.
4. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
5. **Stop on red** — if any test gate fails, diagnose and fix before proceeding. Do not skip.
6. **Update the task file** — after each task completes, update its status in `instructions/tier3_tier4_remaining_tasks.md` from `[ ] Pending` to `[x] Complete`.

---

## Pre-Flight

```bash
# Verify clean baseline
pytest tests/ -v --tb=short 2>&1 | tail -5

# Capture baseline test count
pytest tests/ -v --tb=short 2>&1 | grep -E "passed|failed|error"

# Expected: 143 passed, 0 failures
```

If any tests fail at baseline, **stop and fix them first**.

---

## Task 1: Delete 3 redundant root scripts

**Investigate:**
```bash
# Confirm zero imports/references in code
grep -rn "generate_expected\|verify_environment\|verify_structure" pyedi_core/ tests/ --include="*.py"

# Confirm pyedi test --verify works as replacement
python -m pyedi_core.main test --verify
```

**Execute:**
1. Verify `generate_expected.py`, `verify_environment.py`, `verify_structure.py` exist at project root
2. Delete all 3 files
3. Verify `pyedi test --verify` still passes

**Test Gate:**
```bash
# Full suite — must remain 143 passed
pytest tests/ -v --tb=short

# Verify CLI replacement works
python -m pyedi_core.main test --verify
```

**Commit:** `cleanup(T3): delete redundant root scripts superseded by pyedi test CLI`

---

## Task 2: Delete 3 stale doc files

**Investigate:**
```bash
# Confirm zero references in code/config
grep -rn "AGENTIC_IDE_TEST_PROMPT\|PROJECT_BRIEF\|Testing_Specification.*v1" pyedi_core/ tests/ config/ --include="*.py" --include="*.yaml"
```

**Execute:**
1. Verify these 3 files exist: `AGENTIC_IDE_TEST_PROMPT.md`, `PROJECT_BRIEF.md`, `PyEDI_Core_Testing_Specification-user-supplied-v1.md`
2. Delete all 3 files
3. Do NOT delete `SPECIFICATION.md` or `PyEDI_Core_Testing_Specification-user-supplied.md`

**Test Gate:**
```bash
pytest tests/ -v --tb=short
# Expected: 143 passed
```

**Commit:** `cleanup(T3): remove stale/empty documentation files`

---

## Task 3: Delete stale `rules/200220261215033.yaml` + root `rules/` dir

**Investigate:**
```bash
# Read the file
cat rules/200220261215033.yaml

# Check what else is in the rules/ dir
ls -la rules/

# Understand pipeline usage — _rules_dir glob at pipeline.py:522-523
grep -n "_rules_dir\|rules_dir" pyedi_core/pipeline.py
```

**Execute:**
1. Confirm `rules/200220261215033.yaml` is an empty mapping stub (transaction_type: "810", empty header/lines/summary)
2. Confirm `rules/` contains only this file
3. Delete the file: `rm rules/200220261215033.yaml`
4. Delete the directory: `rmdir rules/`
5. **Important:** The pipeline `_rules_dir` config still points to `./rules` — this is fine, `Path("./rules").glob("*.yaml")` returns empty iterator when dir doesn't exist

**Test Gate:**
```bash
# Full suite
pytest tests/ -v --tb=short

# Specifically run x12 integration tests
pytest tests/integration/test_user_supplied_data.py -v --tb=short

# Verify no dangling references
grep -rn "rules/200220261215033" pyedi_core/ tests/ config/
```

**Commit:** `cleanup(T3): remove stale rules/200220261215033.yaml empty mapping stub`

---

## Task 4: Standardize YAML quoting conventions

**⚠️ Decision gate:** This task is low-value cosmetic work with type-coercion risk. Ask the user before proceeding. If skipped, mark as `[x] Skipped — user decision` and move to Task 5.

**Investigate:**
```python
# For each YAML file, dump parsed types to detect coercion risks
python -c "
import yaml, json
files = [
    'config/config.yaml',
    'pyedi_core/rules/cxml_850_map.yaml',
    'pyedi_core/rules/default_x12_map.yaml',
    'pyedi_core/rules/gfs_810_map.yaml',
    'pyedi_core/rules/gfs_850_map.yaml',
    'pyedi_core/rules/gfs_856_map.yaml',
    'pyedi_core/rules/gfs_csv_map.yaml',
    'schemas/compiled/margin_edge_810_map.yaml',
    'schemas/compiled/gfs_ca_810_map.yaml',
    'tests/user_supplied/metadata.yaml',
]
for f in files:
    try:
        with open(f) as fh:
            data = yaml.safe_load(fh)
        print(f'{f}: OK ({type(data).__name__})')
    except Exception as e:
        print(f'{f}: ERROR - {e}')
"
```

**Execute — Per-File Protocol:**
1. Read the YAML file
2. Parse with `yaml.safe_load()` and save the dict as `before`
3. Apply quoting convention:
   - Single quotes for numeric-looking strings (`'810'`, `'850'`), delimiters (`','`)
   - No quotes for plain strings (`CSV`, `INFO`, `string`, `true`)
   - Double quotes only for strings with escapes
4. Parse modified file as `after`
5. Compare `before == after` — if any difference, **revert** that value's quoting
6. Write the standardized file

**Test Gate:**
```bash
# Verify every file parses identically after changes
python -c "
import yaml
files = [...]  # same list as above
for f in files:
    with open(f) as fh:
        data = yaml.safe_load(fh)
    print(f'{f}: {\"OK\" if data else \"EMPTY\"} - keys: {list(data.keys()) if isinstance(data, dict) else \"list\"}')"

# Full suite
pytest tests/ -v --tb=short
```

**Commit:** `cleanup(T3): standardize YAML quoting conventions across config/schema/rule files`

---

## Task 5: Add cXML fixture + integration test (W53)

**Investigate:**
```bash
# Read the cXML mapping rules
cat pyedi_core/rules/cxml_850_map.yaml

# Read cXML detection and parsing logic
# xml_handler.py lines 87-100 (detection), 131-177 (cXML parsing)

# Check transaction_registry path resolution
grep -n "transaction_registry\|_rules_dir\|cxml" config/config.yaml

# Verify how existing integration tests route to the pipeline
# test_user_supplied_data.py lines 52-76 (pipeline vs direct-handler routing)

# Check driver registry
grep -n "cxml\|xml" pyedi_core/drivers/__init__.py
```

**Execute:**
1. Read `pyedi_core/rules/cxml_850_map.yaml` to understand source paths (XPath-like)
2. Verify path resolution: does `./rules/cxml_850_map.yaml` resolve from working dir? Check how the pipeline loads rule files (pipeline.py `_get_mapping_rules`)
3. Create fixture file `tests/user_supplied/inputs/cxml_850_sample.cxml`:
   - Valid cXML envelope with `<?xml version="1.0"?>` and `<cXML>` root
   - `<Header>` with `<From>`, `<To>`, `<Sender>` credentials
   - `<Request>` containing `<OrderRequest>`
   - `<OrderRequestHeader orderID="PO-001" orderDate="2026-01-15">`
   - 2-3 `<ItemOut>` elements with `<ItemID>`, quantity, `<UnitPrice>`
   - Fields aligned with `cxml_850_map.yaml` source paths
4. Add test case to `tests/user_supplied/metadata.yaml`:
   ```yaml
   - name: "cXML 850 Purchase Order"
     input_file: "inputs/cxml_850_sample.cxml"
     output_file: "outputs/cxml_850_sample.json"
     expected_output: "expected_outputs/cxml_850_sample.json"
     should_succeed: true
     dry_run: true
     skip_fields: []
     transaction_type: "cxml"
     description: "Verify cXML 850 parsing and field extraction"
   ```
   **Note:** If pipeline path resolution doesn't work for cXML, use the direct-handler approach — extend the `else` branch in `test_user_supplied_data.py` to handle `transaction_type == 'cxml'` with `XMLHandler.read()`
5. Generate expected output: run the test case once, capture output, save as expected
6. Optionally add a targeted unit test in `TestCxmlParsing` that loads the fixture from disk

**Test Gate:**
```bash
# Full suite — expect 144+ passed
pytest tests/ -v --tb=short

# Specifically verify cXML test case
pytest tests/integration/test_user_supplied_data.py -v --tb=short -k "cxml or cXML"

# Verify fixture file parses cleanly
python -c "
from pyedi_core.drivers import XMLHandler
h = XMLHandler()
result = h.read('tests/user_supplied/inputs/cxml_850_sample.cxml')
print(f'cXML: {result.get(\"_is_cxml\", False)}')
print(f'Header keys: {list(result.get(\"header\", {}).keys())}')
print(f'Lines count: {len(result.get(\"lines\", []))}')
"
```

**Commit:** `test(W53): add cXML 850 fixture file and integration test`

---

## Task 6: Add `should_succeed: false` failure-path test cases (W57)

**Investigate:**
```bash
# Read the failure code path carefully
# test_user_supplied_data.py lines 116-129

# Understand error handler output
grep -n "handle_failure\|error.json" pyedi_core/core/error_handler.py | head -20

# Check the failed/ directory structure
ls -la failed/ 2>/dev/null || echo "no failed dir"
```

**Critical implementation detail:** The `should_succeed: false` code path at line 117 references `result.status`, but `result` is only assigned in the `if target_inbound_dir:` branch (line 65). Failure test cases **MUST** set `target_inbound_dir` so they go through the pipeline. Also, `dry_run` must be `false` for the error handler to write `.error.json` to `./failed/`.

**Execute:**
1. Create failure input files under `tests/user_supplied/inputs/`:
   - `malformed_x12.dat` — file with X12-like extension but corrupted content (e.g., `ISA*00*` followed by garbage, missing required segments). Should fail at DETECTION or TRANSFORMATION.
   - `unmapped_csv.csv` — simple valid CSV file (`col1,col2\nval1,val2`). Will be placed in a nonexistent inbound dir with no `csv_schema_registry` match. Should fail at DETECTION.
2. Add entries to `tests/user_supplied/metadata.yaml`:
   ```yaml
   - name: "Malformed X12 - detection failure"
     input_file: "inputs/malformed_x12.dat"
     output_file: "outputs/malformed_x12.json"
     expected_output: "expected_outputs/malformed_x12.json"
     should_succeed: false
     expected_error_stage: "DETECTION"
     dry_run: false
     skip_fields: []
     target_inbound_dir: "./inbound/x12"
     description: "Verify graceful failure on malformed X12 input"

   - name: "Unmapped CSV - schema lookup failure"
     input_file: "inputs/unmapped_csv.csv"
     output_file: "outputs/unmapped_csv.json"
     expected_output: "expected_outputs/unmapped_csv.json"
     should_succeed: false
     expected_error_stage: "DETECTION"
     dry_run: false
     skip_fields: []
     target_inbound_dir: "./inbound/csv/nonexistent_schema"
     description: "Verify graceful failure when no schema matches CSV"
   ```
3. Run the tests and observe the actual error stage — adjust `expected_error_stage` if the pipeline reports a different stage
4. Handle cleanup: ensure `./failed/` artifacts from failure tests are cleaned up (check if conftest or test `finally` block handles this)

**Test Gate:**
```bash
# Full suite — expect 145+ passed
pytest tests/ -v --tb=short

# Specifically verify failure test cases pass
pytest tests/integration/test_user_supplied_data.py -v --tb=short

# Verify no orphaned files in failed/
ls failed/ 2>/dev/null
```

**Commit:** `test(W57): add should_succeed=false failure-path test cases for X12 and CSV`

---

## Task 7: Add concurrent batch processing stress test (W26)

**Investigate:**
```bash
# Read batch processing code
# pipeline.py lines 371-446 (_process_batch)

# Read manifest locking
grep -n "Lock\|_lock\|lock" pyedi_core/core/manifest.py

# Read existing batch tests
# test_drivers.py TestPipelineBatchProcessing class (line 821+)
```

**Execute:**
1. Add new test class `TestPipelineConcurrency` in `tests/test_drivers.py` with `@pytest.mark.integration`:

   **Test 1 — Thread isolation:**
   - Create a `tmp_path` config with `max_workers: 4`
   - Create 5 CSV files in separate tmp subdirectories, each with a `csv_schema_registry` entry pointing to its directory
   - Process all 5 via `pipeline.run(files=[f1, f2, f3, f4, f5])`
   - Assert: all 5 results returned, each has unique `correlation_id`, each has `status == 'SUCCESS'` or known failure, no cross-contamination of payload data

   **Test 2 — Manifest consistency:**
   - Process 5 files concurrently with `dry_run=False` and shared `tmp_path` manifest
   - Read the manifest file after processing
   - Assert: exactly 5 entries (one per file), no partial lines, no duplicates, all entries have valid hash|filename|timestamp|status format

   **Test 3 — Exception isolation:**
   - Mix 3 valid CSV files + 2 invalid files (.xyz extension)
   - Process all 5 concurrently
   - Assert: 3 SUCCESS + 2 FAILED results, valid files processed correctly despite failures in other threads

2. Apply `@pytest.mark.integration` marker to the new class

**Test Gate:**
```bash
# Full suite — expect 148+ passed
pytest tests/ -v --tb=short

# Run new concurrency tests specifically
pytest tests/test_drivers.py -v --tb=short -k "Concurrency"

# Verify markers
pytest tests/ -v -m integration --co -q 2>&1 | tail -3
```

**Commit:** `test(W26): add concurrent batch processing stress tests`

---

## Post-Flight

After all 7 tasks are complete:

```bash
# Final full suite
pytest tests/ -v --tb=short

# Compare final test count to baseline (143)
pytest tests/ -v --tb=short 2>&1 | grep -E "passed|failed|error"

# Verify markers still working
pytest tests/ -v -m unit --co -q 2>&1 | tail -3
pytest tests/ -v -m integration --co -q 2>&1 | tail -3

# Verify no pytest warnings
pytest tests/ -W error::pytest.PytestUnknownMarkWarning

# Verify pyedi test CLI
python -m pyedi_core.main test --verify

# Confirm no dangling references to deleted files
grep -rn "generate_expected.py\|verify_environment.py\|verify_structure.py\|AGENTIC_IDE_TEST_PROMPT\|PROJECT_BRIEF\|200220261215033.yaml" pyedi_core/ tests/ config/

# Show git log of all commits
git log --oneline -7
```

**Final validation checklist:**
- [ ] All 7 tasks marked `[x] Complete` in `instructions/tier3_tier4_remaining_tasks.md`
- [ ] 0 test failures
- [ ] Test count >= 148 (143 baseline + 5+ new tests)
- [ ] `pytest -m unit` and `pytest -m integration` each return >0 tests
- [ ] No dangling references to deleted files
- [ ] `pyedi test --verify` passes
- [ ] 7 clean commits, one per task

---

## Resumption Protocol

If execution is interrupted mid-task:
1. Read `instructions/tier3_tier4_remaining_tasks.md` — find the first `[ ] Pending` task
2. Run the pre-flight check to verify the suite is green
3. Resume from that task's **Investigate** step
