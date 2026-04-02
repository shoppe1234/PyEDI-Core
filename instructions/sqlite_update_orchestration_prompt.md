# SQLite Comparator Update — Orchestration Prompt

**Purpose:** Implement 10 improvements to the pyedi_core comparator SQLite reporting — error discovery, reclassification, data model enrichment, enriched CSV export, summary statistics, and new profiles. Closes all gaps identified in `sqlLiteReport.md`.

**Task list:** `instructions/sqlite_update_task_list.md`
**Gap analysis:** `sqlLiteReport.md` (root of repo)
**Coding standards:** `CLAUDE.md`
**Compare engine:** `pyedi_core/comparator/` (store.py, engine.py, rules.py, models.py, __init__.py)
**Portal API:** `portal/api/routes/compare.py`, `portal/api/models.py`
**Tests:** `tests/test_comparator.py` (existing, 410 lines — do not modify)

---

## Rules of Engagement

1. **Sequential within phases** — complete each task fully (including its test gate) before starting the next.
2. **Phase gates are hard stops** — do not start Phase B until Phase A gate passes.
3. **Read before writing** — always read the target file and its imports before making any change.
4. **Minimal diffs** — change only what the task requires. No drive-by fixes, no extra comments, no renaming.
5. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
6. **Stop on red** — if any test gate fails, diagnose and fix before proceeding.
7. **Data-driven, zero hardcoding** — all rules, thresholds, and classification live in YAML config or SQLite.
8. **Profile-driven** — adding a new transaction type or partner is a config change, never a code change.
9. **CLI must still work** — `pyedi run`, `pyedi test`, `pyedi validate`, `pyedi compare` must remain functional after every task.
10. **Match existing patterns** — follow conventions in the codebase exactly. All store functions accept `db_path`, no global state. All models are dataclasses. All new fields have defaults for backward compatibility.
11. **Existing tests untouched** — `tests/test_comparator.py` must pass without modification throughout.

---

## Pre-Flight

Before starting any task, run these checks:

```bash
# Verify existing tests pass
python -m pytest tests/test_comparator.py -v --tb=short 2>&1 | tail -20
python -m pytest tests/ -v --tb=short 2>&1 | tail -30

# Verify portal tests pass
python -m pytest portal/tests/ -v --tb=short 2>/dev/null || echo "No portal tests or failures — check manually"

# Verify pyedi CLI is functional
python -m pycoreedi compare --list-profiles --config config/config.yaml
python -m pycoreedi compare --profile bevager_810 --source-dir outbound/bevager/control --target-dir outbound/bevager/test -v

# Verify compare engine is importable
python -c "from pyedi_core.comparator import compare, export_csv; print('Compare engine OK')"
python -c "from pyedi_core.comparator.store import init_db, get_runs; print('Store OK')"

# Verify current DB exists and has data
python -c "
from pyedi_core.comparator.store import get_runs, init_db
init_db('data/compare.db')
runs = get_runs('data/compare.db')
print(f'DB has {len(runs)} runs')
"
```

If anything fails at baseline, **stop and fix before proceeding**.

---

# PHASE A: Core Parity

> **Prerequisite:** Pre-flight green.
> **Deliverables:** Conditional qualifier in flat compare, error discovery workflow, reclassification command.

---

## Task A3: Conditional Qualifier in Flat Compare

**Investigate:**
```bash
# Read the X12 implementation (already working)
# engine.py lines 173-178 — conditional_qualifier in compare_segment_fields()
# engine.py lines 247-308 — _compare_flat_dict() — currently missing this logic
```

**Execute:**
1. Read `pyedi_core/comparator/engine.py`
2. In `_compare_flat_dict()`, after the `if rule.severity == "ignore": continue` block (~line 290), add:

```python
# Conditional qualifier logic (parity with compare_segment_fields)
if rule.conditional_qualifier:
    if key not in src_dict and src_dict.get(rule.conditional_qualifier):
        continue
    if key not in tgt_dict and tgt_dict.get(rule.conditional_qualifier):
        continue
```

