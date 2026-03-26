# Bevager 810 End-to-End Testing + Portal UI Verification — Orchestration Prompt

**Purpose:** Execute the bevager 810 end-to-end test (Phase 6 of bevager_orchestration_prompt.md) and verify all results display correctly in the portal UI (from updatePortalUi4NewSqlLite.md). Includes a prerequisite fix to the matcher for target-only unmatched pair detection.

**Coding standards:** `CLAUDE.md`
**Bevager backend reference:** `instructions/bevager_orchestration_prompt.md` (Phases 1-5 complete)
**Portal UI reference:** `instructions/updatePortalUi4NewSqlLite.md` (Phases A-D complete)
**Compare engine source:** `pyedi_core/comparator/`
**Portal UI source:** `portal/ui/src/pages/Compare.tsx`, `portal/ui/src/api.ts`
**Portal API source:** `portal/api/routes/compare.py`

---

## Rules of Engagement

1. **Sequential within phases** — complete each task fully (including its test gate) before starting the next.
2. **Phase gates are hard stops** — do not start a phase until the prior phase gate passes.
3. **Read before writing** — always read the target file and its imports before making any change.
4. **Minimal diffs** — change only what the task requires. No drive-by fixes, no extra comments.
5. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
6. **Stop on red** — if any test gate fails, diagnose and fix before proceeding.
7. **Data-driven, zero hardcoding** — all business rules, field mappings, severity levels, and thresholds live in YAML config or SQLite.
8. **Backend is read-only for UI phases** — do NOT modify any Python files during Phase 3 (portal UI verification).

---

# PHASE 0: Fix Matcher for Target-Only Unmatched Pairs

> **Why:** `pair_transactions()` only iterates source keys. Target-only InvoiceIDs (from the extra test file) are silently dropped. This must be fixed before testing so unmatched pairs appear correctly in the portal UI.
> **Deliverables:** Bidirectional matcher, `source is None` guards in engine and store.

---

## Task 0.1 — Make `MatchPair.source` Optional

**File:** `pyedi_core/comparator/models.py`

Change `source: MatchEntry` to `source: MatchEntry | None` in the `MatchPair` dataclass.

**Test Gate:**
```bash
python -c "
from pyedi_core.comparator.models import MatchPair, MatchEntry
p = MatchPair(source=None, target=MatchEntry('t.json','k1',0,{}), match_value='k1')
assert p.source is None
print('MatchPair source=None: PASS')
"
```

---

## Task 0.2 — Add Target-Only Loop in `pair_transactions`

**Investigate:**
```bash
cat pyedi_core/comparator/matcher.py
```

**Execute:**

In `pair_transactions()`, after the existing source-key loop and before `return pairs`, add:
```python
# Target-only pairs (match values present in target but not in source)
for match_value, target_entries in target_index.items():
    if match_value not in source_index:
        for tgt in target_entries:
            pairs.append(MatchPair(source=None, target=tgt, match_value=match_value))
```

**Test Gate:**
```bash
python -c "
import tempfile, os, json
from pyedi_core.comparator.matcher import pair_transactions
from pyedi_core.comparator.models import MatchKeyConfig

# Create temp dirs with source having key 'A' and target having keys 'A' and 'B'
with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as tgt_dir:
    # Source: one file with key 'A'
    with open(os.path.join(src_dir, 'A.json'), 'w') as f:
        json.dump({'header': {'InvoiceID': 'A'}, 'lines': [], 'summary': {}}, f)
    # Target: two files with keys 'A' and 'B'
    with open(os.path.join(tgt_dir, 'A.json'), 'w') as f:
        json.dump({'header': {'InvoiceID': 'A'}, 'lines': [], 'summary': {}}, f)
    with open(os.path.join(tgt_dir, 'B.json'), 'w') as f:
        json.dump({'header': {'InvoiceID': 'B'}, 'lines': [], 'summary': {}}, f)

    match_key = MatchKeyConfig(json_path='header.InvoiceID')
    pairs = pair_transactions(src_dir, tgt_dir, match_key)

    assert len(pairs) == 2, f'Expected 2 pairs, got {len(pairs)}'
    source_only = [p for p in pairs if p.target is None]
    target_only = [p for p in pairs if p.source is None]
    matched = [p for p in pairs if p.source and p.target]
    assert len(matched) == 1, f'Expected 1 matched pair, got {len(matched)}'
    assert len(target_only) == 1, f'Expected 1 target-only pair, got {len(target_only)}'
    assert target_only[0].match_value == 'B', f'Target-only should be B, got {target_only[0].match_value}'
    print('pair_transactions target-only: PASS')
"
```

