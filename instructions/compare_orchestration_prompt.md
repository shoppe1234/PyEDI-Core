# PyEDI Compare — Orchestration Prompt

**Purpose:** Port `json810Compare` comparator engine into `pyedi_core/comparator/` and add a `/compare` page to the portal. Executed as Phase D (core engine) and Phase E (portal integration) — after portal Phases A-C are complete.

**Codebase context:**
- Python project: `pyedi_core/` (EDI/CSV/XML processing pipeline)
- Source port: `C:\Users\SeanHoppe\VS\json810Compare\comparator.py` (852 lines, Google Sheets-backed)
- Design spec: `instructions/compare_integration_plan.md`
- Portal orchestration: `instructions/portal_orchestration_prompt.md` (Phases A-C)
- Tests: `tests/` (pytest)
- Coding standards: see `CLAUDE.md`

**Prerequisites:**
- Portal Phases A-C complete (FastAPI + React running)
- SQLite database schema supplied by user (see Phase D, Task D3)

---

## Rules of Engagement

1. **Sequential within phases** — complete each task fully (including its test gate) before starting the next.
2. **Phase gates are hard stops** — do not start Phase E until Phase D gate passes.
3. **Read before writing** — always read the target file and its imports before making any change.
4. **Read the source** — before porting any function from `json810Compare/comparator.py`, read the original implementation.
5. **Minimal diffs** — change only what the task requires. No drive-by fixes.
6. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
7. **Stop on red** — if any test gate fails, diagnose and fix before proceeding.
8. **No business logic in API or UI layers** — Phase E endpoints are thin wrappers. All logic stays in `pyedi_core/comparator/`.
9. **CLI must still work standalone** — `pyedi run`, `pyedi test`, `pyedi validate` must remain functional.
10. **Profile-driven** — adding a new transaction type is a config change, never a code change.

---

## Pre-Flight

Before starting any task:

```bash
# Verify portal Phases A-C are complete
pytest tests/ -v --tb=short 2>&1 | tail -20
pytest portal/tests/ -v --tb=short 2>/dev/null || true
cd portal/frontend && npm run build && cd ../..

# Verify pyedi CLI is functional
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt --json > /dev/null
python -m pyedi_core.main test --verify

# Verify source code is accessible
ls "C:/Users/SeanHoppe/VS/json810Compare/comparator.py"
```

If any tests fail at baseline, **stop and fix them first**.

---

# PHASE D: Compare Core Engine

> **Prerequisite:** Portal Phases A-C green. SQLite schema supplied by user.
> **Deliverables:** `pyedi_core/comparator/` module, `pyedi compare` CLI subcommand, config files, tests.
> **Duration:** 9 tasks.

---

## Task D1: Create `pyedi_core/comparator/models.py` — Dataclasses

**Investigate:**
```bash
# Read the compare integration plan — models section
# Read comparator.py error_result dict structure (lines ~180-195)
# Read comparator.py SEGMENT_QUALIFIERS dict
```

**Execute:**
1. Read `C:/Users/SeanHoppe/VS/json810Compare/comparator.py` — identify all data structures (error dicts, rule dicts, segment structures)
2. Create `pyedi_core/comparator/__init__.py` — empty for now
3. Create `pyedi_core/comparator/models.py` with these dataclasses:

```python
@dataclass
class MatchKeyConfig:
    segment: str | None       # X12 segment ID (e.g., "BIG")
    field: str | None         # X12 field (e.g., "BIG02")
    json_path: str | None     # Dot-notation for flat JSON (e.g., "header.invoice_number")

@dataclass
class CompareProfile:
    name: str                           # e.g. "810_invoice"
    description: str
    match_key: MatchKeyConfig
    segment_qualifiers: dict[str, str | None]
    rules_file: str

@dataclass
class MatchEntry:
    file_path: str
    match_value: str
    transaction_index: int
    transaction_data: dict

@dataclass
class MatchPair:
    source: MatchEntry
    target: MatchEntry | None
    match_value: str

@dataclass
class FieldRule:
    segment: str
    field: str
    severity: str             # hard | soft | ignore
    ignore_case: bool
    numeric: bool
    conditional_qualifier: str | None

@dataclass
class CompareRules:
    classification: list[FieldRule]
    ignore: list[dict[str, str]]

@dataclass
class FieldDiff:
    segment: str
    field: str
    severity: str
    source_value: str | None
    target_value: str | None
    description: str

@dataclass
class CompareResult:
    pair: MatchPair
    status: str               # MATCH | MISMATCH | UNMATCHED
    diffs: list[FieldDiff]
    timestamp: str

@dataclass
class RunSummary:
    run_id: int
    profile: str
    total_pairs: int
    matched: int
    mismatched: int
    unmatched: int
    started_at: str
    finished_at: str
```

4. All fields must have type hints.