**Test gate:**
```bash
# Existing tests still pass
python -m pytest tests/test_comparator.py -v --tb=short

# Manual verification: the logic mirrors lines 174-178 exactly
```

**Commit:** `feat(comparator): add conditional_qualifier support to flat compare`

---

## Task A1: Error Discovery Table + Workflow

This is the largest single task. Execute sub-steps sequentially.

### A1.1-A1.2: Models

**Investigate:**
```bash
# Read current models
# models.py — FieldDiff dataclass (lines 69-77)
```

**Execute:**
1. Read `pyedi_core/comparator/models.py`
2. Add `wildcard_fallback: bool = False` field to `FieldDiff` (after `description`, with default — backward compatible)
3. Add new `DiscoveryRecord` dataclass after `FieldDiff`:

```python
@dataclass
class DiscoveryRecord:
    """A (segment, field) combo classified by wildcard fallback — needs human review."""
    profile: str
    segment: str
    field: str
    source_value: str | None
    target_value: str | None
    suggested_severity: str = "hard"
    applied: bool = False
    discovered_at: str = ""
```

### A1.3: Rules helper

**Execute:**
1. Read `pyedi_core/comparator/rules.py`
2. Add after `get_field_rule()`:

```python
def is_wildcard_match(rules: CompareRules, segment: str, field: str) -> bool:
    """Return True if (segment, field) resolves only to (*,*) or the hardcoded default."""
    lookup = {(r.segment, r.field) for r in rules.classification}
    return (
        (segment, field) not in lookup
        and (segment, "*") not in lookup
        and ("*", field) not in lookup
    )
```

### A1.4: Engine — emit wildcard signal

**Execute:**
1. Read `pyedi_core/comparator/engine.py`
2. Add `from pyedi_core.comparator.rules import is_wildcard_match` to imports
3. In `compare_segment_fields()`, where `FieldDiff` is constructed (~line 188), add:
   ```python
   wildcard_fallback=is_wildcard_match(rules, segment_id, field_name),
   ```
4. In `_compare_flat_dict()`, where `FieldDiff` is constructed (~line 299), add:
   ```python
   wildcard_fallback=is_wildcard_match(rules, "*", key),
   ```

### A1.5-A1.6: Store — error_discovery table + CRUD