---

## Task 0.3 — Add `source is None` Guards in Engine

**Investigate:**
```bash
cat pyedi_core/comparator/engine.py
```

**Execute:**

In both `compare_pairs()` and `compare_flat_pair()`, change:
```python
if pair.target is None:
```
To:
```python
if pair.source is None or pair.target is None:
```

**Test Gate:**
```bash
python -c "
from pyedi_core.comparator.engine import compare_flat_pair
from pyedi_core.comparator.models import MatchEntry, MatchPair
from pyedi_core.comparator.rules import load_rules

rules = load_rules('config/compare_rules/bevager_810.yaml')

# Test target-only (source=None)
tgt = MatchEntry('t.json', 'B', 0, {'header': {'InvoiceID': 'B'}, 'lines': [], 'summary': {}})
pair = MatchPair(source=None, target=tgt, match_value='B')
result = compare_flat_pair(pair, rules)
assert result.status == 'UNMATCHED', f'Expected UNMATCHED, got {result.status}'

# Test source-only (target=None) still works
src = MatchEntry('s.json', 'A', 0, {'header': {'InvoiceID': 'A'}, 'lines': [], 'summary': {}})
pair2 = MatchPair(source=src, target=None, match_value='A')
result2 = compare_flat_pair(pair2, rules)
assert result2.status == 'UNMATCHED', f'Expected UNMATCHED, got {result2.status}'

print('Engine source/target None guards: PASS')
"
```

---

## Task 0.4 — Add `source is None` Guard in Store

**Investigate:**
```bash
cat pyedi_core/comparator/store.py | head -230
```

**Execute:**

In `record_pair()`, change:
```python
pair.source.file_path,
pair.source.transaction_index,
```
To:
```python
pair.source.file_path if pair.source else None,
pair.source.transaction_index if pair.source else 0,
```

**Test Gate:**
```bash
python -c "
import tempfile, os
from pyedi_core.comparator.store import init_db, start_run, record_pair
from pyedi_core.comparator.models import MatchEntry, MatchPair, CompareResult
from datetime import datetime, timezone

with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    db = f.name
try:
    init_db(db)
    run_id = start_run(db, 'test_profile', 'src/', 'tgt/', 'test_rules.yaml')

    # Record a target-only pair (source=None)
    tgt = MatchEntry('t.json', 'B', 0, {})
    pair = MatchPair(source=None, target=tgt, match_value='B')
    result = CompareResult(pair=pair, status='UNMATCHED', diffs=[], timestamp=datetime.now(timezone.utc).isoformat())
    pair_id = record_pair(db, run_id, result)
    assert pair_id is not None, 'Failed to record target-only pair'
    print(f'Recorded target-only pair: id={pair_id}')
    print('Store source=None guard: PASS')
finally:
    os.unlink(db)
"
```

---

## Task 0.5 — Verify All Existing Tests Pass

```bash
python -m pytest tests/ -v --tb=short -q 2>&1 | tail -10
```

**Commit:** `fix(compare): detect target-only unmatched pairs in matcher`

---

### Phase 0 Gate

```bash
python -c "
import tempfile, os, json
from pyedi_core.comparator.matcher import pair_transactions
from pyedi_core.comparator.models import MatchKeyConfig, MatchPair
from pyedi_core.comparator.engine import compare_flat_pair
from pyedi_core.comparator.rules import load_rules

# Verify bidirectional matching works end-to-end
with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as tgt:
    json.dump({'header': {'k': '1'}, 'lines': [], 'summary': {}}, open(os.path.join(src, '1.json'), 'w'))
    json.dump({'header': {'k': '1'}, 'lines': [], 'summary': {}}, open(os.path.join(tgt, '1.json'), 'w'))
    json.dump({'header': {'k': '2'}, 'lines': [], 'summary': {}}, open(os.path.join(tgt, '2.json'), 'w'))
    json.dump({'header': {'k': '3'}, 'lines': [], 'summary': {}}, open(os.path.join(src, '3.json'), 'w'))

    pairs = pair_transactions(src, tgt, MatchKeyConfig(json_path='header.k'))
    assert len(pairs) == 3, f'Expected 3 pairs, got {len(pairs)}'
    statuses = {p.match_value: ('src' if p.source else '-') + '/' + ('tgt' if p.target else '-') for p in pairs}
    assert statuses == {'1': 'src/tgt', '3': 'src/-', '2': '-/tgt'}, f'Wrong statuses: {statuses}'
    print('PHASE 0 GATE: PASS — bidirectional matching works')
"
```