**Test Gate:**
```bash
# Models import without error
python -c "
from pyedi_core.comparator.models import (
    MatchKeyConfig, CompareProfile, MatchEntry, MatchPair,
    FieldRule, CompareRules, FieldDiff, CompareResult, RunSummary
)
print('All models imported OK')
"

# Full suite still passes
pytest tests/ -v --tb=short
```

**Commit:** `feat(comparator): add dataclass models for compare engine`

---

## Task D2: Create `pyedi_core/comparator/rules.py` — Rule Loading

**Investigate:**
```bash
# Read comparator.py load_error_classification() — understand rule structure from Google Sheets
# Read comparator.py load_ignore_rules()
# Read comparator.py get_rule_property() — wildcard fallback logic
# Read compare_integration_plan.md — per-profile rules YAML format
```

**Execute:**
1. Read `C:/Users/SeanHoppe/VS/json810Compare/comparator.py` — focus on `load_error_classification()`, `load_ignore_rules()`, `get_rule_property()`
2. Create `pyedi_core/comparator/rules.py` with:

```python
def load_rules(rules_path: str) -> CompareRules:
    """Load per-profile rules YAML, return CompareRules with classification + ignore lists.

    YAML format:
      classification:
        - segment: "N1"
          field: "N102"
          severity: "hard"
          ignore_case: true
      ignore:
        - segment: "SE"
          field: "SE01"
          reason: "..."
    """

def get_field_rule(rules: CompareRules, segment: str, field: str) -> FieldRule:
    """Resolve rule for (segment, field) with wildcard fallback.

    Priority: exact (segment, field) > (segment, *) > (*, field) > (*, *)
    Default: hard severity, exact match, no special flags.

    Ported from: comparator.py get_rule_property()
    """
```

3. Port the wildcard resolution logic from `get_rule_property()` in comparator.py
4. Rules come from YAML files (not Google Sheets) — the YAML format is defined in `compare_integration_plan.md`

**Test Gate:**
```bash
# Create a minimal test rules file
python -c "
import yaml, tempfile, os
rules = {
    'classification': [
        {'segment': 'N1', 'field': 'N102', 'severity': 'hard', 'ignore_case': True},
        {'segment': 'IT1', 'field': 'IT104', 'severity': 'hard', 'numeric': True},
        {'segment': '*', 'field': '*', 'severity': 'hard'},
    ],
    'ignore': [
        {'segment': 'SE', 'field': 'SE01', 'reason': 'Segment count varies'},
        {'segment': 'ISA', 'field': '*', 'reason': 'Envelope-level'},
    ]
}
tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
yaml.dump(rules, tmp)
tmp.close()

from pyedi_core.comparator.rules import load_rules, get_field_rule
loaded = load_rules(tmp.name)
print(f'Classification rules: {len(loaded.classification)}')
print(f'Ignore rules: {len(loaded.ignore)}')

# Test wildcard fallback
rule = get_field_rule(loaded, 'N1', 'N102')
assert rule.ignore_case == True, f'Expected ignore_case=True, got {rule.ignore_case}'
print(f'N1/N102: severity={rule.severity}, ignore_case={rule.ignore_case}')

rule = get_field_rule(loaded, 'REF', 'REF02')
assert rule.severity == 'hard', f'Expected hard (wildcard), got {rule.severity}'
print(f'REF/REF02 (wildcard): severity={rule.severity}')

os.unlink(tmp.name)
print('Rules loading + wildcard resolution OK')
"

pytest tests/ -v --tb=short
```

**Commit:** `feat(comparator): add rules.py with YAML loading and wildcard resolution`

---

## Task D3: Create `pyedi_core/comparator/store.py` — SQLite Storage

**Prerequisite:** User supplies the SQLite database schema. If not yet supplied, **stop and ask**.

**Investigate:**
```bash
# Read compare_integration_plan.md — SQLite schema section
# Review the CREATE TABLE statements for compare_runs, compare_pairs, compare_diffs
```

**Execute:**
1. Create `pyedi_core/comparator/store.py` with:

```python
def init_db(db_path: str) -> None:
    """Create tables if they don't exist. Uses schema supplied by user."""

def insert_run(db_path: str, profile: str, source_dir: str, target_dir: str, match_key: str) -> int:
    """Insert a new compare_runs row, return run_id."""

def update_run(db_path: str, run_id: int, summary: RunSummary) -> None:
    """Update run with finished_at and summary counts."""

def insert_pair(db_path: str, run_id: int, pair: MatchPair, status: str, diff_count: int) -> int:
    """Insert compare_pairs row, return pair_id."""

def insert_diffs(db_path: str, pair_id: int, diffs: list[FieldDiff]) -> None:
    """Bulk insert compare_diffs rows."""

def get_runs(db_path: str, profile: str | None = None, limit: int = 20) -> list[RunSummary]:
    """Query compare_runs, optionally filtered by profile."""

def get_run(db_path: str, run_id: int) -> RunSummary | None:
    """Get a single run by ID."""

def get_pairs(db_path: str, run_id: int, status: str | None = None, limit: int = 50) -> list[dict]:
    """Query compare_pairs for a run, optionally filtered by status."""

def get_diffs(db_path: str, pair_id: int) -> list[FieldDiff]:
    """Query compare_diffs for a pair."""
```

