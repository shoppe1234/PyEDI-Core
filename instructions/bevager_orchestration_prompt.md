# Bevager 810 End-to-End Compare — Orchestration Prompt

**Purpose:** Implement the bevager 810 flat-file-to-JSON-to-compare workflow. Compile DSL, add split-by-key output, enhance the compare engine for structured JSON, add a crosswalk table for data-driven severity/variance, add scaffold CLI, then run the full test.

**Task list:** `BeveragerTaskList.md` (root of repo)
**Coding standards:** `CLAUDE.md`
**Compare engine source:** `pyedi_core/comparator/` (already ported from json810Compare)
**DSL file:** `testingData/Batch1/bevager810FF.txt`
**Control data:** `testingData/Batch1/controlSample-FlatFile-Target/` (2 root-level .txt files)
**Test data:** `testingData/Batch1/testSample-FlatFile-Target/` (2 root-level .txt files)

---

## Rules of Engagement

1. **Sequential within phases** — complete each task fully (including its test gate) before starting the next.
2. **Phase gates are hard stops** — do not start a phase until the prior phase gate passes.
3. **Read before writing** — always read the target file and its imports before making any change.
4. **Minimal diffs** — change only what the task requires. No drive-by fixes, no extra comments.
5. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
6. **Stop on red** — if any test gate fails, diagnose and fix before proceeding.
7. **Data-driven, zero hardcoding** — all business rules, field mappings, severity levels, and thresholds live in YAML config or SQLite. No Python conditionals for partner-specific logic.
8. **Profile-driven** — adding a new trading partner is a config change, never a code change.
9. **CLI must still work** — `pyedi run`, `pyedi test`, `pyedi validate`, `pyedi compare` must remain functional after every task.
10. **Match existing patterns** — follow conventions in the codebase exactly. Read neighbor functions before writing new ones.

---

## Pre-Flight

Before starting any task, run these checks:

```bash
# Verify pyedi CLI is functional
python -m pycoreedi validate --help
python -m pycoreedi compare --list-profiles --config config/config.yaml

# Verify existing tests pass
python -m pytest tests/ -v --tb=short 2>&1 | tail -30

# Verify test data exists
ls testingData/Batch1/controlSample-FlatFile-Target/*.txt
ls testingData/Batch1/testSample-FlatFile-Target/*.txt
ls testingData/Batch1/bevager810FF.txt

# Verify compare engine is importable
python -c "from pyedi_core.comparator import compare; print('Compare engine OK')"
```

If anything fails at baseline, **stop and fix before proceeding**.

---

# PHASE 1: Data Preparation (config only)

> **Prerequisite:** Pre-flight green.
> **Deliverables:** Compiled schema, config entries, compare rules YAML.

---

## Task 1.1 — Compile DSL to YAML Schema

**Execute:**
```bash
python -m pycoreedi validate --dsl testingData/Batch1/bevager810FF.txt --output-dir schemas/compiled
```

**Test Gate:**
```bash
# Verify compiled schema exists and has 18 columns
python -c "
import yaml
with open('schemas/compiled/bevager810FF.yaml') as f:
    schema = yaml.safe_load(f)
cols = schema['schema']['columns']
assert len(cols) == 18, f'Expected 18 columns, got {len(cols)}'
# Verify types
type_map = {c['name']: c['type'] for c in cols}
assert type_map['InvoiceID'] == 'integer', f'InvoiceID type: {type_map[\"InvoiceID\"]}'
for field in ['InvoiceAmount','WeightShipped','UnitPrice','QuantityShipped','Discount','Taxes','ExtendedPrice']:
    assert type_map[field] == 'float', f'{field} type: {type_map[field]}'
print('Schema compilation verified: 18 columns, types correct')
"
```

**Commit:** `feat(schema): compile bevager810FF DSL to YAML schema`

---

## Task 1.2 — Register Bevager in config.yaml

**Investigate:**
```bash
# Read current config to see existing patterns
cat config/config.yaml
```

**Execute:**

Add to `csv_schema_registry` section of `config/config.yaml`:
```yaml
  bevager_810:
    source_dsl: ./testingData/Batch1/bevager810FF.txt
    compiled_output: ./schemas/compiled/bevager810FF.yaml
    inbound_dir: ./testingData/Batch1
    transaction_type: '810'
```

Add to `compare.profiles` section of `config/config.yaml`:
```yaml
    bevager_810:
      description: "Bevager 810 Invoice flat file comparison"
      match_key:
        json_path: "header.InvoiceID"
      segment_qualifiers: {}
      rules_file: "config/compare_rules/bevager_810.yaml"
```

**Test Gate:**
```bash
python -c "
import yaml
with open('config/config.yaml') as f:
    cfg = yaml.safe_load(f)
assert 'bevager_810' in cfg['csv_schema_registry'], 'Missing csv_schema_registry entry'
assert 'bevager_810' in cfg['compare']['profiles'], 'Missing compare profile'
profile = cfg['compare']['profiles']['bevager_810']
assert profile['match_key']['json_path'] == 'header.InvoiceID', 'Wrong match key'
print('Config registration verified')
"
```

**Commit:** `config: register bevager_810 in csv_schema_registry and compare profiles`