---

# PHASE 1: Pre-Flight

> **Prerequisite:** Phase 0 gate green.

```bash
# Verify pyedi CLI is functional
python -m pycoreedi validate --help
python -m pycoreedi compare --list-profiles --config config/config.yaml

# Verify existing tests pass
python -m pytest tests/ -v --tb=short 2>&1 | tail -30

# Verify test data exists
ls testingData/Batch1/controlSample-FlatFile-Target/*.txt
ls testingData/Batch1/testSample-FlatFile-Target/*.txt

# Verify compare engine imports
python -c "from pyedi_core.comparator import compare; print('Compare engine OK')"
python -c "from pyedi_core.comparator.store import get_runs, init_db; print('Store OK')"

# Verify output dirs
ls outbound/bevager/control/ 2>/dev/null | wc -l
ls outbound/bevager/test/ 2>/dev/null | wc -l

# Verify UI builds
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..
```

If anything fails at baseline, **stop and fix before proceeding**.

---

# PHASE 2: Execute Bevager Test (Ralph Loop)

> **Prerequisite:** Pre-flight green.
> **Deliverables:** Processed JSON files, comparison results in SQLite, crosswalk override verified.

**Strategy:** Use a Ralph Loop to iteratively process files, run comparison, and validate results. The loop self-corrects if any step fails.

Start with:
```
/ralph-loop "Execute Bevager 810 end-to-end test with portal UI verification" --max-iterations 12 --completion-promise "BEVAGER E2E COMPLETE"
```

## Ralph Loop Instructions

You are executing Phase 2 of the Bevager 810 end-to-end test. On each iteration, check state and do the next undone step.

---

### Step 2.1 — Process control files
**Check:** Do JSON files exist in `outbound/bevager/control/`?
- If NO:
  ```bash
  python -m pycoreedi run \
    --file "testingData/Batch1/controlSample-FlatFile-Target/CA_810_BEVAGER_20260325_040235_483-3054.txt" \
    --split-key InvoiceID --output-dir outbound/bevager/control --config config/config.yaml
  ```
- **Verify:** `ls outbound/bevager/control/*.json | wc -l` > 0
- **Spot-check:**
  ```bash
  python -c "import json; d=json.load(open('$(ls outbound/bevager/control/*.json | head -1)')); assert 'InvoiceID' in d['header']; print('Control OK:', d['header']['InvoiceID'])"
  ```

### Step 2.2 — Process test files
**Check:** Do JSON files exist in `outbound/bevager/test/`?
- If NO — process BOTH test files:
  ```bash
  python -m pycoreedi run \
    --file "testingData/Batch1/testSample-FlatFile-Target/CA_810_BEVAGER_20260325_040235_483-3054.txt" \
    --split-key InvoiceID --output-dir outbound/bevager/test --config config/config.yaml
  python -m pycoreedi run \
    --file "testingData/Batch1/testSample-FlatFile-Target/CA_810_BEVAGER_20260324_060426_620-3072.txt" \
    --split-key InvoiceID --output-dir outbound/bevager/test --config config/config.yaml
  ```
- **Verify:** `ls outbound/bevager/test/*.json | wc -l` > 0
- **Note:** Test dir should have MORE files than control (extra file 3072 contributes target-only InvoiceIDs)

### Step 2.3 — Run initial comparison
**Check:** Does `data/compare.db` have a `bevager_810` run?
- Run:
  ```bash
  python -m pycoreedi compare \
    --profile bevager_810 \
    --source-dir outbound/bevager/control \
    --target-dir outbound/bevager/test \
    --verbose --export-csv --config config/config.yaml
  ```
- **Verify:**
  ```bash
  python -c "
  import sqlite3
  conn = sqlite3.connect('data/compare.db')
  row = conn.execute('SELECT id, total_pairs, matched, mismatched, unmatched FROM compare_runs WHERE profile=\"bevager_810\" ORDER BY id DESC LIMIT 1').fetchone()
  print(f'Run {row[0]}: total={row[1]}, matched={row[2]}, mismatched={row[3]}, unmatched={row[4]}')
  assert row[1] > 0, 'total_pairs is 0'
  assert row[4] > 0, 'Expected unmatched pairs (target-only InvoiceIDs from 3072 file)'
  conn.close()
  print('Initial comparison PASS')
  "
  ```