2. Use `sqlite3` stdlib — no ORM
3. Use parameterized queries (no string interpolation) to prevent SQL injection
4. All functions accept `db_path: str` — no global state
5. `init_db()` uses `CREATE TABLE IF NOT EXISTS` — idempotent

**Test Gate:**
```bash
python -c "
import tempfile, os
from pyedi_core.comparator.store import init_db, insert_run, get_runs

db = os.path.join(tempfile.mkdtemp(), 'test.db')
init_db(db)

run_id = insert_run(db, '810_invoice', '/source', '/target', 'BIG:BIG02')
print(f'Inserted run_id={run_id}')

runs = get_runs(db)
assert len(runs) == 1
print(f'Run: profile={runs[0].profile}, started_at={runs[0].started_at}')

os.unlink(db)
print('SQLite store OK')
"

pytest tests/ -v --tb=short
```

**Commit:** `feat(comparator): add store.py SQLite CRUD for compare runs/pairs/diffs`

---

## Task D4: Create `pyedi_core/comparator/matcher.py` — File Pairing

**Investigate:**
```bash
# Read comparator.py find_invoice_in_json() — how it extracts ST/SE transactions
# Read comparator.py find_target_file_for_invoice() — how it pairs files
# Read comparator.py load_target_files_cache() / load_source_files_cache()
# Read compare_integration_plan.md — matcher.py spec
```

**Execute:**
1. Read `C:/Users/SeanHoppe/VS/json810Compare/comparator.py` — focus on `find_invoice_in_json()`, `find_target_file_for_invoice()`, `load_target_files_cache()`
2. Create `pyedi_core/comparator/matcher.py` with:

```python
def extract_match_values(json_data: dict, match_key: MatchKeyConfig) -> list[MatchEntry]:
    """Extract ALL matching values from a JSON file.

    For X12: walks every ST/SE transaction, finds segment, extracts field.
    For flat JSON (CSV/cXML): resolves dot-notation json_path.
    Returns list of MatchEntry(match_value, transaction_index, transaction_data).

    Ported from: comparator.py find_invoice_in_json() — generalized from BIG02
    """

def build_match_index(directory: str, match_key: MatchKeyConfig) -> dict[str, list[MatchEntry]]:
    """Scan all JSON files in a directory, return {match_value: [MatchEntry, ...]}.

    Ported from: comparator.py load_target_files_cache() — generalized to index by any match key
    """

def pair_transactions(
    source_dir: str,
    target_dir: str,
    match_key: MatchKeyConfig
) -> list[MatchPair]:
    """Pair source and target transactions by match key value.

    Ported from: comparator.py find_target_file_for_invoice() — direct dir scan instead of Sheet lookup
    """
```

3. **Key changes from comparator.py:**
   - No Google Sheet intermediary — files paired directly by scanning directories
   - Multi-transaction aware — extracts every ST/SE loop, not just the first match
   - Format-agnostic — X12 uses `segment/field`, CSV/cXML uses `json_path`
4. The JSON file structure is: `{"document": {"segments": [{"segment": "BIG", "fields": [{"name": "BIG02", "content": "INV-123"}]}]}}`
5. ST/SE boundaries: transaction starts at `segment == "ST"`, ends at `segment == "SE"`

**Test Gate:**
```bash
# Test with real JSON files if available, or create synthetic ones
python -c "
import json, tempfile, os
from pyedi_core.comparator.models import MatchKeyConfig
from pyedi_core.comparator.matcher import extract_match_values, pair_transactions

# Create synthetic X12 JSON
source_json = {
    'document': {
        'segments': [
            {'segment': 'ST', 'fields': [{'name': 'ST01', 'content': '810'}]},
            {'segment': 'BIG', 'fields': [
                {'name': 'BIG01', 'content': 'BIG'},
                {'name': 'BIG02', 'content': 'INV-001'}
            ]},
            {'segment': 'SE', 'fields': [{'name': 'SE01', 'content': '5'}]},
        ]
    }
}

target_json = {
    'document': {
        'segments': [
            {'segment': 'ST', 'fields': [{'name': 'ST01', 'content': '810'}]},
            {'segment': 'BIG', 'fields': [
                {'name': 'BIG01', 'content': 'BIG'},
                {'name': 'BIG02', 'content': 'INV-001'}
            ]},
            {'segment': 'SE', 'fields': [{'name': 'SE01', 'content': '5'}]},
        ]
    }
}

# Write to temp dirs
src_dir = tempfile.mkdtemp()
tgt_dir = tempfile.mkdtemp()
with open(os.path.join(src_dir, 'source.json'), 'w') as f:
    json.dump(source_json, f)
with open(os.path.join(tgt_dir, 'target.json'), 'w') as f:
    json.dump(target_json, f)

mk = MatchKeyConfig(segment='BIG', field='BIG02', json_path=None)
entries = extract_match_values(source_json, mk)
assert len(entries) == 1
assert entries[0].match_value == 'INV-001'
print(f'Extracted: {entries[0].match_value} at tx_index={entries[0].transaction_index}')

pairs = pair_transactions(src_dir, tgt_dir, mk)
assert len(pairs) == 1
assert pairs[0].target is not None
print(f'Paired: {pairs[0].match_value} — source + target matched')

# Cleanup
import shutil
shutil.rmtree(src_dir)
shutil.rmtree(tgt_dir)
print('Matcher OK')
"

pytest tests/ -v --tb=short
```