---

## Task 1.3 — Create Bevager Compare Rules YAML

**Investigate:**
```bash
# Read existing rules files for pattern reference
cat config/compare_rules/csv_generic.yaml
cat config/compare_rules/810_invoice.yaml
```

**Execute:**

Create `config/compare_rules/bevager_810.yaml`:
```yaml
# Bevager 810 Invoice flat file comparison rules
# Numeric fields use float comparison (tolerates precision differences)
# ProductDescription is soft (warning-only, case-insensitive)
# All other fields are hard (must match exactly)

classification:
  # --- Numeric fields (float comparison, hard severity) ---
  - segment: "*"
    field: "InvoiceAmount"
    severity: hard
    ignore_case: false
    numeric: true

  - segment: "*"
    field: "WeightShipped"
    severity: hard
    ignore_case: false
    numeric: true

  - segment: "*"
    field: "UnitPrice"
    severity: hard
    ignore_case: false
    numeric: true

  - segment: "*"
    field: "QuantityShipped"
    severity: hard
    ignore_case: false
    numeric: true

  - segment: "*"
    field: "Discount"
    severity: hard
    ignore_case: false
    numeric: true

  - segment: "*"
    field: "Taxes"
    severity: hard
    ignore_case: false
    numeric: true

  - segment: "*"
    field: "ExtendedPrice"
    severity: hard
    ignore_case: false
    numeric: true

  # --- Soft fields (warning only) ---
  - segment: "*"
    field: "ProductDescription"
    severity: soft
    ignore_case: true
    numeric: false

  # --- Default: all remaining fields hard match ---
  - segment: "*"
    field: "*"
    severity: hard
    ignore_case: false
    numeric: false

ignore: []
```

**Test Gate:**
```bash
python -c "
from pyedi_core.comparator.rules import load_rules, get_field_rule
rules = load_rules('config/compare_rules/bevager_810.yaml')
assert len(rules.classification) == 9, f'Expected 9 rules, got {len(rules.classification)}'
inv_rule = get_field_rule(rules, '*', 'InvoiceAmount')
assert inv_rule.numeric == True, 'InvoiceAmount should be numeric'
assert inv_rule.severity == 'hard', 'InvoiceAmount should be hard'
desc_rule = get_field_rule(rules, '*', 'ProductDescription')
assert desc_rule.severity == 'soft', 'ProductDescription should be soft'
assert desc_rule.ignore_case == True, 'ProductDescription should ignore case'
default_rule = get_field_rule(rules, '*', 'CustomerCode')
assert default_rule.severity == 'hard', 'Default should be hard'
assert default_rule.numeric == False, 'Default should not be numeric'
print('Compare rules verified: 9 rules, numeric/soft/hard correct')
"
```

**Commit:** `config: create bevager_810 compare rules YAML`

---

### Phase 1 Gate

```bash
# All three artifacts exist and are valid
ls schemas/compiled/bevager810FF.yaml
python -c "
import yaml
with open('config/config.yaml') as f:
    cfg = yaml.safe_load(f)
assert 'bevager_810' in cfg['csv_schema_registry']
assert 'bevager_810' in cfg['compare']['profiles']
"
python -c "
from pyedi_core.comparator.rules import load_rules
rules = load_rules('config/compare_rules/bevager_810.yaml')
assert len(rules.classification) == 9
print('PHASE 1 GATE: PASS')
"
```

---

# PHASE 2: Split Output (code changes)

> **Prerequisite:** Phase 1 gate green.
> **Deliverables:** Delimiter auto-detection, `write_split()` method, `--split-key` / `--output-dir` CLI args.

---

## Task 2.1 — Delimiter Auto-Detection

**Investigate:**
```bash
# Read csv_handler.py — find where delimiter is currently set
cat pyedi_core/drivers/csv_handler.py
# Read a sample data file to confirm delimiter
head -3 "testingData/Batch1/controlSample-FlatFile-Target/CA_810_BEVAGER_20260324_060426_620-3072.txt"
```

**Execute:**

Add a `_detect_delimiter()` method to the CSVHandler class in `pyedi_core/drivers/csv_handler.py`:

```python
def _detect_delimiter(self, file_path: str, schema_delimiter: str) -> str:
    """Auto-detect delimiter by counting occurrences in the first line."""
    with open(file_path, 'r', encoding='utf-8') as f:
        first_line = f.readline().rstrip('\n\r')

    candidates = {'|': first_line.count('|'), ',': first_line.count(','), '\t': first_line.count('\t')}
    detected = max(candidates, key=candidates.get)

    if detected != schema_delimiter and candidates[detected] > candidates.get(schema_delimiter, 0):
        self.logger.info("Auto-detected delimiter '%s' (schema says '%s')", detected, schema_delimiter)
        return detected
    return schema_delimiter
```

Wire it into the `read()` method — call `_detect_delimiter()` before using the schema's delimiter.

**Test Gate:**
```bash
python -c "
from pyedi_core.drivers.csv_handler import CSVHandler
handler = CSVHandler()
# Test with pipe-delimited file
detected = handler._detect_delimiter(
    'testingData/Batch1/controlSample-FlatFile-Target/CA_810_BEVAGER_20260324_060426_620-3072.txt', ',')
assert detected == '|', f'Expected pipe delimiter, got: {detected}'
print(f'Delimiter auto-detection verified: {detected}')
"
```

