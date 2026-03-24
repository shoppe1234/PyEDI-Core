# Tier 2 Orchestration Prompt — Refactoring & Validation

**Purpose:** Execute all 6 remaining Tier 2 tasks from `instructions/tier2_remaining_tasks.md` sequentially, with built-in verification after each task. Each task is a self-contained refactoring mod with its own test gate.

**Codebase context:**
- Python project: `pyedi_core/` (EDI processing pipeline)
- Tests: `tests/` (pytest — `test_core.py`, `test_core_extended.py`, `test_drivers.py`, `test_harness.py`, `test_main.py`, `integration/test_user_supplied_data.py`, `conftest.py`)
- Coding standards: see `CLAUDE.md` (read before writing, minimal diffs, match patterns, type hints, explicit error handling)
- Baseline: 90+ tests passing, 0 failures (established after Tier 1 + partial Tier 2 fixes on 2026-03-17)

---

## Rules of Engagement

1. **Sequential execution** — complete each task fully (including its test gate) before starting the next.
2. **Read before writing** — always read the target file and its imports before making any change.
3. **Minimal diffs** — change only what the task requires. No drive-by fixes, no opportunistic refactoring.
4. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
5. **Stop on red** — if any test gate fails, diagnose and fix before proceeding. Do not skip.
6. **Update the task file** — after each task completes, update its status in `instructions/tier2_remaining_tasks.md` from `[ ] Pending` to `[x] Complete`.

---

## Pre-Flight

Before starting any task:

```
# Verify clean baseline — all existing tests must pass
pytest tests/ -v --tb=short 2>&1 | tail -20

# Capture baseline test count for comparison
pytest tests/ -v --tb=short 2>&1 | grep -E "passed|failed|error"
```

If any tests fail at baseline, **stop and fix them first** — do not begin refactoring on a red suite.

---

## Task 1: W8 — Remove dead `_setup_file_output()` from logger.py

**Investigate:**
```
# Read the target file
cat pyedi_core/core/logger.py

# Confirm zero call sites
grep -rn "_setup_file_output" pyedi_core/ tests/

# Check ObservabilityConfig for fields used only by this method
grep -rn "log_file\|log_format\|file_output" pyedi_core/core/
```

**Execute:**
1. Read `pyedi_core/core/logger.py` — identify the `_setup_file_output()` method boundaries
2. Read `pyedi_core/core/config.py` — identify any `ObservabilityConfig` fields used exclusively by this method
3. Remove `_setup_file_output()` method entirely
4. Remove any `ObservabilityConfig` fields that are now orphaned (only if they have zero other consumers)
5. Do NOT remove any imports, fields, or code that other parts of the codebase still use

**Test Gate:**
```
# Full suite — must match or exceed baseline count, 0 failures
pytest tests/ -v --tb=short

# Targeted: logger-specific tests
pytest tests/ -v --tb=short -k "logger or log"

# Smoke: import the module to confirm no syntax errors
python -c "from pyedi_core.core.logger import get_logger; print('OK')"
```

**Commit:** `refactor(W8): remove dead _setup_file_output() from logger.py`

---

## Task 2: W20 — Remove unreachable `default_value` block from schema.py

**Investigate:**
```
# Read the target file
cat pyedi_core/core/schema.py

# Understand the control flow around lines 117-127
# Identify what condition makes default_value unreachable
```

**Execute:**
1. Read `pyedi_core/core/schema.py` — trace the control flow to confirm the `default_value` block is unreachable
2. Document the reasoning: which prior condition always returns/continues before reaching this block
3. Remove the dead block only — do not restructure surrounding code
4. If removing the block leaves an empty `else` or dangling `elif`, clean up the minimal syntax needed

**Test Gate:**
```
# Full suite
pytest tests/ -v --tb=short

# Targeted: schema-specific tests
pytest tests/ -v --tb=short -k "schema or compile"

# Smoke: compile a schema to confirm behavior unchanged
python -c "from pyedi_core.core.schema import SchemaCompiler; print('OK')"
```

**Commit:** `refactor(W20): remove unreachable default_value block from schema.py`

---

## Task 3: W54 — Apply pytest markers to all tests

**Investigate:**
```
# Confirm marker definitions exist
grep -A5 "markers" pyproject.toml

# List all test files
find tests/ -name "test_*.py" -type f

# Read each test file to classify functions/classes
```

**Execute:**
1. Read `pyproject.toml` — confirm `unit`, `integration`, `scale` markers are registered
2. Read each test file and classify every test function/class:
   - `@pytest.mark.unit` — isolated tests, no file I/O, no real pipeline execution, mocks/patches only
   - `@pytest.mark.integration` — touches real files, invokes pipeline, multi-module, YAML-driven
   - `@pytest.mark.scale` — load, stress, concurrency (if any exist)
3. Add `import pytest` at the top of each test file if not already present
4. Apply decorators at the **class level** when all methods in a class share the same category; apply at the **function level** when mixed
5. Do NOT change any test logic, names, or assertions — only add marker decorators

**Classification guide:**
| Test file | Expected marker |
|-----------|----------------|
| `test_core.py` | `unit` (most), check individually |
| `test_core_extended.py` | `unit` (most), check individually |
| `test_drivers.py` | `unit` (mocked) or `integration` (real files) |
| `test_harness.py` | `integration` |
| `test_main.py` | `unit` or `integration` depending on CLI testing approach |
| `integration/test_user_supplied_data.py` | `integration` |

**Test Gate:**
```
# Full suite — same count, 0 failures
pytest tests/ -v --tb=short

# Verify markers are applied and selectable
pytest tests/ -v --tb=short -m unit 2>&1 | tail -5
pytest tests/ -v --tb=short -m integration 2>&1 | tail -5

# Confirm no "unknown marker" warnings
pytest tests/ -v --tb=short -W error::pytest.PytestUnknownMarkWarning
```