**Commit:** `feat(comparator): add matcher.py with file pairing and transaction extraction`

---

## Task D5: Create `pyedi_core/comparator/engine.py` — Comparison Logic

**Investigate:**
```bash
# Read comparator.py compare_transactions() — the core comparison orchestrator
# Read comparator.py match_segments_by_qualifier() — segment matching by qualifier
# Read comparator.py compare_segment_fields() — field-level comparison with rules
# Read comparator.py segment_to_dict() — segment normalization
# Read comparator.py group_segments_by_id() — segment grouping
```

**Execute:**
1. Read `C:/Users/SeanHoppe/VS/json810Compare/comparator.py` — focus on `compare_transactions()`, `match_segments_by_qualifier()`, `compare_segment_fields()`, `segment_to_dict()`, `group_segments_by_id()`
2. Create `pyedi_core/comparator/engine.py` with:

```python
def segment_to_dict(segment: dict) -> dict[str, str]:
    """Convert {"segment": "N1", "fields": [{"name":"N101","content":"ST"},...]} to {"N101":"ST",...}.

    Direct port from: comparator.py segment_to_dict()
    """

def group_segments_by_id(segments: list[dict]) -> dict[str, list[dict]]:
    """Group segments by segment ID. {"N1": [seg1, seg2], "REF": [seg1, seg2, seg3]}.

    Direct port from: comparator.py group_segments_by_id()
    """

def match_segments_by_qualifier(
    source_segments: list[dict],
    target_segments: list[dict],
    qualifier_field: str | None
) -> list[tuple[dict, dict | None]]:
    """Match multi-instance segments by qualifier value, fallback to positional.

    Ported from: comparator.py match_segments_by_qualifier()
    - qualifier_field="N101": matches N1 segments where N101 values are equal
    - qualifier_field=None: matches by position (N3, N4)
    """

def compare_segment_fields(
    source_seg: dict,
    target_seg: dict | None,
    segment_id: str,
    qualifier_value: str | None,
    rules: CompareRules
) -> list[FieldDiff]:
    """Compare all fields in a matched segment pair, applying rules.

    Ported from: comparator.py compare_segment_fields()
    Handles: ignore_case, numeric, conditional_qualifier, severity classification
    """

def compare_pair(
    pair: MatchPair,
    rules: CompareRules,
    qualifiers: dict[str, str | None]
) -> CompareResult:
    """Compare a matched source/target pair.

    1. Group segments by ID for both source and target
    2. For each segment type, match by qualifier
    3. Compare fields using rules
    4. Return CompareResult with all diffs

    Ported from: comparator.py compare_transactions()
    """

def compare_flat_pair(
    pair: MatchPair,
    rules: CompareRules
) -> CompareResult:
    """Compare flat JSON pairs (CSV/cXML output).

    No segment structure — walks JSON keys, applies json_path rules.
    """
```

3. **Key changes from comparator.py:**
   - `qualifiers` dict is passed in (from profile config), not hardcoded `SEGMENT_QUALIFIERS`
   - Error dicts replaced by `FieldDiff` dataclasses
   - No Google Sheets I/O — pure computation
   - Added `compare_flat_pair()` for CSV/cXML (no segments)
4. Preserve the exact comparison semantics: numeric → `float(src) == float(tgt)`, case-insensitive → `.lower()`, conditional → skip if qualifier absent