**Commit:** `feat(csv): add delimiter auto-detection to CSVHandler`

---

## Task 2.2 — Add `write_split()` Method

**Investigate:**
```bash
# Read CSVHandler write() method for pattern reference
# Read pipeline.py to understand how write is called
cat pyedi_core/drivers/csv_handler.py
cat pyedi_core/pipeline.py
```

**Execute:**

Add `write_split()` to CSVHandler in `pyedi_core/drivers/csv_handler.py`:

```python
def write_split(self, payload: dict, output_dir: str, split_key: str) -> list[str]:
    """Write transformed data split by a key field — one JSON per unique key value.

    Groups lines by split_key, promotes split_key into header for each group,
    writes each group as a separate JSON file.
    """
    from collections import defaultdict
    from pathlib import Path

    groups: dict[str, list[dict]] = defaultdict(list)
    for line in payload.get("lines", []):
        key_val = str(line.get(split_key, "unknown"))
        groups[key_val].append(line)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_paths: list[str] = []

    for key_val, lines in groups.items():
        split_payload = {
            "header": {**payload.get("header", {}), split_key: key_val},
            "lines": lines,
            "summary": payload.get("summary", {}),
        }
        out_path = str(Path(output_dir) / f"{split_key}_{key_val}.json")
        self.write(split_payload, out_path)
        output_paths.append(out_path)

    self.logger.info("Split %d lines into %d files by '%s'", len(payload.get("lines", [])), len(groups), split_key)
    return output_paths
```

**Test Gate:**
```bash
python -c "
import json, tempfile, os
from pyedi_core.drivers.csv_handler import CSVHandler

handler = CSVHandler()
payload = {
    'header': {'source': 'test'},
    'lines': [
        {'InvoiceID': '100', 'Amount': '50.00'},
        {'InvoiceID': '100', 'Amount': '25.00'},
        {'InvoiceID': '200', 'Amount': '75.00'},
    ],
    'summary': {}
}

with tempfile.TemporaryDirectory() as tmpdir:
    paths = handler.write_split(payload, tmpdir, 'InvoiceID')
    assert len(paths) == 2, f'Expected 2 files, got {len(paths)}'
    for p in paths:
        with open(p) as f:
            data = json.load(f)
        assert 'InvoiceID' in data['header'], f'Missing InvoiceID in header: {p}'
        key_val = data['header']['InvoiceID']
        for line in data['lines']:
            assert str(line['InvoiceID']) == key_val, f'Line InvoiceID mismatch in {p}'
    print(f'write_split verified: {len(paths)} files, headers and lines correct')
"
```

**Commit:** `feat(csv): add write_split() for split-by-key JSON output`

---

## Task 2.3 — Add `--split-key` and `--output-dir` to CLI

**Investigate:**
```bash
# Read main.py run subparser and pipeline.py run() method
cat pyedi_core/main.py
cat pyedi_core/pipeline.py
```

**Execute:**

1. In `pyedi_core/main.py`, add arguments to the `run` subparser:
   ```python
   run_parser.add_argument("--split-key", default=None, help="Split output into separate JSON files by this field")
   run_parser.add_argument("--output-dir", default=None, help="Output directory (used with --split-key)")
   ```

2. In the run handler, pass `split_key` and `output_dir` to `pipeline.run()`.

3. In `pyedi_core/pipeline.py`, add `split_key: str | None = None` and `output_dir: str | None = None` parameters to `run()`. In `_process_single()`, when `split_key` is set, call `driver.write_split(transformed, output_dir, split_key)` instead of `driver.write(transformed, output_path)`.

**Test Gate:**
```bash
# Verify CLI help shows new args
python -m pycoreedi run --help | grep -E "split-key|output-dir"

# Verify existing run still works without new args
python -m pycoreedi run --help > /dev/null && echo "CLI still functional"

# Existing tests still pass
python -m pytest tests/ -v --tb=short -q 2>&1 | tail -5
```

**Commit:** `feat(cli): add --split-key and --output-dir to run subcommand`

---

### Phase 2 Gate

```bash
# End-to-end: process one control file with split
python -m pycoreedi run \
  --file "testingData/Batch1/controlSample-FlatFile-Target/CA_810_BEVAGER_20260324_060426_620-3072.txt" \
  --split-key InvoiceID \
  --output-dir outbound/bevager/phase2_test \
  --config config/config.yaml

# Verify split output
python -c "
import os, json
out_dir = 'outbound/bevager/phase2_test'
files = [f for f in os.listdir(out_dir) if f.endswith('.json')]
assert len(files) > 0, 'No JSON files produced'
# Spot-check one file
with open(os.path.join(out_dir, files[0])) as f:
    data = json.load(f)
assert 'InvoiceID' in data['header'], 'Missing InvoiceID in header'
assert isinstance(data['lines'], list), 'lines should be a list'
assert len(data['lines']) > 0, 'lines should not be empty'
print(f'PHASE 2 GATE: PASS — {len(files)} split JSON files produced')
"

# Cleanup
rm -rf outbound/bevager/phase2_test
```