**Execute:**
1. Read `pyedi_core/comparator/store.py`
2. Add to `_SCHEMA` string (after the `field_crosswalk` CREATE TABLE, before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS error_discovery (
    id               INTEGER PRIMARY KEY,
    run_id           INTEGER NOT NULL REFERENCES compare_runs(id),
    profile          TEXT NOT NULL,
    segment          TEXT NOT NULL,
    field            TEXT NOT NULL,
    source_value     TEXT,
    target_value     TEXT,
    suggested_severity TEXT NOT NULL DEFAULT 'hard',
    applied          BOOLEAN NOT NULL DEFAULT 0,
    applied_at       TEXT,
    applied_by       TEXT,
    discovered_at    TEXT NOT NULL,
    UNIQUE(profile, segment, field)
);

CREATE INDEX IF NOT EXISTS idx_discovery_profile ON error_discovery(profile);
CREATE INDEX IF NOT EXISTS idx_discovery_applied ON error_discovery(applied);
```

3. Add import: `from pyedi_core.comparator.models import DiscoveryRecord` (add to existing import line)
4. Add three new functions following existing patterns (accept `db_path`, use `_connect()`, try/finally):

```python
def insert_discoveries(db_path: str, discoveries: list[DiscoveryRecord]) -> int:
    """Bulk-insert discovery records (INSERT OR IGNORE). Returns count inserted."""
    # Use executemany with INSERT OR IGNORE
    # Return cursor.rowcount or count via changes()

def get_discoveries(db_path: str, profile: str, applied: bool | None = None) -> list[dict]:
    """Return discovery records for a profile, optionally filtered by applied status."""
    # If applied is None, return all; if True/False, filter by applied column

def apply_discovery(db_path: str, discovery_id: int, applied_by: str = "user") -> None:
    """Mark a discovery as applied (sets applied=1, applied_at, applied_by)."""
    # UPDATE error_discovery SET applied=1, applied_at=NOW, applied_by=? WHERE id=?
```

### A1.7: Orchestrator — collect discoveries

**Execute:**
1. Read `pyedi_core/comparator/__init__.py`
2. Add imports: `DiscoveryRecord` from models, `insert_discoveries` from store, `is_wildcard_match` from rules
3. In `compare()`, after the for-pair loop (after line ~88, before `finished_at`):
   - Collect all diffs across all results where `wildcard_fallback=True`
   - Deduplicate by `(segment, field)` — keep first occurrence's values
   - Build `DiscoveryRecord` objects with `profile=profile.name`, `discovered_at=now`
   - Call `insert_discoveries(db_path, discoveries)`
   - Store the returned count for the print statement
4. After `update_run()` and before `return summary`, print:
   ```python
   if discovery_count:
       print(f"Discovered {discovery_count} new field combinations not yet classified")
   ```

**Important:** To collect diffs, you need to accumulate them during the loop. Add a `all_diffs: list[FieldDiff] = []` before the loop and `all_diffs.extend(result.diffs)` inside it.

### A1.8: CLI flags

**Execute:**
1. Read `pyedi_core/main.py` — compare subparser section (~lines 112-144)
2. Add two new arguments to `compare_parser`:
   - `--show-discoveries` with optional `--profile` (already exists on compare)
   - `--apply-discovery` accepting an integer ID
3. In `_handle_compare()`, add early returns for these flags:
   - `--show-discoveries`: load db_path from config, call `get_discoveries()`, print table
   - `--apply-discovery`: call `apply_discovery()`, then optionally `upsert_crosswalk()` to promote to crosswalk

### A1.9-A1.10: Portal API

**Execute:**
1. Read `portal/api/models.py` — add `DiscoveryResponse` Pydantic model:
   ```python
   class DiscoveryResponse(BaseModel):
       id: int
       run_id: int
       profile: str
       segment: str
       field: str
       source_value: Optional[str] = None
       target_value: Optional[str] = None
       suggested_severity: str
       applied: bool
       discovered_at: str
   ```

2. Read `portal/api/routes/compare.py` — add two endpoints:
   ```python
   @router.get("/discoveries", response_model=List[DiscoveryResponse])
   def list_discoveries(profile: str, applied: Optional[bool] = None):
       db_path = _get_db_path()
       return get_discoveries(db_path, profile, applied=applied)

   @router.post("/discoveries/{discovery_id}/apply")
   def apply_discovery_endpoint(discovery_id: int):
       db_path = _get_db_path()
       apply_discovery(db_path, discovery_id)
       return {"status": "applied"}
   ```

**Test gate (Phase A1):**
```bash
python -m pytest tests/test_comparator.py -v --tb=short
# Run a compare and check for discoveries
python -m pycoreedi compare --profile bevager_810 --source-dir outbound/bevager/control --target-dir outbound/bevager/test -v
python -m pycoreedi compare --show-discoveries --profile bevager_810 --config config/config.yaml
```

**Commit:** `feat(comparator): add error discovery table and workflow (A1)`

---

## Task A2: Reclassification (New Run)

### A2.1-A2.2: Store functions

**Execute:**
1. Read `pyedi_core/comparator/store.py`
2. Add migration in `_migrate_db()` (create this function if it doesn't exist yet from B1 — if A1 didn't add it, add it now):
   ```python
   _add_column_if_missing(conn, "compare_runs", "reclassified_from", "INTEGER")
   ```
3. Call `_migrate_db(conn)` from `init_db()` after `executescript(_SCHEMA)`
4. Add new store functions:

```python
def get_all_diffs_for_run(db_path: str, run_id: int) -> list[dict]:
    """Return all diffs for a run, joined with pair info."""
    # SELECT d.*, p.match_value, p.source_file, p.target_file
    # FROM compare_diffs d JOIN compare_pairs p ON d.pair_id = p.id
    # WHERE p.run_id = ?

def clone_run_for_reclassify(db_path: str, original_run_id: int) -> int:
    """Create a new run row cloned from original, with reclassified_from set. Returns new run_id."""
    # SELECT original run, INSERT new row with same profile/dirs/match_key
    # Set reclassified_from = original_run_id

def clone_pairs_for_reclassify(db_path: str, original_run_id: int, new_run_id: int) -> dict[int, int]:
    """Copy pairs from original run to new run. Returns {old_pair_id: new_pair_id}."""
    # SELECT pairs WHERE run_id = original, INSERT with new_run_id
```

### A2.3: Model update

**Execute:**
1. Read `pyedi_core/comparator/models.py`
2. Add `reclassified_from: int | None = None` to `RunSummary` dataclass

### A2.4: Orchestrator — reclassify function

**Execute:**
1. Read `pyedi_core/comparator/__init__.py`
2. Add `reclassify()` function:

```python
def reclassify(run_id: int, db_path: str, config_path: str) -> RunSummary:
    """Create a new run by re-evaluating diffs from an existing run against current rules + crosswalk.

    1. Get original run (profile name) via get_run()
    2. Load profile from config via load_profile()
    3. Load rules + crosswalk
    4. Clone run + pairs into new run
    5. Get all original diffs
    6. For each diff: re-resolve severity via get_field_rule() with current rules
    7. Insert diffs with updated severities into new pairs
    8. Calculate counts: per-pair diff_count, run matched/mismatched/unmatched
    9. Update new run summary
    10. Return new RunSummary
    """
```

Key implementation detail: group original diffs by `pair_id`, use the `{old_pair_id: new_pair_id}` mapping from `clone_pairs_for_reclassify()` to assign diffs to new pairs.

### A2.5: CLI flag

**Execute:**
1. Read `pyedi_core/main.py`
2. Add `--reclassify-run` argument (type=int) to compare subparser
3. In `_handle_compare()`, add early return: if `parsed.reclassify_run`, call `reclassify()`, print summary

### A2.6-A2.7: Portal API

**Execute:**
1. Read `portal/api/routes/compare.py`
2. Add endpoint:
   ```python
   @router.post("/runs/{run_id}/reclassify", response_model=CompareRunResponse)
   def reclassify_run(run_id: int):
       db_path = _get_db_path()
       summary = reclassify(run_id, db_path, _CONFIG_PATH)
       return CompareRunResponse(...)
   ```
3. Read `portal/api/models.py` — add `reclassified_from: Optional[int] = None` to `CompareRunResponse`

**Test gate (Phase A2):**
```bash
python -m pytest tests/test_comparator.py -v --tb=short
# Reclassify an existing run
python -m pycoreedi compare --reclassify-run 34 --config config/config.yaml
# Verify new run created
python -c "
from pyedi_core.comparator.store import get_runs, init_db
init_db('data/compare.db')
runs = get_runs('data/compare.db', limit=5)
for r in runs:
    print(f'Run #{r.run_id} profile={r.profile} matched={r.matched} mismatched={r.mismatched}')
"
```

**Commit:** `feat(comparator): add reclassification as new run (A2)`

---

## Phase A Gate

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
python -m pycoreedi compare --profile bevager_810 --source-dir outbound/bevager/control --target-dir outbound/bevager/test -v
python -m pycoreedi compare --show-discoveries --profile bevager_810 --config config/config.yaml
```

All tests pass, discoveries appear, reclassify creates new run. **Proceed to Phase B.**

---

# PHASE B: Data Model Enrichment

> **Prerequisite:** Phase A gate green.
> **Deliverables:** Trading partner/tx type on runs, segment-aware crosswalk, crosswalk pre-seeding.

---

## Task B1: Trading Partner + Transaction Type

**Execute:**
1. Read `pyedi_core/comparator/store.py`
2. Add or extend `_migrate_db()` (may already exist from A2):
   ```python
   _add_column_if_missing(conn, "compare_runs", "trading_partner", "TEXT")
   _add_column_if_missing(conn, "compare_runs", "transaction_type", "TEXT")
   _add_column_if_missing(conn, "compare_runs", "run_notes", "TEXT")
   ```
3. Update `insert_run()` signature: add `trading_partner: str = ""`, `transaction_type: str = ""`. Include in INSERT statement.
4. Update `_row_to_run_summary()`: read new columns with safe dict-style access. Handle missing columns for old DBs.
5. Read `pyedi_core/comparator/models.py` — add fields to `CompareProfile` and `RunSummary`
6. Read `pyedi_core/comparator/__init__.py`:
   - Update `_parse_profile()` to read `trading_partner` and `transaction_type` from config dict
   - Update `compare()` to pass them to `insert_run()`
7. Read `config/config.yaml` — add `trading_partner` and `transaction_type` to each profile:
   - `bevager_810`: `trading_partner: "Bevager"`, `transaction_type: "810"`
   - `810_invoice`: `trading_partner: ""`, `transaction_type: "810"`
   - (etc for all profiles)
8. Read `portal/api/models.py` — add optional fields to `CompareRunResponse` and `CompareProfileResponse`
9. Read `portal/api/routes/compare.py` — thread new fields in response construction

**Test gate:**
```bash
python -m pytest tests/test_comparator.py -v --tb=short
python -m pycoreedi compare --profile bevager_810 --source-dir outbound/bevager/control --target-dir outbound/bevager/test -v
# Verify trading partner appears
python -c "
from pyedi_core.comparator.store import get_run, init_db
init_db('data/compare.db')
from pyedi_core.comparator.store import get_runs
runs = get_runs('data/compare.db', limit=3)
for r in runs:
    print(f'Run #{r.run_id} partner={r.trading_partner} type={r.transaction_type}')
"
```

**Commit:** `feat(comparator): add trading partner and transaction type to compare_runs (B1)`

---

## Task B3: Segment Column on field_crosswalk

**Execute:**
1. Read `pyedi_core/comparator/store.py`
2. In `_migrate_db()`, add:
   ```python
   _add_column_if_missing(conn, "field_crosswalk", "segment", "TEXT DEFAULT '*'")
   ```
3. Add a constraint migration function that checks if the old UNIQUE constraint exists and rebuilds:
   ```python
   def _migrate_crosswalk_constraint(conn):
       # Check current DDL for UNIQUE(profile, field_name)
       # If old constraint: CREATE field_crosswalk_new with UNIQUE(profile, segment, field_name)
       # INSERT INTO new SELECT ... FROM old (with segment defaulting to '*')
       # DROP old, RENAME new
   ```
4. Update `upsert_crosswalk()`: add `segment: str = "*"` parameter, include in INSERT
5. Update `get_crosswalk()`: include segment in returned dict
6. Update `get_crosswalk_field()`: add optional `segment: str = "*"` parameter
7. Read `pyedi_core/comparator/rules.py` — update `load_crosswalk_overrides()`:
   - Still return `dict[str, FieldRule]` for backward compatibility
   - Set `FieldRule.segment` from the crosswalk entry instead of hardcoding `"*"`
8. Read `pyedi_core/comparator/engine.py` — update `_apply_crosswalk()`:
   - When matching crosswalk entries, check segment matches (or is `"*"`)

**Test gate:**
```bash
python -m pytest tests/test_comparator.py -v --tb=short
# Verify crosswalk migration works
python -c "
from pyedi_core.comparator.store import init_db, get_crosswalk
init_db('data/compare.db')
xwalk = get_crosswalk('data/compare.db', 'bevager_810')
for x in xwalk:
    print(x)
"
```

**Commit:** `feat(comparator): add segment column to field_crosswalk (B3)`

---

## Task B2: Pre-Seed Crosswalk for All Profiles

**Execute:**
1. Read `pyedi_core/scaffold.py`
2. Add new function:
   ```python
   def scaffold_crosswalk_from_rules(rules_path: str, profile: str, db_path: str) -> int:
       """Read classification entries from rules YAML, seed crosswalk. Returns count upserted."""
       # load_rules(rules_path)
       # For each classification entry (excluding (*,*) wildcard):
       #   upsert_crosswalk(db_path, profile, field_name, segment=entry.segment, ...)
       # Return count
   ```
3. Read `pyedi_core/main.py` — add `--from-profile` option to `scaffold-rules` subparser
4. Read `pyedi_core/comparator/__init__.py` — in `compare()`, after loading crosswalk (~line 54):
   ```python
   if not crosswalk and profile.rules_file:
       from pyedi_core.scaffold import scaffold_crosswalk_from_rules
       scaffold_crosswalk_from_rules(profile.rules_file, profile.name, db_path)
       crosswalk = load_crosswalk_overrides(db_path, profile.name)
   ```

**Test gate:**
```bash
python -m pytest tests/test_comparator.py -v --tb=short
# Seed crosswalk for 810_invoice
python -m pycoreedi scaffold-rules --from-profile 810_invoice --db data/compare.db --config config/config.yaml
python -c "
from pyedi_core.comparator.store import get_crosswalk, init_db
init_db('data/compare.db')
xwalk = get_crosswalk('data/compare.db', '810_invoice')
print(f'810_invoice crosswalk: {len(xwalk)} entries')
for x in xwalk[:5]:
    print(f'  {x[\"field_name\"]} severity={x[\"severity\"]} numeric={x[\"numeric\"]}')
"
```

**Commit:** `feat(comparator): pre-seed crosswalk from rules YAML (B2)`

---

## Phase B Gate

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
python -m pycoreedi compare --profile bevager_810 --source-dir outbound/bevager/control --target-dir outbound/bevager/test -v
```

Trading partner/tx type stored. Crosswalk has segment column. Auto-seed works. **Proceed to Phase C.**

---

# PHASE C: Reporting

> **Prerequisite:** Phase B gate green.
> **Deliverables:** Enriched CSV export, summary statistics queries + CLI + API.

---

## Task C1: Enrich CSV Export

**Execute:**
1. Read `pyedi_core/comparator/__init__.py` — `export_csv()` function (lines 106-142)
2. Rewrite `export_csv()`:
   - Fetch run metadata via `get_run(db_path, run_id)` (already imported)
   - Write `#`-prefixed metadata header:
     ```
     # Profile: {run.profile}
     # Trading Partner: {run.trading_partner}
     # Transaction Type: {run.transaction_type}
     # Run ID: {run_id}
     # Started: {run.started_at}
     # Total Pairs: {run.total_pairs} | Matched: {run.matched} | Mismatched: {run.mismatched} | Unmatched: {run.unmatched}
     ```
   - Write 15-column header: `timestamp,profile,trading_partner,run_id,pair_id,source_file,target_file,match_value,status,segment,field,severity,source_value,target_value,description`
   - For each pair+diff, populate timestamp from `run.started_at`, profile from `run.profile`, trading_partner from `run.trading_partner`
   - Track severity counts during iteration
   - Write summary footer: `# Summary: hard={n}, soft={n}, ignore={n}`

**Test gate:**
```bash
python -m pytest tests/test_comparator.py -v --tb=short
python -m pycoreedi compare --profile bevager_810 --source-dir outbound/bevager/control --target-dir outbound/bevager/test --export-csv
# Check the CSV
head -20 reports/compare/compare_run_*.csv | tail -1
# Verify 15 columns and # header present
```

**Commit:** `feat(comparator): enrich CSV export with metadata header and 15 columns (C1)`

---

## Task C2: Summary Statistics Queries

**Execute:**
1. Read `pyedi_core/comparator/store.py`
2. Add four query functions (all join diffs to pairs WHERE run_id = ?):

```python
def get_severity_breakdown(db_path: str, run_id: int) -> dict[str, int]:
    """COUNT(*) GROUP BY severity for all diffs in a run."""

def get_segment_breakdown(db_path: str, run_id: int) -> dict[str, int]:
    """COUNT(*) GROUP BY segment for all diffs in a run."""

def get_field_breakdown(db_path: str, run_id: int) -> dict[str, int]:
    """COUNT(*) GROUP BY field for all diffs in a run."""

def get_top_errors(db_path: str, run_id: int, limit: int = 10) -> list[dict]:
    """Top N (segment, field) combos by occurrence count.
    Returns [{segment, field, count}, ...]"""
```

3. Read `pyedi_core/main.py` — add `--summary` flag (type=int, metavar="RUN_ID") to compare subparser
   - When present: load db_path, call all four functions, print formatted tables

4. Read `portal/api/models.py` — add:
   ```python
   class CompareSummaryResponse(BaseModel):
       severity: dict[str, int]
       segments: dict[str, int]
       fields: dict[str, int]
       top_errors: list[dict]
   ```

5. Read `portal/api/routes/compare.py` — add:
   ```python
   @router.get("/runs/{run_id}/summary", response_model=CompareSummaryResponse)
   def get_run_summary(run_id: int):
       db_path = _get_db_path()
       return CompareSummaryResponse(
           severity=get_severity_breakdown(db_path, run_id),
           segments=get_segment_breakdown(db_path, run_id),
           fields=get_field_breakdown(db_path, run_id),
           top_errors=get_top_errors(db_path, run_id),
       )
   ```

**Test gate:**
```bash
python -m pytest tests/test_comparator.py -v --tb=short
python -m pycoreedi compare --summary 34 --config config/config.yaml
```

**Commit:** `feat(comparator): add summary statistics queries and CLI/API (C2)`

---

## Phase C Gate

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
python -m pycoreedi compare --profile bevager_810 --source-dir outbound/bevager/control --target-dir outbound/bevager/test --export-csv -v
python -m pycoreedi compare --summary 34 --config config/config.yaml
```

CSV is self-contained with 15 columns. Summary stats work. **Proceed to Phase D.**

---

# PHASE D: Polish

> **Prerequisite:** Phase C gate green.
> **Deliverables:** 855/860 profiles, run comparison view.

---

## Task D1: 855 PO Ack + 860 PO Change Profiles

**Execute:**
1. Read `config/compare_rules/810_invoice.yaml` for the template structure
2. Create `config/compare_rules/855_po_ack.yaml`:
   - BAK segment rules (BAK03 = PO number, BAK01 = purpose code)
   - N1*ST, N1*BY qualifier rules
   - REF, DTM, PO1 classification entries
   - Default `(*,*)` wildcard: hard severity
3. Create `config/compare_rules/860_po_change.yaml`:
   - BCH segment rules (BCH03 = PO number, BCH01 = purpose code)
   - N1*ST, N1*BY qualifier rules
   - REF, DTM, POC classification entries
   - Default `(*,*)` wildcard: hard severity
4. Read `config/config.yaml` — add two profile entries:
   ```yaml
   855_po_ack:
     description: "EDI 855 Purchase Order Acknowledgment"
     trading_partner: ""
     transaction_type: "855"
     match_key:
       segment: "BAK"
       field: "BAK03"
     segment_qualifiers:
       N1: "N101"
       REF: "REF01"
       DTM: "DTM01"
       PO1: null
     rules_file: "config/compare_rules/855_po_ack.yaml"

   860_po_change:
     description: "EDI 860 Purchase Order Change"
     trading_partner: ""
     transaction_type: "860"
     match_key:
       segment: "BCH"
       field: "BCH03"
     segment_qualifiers:
       N1: "N101"
       REF: "REF01"
       DTM: "DTM01"
       POC: null
     rules_file: "config/compare_rules/860_po_change.yaml"
   ```

**Test gate:**
```bash
python -m pycoreedi compare --list-profiles --config config/config.yaml
# Should show 855_po_ack and 860_po_change
python -c "
from pyedi_core.comparator import load_profile
p = load_profile('config/config.yaml', '855_po_ack')
print(f'{p.name} match_key={p.match_key.segment}:{p.match_key.field}')
"
```

**Commit:** `feat(comparator): add 855 PO Ack and 860 PO Change compare profiles (D1)`

---

## Task D2: Run Comparison View (Diff Two Runs)

**Execute:**
1. Read `pyedi_core/comparator/models.py` — add:
   ```python
   @dataclass
   class RunDiffResult:
       new_errors: list[dict]       # in run B but not A
       resolved_errors: list[dict]  # in run A but not B
       changed_errors: list[dict]   # same (seg,field) different severity
       unchanged_count: int
   ```

2. Read `pyedi_core/comparator/store.py` — add:
   ```python
   def compare_two_runs(db_path: str, run_id_a: int, run_id_b: int) -> RunDiffResult:
       """Diff two runs by match_value. Returns new/resolved/changed/unchanged."""
       # For each match_value in both runs:
       #   Get diffs as set of (segment, field, severity) tuples
       #   new = B - A (by segment,field key)
       #   resolved = A - B (by segment,field key)
       #   changed = intersection where severity differs
       #   unchanged = intersection where severity matches
   ```

3. Read `pyedi_core/main.py` — add `--diff-runs` argument (nargs=2, type=int, metavar=("RUN_A", "RUN_B"))
   - When present: call `compare_two_runs()`, print results

4. Read `portal/api/routes/compare.py` — add:
   ```python
   @router.get("/runs/{run_id_a}/diff/{run_id_b}")
   def diff_runs(run_id_a: int, run_id_b: int):
       db_path = _get_db_path()
       result = compare_two_runs(db_path, run_id_a, run_id_b)
       return {
           "new_errors": result.new_errors,
           "resolved_errors": result.resolved_errors,
           "changed_errors": result.changed_errors,
           "unchanged_count": result.unchanged_count,
       }
   ```

**Test gate:**
```bash
python -m pytest tests/test_comparator.py -v --tb=short
# Run compare, change a rule, reclassify, then diff the two
python -m pycoreedi compare --diff-runs 33 34 --config config/config.yaml
```

**Commit:** `feat(comparator): add run comparison view to diff two runs (D2)`

---

## Phase D Gate

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
python -m pycoreedi compare --list-profiles --config config/config.yaml
```

---

# FINAL GATE

```bash
# All tests green
python -m pytest tests/ -v --tb=short
python -m pytest portal/tests/ -v --tb=short 2>/dev/null || true

# Full CLI smoke test
python -m pycoreedi compare --profile bevager_810 --source-dir outbound/bevager/control --target-dir outbound/bevager/test -v --export-csv
python -m pycoreedi compare --show-discoveries --profile bevager_810 --config config/config.yaml
python -m pycoreedi compare --summary 34 --config config/config.yaml
python -m pycoreedi compare --list-profiles --config config/config.yaml

# Migration safety: delete DB and recreate from scratch
mv data/compare.db data/compare.db.bak
python -m pycoreedi compare --profile bevager_810 --source-dir outbound/bevager/control --target-dir outbound/bevager/test -v
mv data/compare.db.bak data/compare.db

# Portal API (if running)
# curl http://localhost:8000/api/compare/runs
# curl http://localhost:8000/api/compare/discoveries?profile=bevager_810
# curl http://localhost:8000/api/compare/runs/34/summary
```

All gates pass. Implementation complete.