**Test Gate:**
```bash
python -c "
from pyedi_core.comparator.engine import segment_to_dict, group_segments_by_id

# Test segment_to_dict
seg = {'segment': 'N1', 'fields': [
    {'name': 'N101', 'content': 'ST'},
    {'name': 'N102', 'content': 'Ship To Corp'}
]}
d = segment_to_dict(seg)
assert d == {'N101': 'ST', 'N102': 'Ship To Corp'}
print(f'segment_to_dict: {d}')

# Test group_segments_by_id
segs = [
    {'segment': 'N1', 'fields': [{'name': 'N101', 'content': 'ST'}]},
    {'segment': 'N1', 'fields': [{'name': 'N101', 'content': 'BT'}]},
    {'segment': 'REF', 'fields': [{'name': 'REF01', 'content': 'ZZ'}]},
]
grouped = group_segments_by_id(segs)
assert len(grouped['N1']) == 2
assert len(grouped['REF']) == 1
print(f'group_segments_by_id: N1={len(grouped[\"N1\"])}, REF={len(grouped[\"REF\"])}')
print('Engine helpers OK')
"

pytest tests/ -v --tb=short
```

**Commit:** `feat(comparator): add engine.py with segment matching and field comparison`

---

## Task D6: Create `pyedi_core/comparator/__init__.py` — Public API

**Execute:**
1. Create `pyedi_core/comparator/__init__.py` with:

```python
def compare(
    profile: CompareProfile,
    source_dir: str,
    target_dir: str,
    db_path: str
) -> RunSummary:
    """Run a full comparison. Public API entry point.

    1. Load rules from profile.rules_file
    2. Pair transactions via matcher.pair_transactions()
    3. Insert run into SQLite via store
    4. For each pair: compare via engine, insert results into SQLite
    5. Update run summary
    6. Return RunSummary
    """

def export_csv(db_path: str, run_id: int, output_dir: str) -> str:
    """Export a run's results to CSV. Returns the output file path.

    Format: run_id,timestamp,source_file,target_file,match_value,status,
            segment,field,severity,source_value,target_value,description
    """

def load_profile(config_path: str, profile_name: str) -> CompareProfile:
    """Load a named profile from config.yaml compare.profiles section."""

def list_profiles(config_path: str) -> list[CompareProfile]:
    """List all available profiles from config.yaml."""
```

2. Wire together matcher → engine → store in `compare()`
3. `export_csv()` reads from SQLite via `store.get_pairs()` + `store.get_diffs()`, writes CSV

**Test Gate:**
```bash
python -c "
from pyedi_core.comparator import compare, export_csv, load_profile, list_profiles
print('Public API imports OK')
"

pytest tests/ -v --tb=short
```

**Commit:** `feat(comparator): wire public API in __init__.py (compare, export_csv, load/list profiles)`

---

## Task D7: Add `compare` subcommand to `pyedi_core/main.py`

**Investigate:**
```bash
# Read main.py — understand the subparser pattern (run, test, validate)
# Mirror the validate subparser structure
```

**Execute:**
1. Read `pyedi_core/main.py`
2. Add `compare` subparser:
   - `--profile` (required) — profile name from config.yaml
   - `--source-dir` — source JSON directory
   - `--target-dir` — target JSON directory
   - `--match-json-path` — override match key for flat JSON
   - `--rules` — override rules YAML path
   - `--export-csv` — write CSV report
   - `--verbose / -v` — show per-field diffs
   - `--config / -c` — config file path (default: `./config/config.yaml`)
   - `--list-profiles` — list profiles and exit
   - `--db` — SQLite database path (default from config)
3. Add dispatch: `if parsed.command == "compare": return _handle_compare(parsed)`
4. Add `_handle_compare(parsed) -> int`
5. Add `_print_compare_summary(summary, verbose)` — human-readable console output

**Test Gate:**
```bash
# CLI help works
python -m pyedi_core.main compare --help

# List profiles (requires config.yaml compare section — may need D8 first)
# python -m pyedi_core.main compare --list-profiles

# Existing CLI still works
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt --json > /dev/null
python -m pyedi_core.main test --verify

pytest tests/ -v --tb=short
```

**Commit:** `feat(cli): add pyedi compare subcommand`

---

## Task D8: Create config files — profiles + rules YAMLs

**Execute:**
1. Add `compare` section to `config/config.yaml` (see compare_integration_plan.md for full structure):
   - `sqlite_db: "data/compare.db"`
   - `csv_dir: "reports/compare"`
   - Profiles: `810_invoice`, `850_purchase_order`, `856_asn`, `820_payment`, `csv_generic`, `cxml_generic`
2. Create `config/compare_rules/` directory
3. Create per-profile rules YAMLs:
   - `config/compare_rules/810_invoice.yaml`
   - `config/compare_rules/850_po.yaml`
   - `config/compare_rules/856_asn.yaml`
   - `config/compare_rules/820_payment.yaml`
   - `config/compare_rules/csv_generic.yaml`
   - `config/compare_rules/cxml_generic.yaml`
4. Create `data/` directory (for SQLite DB)
5. Create `reports/compare/` directory (for CSV exports)