---

# PHASE 3: Compare Engine Enhancement

> **Prerequisite:** Phase 2 gate green.
> **Deliverables:** Enhanced `compare_flat_pair` that handles `{header, lines, summary}` structure.

---

## Task 3.1 — Enhance `compare_flat_pair` for Structured JSON

**Investigate:**
```bash
# Read the current compare_flat_pair implementation
cat pyedi_core/comparator/engine.py
# Read rules.py for get_field_rule signature
cat pyedi_core/comparator/rules.py
```

**Execute:**

1. Extract the existing field-comparison loop from `compare_flat_pair` into a helper:
   ```python
   def _compare_flat_dict(
       src_dict: dict,
       tgt_dict: dict,
       segment_label: str,
       rules: CompareRules,
   ) -> list[FieldDiff]:
   ```
   This contains the existing key-iteration logic (lines 266-309 of current engine.py).

2. Rewrite `compare_flat_pair` to detect structured JSON:
   - If `"lines"` key exists in source or target data → structured comparison:
     - Compare `header` dicts via `_compare_flat_dict`
     - Match `lines` arrays positionally, compare each pair via `_compare_flat_dict`
     - Handle extra/missing lines
     - Compare `summary` dicts via `_compare_flat_dict`
   - Else → original flat comparison via `_compare_flat_dict` (backward compatible)

**Test Gate:**
```bash
python -c "
from pyedi_core.comparator.engine import compare_flat_pair
from pyedi_core.comparator.models import MatchEntry, MatchPair
from pyedi_core.comparator.rules import load_rules

rules = load_rules('config/compare_rules/bevager_810.yaml')

# Build a matching pair
src_entry = MatchEntry(file_path='src.json', match_value='100', transaction_index=0,
    transaction_data={
        'header': {'InvoiceID': '100'},
        'lines': [
            {'InvoiceID': '100', 'UnitPrice': '10.00', 'QuantityShipped': '5', 'ProductDescription': 'CHEESE'},
        ],
        'summary': {}
    })
tgt_entry = MatchEntry(file_path='tgt.json', match_value='100', transaction_index=0,
    transaction_data={
        'header': {'InvoiceID': '100'},
        'lines': [
            {'InvoiceID': '100', 'UnitPrice': '10.00', 'QuantityShipped': '5', 'ProductDescription': 'cheese'},
        ],
        'summary': {}
    })
pair = MatchPair(source=src_entry, target=tgt_entry, match_value='100')
result = compare_flat_pair(pair, rules)

# ProductDescription differs in case but rule is ignore_case=True, so should match
# Everything else matches
assert result.status == 'MATCH', f'Expected MATCH, got {result.status} with diffs: {[d.field for d in result.diffs]}'

# Now test a real mismatch
tgt_entry.transaction_data['lines'][0]['UnitPrice'] = '11.00'
result2 = compare_flat_pair(pair, rules)
assert result2.status == 'MISMATCH', 'Expected MISMATCH for price diff'
price_diffs = [d for d in result2.diffs if d.field == 'UnitPrice']
assert len(price_diffs) == 1, 'Expected one UnitPrice diff'
assert price_diffs[0].severity == 'hard', 'UnitPrice diff should be hard'
print('compare_flat_pair structured JSON: PASS')
"

# Backward compatibility — flat JSON still works
python -c "
from pyedi_core.comparator.engine import compare_flat_pair
from pyedi_core.comparator.models import MatchEntry, MatchPair
from pyedi_core.comparator.rules import load_rules

rules = load_rules('config/compare_rules/csv_generic.yaml')
src = MatchEntry('a.json', 'k1', 0, {'name': 'Alice', 'score': '95'})
tgt = MatchEntry('b.json', 'k1', 0, {'name': 'Alice', 'score': '95'})
pair = MatchPair(source=src, target=tgt, match_value='k1')
result = compare_flat_pair(pair, rules)
assert result.status == 'MATCH', 'Backward compat broken'
print('compare_flat_pair backward compat: PASS')
"

# Existing tests still pass
python -m pytest tests/ -v --tb=short -q 2>&1 | tail -5
```

**Commit:** `feat(compare): enhance compare_flat_pair for structured {header, lines, summary} JSON`

---

### Phase 3 Gate

```bash
# Full structured comparison test with line-count mismatch
python -c "
from pyedi_core.comparator.engine import compare_flat_pair
from pyedi_core.comparator.models import MatchEntry, MatchPair
from pyedi_core.comparator.rules import load_rules

rules = load_rules('config/compare_rules/bevager_810.yaml')
src = MatchEntry('s.json', '100', 0, {
    'header': {'InvoiceID': '100'},
    'lines': [
        {'InvoiceID': '100', 'UnitPrice': '10.00'},
        {'InvoiceID': '100', 'UnitPrice': '20.00'},
    ],
    'summary': {}
})
tgt = MatchEntry('t.json', '100', 0, {
    'header': {'InvoiceID': '100'},
    'lines': [
        {'InvoiceID': '100', 'UnitPrice': '10.00'},
    ],
    'summary': {}
})
pair = MatchPair(source=src, target=tgt, match_value='100')
result = compare_flat_pair(pair, rules)
assert result.status == 'MISMATCH', 'Should detect missing line'
print('PHASE 3 GATE: PASS')
"
```