**Commit:** `refactor(W54): apply pytest markers (unit/integration) to all test files`

---

## Task 4: W45 — Deduplicate `gfs_ca_810_map.yaml`

**Investigate:**
```
# Read the file and count lines
wc -l pyedi_core/schemas/mappings/gfs_ca_810_map.yaml
cat pyedi_core/schemas/mappings/gfs_ca_810_map.yaml

# Check what references this file
grep -rn "gfs_ca_810_map" pyedi_core/ tests/ config/
```

**Execute:**
1. Read the full file — identify where the column block repeats (expect 3 copies)
2. Identify the canonical block (first occurrence)
3. Remove the 2nd and 3rd duplicate blocks
4. Validate the YAML parses: `python -c "import yaml; yaml.safe_load(open('pyedi_core/schemas/mappings/gfs_ca_810_map.yaml'))"`
5. Record the before/after line count (expect ~66% reduction)

**Test Gate:**
```
# Full suite
pytest tests/ -v --tb=short

# YAML parse validation
python -c "
import yaml
with open('pyedi_core/schemas/mappings/gfs_ca_810_map.yaml') as f:
    data = yaml.safe_load(f)
print(f'Keys: {list(data.keys()) if isinstance(data, dict) else \"list\"}')
print('YAML OK')
"

# Any tests that load this mapping
pytest tests/ -v --tb=short -k "gfs or 810 or mapping"
```

**Commit:** `fix(W45): remove triple-duplicated columns from gfs_ca_810_map.yaml`

---

## Task 5: W46 — Deduplicate `test_map.yaml`

**Investigate:**
```
# Read the file
wc -l pyedi_core/schemas/mappings/test_map.yaml
cat pyedi_core/schemas/mappings/test_map.yaml

# Check what references this file
grep -rn "test_map" pyedi_core/ tests/ config/
```

**Execute:**
1. Read the full file — identify the 3 repeated column blocks
2. Keep the canonical (first) block, remove duplicates 2 and 3
3. Validate YAML parses cleanly
4. Do NOT merge with `gfs_ca_810_map.yaml` — that is W48 (Tier 3)

**Test Gate:**
```
# Full suite
pytest tests/ -v --tb=short

# YAML parse validation
python -c "
import yaml
with open('pyedi_core/schemas/mappings/test_map.yaml') as f:
    data = yaml.safe_load(f)
print(f'Keys: {list(data.keys()) if isinstance(data, dict) else \"list\"}')
print('YAML OK')
"

# Any tests that load this mapping
pytest tests/ -v --tb=short -k "test_map or mapping"
```

**Commit:** `fix(W46): remove triple-duplicated columns from test_map.yaml`

---

## Task 6: W47 — Resolve empty `gfsGenericOut810FF.yaml`

**Investigate:**
```
# Read the file
cat pyedi_core/schemas/mappings/gfsGenericOut810FF.yaml

# Find all references
grep -rn "gfsGenericOut810FF" pyedi_core/ tests/ config/
```

**Execute — Decision Tree:**

**If zero references outside the file itself:**
1. Delete the file: `rm pyedi_core/schemas/mappings/gfsGenericOut810FF.yaml`
2. Done — no cleanup needed

**If referenced by config/code:**
1. List every reference location
2. If references are in config registries only (not runtime code): remove the registry entry and delete the file
3. If references are in runtime code: **stop and ask the user** whether to populate it or remove the code path
4. If populating: model the mapping structure after a working sibling (e.g., `gfs_ca_810_map.yaml` post-dedup) and fill in field names from the GFS 810FF schema

**Test Gate:**
```
# Full suite
pytest tests/ -v --tb=short

# Confirm no dangling references
grep -rn "gfsGenericOut810FF" pyedi_core/ tests/ config/
# Expected: 0 matches if deleted, or valid references if populated

# If populated: YAML parse validation
python -c "
import yaml
with open('pyedi_core/schemas/mappings/gfsGenericOut810FF.yaml') as f:
    data = yaml.safe_load(f)
print(f'Keys: {list(data.keys()) if isinstance(data, dict) else \"list\"}')
print('YAML OK')
"
```

**Commit:** `fix(W47): remove empty gfsGenericOut810FF.yaml placeholder` (or `populate` if filled)

---

## Post-Flight

After all 6 tasks are complete:

```
# Final full suite — must pass with 0 failures
pytest tests/ -v --tb=short

# Compare final test count to baseline
pytest tests/ -v --tb=short 2>&1 | grep -E "passed|failed|error"

# Verify all markers are working
pytest tests/ -v -m unit --co -q 2>&1 | tail -3
pytest tests/ -v -m integration --co -q 2>&1 | tail -3

# Confirm no pytest warnings about unknown markers
pytest tests/ -W error::pytest.PytestUnknownMarkWarning

# Show git log of all 6 commits
git log --oneline -6
```

**Final validation checklist:**
- [ ] All 6 tasks marked `[x] Complete` in `instructions/tier2_remaining_tasks.md`
- [ ] 0 test failures
- [ ] Test count >= baseline (Task 3 adds no new tests, but markers must not exclude any)
- [ ] `pytest -m unit` and `pytest -m integration` each return >0 tests
- [ ] No dangling references to deleted files
- [ ] 6 clean commits, one per task

**Final commit (optional):** `docs: mark all Tier 2 remaining tasks complete`

---

## Resumption Protocol

If execution is interrupted mid-task:
1. Read `instructions/tier2_remaining_tasks.md` — find the first `[ ] Pending` task
2. Run the pre-flight check to verify the suite is green
3. Resume from that task's **Investigate** step