**Test Gate:**
```bash
# Profiles load from config
python -c "
from pyedi_core.comparator import list_profiles
profiles = list_profiles('./config/config.yaml')
print(f'Profiles: {len(profiles)}')
for p in profiles:
    print(f'  {p.name}: {p.description} — match_key={p.match_key}')
"

# Rules load for each profile
python -c "
from pyedi_core.comparator.rules import load_rules
for name in ['810_invoice', '850_po', '856_asn', '820_payment', 'csv_generic', 'cxml_generic']:
    rules = load_rules(f'config/compare_rules/{name}.yaml')
    print(f'{name}: {len(rules.classification)} classification, {len(rules.ignore)} ignore')
"

# End-to-end: list profiles via CLI
python -m pyedi_core.main compare --list-profiles

pytest tests/ -v --tb=short
```

**Commit:** `feat(comparator): add compare profiles and per-profile rules YAML files`

---

## Task D9: Create `tests/test_comparator.py`

**Execute:**
1. Create `tests/test_comparator.py` with:
   - **Unit tests** (`@pytest.mark.unit`):
     - `test_segment_to_dict` — converts segment object to flat dict
     - `test_group_segments_by_id` — groups segments correctly
     - `test_match_segments_by_qualifier` — qualifier matching + positional fallback
     - `test_compare_segment_fields_exact` — exact match produces no diffs
     - `test_compare_segment_fields_mismatch` — value difference produces FieldDiff
     - `test_compare_segment_fields_numeric` — `70.00` vs `70.0300` match with numeric=True
     - `test_compare_segment_fields_case_insensitive` — `GFS Canada` vs `GFS CANADA` match
     - `test_compare_segment_fields_conditional` — conditional qualifier skip logic
     - `test_rules_wildcard_fallback` — `(*, *)` default applies when no specific rule
     - `test_rules_exact_over_wildcard` — specific rule takes priority
     - `test_match_key_x12` — extract BIG02 from X12 JSON
     - `test_match_key_json_path` — extract value via dot-notation for flat JSON
     - `test_models_serializable` — all dataclasses serialize to dict
   - **Integration tests** (`@pytest.mark.integration`):
     - `test_pair_transactions_matched` — synthetic source + target paired by match key
     - `test_pair_transactions_unmatched` — source with no target → MatchPair.target is None
     - `test_compare_full_pipeline` — profile → pair → compare → store → retrieve
     - `test_export_csv` — run comparison, export CSV, verify format
     - `test_store_init_idempotent` — `init_db()` called twice doesn't error
     - `test_store_insert_and_query` — insert run + pairs + diffs, query them back
   - Use `tmp_path` fixture for SQLite DB and temp directories
   - Create synthetic JSON fixtures within tests (not external files)

**Test Gate:**
```bash
# New tests pass
pytest tests/test_comparator.py -v --tb=short

# Full suite
pytest tests/ -v --tb=short
```

**Commit:** `test(comparator): add unit and integration tests for compare engine`

---

## PHASE D GATE

**All of these must pass before starting Phase E:**

```bash
# 1. Full test suite green
pytest tests/ -v --tb=short

# 2. Compare CLI works
python -m pyedi_core.main compare --list-profiles

# 3. Public API importable
python -c "
from pyedi_core.comparator import compare, export_csv, load_profile, list_profiles
from pyedi_core.comparator.models import CompareResult, RunSummary, FieldDiff
from pyedi_core.comparator.rules import load_rules, get_field_rule
from pyedi_core.comparator.matcher import pair_transactions, extract_match_values
from pyedi_core.comparator.engine import compare_pair
from pyedi_core.comparator.store import init_db, get_runs
print('All comparator modules importable')
"

# 4. Existing CLI unchanged
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt --json > /dev/null
python -m pyedi_core.main test --verify

# 5. Portal still works
pytest portal/tests/ -v --tb=short 2>/dev/null || true
cd portal/frontend && npm run build && cd ../..

# 6. Show commits
git log --oneline -9
```

**Checklist:**
- [ ] 0 test failures
- [ ] `pyedi_core/comparator/` module complete (models, rules, matcher, engine, store, __init__)
- [ ] `pyedi compare` CLI works with `--profile`, `--list-profiles`, `--export-csv`, `--verbose`
- [ ] 6 config/rules YAML files created
- [ ] SQLite store works (init, insert, query)
- [ ] File pairing works for X12 and flat JSON
- [ ] Comparison logic preserves semantics from `json810Compare/comparator.py`
- [ ] All comparator tests pass
- [ ] Existing CLI + portal unaffected
- [ ] 9 clean commits

---

# PHASE E: Compare Portal Integration

> **Prerequisite:** Phase D gate passed. Portal Phases A-C complete.
> **Deliverables:** `/compare` API routes, `/compare` React page, nav link.
> **Duration:** 5 tasks.

---