---

# PHASE 4: Crosswalk Table

> **Prerequisite:** Phase 3 gate green.
> **Deliverables:** `field_crosswalk` SQLite table, `amount_variance` on FieldRule, crosswalk-aware rule resolution.

---

## Task 4.1 — Add `field_crosswalk` Table

**Investigate:**
```bash
cat pyedi_core/comparator/store.py
```

**Execute:**

1. Add DDL to `_SCHEMA` in `store.py`:
   ```sql
   CREATE TABLE IF NOT EXISTS field_crosswalk (
       id              INTEGER PRIMARY KEY,
       profile         TEXT NOT NULL,
       field_name      TEXT NOT NULL,
       severity        TEXT NOT NULL DEFAULT 'hard',
       numeric         BOOLEAN NOT NULL DEFAULT 0,
       ignore_case     BOOLEAN NOT NULL DEFAULT 0,
       amount_variance REAL DEFAULT NULL,
       updated_at      TEXT NOT NULL,
       updated_by      TEXT DEFAULT 'system',
       UNIQUE(profile, field_name)
   );
   CREATE INDEX IF NOT EXISTS idx_crosswalk_profile ON field_crosswalk(profile);
   ```

2. Add CRUD functions:
   - `upsert_crosswalk(db_path, profile, field_name, severity, numeric, ignore_case, amount_variance, updated_by) -> None`
   - `get_crosswalk(db_path, profile) -> list[dict]` — all entries for a profile
   - `get_crosswalk_field(db_path, profile, field_name) -> dict | None` — single field lookup

**Test Gate:**
```bash
python -c "
import tempfile, os
from pyedi_core.comparator.store import init_db, upsert_crosswalk, get_crosswalk, get_crosswalk_field

with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    db = f.name
try:
    init_db(db)
    upsert_crosswalk(db, 'bevager_810', 'Taxes', 'hard', True, False, 0.05, 'test')
    upsert_crosswalk(db, 'bevager_810', 'ProductDescription', 'soft', False, True, None, 'test')

    entries = get_crosswalk(db, 'bevager_810')
    assert len(entries) == 2, f'Expected 2 entries, got {len(entries)}'

    taxes = get_crosswalk_field(db, 'bevager_810', 'Taxes')
    assert taxes is not None, 'Taxes entry not found'
    assert taxes['amount_variance'] == 0.05, f'Wrong variance: {taxes[\"amount_variance\"]}'
    assert taxes['numeric'] == 1, 'Taxes should be numeric'

    # Test upsert (update existing)
    upsert_crosswalk(db, 'bevager_810', 'Taxes', 'hard', True, False, 0.10, 'test2')
    taxes2 = get_crosswalk_field(db, 'bevager_810', 'Taxes')
    assert taxes2['amount_variance'] == 0.10, 'Upsert did not update variance'

    missing = get_crosswalk_field(db, 'bevager_810', 'NonExistent')
    assert missing is None, 'Should return None for missing field'

    print('field_crosswalk table: PASS')
finally:
    os.unlink(db)
"
```

**Commit:** `feat(compare): add field_crosswalk table and CRUD to store.py`

---

## Task 4.2 — Add `amount_variance` to FieldRule

**Investigate:**
```bash
cat pyedi_core/comparator/models.py
```

**Execute:**

Add `amount_variance` field to `FieldRule` in `models.py`:
```python
@dataclass
class FieldRule:
    segment: str
    field: str
    severity: str = "hard"
    ignore_case: bool = False
    numeric: bool = False
    conditional_qualifier: str | None = None
    amount_variance: float | None = None      # tolerance for numeric comparison
```

**Test Gate:**
```bash
python -c "
from pyedi_core.comparator.models import FieldRule
rule = FieldRule(segment='*', field='Taxes', severity='hard', numeric=True, amount_variance=0.05)
assert rule.amount_variance == 0.05
rule2 = FieldRule(segment='*', field='Name')
assert rule2.amount_variance is None
print('FieldRule.amount_variance: PASS')
"
```

**Commit:** `feat(compare): add amount_variance to FieldRule model`

---

## Task 4.3 — Wire Crosswalk into Rule Resolution

**Investigate:**
```bash
cat pyedi_core/comparator/rules.py
cat pyedi_core/comparator/engine.py
cat pyedi_core/comparator/__init__.py
```

**Execute:**

1. In `rules.py`, add a function to load crosswalk entries and merge with YAML rules:
   ```python
   def load_crosswalk_overrides(db_path: str, profile: str) -> dict[str, FieldRule]:
       """Load crosswalk entries as a {field_name: FieldRule} dict for fast lookup."""
   ```

2. Modify `get_field_rule()` (or add `get_effective_rule()`) to accept an optional crosswalk dict. If the field has a crosswalk entry, use it; otherwise fall back to YAML rules.

3. In `engine.py`, update `compare_flat_pair` and `_compare_flat_dict` to use `amount_variance`:
   ```python
   if rule.numeric and rule.amount_variance is not None:
       try:
           if abs(float(src_val) - float(tgt_val)) <= rule.amount_variance:
               continue
       except (ValueError, TypeError):
           pass
   ```