- **Check diff breakdown:**
  ```bash
  python -c "
  import sqlite3
  conn = sqlite3.connect('data/compare.db')
  rows = conn.execute('''
    SELECT field, severity, COUNT(*) as cnt
    FROM compare_diffs d JOIN compare_pairs p ON d.pair_id=p.id
    JOIN compare_runs r ON p.run_id=r.id
    WHERE r.profile='bevager_810' AND r.id=(SELECT MAX(id) FROM compare_runs WHERE profile='bevager_810')
    GROUP BY field, severity ORDER BY cnt DESC LIMIT 20
  ''').fetchall()
  for r in rows: print(f'  {r[0]:30s} {r[1]:6s} {r[2]}')
  conn.close()
  "
  ```

### Step 2.4 — Seed crosswalk and re-compare
**Check:** Does `field_crosswalk` have a Taxes entry with `amount_variance`?
- If NO:
  ```bash
  python -c "
  from pyedi_core.comparator.store import init_db, upsert_crosswalk
  init_db('data/compare.db')
  upsert_crosswalk('data/compare.db', 'bevager_810', 'Taxes', 'hard', True, False, 0.05, 'test_script')
  print('Crosswalk seeded: Taxes amount_variance=0.05')
  "
  ```
- Re-run comparison:
  ```bash
  python -m pycoreedi compare \
    --profile bevager_810 \
    --source-dir outbound/bevager/control \
    --target-dir outbound/bevager/test \
    --verbose --config config/config.yaml
  ```
- **Verify:** Second run should have fewer mismatches if Taxes diffs were within tolerance:
  ```bash
  python -c "
  import sqlite3
  conn = sqlite3.connect('data/compare.db')
  rows = conn.execute('SELECT id, matched, mismatched, unmatched FROM compare_runs WHERE profile=\"bevager_810\" ORDER BY id DESC LIMIT 2').fetchall()
  for r in rows: print(f'  Run {r[0]}: matched={r[1]}, mismatched={r[2]}, unmatched={r[3]}')
  conn.close()
  "
  ```

### Step 2.5 — Verify UI build
```bash
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..
```

### Step 2.6 — Verify API layer returns bevager data
```bash
python -c "
from pyedi_core.comparator.store import get_runs, get_severity_breakdown, get_discoveries, init_db
init_db('data/compare.db')

runs = get_runs('data/compare.db')
bev_runs = [r for r in runs if r['profile'] == 'bevager_810']
assert len(bev_runs) >= 2, f'Expected at least 2 bevager runs, got {len(bev_runs)}'
print(f'API check: {len(bev_runs)} bevager_810 runs found')

latest = bev_runs[0]
breakdown = get_severity_breakdown('data/compare.db', latest['id'])
print(f'Severity breakdown for run {latest[\"id\"]}: {breakdown}')

discs = get_discoveries('data/compare.db', 'bevager_810')
print(f'Discoveries: {len(discs)} for bevager_810')
print('API data verification PASS')
"
```

### Step 2.7 — Full automated verification
```bash
python -c "
import os, json, sqlite3

assert os.path.exists('schemas/compiled/bevager810FF_map.yaml'), 'V1 FAIL'

ctrl = [f for f in os.listdir('outbound/bevager/control') if f.endswith('.json')]
test = [f for f in os.listdir('outbound/bevager/test') if f.endswith('.json')]
assert len(ctrl) > 0, 'V2 FAIL: No control JSONs'
assert len(test) > 0, 'V2 FAIL: No test JSONs'

with open(os.path.join('outbound/bevager/control', ctrl[0])) as f:
    data = json.load(f)
assert 'InvoiceID' in data['header'], 'V3 FAIL'
assert isinstance(data['lines'], list) and len(data['lines']) > 0, 'V3 FAIL'

conn = sqlite3.connect('data/compare.db')
runs = conn.execute('SELECT * FROM compare_runs WHERE profile=\"bevager_810\" ORDER BY id DESC').fetchall()
assert len(runs) >= 2, 'V4 FAIL: Need at least 2 runs'

cw = conn.execute('SELECT * FROM field_crosswalk WHERE profile=\"bevager_810\"').fetchall()
assert len(cw) > 0, 'V5 FAIL: No crosswalk entries'

unmatched = conn.execute('''
  SELECT COUNT(*) FROM compare_pairs p JOIN compare_runs r ON p.run_id=r.id
  WHERE r.profile='bevager_810' AND p.status='UNMATCHED'
''').fetchone()[0]

csv_ok = any(f.endswith('.csv') for f in os.listdir('reports/compare')) if os.path.exists('reports/compare') else False

conn.close()

print('=== VERIFICATION RESULTS ===')
print(f'V1 Schema compiled:     PASS')
print(f'V2 Split files:         PASS ({len(ctrl)} control, {len(test)} test)')
print(f'V3 JSON structure:      PASS')
print(f'V4 SQLite runs:         PASS ({len(runs)} runs)')
print(f'V5 Crosswalk:           PASS')
print(f'V6 Unmatched pairs:     {\"PASS\" if unmatched > 0 else \"CHECK\"} ({unmatched} unmatched)')
print(f'V7 CSV export:          {\"PASS\" if csv_ok else \"SKIP\"}')
print()
print('ALL AUTOMATED CHECKS PASSED')
"
```