## Task E1: Pydantic models for compare (`portal/api/models.py`)

**Execute:**
1. Read `portal/api/models.py` — understand existing model patterns
2. Add compare-specific models:
   - `CompareProfileResponse` — mirrors `CompareProfile` dataclass
   - `CompareRunRequest(profile, source_dir, target_dir, match_json_path?)`
   - `CompareRunResponse` — mirrors `RunSummary`
   - `ComparePairResponse` — pair detail with source/target file, status, diff count
   - `CompareFieldDiffResponse` — mirrors `FieldDiff`
   - `CompareRulesResponse` — rules as JSON
   - `CompareRulesUpdateRequest` — updated rules body

**Test Gate:**
```bash
python -c "
from portal.api.models import CompareProfileResponse, CompareRunRequest, CompareRunResponse
print('Compare models OK')
"
```

**Commit:** `feat(portal): add Pydantic models for compare endpoints`

---

## Task E2: Compare API routes (`portal/api/routes/compare.py`)

**Investigate:**
```bash
# Read portal/api/routes/validate.py — understand the route pattern
# Read compare_integration_plan.md — API endpoint table
```

**Execute:**
1. Create `portal/api/routes/compare.py` with `APIRouter(prefix="/api/compare")`
2. Endpoints (all thin wrappers around `pyedi_core.comparator`):

| Method | Path | Wraps |
|---|---|---|
| `GET` | `/api/compare/profiles` | `comparator.list_profiles()` |
| `POST` | `/api/compare/run` | `comparator.compare()` |
| `GET` | `/api/compare/runs` | `store.get_runs()` |
| `GET` | `/api/compare/runs/{id}` | `store.get_run()` |
| `GET` | `/api/compare/runs/{id}/pairs` | `store.get_pairs()` |
| `GET` | `/api/compare/runs/{id}/pairs/{pair_id}/diffs` | `store.get_diffs()` |
| `GET` | `/api/compare/runs/{id}/export` | `comparator.export_csv()` — returns `FileResponse` |
| `GET` | `/api/compare/profiles/{name}/rules` | `rules.load_rules()` as JSON |
| `PUT` | `/api/compare/profiles/{name}/rules` | Writes updated rules to profile YAML |

3. Register router in `portal/api/app.py`

**Test Gate:**
```bash
uvicorn portal.api.app:app --port 8000 &
sleep 2

# Profiles
curl -s http://localhost:8000/api/compare/profiles | python -m json.tool | head -10

# Runs (may be empty)
curl -s http://localhost:8000/api/compare/runs | python -m json.tool

# Rules for 810
curl -s http://localhost:8000/api/compare/profiles/810_invoice/rules | python -m json.tool | head -10

kill %1 2>/dev/null

pytest tests/ -v --tb=short
```

**Commit:** `feat(portal): add /api/compare endpoints`

---

## Task E3: Compare React page (`/compare`)

**Investigate:**
```bash
# Read portal/frontend/src/pages/Validate.tsx — understand the page pattern
# Read compare_integration_plan.md — Page Layout section
```

**Execute:**
1. Create `portal/frontend/src/pages/Compare.tsx` — see layout in `compare_integration_plan.md`
2. Sections:
   - **New Comparison** panel:
     - Profile dropdown (loads from `GET /api/compare/profiles`)
     - Profile detail display (description, match key, qualifiers)
     - Source dir + target dir inputs
     - "Run Comparison" button → `POST /api/compare/run`
     - "Export CSV" button → `GET /api/compare/runs/{id}/export`
   - **Run History** table:
     - Loads from `GET /api/compare/runs`
     - Columns: Run #, Date, Profile, Key, Pairs, Match, Diff, Unmatched
     - Click row to expand detail
   - **Run Detail** panel (expandable):
     - Loads from `GET /api/compare/runs/{id}/pairs`
     - Columns: Source File, Target File, Match Value, Status (with StatusBadge)
     - Status filter (MATCH / MISMATCH / UNMATCHED)
   - **Pair Detail** panel (click MISMATCH row):
     - Loads from `GET /api/compare/runs/{id}/pairs/{pair_id}/diffs`
     - Columns: Segment, Field, Severity (with StatusBadge), Source Value, Target Value, Description
   - **Rules Editor** (collapsible):
     - Loads from `GET /api/compare/profiles/{name}/rules`
     - Inline JSON editor
     - Save button → `PUT /api/compare/profiles/{name}/rules`
3. Use `@tanstack/react-query` for data fetching
4. Loading states, error states, empty states all handled

**Test Gate:**
```bash
cd portal/frontend && npm run build
# Build succeeds with 0 errors

# Manual: navigate to http://localhost:5173/compare
# Verify profile dropdown populates
# Verify run history loads (may be empty)
```

**Commit:** `feat(portal): add Compare page with profile selection, run history, and diff viewer`

---