4. In `comparator/__init__.py`, pass `db_path` and `profile` so crosswalk can be loaded once per run and cached.

**Test Gate:**
```bash
python -c "
import tempfile, os
from pyedi_core.comparator.store import init_db, upsert_crosswalk
from pyedi_core.comparator.rules import load_rules, load_crosswalk_overrides, get_field_rule
from pyedi_core.comparator.engine import compare_flat_pair
from pyedi_core.comparator.models import MatchEntry, MatchPair

# Setup: crosswalk with 0.05 variance on Taxes
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    db = f.name
try:
    init_db(db)
    upsert_crosswalk(db, 'bevager_810', 'Taxes', 'hard', True, False, 0.05, 'test')

    rules = load_rules('config/compare_rules/bevager_810.yaml')
    crosswalk = load_crosswalk_overrides(db, 'bevager_810')

    # Taxes diff of 0.03 should PASS with 0.05 variance
    src = MatchEntry('s.json', '100', 0, {
        'header': {'InvoiceID': '100'},
        'lines': [{'Taxes': '0.03', 'UnitPrice': '10.00'}],
        'summary': {}
    })
    tgt = MatchEntry('t.json', '100', 0, {
        'header': {'InvoiceID': '100'},
        'lines': [{'Taxes': '0.00', 'UnitPrice': '10.00'}],
        'summary': {}
    })
    pair = MatchPair(source=src, target=tgt, match_value='100')
    result = compare_flat_pair(pair, rules, crosswalk=crosswalk)
    taxes_diffs = [d for d in result.diffs if d.field == 'Taxes']
    assert len(taxes_diffs) == 0, f'Taxes within variance should not diff: {taxes_diffs}'

    # Taxes diff of 0.10 should FAIL (exceeds 0.05 variance)
    tgt.transaction_data['lines'][0]['Taxes'] = '0.13'
    result2 = compare_flat_pair(pair, rules, crosswalk=crosswalk)
    taxes_diffs2 = [d for d in result2.diffs if d.field == 'Taxes']
    assert len(taxes_diffs2) == 1, 'Taxes exceeding variance should diff'

    print('Crosswalk + amount_variance: PASS')
finally:
    os.unlink(db)
"

# Existing tests still pass
python -m pytest tests/ -v --tb=short -q 2>&1 | tail -5
```

**Commit:** `feat(compare): wire crosswalk overrides and amount_variance into rule resolution`

---

### Phase 4 Gate

```bash
python -c "
from pyedi_core.comparator.models import FieldRule
from pyedi_core.comparator.store import init_db
import tempfile, os

# Verify model has amount_variance
r = FieldRule('*', 'X', amount_variance=0.01)
assert r.amount_variance == 0.01

# Verify table creates without error
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    db = f.name
try:
    init_db(db)
    import sqlite3
    conn = sqlite3.connect(db)
    tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
    assert 'field_crosswalk' in tables, f'Missing field_crosswalk table. Tables: {tables}'
    conn.close()
    print('PHASE 4 GATE: PASS')
finally:
    os.unlink(db)
"
```

---

# PHASE 5: Scaffold CLI Command

> **Prerequisite:** Phase 4 gate green.
> **Deliverables:** `pyedi scaffold-rules` subcommand, `pyedi_core/scaffold.py` module.

---

## Task 5.1 — Add `scaffold-rules` Subcommand

**Investigate:**
```bash
# Read main.py for subcommand registration pattern
cat pyedi_core/main.py
# Read a compiled schema to understand column structure
cat schemas/compiled/bevager810FF.yaml | head -40
```

**Execute:**

1. Create `pyedi_core/scaffold.py`:
   ```python
   def scaffold_rules(schema_path: str, output_path: str | None = None,
                      profile: str | None = None, db_path: str | None = None) -> str:
       """Generate a starter compare rules YAML from a compiled schema.

       Reads column definitions, sets numeric=True for float/integer types,
       generates classification entries, writes rules YAML.
       Optionally seeds crosswalk table if profile and db_path are provided.
       """
   ```

2. In `pyedi_core/main.py`, add `scaffold-rules` subparser:
   ```python
   scaffold_parser = subparsers.add_parser("scaffold-rules", help="Generate starter compare rules from compiled schema")
   scaffold_parser.add_argument("--schema", required=True, help="Path to compiled schema YAML")
   scaffold_parser.add_argument("--output", default=None, help="Output rules YAML path (default: config/compare_rules/<schema_stem>.yaml)")
   scaffold_parser.add_argument("--profile", default=None, help="Profile name for optional crosswalk seeding")
   scaffold_parser.add_argument("--db", default=None, help="SQLite DB path for crosswalk seeding")
   ```