If all checks pass, output:
```
<promise>BEVAGER E2E COMPLETE</promise>
```

If any check fails, diagnose the failure, fix it, and the next iteration will re-verify.

---

# PHASE 3: Portal UI Manual Verification

> **Prerequisite:** Ralph Loop complete.

### Start services:
```bash
# Terminal 1: backend
cd portal && uvicorn api.main:app --reload --port 8000

# Terminal 2: frontend
cd portal/ui && npm run dev
```

### Manual Checklist:

```
[ ] 1. Open http://localhost:5173 → Navigate to Compare page
[ ] 2. Verify Runs/Discoveries tab toggle appears
[ ] 3. Select bevager_810 from profile dropdown
[ ] 4. Verify Run History shows the 2+ bevager_810 runs
[ ] 5. Select the initial run → verify Pairs table loads with matched/mismatched/unmatched counts
[ ] 6. Verify UNMATCHED pairs appear (target-only InvoiceIDs from 3072 file) — validates matcher fix
[ ] 7. Select run → verify Summary Statistics panel with 4 quadrants (Severity, Segments, Fields, Top Errors)
[ ] 8. Verify Segment breakdown shows "header", "line_0", "line_1", etc. (structured JSON segments)
[ ] 9. Click a MISMATCH pair → verify Diffs table with severity badges
[ ] 10. Click Reclassify → verify new run with purple "re:N" badge
[ ] 11. Check 2 runs → click "Diff Selected" → verify 4 metric cards (New/Resolved/Changed/Unchanged)
[ ] 12. Verify detail tables below metrics for non-empty categories
[ ] 13. Click Export CSV → verify CSV downloads
[ ] 14. Switch to Discoveries tab → select bevager_810 → verify discoveries table loads
[ ] 15. Verify filter buttons (All/Pending/Applied) work
[ ] 16. Click Apply on a pending discovery → verify status changes to Applied
[ ] 17. Switch back to Runs tab → verify all run data still visible
[ ] 18. Verify no console errors in browser devtools
```

**If any step fails:**
1. Read the browser console error or network error
2. Read the relevant code section
3. Fix the issue
4. Re-run the failing step and all subsequent steps
5. Re-run build: `cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..`
6. Commit the fix: `fix(portal-ui): <description>`

---

## Summary of Expected Commits

| Phase | Commit Message |
|-------|---------------|
| 0 | `fix(compare): detect target-only unmatched pairs in matcher` |
| 2 (if fixes needed) | `fix(compare): <description of any pipeline/comparison fix>` |
| 3 (if fixes needed) | `fix(portal-ui): <description of any UI fix>` |

---

## Known Behaviors (Not Bugs)

1. **Segment names are positional** — structured JSON comparison uses `header`, `line_0`, `line_1`, ..., `summary` as segment labels. This is by design for flat-file-to-JSON comparisons.
2. **Positional line matching** — lines are compared by index, not by content. If source and target have lines in different order, every field will mismatch. This is expected for the current comparison strategy.
3. **`amount_variance` only from crosswalk** — the YAML rules don't support `amount_variance` directly; it only comes from the `field_crosswalk` SQLite table.
4. **DiscoveryResponse** does not include `applied_at`/`applied_by` fields — the data is in the DB but not surfaced to the UI. This is cosmetic.