## Task E4: Add `/compare` route + nav link

**Execute:**
1. Read `portal/frontend/src/App.tsx` — add route `<Route path="/compare" element={<Compare />} />`
2. Read `portal/frontend/src/components/Layout.tsx` — add nav link for Compare
3. Place it after Manifest in the sidebar (5th page)

**Test Gate:**
```bash
cd portal/frontend && npm run build
npx tsc --noEmit

# Manual: verify sidebar shows Compare link, navigating to /compare renders the page
```

**Commit:** `feat(portal): add /compare route and navigation link`

---

## Task E5: Compare API integration tests

**Execute:**
1. Add to `portal/tests/test_api.py` (or create `portal/tests/test_compare_api.py`):
   - `test_compare_profiles` — GET /api/compare/profiles returns list
   - `test_compare_run_and_query` — POST run, GET runs, GET pairs, GET diffs
   - `test_compare_export_csv` — GET export returns CSV content
   - `test_compare_rules_read` — GET rules returns valid JSON
   - `test_compare_rules_update` — PUT rules, GET rules, verify change persisted

**Test Gate:**
```bash
pytest portal/tests/ -v --tb=short

# Full engine suite still green
pytest tests/ -v --tb=short
```

**Commit:** `test(portal): add Compare API integration tests`

---

## PHASE E GATE

```bash
# 1. All engine tests green
pytest tests/ -v --tb=short

# 2. All API tests green (including compare)
pytest portal/tests/ -v --tb=short

# 3. Frontend builds
cd portal/frontend && npm run build && npx tsc --noEmit && cd ../..

# 4. Compare endpoints respond
uvicorn portal.api.app:app --port 8000 &
sleep 2
curl -sf http://localhost:8000/api/compare/profiles
curl -sf http://localhost:8000/api/compare/runs
curl -sf http://localhost:8000/api/compare/profiles/810_invoice/rules
kill %1 2>/dev/null

# 5. CLI still standalone
python -m pyedi_core.main compare --list-profiles
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt --json > /dev/null
python -m pyedi_core.main test --verify

# 6. Dev script works
bash portal/dev.sh &
sleep 5
curl -sf http://localhost:8000/api/health
curl -sf http://localhost:5173/ > /dev/null
kill %1 2>/dev/null

# 7. Show commits
git log --oneline -5
```

**Checklist:**
- [ ] 0 test failures (engine + API + frontend build)
- [ ] `/api/compare/*` endpoints all responding
- [ ] `/compare` page renders in portal with profile dropdown, run history, diff viewer
- [ ] Rules editor loads and saves
- [ ] CSV export works
- [ ] CLI `pyedi compare` still works standalone
- [ ] Existing portal pages unaffected
- [ ] 5 clean commits

---

# POST-FLIGHT

After both phases complete:

```bash
# Final full verification
pytest tests/ -v --tb=short
pytest portal/tests/ -v --tb=short
cd portal/frontend && npm run build && npx tsc --noEmit && cd ../..

# CLI standalone
python -m pyedi_core.main compare --list-profiles
python -m pyedi_core.main validate --dsl tpm810SourceFF.txt
python -m pyedi_core.main test --verify

# API standalone
uvicorn portal.api.app:app --port 8000 &
sleep 2
curl -sf http://localhost:8000/api/health
curl -sf http://localhost:8000/api/compare/profiles
kill %1 2>/dev/null

# Show all commits
git log --oneline -14

# Show compare module structure
find pyedi_core/comparator/ -type f -name "*.py" | sort
find portal/api/routes/ -type f -name "*.py" | sort
find portal/frontend/src/pages/ -type f -name "*.tsx" | sort
```

**Final checklist:**
- [ ] Phase D: 9 commits — models, rules, store, matcher, engine, public API, CLI, config, tests
- [ ] Phase E: 5 commits — Pydantic models, API routes, React page, nav link, API tests
- [ ] 0 test failures across all suites
- [ ] CLI works without portal
- [ ] Portal works without modifying pyedi_core behavior
- [ ] `pyedi compare --profile 810_invoice` works end-to-end
- [ ] React `/compare` page renders profile selection, run history, and diff viewer
- [ ] Profile-driven: new transaction type = config change only
- [ ] SQLite stores run history, queryable from CLI + portal

---

## Resumption Protocol

If execution is interrupted mid-task:
1. Identify the last successful commit: `git log --oneline -5`
2. Determine which phase/task to resume from
3. Run the **pre-flight** check for the current phase:
   - Phase D: `pytest tests/ -v --tb=short`
   - Phase E: pre-flight + `uvicorn portal.api.app:app --port 8000` starts + `cd portal/frontend && npm run build`
4. Resume from the current task's **Investigate** step

---

*This document lives at `instructions/compare_orchestration_prompt.md`. It is an instruction artifact, not a runnable file.*