**Test Gate:**
```bash
# Generate rules from bevager schema
python -m pycoreedi scaffold-rules --schema schemas/compiled/bevager810FF.yaml --output /tmp/scaffolded_bevager.yaml

python -c "
import yaml
with open('/tmp/scaffolded_bevager.yaml') as f:
    rules = yaml.safe_load(f)
classification = rules['classification']
# Should have 18 field-specific rules + 1 default wildcard = 19
assert len(classification) >= 18, f'Expected at least 18 rules, got {len(classification)}'
# Verify numeric flags are set correctly
field_map = {r['field']: r for r in classification if r['field'] != '*'}
for name in ['InvoiceAmount','WeightShipped','UnitPrice','QuantityShipped','Discount','Taxes','ExtendedPrice']:
    assert field_map[name]['numeric'] == True, f'{name} should be numeric'
for name in ['PurchaseOrderNumber','CustomerCode','ProductDescription','GTIN']:
    assert field_map[name]['numeric'] == False, f'{name} should not be numeric'
print('scaffold-rules: PASS — correct numeric flags from schema types')
"

rm /tmp/scaffolded_bevager.yaml

# Existing tests still pass
python -m pytest tests/ -v --tb=short -q 2>&1 | tail -5
```

**Commit:** `feat(cli): add scaffold-rules subcommand for auto-generating compare rules`

---

### Phase 5 Gate

```bash
python -m pycoreedi scaffold-rules --help > /dev/null && echo "PHASE 5 GATE: PASS"
```

---

# PHASE 6: Execute the Test (Ralph Loop)

> **Prerequisite:** Phase 5 gate green.
> **Deliverables:** Processed JSON files, comparison results, verified crosswalk override.

**Strategy:** Use a Ralph Loop to iteratively process files, run comparison, and validate results. The loop self-corrects if any step fails.

---

## Ralph Loop Prompt

Use the following Ralph Loop to execute Phase 6. Start it with:

```
/ralph-loop "Execute Phase 6 of the Bevager 810 test plan" --max-iterations 10 --completion-promise "BEVAGER TEST COMPLETE"
```

### Ralph Loop Instructions

You are executing Phase 6 of the Bevager 810 end-to-end compare test. Reference: `BeveragerTaskList.md` and `instructions/bevager_orchestration_prompt.md`.

**On each iteration, check state and do the next undone step:**

#### Step 6.1 — Process control files
Check: Do JSON files exist in `outbound/bevager/control/`?
- If NO:
  ```bash
  python -m pycoreedi run --file "testingData/Batch1/controlSample-FlatFile-Target/CA_810_BEVAGER_20260324_060426_620-3072.txt" --split-key InvoiceID --output-dir outbound/bevager/control --config config/config.yaml
  python -m pycoreedi run --file "testingData/Batch1/controlSample-FlatFile-Target/CA_810_BEVAGER_20260325_040235_483-3054.txt" --split-key InvoiceID --output-dir outbound/bevager/control --config config/config.yaml
  ```
- Verify: `ls outbound/bevager/control/*.json | wc -l` > 0
- Spot-check: `python -c "import json; d=json.load(open('$(ls outbound/bevager/control/*.json | head -1)')); assert 'InvoiceID' in d['header']; print('Control OK:', d['header']['InvoiceID'])"`

#### Step 6.2 — Process test files
Check: Do JSON files exist in `outbound/bevager/test/`?
- If NO:
  ```bash
  python -m pycoreedi run --file "testingData/Batch1/testSample-FlatFile-Target/CA_810_BEVAGER_20260324_060426_620-3072.txt" --split-key InvoiceID --output-dir outbound/bevager/test --config config/config.yaml
  python -m pycoreedi run --file "testingData/Batch1/testSample-FlatFile-Target/CA_810_BEVAGER_20260325_040235_483-3054.txt" --split-key InvoiceID --output-dir outbound/bevager/test --config config/config.yaml
  ```
- Verify: `ls outbound/bevager/test/*.json | wc -l` > 0
- Verify counts match: control and test directories should have similar file counts

#### Step 6.3 — Run comparison
Check: Does `data/compare.db` have a `bevager_810` run?
- Run:
  ```bash
  python -m pycoreedi compare --profile bevager_810 --source-dir outbound/bevager/control --target-dir outbound/bevager/test --verbose --export-csv --config config/config.yaml
  ```
- Verify with SQL:
  ```bash
  sqlite3 data/compare.db "SELECT profile, total_pairs, matched, mismatched, unmatched FROM compare_runs WHERE profile='bevager_810' ORDER BY id DESC LIMIT 1"
  ```
- Expected: `total_pairs` > 0, at least some `mismatched` (DueDate, Taxes diffs expected)
- Check diff details:
  ```bash
  sqlite3 data/compare.db "SELECT field, severity, COUNT(*) as cnt FROM compare_diffs d JOIN compare_pairs p ON d.pair_id=p.id JOIN compare_runs r ON p.run_id=r.id WHERE r.profile='bevager_810' GROUP BY field, severity ORDER BY cnt DESC LIMIT 20"
  ```

#### Step 6.4 — Validate crosswalk override
Check: Does `field_crosswalk` have a Taxes entry?
- If NO:
  ```bash
  sqlite3 data/compare.db "INSERT OR REPLACE INTO field_crosswalk (profile, field_name, severity, numeric, ignore_case, amount_variance, updated_at, updated_by) VALUES ('bevager_810', 'Taxes', 'hard', 1, 0, 0.05, datetime('now'), 'ralph_loop')"
  ```
