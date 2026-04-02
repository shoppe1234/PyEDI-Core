# Fixed-Width Multi-Record Pipeline Fix — Orchestration Prompt

**Purpose:** Fix 5 issues discovered during the first end-to-end run of Retalix PI Invoice fixed-width files through the pycoreEdi pipeline. The critical fix is decomposing batch files into individual transactions so comparison works at the invoice level.

**Core design principle:** Batch files must produce one JSON per transaction. The compare engine matches by key field (e.g., invoice 123 in test set vs invoice 123 in control set). ALL records belonging to a transaction (header, detail, trailer) must be in the same JSON.

**Coding standards:** `CLAUDE.md`
**DSL schema:** `artifacts/RetalixPIInvoiceFileSchemaSacFF.ffSchema`
**Compiled schema:** `schemas/compiled/RetalixPIInvoiceFileSchemaSacFF_map.yaml`
**Silver data:** `artifacts/silver/ca-silver/` (control), `artifacts/silver/na-silver/` (test)

---

## Known State

From the Silver end-to-end run (Run #80):
- 3 batch files, each containing 1-3 invoices
- `TPM_HDR.invoiceNumber` is the transaction boundary and key field (String, width 10)
- `--split-key invoiceNumber` failed because only `TPM_HDR` and `OIN_HDR1` records have `invoiceNumber` — detail records went to `unknown.json`
- Whole-file comparison worked as a workaround but violates the transaction-level design principle
- 4 known field diffs across 2 files (billToName, remitToCareOf, 2x itemDescription)

## DSL Hierarchy (from ffSchema lines 1474-1520)

```
OTpidGroup (groupOnRecord = true)        ← Invoice transaction boundary
  ├── O_TPID [0..0]                      ← Trading partner ID (file-level)
  ├── OIN_DSTID []                       ← Destination ID
  ├── OIN_HDRA []                        ← Header A
  ├── TPM_HDR []                         ← **KEY RECORD: has invoiceNumber**
  ├── OIN_HDR1-5 []                      ← Invoice headers
  ├── OIN_REFH1, OIN_TRM1 []            ← Reference, terms
  ├── OIN_ST1-3, OIN_BT1-3, OIN_RE1-3 []← Ship-to, bill-to, remit-to
  ├── OinDtl1Group []                    ← Item detail group (nested)
  │     ├── OIN_DTL1 []                  ← Line item
  │     ├── OIN_DTL2-9, OIN_DTL11 []     ← Detail extensions
  │     ├── OIN_TAXD1 []                 ← Tax detail
  │     └── OinSacd1Group []             ← SAC detail (nested)
  ├── OIN_TTL1 []                        ← Invoice totals
  ├── OIN_TAXS1 []                       ← Tax summary
  └── OinSacs1Group []                   ← SAC summary (nested)
```

---

## Rules of Engagement

1. **Sequential phases** — complete each phase fully (including Ralph Loop verification) before starting the next.
2. **Read before writing** — always read the target file and its imports before making any change.
3. **Minimal diffs** — change only what the task requires. No drive-by fixes.
4. **Stop on red** — if any step fails, diagnose and fix before proceeding.
5. **Match existing patterns** — follow conventions in the codebase exactly.
6. **Transaction-level design** — every batch file must decompose to one JSON per transaction.
7. **Backward compatible** — existing delimited CSV files (Bevager, etc.) must continue to work.

---

## Pre-Flight

```bash
cd ~/VS/pycoreEdi

# Verify clean baseline
python -m pytest tests/ -v --tb=short 2>&1 | tail -30

# Verify CLI works
python -c "from pyedi_core.main import main; main(['compare', '--list-profiles', '--config', 'config/config.yaml'])"

# Verify Silver data exists
ls artifacts/silver/ca-silver/ artifacts/silver/na-silver/

# Verify compiled schema exists
ls schemas/compiled/RetalixPIInvoiceFileSchemaSacFF_map.yaml

# Show current TPM_HDR records (transaction boundaries)
grep "^TPM_HDR" artifacts/silver/ca-silver/CA_810_SILVR_20260210_063047_373-3072.txt
# Expected: 3 lines (3 invoices in this file)
```

If any tests fail at baseline, **stop and fix them first**.

---

# PHASE 1: Multi-Record Split-Key Fix (Critical)

> **Goal:** Parse DSL hierarchy, preserve in compiled YAML, and use it to group records by transaction so `--split-key invoiceNumber` produces one JSON per invoice with ALL records.

---

## Task 1.1 — Parse `recordSequence` from DSL

**Read first:**
- `pyedi_core/core/schema_compiler.py` — entire file, understand `_parse_dsl_record()` and `_compile_to_yaml()`
- `artifacts/RetalixPIInvoiceFileSchemaSacFF.ffSchema` lines 1458-1520 — hierarchy definitions

**What to implement:**
Add a new function `_parse_record_sequences(dsl_text: str)` that extracts:
- `recordSequence` block names (e.g., `OTpidGroup`, `OinDtl1Group`)
- `groupOnRecord` flag (boolean)
- `groupType` (e.g., `UnorderedAfterStart`)
- Member records with cardinality (e.g., `_TpmHdr TpmHdr []`, `_oinHdr1 OinHdr1 [0..0]`)
- Nested group references (e.g., `_oinDtl1Group OinDtl1Group []`)

Return a dict like:
```python
{
    "OTpidGroup": {
        "group_on_record": True,
        "members": [
            {"name": "O_TPID", "record_type": "OTpid", "cardinality": "0..0"},
            {"name": "TPM_HDR", "record_type": "TpmHdr", "cardinality": "repeating"},
            {"name": "OIN_HDR1", "record_type": "OinHdr1", "cardinality": "repeating"},
            ...
            {"name": "OinDtl1Group", "is_group": True, "cardinality": "repeating"},
        ]
    },
    "OinDtl1Group": {
        "group_type": "UnorderedAfterStart",
        "members": [...]
    }
}
```

**Important:** Use the `fieldIdentifier.value` from each record definition to map DSL record names (e.g., `TpmHdr`) to actual record IDs (e.g., `TPM_HDR`). Strip padding from identifier values.

**Verification:**
```python
from pyedi_core.core.schema_compiler import _parse_record_sequences
with open('artifacts/RetalixPIInvoiceFileSchemaSacFF.ffSchema') as f:
    dsl = f.read()
groups = _parse_record_sequences(dsl)
assert 'OTpidGroup' in groups
assert groups['OTpidGroup']['group_on_record'] == True
print(f"Groups: {list(groups.keys())}")
print(f"OTpidGroup members: {len(groups['OTpidGroup']['members'])}")
```

---

## Task 1.2 — Emit `record_groups` in compiled YAML

**Read first:** `_compile_to_yaml()` in `schema_compiler.py`

**What to implement:**
In the `_compile_to_yaml()` function, after building `schema.records` and `schema.record_layouts`, call `_parse_record_sequences()` and add a new top-level section to the compiled YAML:

```yaml
record_groups:
  OTpidGroup:
    group_on_record: true
    boundary_record: TPM_HDR       # First record with a unique key field
    key_field: invoiceNumber        # The field that identifies the transaction
    member_records:
      - O_TPID
      - OIN_DSTID
      - OIN_HDRA
      - TPM_HDR
      - OIN_HDR1
      - OIN_HDR2
      # ... all records in this group
    nested_groups:
      - OinDtl1Group
  OinDtl1Group:
    group_type: UnorderedAfterStart
    member_records:
      - OIN_DTL1
      - OIN_DTL11
      - OIN_DTL2
      # ... all detail records
    nested_groups:
      - OinSacd1Group
```

**How to determine `boundary_record` and `key_field`:**
- The boundary record is the first member that has `groupOnRecord = true` AND contains a field that serves as a transaction identifier
- For Retalix, this is `TPM_HDR` with `invoiceNumber`
- For now, use heuristic: if a group has `group_on_record: true`, the boundary record is the first member with `invoiceNumber` or `InvoiceID` field. If no such field exists, use the first record in the group.

**Verification:**
```bash
# Re-compile the schema
python -c "
from pyedi_core.core.schema_compiler import compile_dsl
compile_dsl('artifacts/RetalixPIInvoiceFileSchemaSacFF.ffSchema', compiled_dir='schemas/compiled', target_yaml_path='schemas/compiled/RetalixPIInvoiceFileSchemaSacFF_map.yaml')
"

# Verify record_groups in compiled YAML
python -c "
import yaml
with open('schemas/compiled/RetalixPIInvoiceFileSchemaSacFF_map.yaml') as f:
    data = yaml.safe_load(f)
groups = data.get('record_groups', {})
print(f'Groups: {list(groups.keys())}')
otpid = groups.get('OTpidGroup', {})
print(f'boundary_record: {otpid.get(\"boundary_record\")}')
print(f'key_field: {otpid.get(\"key_field\")}')
print(f'member_records: {otpid.get(\"member_records\", [])[:5]}...')
"
```

**Test gate:**
```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
# Must show: 192 passed (or more if new tests added)
```

---

## Task 1.3 — Hierarchy-aware `_read_fixed_width()`

**Read first:** `pyedi_core/drivers/csv_handler.py` — `_read_fixed_width()` (lines 87-145)

**What to implement:**
When the compiled schema has `record_groups` with a `boundary_record`, the reader must:

1. Identify the boundary record ID (e.g., `TPM_HDR`) and its `key_field` (e.g., `invoiceNumber`)
2. Flatten all group `member_records` + nested group members into a set of "transaction records"
3. While reading line-by-line:
   - When a boundary record is encountered, extract the key field value and start a new transaction group
   - All subsequent records that are members of the transaction group get tagged with the boundary's key value
   - Records that appear before the first boundary (like `O_TPID`, `OIN_DSTID`) are "file-level" records — they go into every transaction or into the header

**Implementation approach:**
Add a method `_group_by_transaction(lines, record_groups, record_layouts)` that takes the flat `lines` list and returns grouped lines where each line has the key field value propagated:

```python
def _group_by_transaction(
    self,
    lines: list[dict],
    record_groups: dict,
    record_layouts: dict,
) -> list[dict]:
    """Propagate boundary record's key field to all lines in same transaction."""
    # Find the primary group with group_on_record
    primary = next((g for g in record_groups.values() if g.get('group_on_record')), None)
    if not primary:
        return lines  # No grouping defined, return as-is

    boundary_record = primary['boundary_record']
    key_field = primary['key_field']

    current_key = None
    for line in lines:
        record_id = line.get('recordID', '').strip()
        if record_id == boundary_record:
            current_key = line.get(key_field)
        if current_key is not None:
            line[key_field] = current_key  # Propagate key to all transaction records

    return lines
```

Call this after `_read_fixed_width()` builds the `lines` list, before returning.

**Backward compatibility:** If `record_groups` is not present in the compiled schema (older schemas, CSV files), skip grouping entirely. This ensures Bevager and other existing schemas continue to work.

**Verification:**
```bash
# Process one Silver file with split-key
python -c "
from pyedi_core.pipeline import Pipeline
p = Pipeline(config_path='config/config.yaml')
p._outbound_dir = '/tmp/silver_test'
result = p.run(file='artifacts/silver/ca-silver/CA_810_SILVR_20260210_063047_373-3072.txt', split_key='invoiceNumber', output_dir='/tmp/silver_split')
print(f'Status: {result.status}')
"

# Check split output
ls /tmp/silver_split/
# Should show 3 JSON files (3 invoices), NO unknown.json

# Verify JSON structure
python -c "
import json, glob
files = sorted(glob.glob('/tmp/silver_split/*.json'))
print(f'Files: {len(files)}')
for f in files:
    with open(f) as fh:
        data = json.load(fh)
    record_types = set(l.get('recordID','').strip() for l in data['lines'])
    print(f'  {f}: invoiceNumber={data[\"header\"].get(\"invoiceNumber\")}, lines={len(data[\"lines\"])}, records={sorted(record_types)}')
"
# Each file should have header.invoiceNumber AND lines from multiple record types (TPM_HDR, OIN_HDR1, OIN_DTL1, etc.)
```

**Test gate:**
```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
```

---

## Task 1.4 — Ralph Loop: End-to-End Silver Validation

Use the following Ralph Loop to validate the multi-record split fix end-to-end:

```
/ralph-loop "Validate Silver Retalix split-key fix" --max-iterations 8 --completion-promise "SILVER SPLIT COMPLETE"
```

### Ralph Loop Instructions

You are validating the multi-record split-key fix for Retalix PI Invoice fixed-width files. Reference: `instructions/flatfileFix.md`.

**On each iteration, check state and do the next undone step:**

#### Step 1 — Clean previous output
Check: Is `outbound/silver/` empty?
- If NO:
  ```bash
  rm -rf outbound/silver/control outbound/silver/test
  ```
- Also clear Silver entries from manifest:
  ```bash
  grep -v "CA_810_SILVR" .processed > .processed.tmp && mv .processed.tmp .processed
  ```

#### Step 2 — Process control files with split-key
Check: Do JSON files exist in `outbound/silver/control/`?
- If NO:
  ```bash
  python -c "
  from pyedi_core.pipeline import Pipeline
  p = Pipeline(config_path='config/config.yaml')
  import glob
  for f in sorted(glob.glob('artifacts/silver/ca-silver/*.txt')):
      result = p.run(file=f, split_key='invoiceNumber', output_dir='outbound/silver/control')
      print(f'{f}: {result.status}')
  "
  ```
- Verify: `ls outbound/silver/control/*.json | wc -l` should be > 0 and NO `unknown.json`
- Spot-check:
  ```bash
  python -c "
  import json
  d = json.load(open('$(ls outbound/silver/control/*.json | head -1)'))
  assert 'invoiceNumber' in d['header'], 'FAIL: Missing invoiceNumber in header'
  record_types = set(l.get('recordID','').strip() for l in d['lines'])
  assert len(record_types) > 3, f'FAIL: Only {len(record_types)} record types, expected many'
  print(f'OK: invoiceNumber={d[\"header\"][\"invoiceNumber\"]}, {len(d[\"lines\"])} lines, {len(record_types)} record types')
  "
  ```

#### Step 3 — Process test files with split-key
Check: Do JSON files exist in `outbound/silver/test/`?
- If NO:
  ```bash
  # Clear manifest again for na-silver
  grep -v "CA_810_SILVR" .processed > .processed.tmp && mv .processed.tmp .processed
  python -c "
  from pyedi_core.pipeline import Pipeline
  p = Pipeline(config_path='config/config.yaml')
  import glob
  for f in sorted(glob.glob('artifacts/silver/na-silver/*.txt')):
      result = p.run(file=f, split_key='invoiceNumber', output_dir='outbound/silver/test')
      print(f'{f}: {result.status}')
  "
  ```
- Verify counts match:
  ```bash
  echo "Control:" && ls outbound/silver/control/*.json | wc -l
  echo "Test:" && ls outbound/silver/test/*.json | wc -l
  ```
- File counts should be equal and filenames should match (same invoice numbers)

#### Step 4 — Run comparison
```bash
python -c "
from pyedi_core.main import main
main(['compare', '--profile', 'retalix_p_i_invo', '--source-dir', 'outbound/silver/control', '--target-dir', 'outbound/silver/test', '--export-csv', '--verbose'])
"
```
- Verify with SQL:
  ```bash
  python -c "
  import sqlite3
  conn = sqlite3.connect('data/compare.db')
  row = conn.execute('SELECT profile, total_pairs, matched, mismatched, unmatched FROM compare_runs WHERE profile=\"retalix_p_i_invo\" ORDER BY id DESC LIMIT 1').fetchone()
  print(f'Profile: {row[0]}, Pairs: {row[1]}, Matched: {row[2]}, Mismatched: {row[3]}, Unmatched: {row[4]}')
  assert row[1] > 0, 'FAIL: No pairs found'
  "
  ```
- Expected: Some matched, some mismatched (the same 4 field diffs from files 3071/3060)

#### Step 5 — Run full test suite
```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -10
```
- All tests must pass

#### Completion Check
All 5 steps done? Run:
```python
import os, json, sqlite3

# V1: Split files exist, no unknown.json
control = [f for f in os.listdir('outbound/silver/control') if f.endswith('.json')]
test = [f for f in os.listdir('outbound/silver/test') if f.endswith('.json')]
assert len(control) > 0, 'V1 FAIL: No control files'
assert len(test) > 0, 'V1 FAIL: No test files'
assert not any('unknown' in f for f in control), 'V1 FAIL: unknown.json exists in control'
assert not any('unknown' in f for f in test), 'V1 FAIL: unknown.json exists in test'

# V2: JSON has invoiceNumber in header AND multiple record types in lines
with open(os.path.join('outbound/silver/control', control[0])) as f:
    data = json.load(f)
assert 'invoiceNumber' in data['header'], 'V2 FAIL: No invoiceNumber in header'
record_types = set(l.get('recordID','').strip() for l in data['lines'])
assert len(record_types) > 3, f'V2 FAIL: Only {len(record_types)} record types'

# V3: Compare run has results
conn = sqlite3.connect('data/compare.db')
row = conn.execute("SELECT total_pairs, matched, mismatched FROM compare_runs WHERE profile='retalix_p_i_invo' ORDER BY id DESC LIMIT 1").fetchone()
assert row[0] > 0, 'V3 FAIL: No pairs'

print(f"ALL CHECKS PASSED: {len(control)} control, {len(test)} test, {row[0]} pairs ({row[1]} match, {row[2]} mismatch)")
```

If all pass, output: **SILVER SPLIT COMPLETE**

---

# PHASE 2: JSON Encoding Bug

> **Goal:** Fix the double-colon serialization issue (`"quantityDifference": : "0002"`).

**Read first:**
- `pyedi_core/core/mapper.py` — `map_data()` function
- `pyedi_core/drivers/csv_handler.py` — `write()` method

**Root cause investigation:**
The double-colon appears when the mapper produces a value that itself contains a colon, or when the mapping configuration creates a malformed dict entry. Steps:

1. Process a Silver file and examine the raw `transformed_data` before JSON write:
   ```python
   from pyedi_core.pipeline import Pipeline
   p = Pipeline(config_path='config/config.yaml')
   result = p.run(file='artifacts/silver/ca-silver/CA_810_SILVR_20260210_080223_595-3060.txt', return_payload=True)
   # Search for the problematic field
   for i, line in enumerate(result.payload['lines']):
       if 'quantityDifference' in line:
           print(f"Line {i}: quantityDifference = {repr(line['quantityDifference'])}")
           break
   ```

2. If the value is malformed in the payload, trace back to the mapper rule
3. If the value is correct in the payload, the bug is in `json.dump` handling (unlikely)

**Fix:** Based on root cause. Most likely a mapping rule or field extraction issue.

**Verification:**
```bash
# Process and validate all JSON is well-formed
python -c "
import json, glob
for f in glob.glob('outbound/silver/control/*.json'):
    with open(f) as fh:
        data = json.load(fh)  # Will throw if malformed
    print(f'{f}: OK ({len(data[\"lines\"])} lines)')
print('All JSON valid')
"
```

**Test gate:**
```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
```

---

# PHASE 3: Windows Unicode Fix

> **Goal:** Replace `∅` character with ASCII fallback so validate report doesn't crash on Windows cp1252.

**Read first:** `pyedi_core/main.py` — `_print_validate_report()` function, around line 464

**What to change:**
```python
# Before:
marker = "=" if ft.mapped else "∅"

# After:
marker = "=" if ft.mapped else "-"
```

**Verification:**
```bash
PYTHONIOENCODING=utf-8 python -c "
from pyedi_core.main import main
main(['validate', '--dsl', 'artifacts/RetalixPIInvoiceFileSchemaSacFF.ffSchema', '--sample', 'artifacts/silver/ca-silver/CA_810_SILVR_20260210_063047_373-3072.txt', '--verbose'])
"
# Should complete without UnicodeEncodeError
```

**Test gate:**
```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
```

---

# PHASE 4: Compare Rules Tuning

> **Goal:** Reclassify non-critical fields as `soft` or `ignore` in the Retalix compare rules.

**Read first:** `config/compare_rules/retalix_p_i_invo.yaml` — current scaffolded rules (all `hard`)

**Fields to reclassify as `soft`** (content differences that don't affect financial accuracy):
- `itemDescription` — product description text
- `billToCareOf` — care-of text
- `remitToCareOf` — care-of text
- `shipToName`, `billToName`, `remitToName` — name variations
- `chainDescription` — chain description text
- `brand` — brand name text
- `vendorName` — vendor name text
- `priceBookFamilyDescription` — description text
- `orderGuideCategoryDes` — description text
- `allowChargeDesc` — description text
- `creditCodeDescription` — description text

All `soft` fields should also have `ignore_case: true`.

**Fields to reclassify as `ignore`**:
- `recordID` — record type prefix, not business data
- `ignore` — explicitly named "ignore" in schema

**Verification:**
```bash
python -c "
import yaml
with open('config/compare_rules/retalix_p_i_invo.yaml') as f:
    rules = yaml.safe_load(f)
soft = [r['field'] for r in rules['classification'] if r.get('severity') == 'soft']
ignore = [r['field'] for r in rules['classification'] if r.get('severity') == 'ignore']
hard = [r['field'] for r in rules['classification'] if r.get('severity') == 'hard']
print(f'Hard: {len(hard)}, Soft: {len(soft)}, Ignore: {len(ignore)}')
print(f'Soft fields: {soft}')
"
```

**Test gate:**
```bash
# Re-run comparison with tuned rules
python -c "
from pyedi_core.main import main
main(['compare', '--profile', 'retalix_p_i_invo', '--source-dir', 'outbound/silver/control', '--target-dir', 'outbound/silver/test', '--verbose'])
"
# billToName and itemDescription diffs should now show as [soft] instead of [hard]
```

---

# PHASE 5: Documentation Updates

> **Goal:** Update orchestration prompt with lessons learned and write post-implementation review.

## Task 5.1 — Update `instructions/silver_retalix_orchestration_prompt.md`

Add a "Lessons Learned" section at the top with:
- Transaction-level comparison is the design principle
- `TPM_HDR.invoiceNumber` is the transaction boundary and key field
- `--split-key invoiceNumber` requires the multi-record grouping fix (Phase 1)
- Whole-file comparison is a workaround, not the design
- `--match-json-path` CLI override can be used to override the profile match key

Update the pipeline run commands (Tasks 5-6) to use `--split-key invoiceNumber` now that it works.

## Task 5.2 — Write `instructions/ffPostImplement.md`

Create post-implementation review documenting:

```markdown
# Fixed-Width Multi-Record Pipeline — Post-Implementation Review

## Date: [execution date]

## Issues Encountered

### Issue 1: Multi-record split-key produced orphaned records
**Observed:** --split-key invoiceNumber on batch files put only OIN_HDR1/TPM_HDR records into invoice JSONs. All detail records (OIN_DTL1-11, OIN_ST1-3, etc.) went to unknown.json.
**Root Cause:** [describe — schema compiler didn't parse recordSequence, reader flattened all records]
**Solution:** [describe — parsed DSL hierarchy, emitted record_groups in compiled YAML, propagated key field to all transaction records]
**Verification:** [describe — Ralph Loop confirmed N invoices split correctly with all record types]

### Issue 2: JSON double-colon encoding
**Observed:** "quantityDifference": : "0002" in output JSON
**Root Cause:** [describe after fixing]
**Solution:** [describe]
**Verification:** All JSON files pass json.load() without error

### Issue 3: Windows Unicode crash
**Observed:** UnicodeEncodeError on ∅ character in validate --verbose output
**Root Cause:** Python cp1252 encoding on Windows can't encode ∅ (U+2205)
**Solution:** Replaced ∅ with ASCII "-" in _print_validate_report()
**Verification:** validate --verbose completes without error on Windows

### Issue 4: Compare rules all hard severity
**Observed:** All 135 scaffolded rules default to hard, making description diffs block comparison
**Root Cause:** scaffold-rules doesn't distinguish business-critical fields from descriptive text
**Solution:** Manually reclassified 11 description/name fields as soft with ignore_case
**Verification:** Compare run shows [soft] for name/description diffs

## Metrics
- Tests before: 192 passed
- Tests after: [count] passed
- Compare Run #80 (whole-file workaround): 3 pairs, 1 match, 2 mismatch
- Compare Run #[N] (transaction-level): [count] pairs, [match] match, [mismatch] mismatch
```

**Verification:**
```bash
# Both files exist
ls instructions/silver_retalix_orchestration_prompt.md instructions/ffPostImplement.md

# Final full test suite
python -m pytest tests/ -v --tb=short 2>&1 | tail -10
```

---

## Success Criteria

All of the following must be true:

- [ ] `--split-key invoiceNumber` produces one JSON per invoice with ALL record types (no unknown.json)
- [ ] Each JSON has `header.invoiceNumber` populated from `TPM_HDR`
- [ ] Compare matches invoice-to-invoice and finds expected field diffs
- [ ] All JSON output is well-formed (no double-colon)
- [ ] `validate --verbose` completes without Unicode error on Windows
- [ ] Compare rules have soft/ignore classifications for non-critical fields
- [ ] All existing tests pass (192+)
- [ ] Post-implementation review documents all issues and solutions
- [ ] Existing Bevager pipeline still works (backward compatible)