- Re-run comparison:
  ```bash
  python -m pycoreedi compare --profile bevager_810 --source-dir outbound/bevager/control --target-dir outbound/bevager/test --verbose --config config/config.yaml
  ```
- Verify: Taxes diffs where `|control - test| <= 0.05` should no longer appear as diffs
- Compare before/after:
  ```bash
  sqlite3 data/compare.db "SELECT r.id, r.matched, r.mismatched FROM compare_runs r WHERE r.profile='bevager_810' ORDER BY r.id DESC LIMIT 2"
  ```
  The second run should have fewer mismatches (or more matches) than the first.

#### Completion Check
All 4 steps done? Run the full verification:
```bash
python -c "
import os, json, sqlite3

# V1: Schema exists
assert os.path.exists('schemas/compiled/bevager810FF.yaml'), 'V1 FAIL: No compiled schema'

# V2: Split files exist
control_files = [f for f in os.listdir('outbound/bevager/control') if f.endswith('.json')]
test_files = [f for f in os.listdir('outbound/bevager/test') if f.endswith('.json')]
assert len(control_files) > 0, 'V2 FAIL: No control JSON files'
assert len(test_files) > 0, 'V2 FAIL: No test JSON files'

# V3: JSON structure correct
with open(os.path.join('outbound/bevager/control', control_files[0])) as f:
    data = json.load(f)
assert 'InvoiceID' in data['header'], 'V3 FAIL: Missing InvoiceID in header'
assert isinstance(data['lines'], list) and len(data['lines']) > 0, 'V3 FAIL: Empty lines'

# V4-V9: SQLite records
conn = sqlite3.connect('data/compare.db')
runs = conn.execute(\"SELECT * FROM compare_runs WHERE profile='bevager_810' ORDER BY id DESC LIMIT 2\").fetchall()
assert len(runs) >= 1, 'V4 FAIL: No bevager_810 runs'
assert runs[0][7] > 0, 'V4 FAIL: total_pairs is 0'

# V7: Crosswalk exists
crosswalk = conn.execute(\"SELECT * FROM field_crosswalk WHERE profile='bevager_810'\").fetchall()
assert len(crosswalk) > 0, 'V7 FAIL: No crosswalk entries'

# V8: CSV export
csv_exists = any(f.endswith('.csv') for f in os.listdir('reports/compare')) if os.path.exists('reports/compare') else False

conn.close()

print('=== VERIFICATION RESULTS ===')
print(f'V1 Schema compiled:     PASS')
print(f'V2 Split files:         PASS ({len(control_files)} control, {len(test_files)} test)')
print(f'V3 JSON structure:      PASS')
print(f'V4 Pairing works:       PASS (total_pairs={runs[0][7]})')
print(f'V5 Expected diffs:      CHECK MANUALLY (see diff query above)')
print(f'V6 Soft severity:       CHECK MANUALLY (ProductDescription)')
print(f'V7 Crosswalk override:  PASS')
print(f'V8 CSV export:          {\"PASS\" if csv_exists else \"SKIP (--export-csv may not have been used)\"}')
print(f'V9 SQLite records:      PASS ({len(runs)} runs)')
print()
print('ALL AUTOMATED CHECKS PASSED')
"
```

If all checks pass, output:
```
<promise>BEVAGER TEST COMPLETE</promise>
```

If any check fails, diagnose the failure, fix it, and the next iteration will re-verify.

---

## Post-Execution

After the Ralph Loop completes:

1. **Review CSV report:** `cat reports/compare/*.csv | head -30`
2. **Review diff summary:** `sqlite3 data/compare.db "SELECT field, severity, COUNT(*) FROM compare_diffs d JOIN compare_pairs p ON d.pair_id=p.id JOIN compare_runs r ON p.run_id=r.id WHERE r.profile='bevager_810' AND r.id=(SELECT MAX(id) FROM compare_runs WHERE profile='bevager_810') GROUP BY field, severity ORDER BY COUNT(*) DESC"`
3. **Commit test artifacts:** Commit the outbound JSON, compare DB, and CSV reports
4. **Update BeveragerTaskList.md:** Mark all Phase 6 tasks as `[x]`

---

## Summary of All Commits (expected)

| Phase | Commit Message |
|-------|---------------|
| 1.1 | `feat(schema): compile bevager810FF DSL to YAML schema` |
| 1.2 | `config: register bevager_810 in csv_schema_registry and compare profiles` |
| 1.3 | `config: create bevager_810 compare rules YAML` |
| 2.1 | `feat(csv): add delimiter auto-detection to CSVHandler` |
| 2.2 | `feat(csv): add write_split() for split-by-key JSON output` |
| 2.3 | `feat(cli): add --split-key and --output-dir to run subcommand` |
| 3.1 | `feat(compare): enhance compare_flat_pair for structured JSON` |
| 4.1 | `feat(compare): add field_crosswalk table and CRUD to store.py` |
| 4.2 | `feat(compare): add amount_variance to FieldRule model` |
| 4.3 | `feat(compare): wire crosswalk overrides and amount_variance into rule resolution` |
| 5.1 | `feat(cli): add scaffold-rules subcommand for auto-generating compare rules` |
| 6.x | `test(bevager): add Phase 6 test artifacts and results` |
