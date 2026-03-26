# PyEDI Compare — Integration Plan

> **Origin:** `C:\Users\SeanHoppe\VS\json810Compare` (comparator.py)
> **Destination:** `pyedi_core/comparator/` module + `pyedi compare` subcommand
> **Storage:** SQLite (replaces Google Sheets)
> **Output:** React portal page (`/compare`) + CSV export

---

## What json810Compare Does Today

```
config.json (partner directory paths)
    |
main.py (extract invoice headers from JSON, populate Google Sheet)
    |
comparator.py (for each invoice row in the sheet):
    1. Read BIG02 (invoice number) from Column E
    2. Find source JSON in NA_output_dir by filename
    3. Scan all target JSONs in CA_output_dir for matching BIG02
    4. Extract the ST/SE transaction containing that BIG02
    5. Match segments by qualifier (N1→N101, REF→REF01, DTM→DTM01)
    6. Compare fields with rules: severity, ignore_case, numeric, conditional_qualifier
    7. Write errors to "Comparison Report" sheet
    |
errorConfig.py (discover new error types, suggest severity)
```

**What's hardcoded:**
- BIG02 as the sole matching key (invoice number)
- SEGMENT_QUALIFIERS dict: `{N1: N101, REF: REF01, DTM: DTM01, PER: PER01}`
- Google Sheets for input tracking, config, and output
- Two directories: NA (source) and CA (target) — both hardcoded in config.json

**What's reusable:**
- Segment-level qualifier matching (`match_segments_by_qualifier`)
- Field comparison engine (case-insensitive, numeric precision, conditional qualifiers)
- Error classification with severity levels (Hard/Soft/Ignore)
- Error discovery pattern (auto-detect new error types from comparison results)

---

## Design: Transaction-Type Profiles

The core problem: BIG02 is an 810-specific concept. Every transaction type has its own matching key, its own segment qualifiers, and its own comparison rules. The system must be profile-driven so adding a new transaction type is a config change, not a code change.

### Profile Registry

Each transaction type is a **compare profile** — a self-contained bundle of:
- **Match key:** how to pair source ↔ target files
- **Segment qualifiers:** how to match segments of the same type within a transaction
- **Rules:** field-level comparison behavior (severity, case, numeric, conditional)
- **Ignore list:** fields to skip entirely

### Known Transaction Types

| Transaction | Match Key | Qualifier Segments | Notes |
|---|---|---|---|
| 810 (Invoice) | `BIG:BIG02` | N1→N101, REF→REF01, DTM→DTM01, PER→PER01, IT1→IT101 | Line items matched by IT101 (line number) |
| 850 (Purchase Order) | `BEG:BEG03` | N1→N101, REF→REF01, DTM→DTM01, PER→PER01, PO1→PO101 | PO1 lines matched by PO101 |
| 856 (ASN) | `BSN:BSN02` | N1→N101, REF→REF01, DTM→DTM01, HL→HL01, LIN→LIN01 | Hierarchical loops via HL |
| 820 (Payment) | `BPR:BPR16` | N1→N101, REF→REF01, DTM→DTM01, ENT→ENT01 | Entity matched by ENT01 |
| 855 (PO Ack) | `BAK:BAK03` | N1→N101, REF→REF01, DTM→DTM01, PO1→PO101 | Mirrors 850 structure |
| CSV | `json_path` | n/a (flat structure) | User defines the path, e.g., `header.po_number` |
| cXML | `json_path` | n/a (flat structure) | User defines the path, e.g., `header.order_id` |

### Configuration in `config.yaml`

```yaml
compare:
  # Global defaults
  sqlite_db: "data/compare.db"
  csv_dir: "reports/compare"

  # Transaction-type profiles
  profiles:
    810_invoice:
      description: "EDI 810 Invoice comparison"
      match_key:
        segment: "BIG"
        field: "BIG02"
      segment_qualifiers:
        N1: "N101"
        REF: "REF01"
        DTM: "DTM01"
        PER: "PER01"
        IT1: "IT101"       # Line items matched by line number
        N3: null            # Match by position
        N4: null            # Match by position
      rules_file: "config/compare_rules/810_invoice.yaml"

    850_purchase_order:
      description: "EDI 850 Purchase Order comparison"
      match_key:
        segment: "BEG"
        field: "BEG03"
      segment_qualifiers:
        N1: "N101"
        REF: "REF01"
        DTM: "DTM01"
        PER: "PER01"
        PO1: "PO101"       # Line items matched by line number
        N3: null
        N4: null
      rules_file: "config/compare_rules/850_po.yaml"

    856_asn:
      description: "EDI 856 Advance Ship Notice comparison"
      match_key:
        segment: "BSN"
        field: "BSN02"
      segment_qualifiers:
        N1: "N101"
        REF: "REF01"
        DTM: "DTM01"
        HL: "HL01"          # Hierarchical level ID
        LIN: "LIN01"
      rules_file: "config/compare_rules/856_asn.yaml"

    820_payment:
      description: "EDI 820 Payment Order comparison"
      match_key:
        segment: "BPR"
        field: "BPR16"
      segment_qualifiers:
        N1: "N101"
        REF: "REF01"
        DTM: "DTM01"
        ENT: "ENT01"
      rules_file: "config/compare_rules/820_payment.yaml"

    csv_generic:
      description: "CSV output comparison (user-defined match key)"
      match_key:
        json_path: "header.invoice_number"   # override per use case
      segment_qualifiers: {}                  # flat structure, no segments
      rules_file: "config/compare_rules/csv_generic.yaml"

    cxml_generic:
      description: "cXML output comparison (user-defined match key)"
      match_key:
        json_path: "header.order_id"         # override per use case
      segment_qualifiers: {}
      rules_file: "config/compare_rules/cxml_generic.yaml"
```

### Per-Profile Rules Files (`config/compare_rules/<profile>.yaml`)

Each profile has its own rules file. This keeps rules scoped — an 810 rule doesn't accidentally affect an 856 comparison.

**Example: `config/compare_rules/810_invoice.yaml`**

```yaml
classification:
  - segment: "N1"
    field: "N102"
    severity: "hard"
    ignore_case: true

  - segment: "IT1"
    field: "IT104"
    severity: "hard"
    numeric: true          # Compare as float (exact, no epsilon)

  - segment: "IT1"
    field: "IT109"
    severity: "soft"
    conditional_qualifier: "IT108"

  # Default: anything not listed is hard severity, exact match
  - segment: "*"
    field: "*"
    severity: "hard"

ignore:
  - segment: "SE"
    field: "SE01"
    reason: "Segment count varies by implementation"

  - segment: "ISA"
    field: "*"
    reason: "Envelope-level fields are not business data"
```

**Example: `config/compare_rules/850_po.yaml`**

```yaml
classification:
  - segment: "N1"
    field: "N102"
    severity: "hard"
    ignore_case: true

  - segment: "PO1"
    field: "PO104"
    severity: "hard"
    numeric: true          # Unit price

  - segment: "PO1"
    field: "PO102"
    severity: "hard"
    numeric: true          # Quantity

  - segment: "*"
    field: "*"
    severity: "hard"

ignore:
  - segment: "SE"
    field: "SE01"
    reason: "Segment count varies"

  - segment: "ISA"
    field: "*"
    reason: "Envelope-level"
```

**Example: `config/compare_rules/csv_generic.yaml`**

```yaml
# CSV/cXML outputs are flat JSON — no segment structure.
# Rules use json_path patterns instead of segment/field.
classification:
  - json_path: "header.*"
    severity: "hard"

  - json_path: "lines.*.amount"
    severity: "hard"
    numeric: true

  - json_path: "lines.*.description"
    severity: "soft"
    ignore_case: true

  - json_path: "*"
    severity: "hard"

ignore:
  - json_path: "_metadata.*"
    reason: "Internal metadata, not business data"

  - json_path: "id"
    reason: "Generated UUID, not comparable"

  - json_path: "timestamp"
    reason: "Processing timestamp, not comparable"

  - json_path: "correlation_id"
    reason: "Trace ID, not comparable"
```

### Adding a New Transaction Type

To add comparison support for a new transaction type (e.g., 846 Inventory Inquiry):

1. Add a profile to `config.yaml` under `compare.profiles`:
   ```yaml
   846_inventory:
     description: "EDI 846 Inventory Inquiry"
     match_key:
       segment: "BIA"
       field: "BIA03"
     segment_qualifiers:
       N1: "N101"
       REF: "REF01"
       QTY: "QTY01"
       LIN: "LIN01"
     rules_file: "config/compare_rules/846_inventory.yaml"
   ```
2. Create `config/compare_rules/846_inventory.yaml` with classification + ignore rules.
3. Run: `pyedi compare --profile 846_inventory --source-dir ... --target-dir ...`

**No code changes required.** The engine reads the profile, extracts match keys, applies qualifiers, and uses the rules file — all from config.

---

## Architecture

```
pyedi_core/
├── comparator/
│   ├── __init__.py           # Public API: compare(), export_csv()
│   ├── engine.py             # Core comparison logic (ported from comparator.py)
│   ├── matcher.py            # File pairing by match_key + segment qualifier matching
│   ├── models.py             # Dataclasses: CompareResult, FieldDiff, MatchPair, etc.
│   ├── rules.py              # Load/apply compare_rules.yaml (replaces Sheets config)
│   └── store.py              # SQLite read/write (replaces Google Sheets I/O)
├── main.py                   # + `compare` subparser
└── ...

data/
└── compare.db                # SQLite database

config/
├── config.yaml               # + compare section with profiles
└── compare_rules/            # Per-profile rules
    ├── 810_invoice.yaml
    ├── 850_po.yaml
    ├── 856_asn.yaml
    ├── 820_payment.yaml
    ├── csv_generic.yaml
    └── cxml_generic.yaml

reports/
└── compare/                  # CSV exports land here
```

### Module Responsibilities

#### `matcher.py` — File Pairing & Transaction Extraction

Replaces `find_target_file_for_invoice()` and `find_invoice_in_json()` from comparator.py.

**Multi-transaction support:** A single JSON file can contain >=1 ST/SE transactions. The matcher extracts ALL match key values from each file, producing one MatchPair per transaction — not per file. Two files might pair on 3 different transactions if they each contain 3 invoices.

```python
def extract_match_values(json_data: dict, match_key: MatchKeyConfig) -> list[MatchEntry]:
    """Extract ALL matching values from a JSON file.

    For X12: walks every ST/SE transaction, finds segment, extracts field.
      - A file with 5 ST/SE loops yields up to 5 MatchEntry objects.
    For flat JSON (CSV/cXML): resolves dot-notation json_path.
      - Typically yields 1 MatchEntry (single transaction per output).
    Returns list of MatchEntry(match_value, transaction_index, transaction_data).
    """

def build_match_index(directory: str, match_key: MatchKeyConfig) -> dict[str, list[MatchEntry]]:
    """Scan all JSON files in a directory, return {match_value: [MatchEntry, ...]}.

    This is the lookup table — given a match value, find which file(s) and
    which transaction(s) within those files contain it.
    """

def pair_transactions(
    source_dir: str,
    target_dir: str,
    match_key: MatchKeyConfig
) -> list[MatchPair]:
    """Pair source and target transactions by match key value.

    1. Build match index for source_dir
    2. Build match index for target_dir
    3. For each match_value in source index:
       - If found in target index: create MatchPair(source, target, match_value)
       - If not found: create MatchPair(source, None, match_value) — UNMATCHED
    4. For each match_value in target index not in source: UNMATCHED (target orphan)

    Returns list of MatchPair. One pair per transaction, not per file.
    """
```

**Key changes from json810Compare:**
- No Google Sheet as intermediary — files paired directly by scanning directories
- Multi-transaction aware — extracts every ST/SE loop, not just the first match
- Format-agnostic — X12 uses segment/field, CSV/cXML uses json_path

#### `engine.py` — Comparison Logic

Ports `compare_transactions()`, `match_segments_by_qualifier()`, and field comparison from comparator.py.

```python
def compare_pair(pair: MatchPair, rules: CompareRules, qualifiers: dict[str, str]) -> CompareResult:
    """Compare a matched source/target pair.

    1. Load both JSON files
    2. Extract transactions containing the match key value
    3. Match segments by qualifier
    4. Compare fields using rules (severity, ignore_case, numeric, conditional)
    5. Return CompareResult with all diffs
    """
```

#### `store.py` — SQLite Storage

Replaces all Google Sheets read/write operations.

```sql
-- compare_runs: one row per invocation of `pyedi compare`
CREATE TABLE compare_runs (
    id          INTEGER PRIMARY KEY,
    profile     TEXT NOT NULL,        -- e.g. "810_invoice", "850_purchase_order"
    started_at  TEXT NOT NULL,        -- ISO timestamp
    finished_at TEXT,
    source_dir  TEXT NOT NULL,
    target_dir  TEXT NOT NULL,
    match_key   TEXT NOT NULL,        -- e.g. "BIG:BIG02" or "json_path:header.invoice_number"
    total_pairs INTEGER DEFAULT 0,
    matched     INTEGER DEFAULT 0,
    mismatched  INTEGER DEFAULT 0,
    unmatched   INTEGER DEFAULT 0
);

-- compare_pairs: one row per TRANSACTION pair (not per file)
-- A file with 5 ST/SE transactions produces up to 5 rows here
CREATE TABLE compare_pairs (
    id                  INTEGER PRIMARY KEY,
    run_id              INTEGER NOT NULL REFERENCES compare_runs(id),
    source_file         TEXT NOT NULL,
    source_tx_index     INTEGER NOT NULL DEFAULT 0,  -- ST/SE loop index within file
    target_file         TEXT,                         -- NULL if no match found
    target_tx_index     INTEGER DEFAULT 0,
    match_value         TEXT NOT NULL,                -- e.g. "9031841147"
    status              TEXT NOT NULL,                -- MATCH | MISMATCH | UNMATCHED
    diff_count          INTEGER DEFAULT 0
);

-- compare_diffs: one row per field-level difference
CREATE TABLE compare_diffs (
    id              INTEGER PRIMARY KEY,
    pair_id         INTEGER NOT NULL REFERENCES compare_pairs(id),
    segment         TEXT NOT NULL,    -- e.g. "N1*ST" or json_path "header.vendor_name"
    field           TEXT NOT NULL,    -- e.g. "N102" or leaf key
    severity        TEXT NOT NULL,    -- hard | soft | ignore
    source_value    TEXT,
    target_value    TEXT,
    description     TEXT NOT NULL
);

-- Indexes for portal queries
CREATE INDEX idx_runs_profile ON compare_runs(profile);
CREATE INDEX idx_pairs_run_id ON compare_pairs(run_id);
CREATE INDEX idx_pairs_status ON compare_pairs(status);
CREATE INDEX idx_diffs_pair_id ON compare_diffs(pair_id);
CREATE INDEX idx_diffs_severity ON compare_diffs(severity);
```

**Why SQLite over flat files:**
- Queryable: the portal can filter/sort/aggregate without loading everything into memory
- Atomic writes: concurrent CLI + portal access won't corrupt data
- History: multiple runs stored, diffable over time
- Lightweight: zero-config, single file, ships with Python

#### `rules.py` — Rule Loading

```python
def load_rules(rules_path: str) -> CompareRules:
    """Load compare_rules.yaml, return CompareRules with classification + ignore lists."""

def get_field_rule(rules: CompareRules, segment: str, field: str) -> FieldRule:
    """Resolve rule for (segment, field) with wildcard fallback.

    Priority: exact match > (segment, *) > (*, field) > (*, *)
    """
```

#### `models.py` — Data Structures

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
    segment_qualifiers: dict[str, str | None]  # e.g. {"N1": "N101", "N3": None}
    rules_file: str                     # Path to per-profile rules YAML

@dataclass
class MatchEntry:
    file_path: str
    match_value: str
    transaction_index: int    # Which ST/SE loop (0-based) within the file
    transaction_data: dict    # The extracted transaction segments

@dataclass
class MatchPair:
    source: MatchEntry
    target: MatchEntry | None  # None = unmatched
    match_value: str

@dataclass
class FieldDiff:
    segment: str              # e.g. "N1*ST" or json_path "header.vendor_name"
    field: str                # e.g. "N102" or leaf key
    severity: str             # hard | soft | ignore
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
    profile: str              # Which profile was used
    total_pairs: int
    matched: int
    mismatched: int
    unmatched: int
    started_at: str
    finished_at: str
```

---

## CLI: `pyedi compare`

```
pyedi compare --profile PROFILE [OPTIONS]

Required:
  --profile TEXT          Profile name from config.yaml (e.g., "810_invoice", "850_purchase_order")

Options:
  --source-dir PATH       Source JSON directory (overrides profile default)
  --target-dir PATH       Target JSON directory (overrides profile default)
  --match-json-path TEXT  Override match key for flat JSON (e.g., "header.po_number")
  --rules PATH            Override rules YAML (overrides profile default)
  --export-csv            Write CSV report to reports/compare/
  --verbose / -v          Show per-field diffs in terminal output
  --config / -c PATH      Config file (default: ./config/config.yaml)
  --list-profiles         List available profiles and exit
```

**Examples:**

```bash
# List all configured profiles
pyedi compare --list-profiles

# 810 invoices — uses BIG02 match key, 810 qualifiers, 810 rules
pyedi compare --profile 810_invoice \
              --source-dir outbound/na --target-dir outbound/ca

# 850 purchase orders — uses BEG03 match key, 850 qualifiers, 850 rules
pyedi compare --profile 850_purchase_order \
              --source-dir outbound/na --target-dir outbound/ca

# 856 ASN — uses BSN02 match key, HL-aware qualifiers
pyedi compare --profile 856_asn \
              --source-dir outbound/na --target-dir outbound/ca

# CSV outputs — uses json_path from profile, override if needed
pyedi compare --profile csv_generic \
              --source-dir outbound/system_a --target-dir outbound/system_b \
              --match-json-path "header.po_number"

# Export CSV report
pyedi compare --profile 810_invoice --export-csv

# Verbose: show every field diff in terminal
pyedi compare --profile 810_invoice -v
```

**Profile is required** — this forces the user to be explicit about which transaction type they're comparing. No ambiguity, no silent misconfiguration.

---

## Portal Integration: `/compare` Page

Adds a fifth page to the existing portal plan (alongside Validate, Pipeline, Test Harness, Manifest).

### API Endpoints (added to `portal/api/routes/compare.py`)

| Method | Path | Request | Response | Wraps |
|---|---|---|---|---|
| `GET` | `/api/compare/profiles` | — | `List[CompareProfile]` | List available profiles from config |
| `POST` | `/api/compare/run` | `{profile, source_dir, target_dir}` | `RunSummary` | `comparator.compare()` |
| `GET` | `/api/compare/runs` | `?profile=810_invoice&limit=20` | `List[RunSummary]` | `store.get_runs()` |
| `GET` | `/api/compare/runs/{id}` | — | `RunDetail` (pairs + stats) | `store.get_run()` |
| `GET` | `/api/compare/runs/{id}/pairs` | `?status=MISMATCH&limit=50` | `List[PairDetail]` | `store.get_pairs()` |
| `GET` | `/api/compare/runs/{id}/pairs/{pair_id}/diffs` | — | `List[FieldDiff]` | `store.get_diffs()` |
| `GET` | `/api/compare/runs/{id}/export` | — | CSV file download | `comparator.export_csv()` |
| `GET` | `/api/compare/profiles/{name}/rules` | — | Profile rules YAML as JSON | `rules.load_rules()` |
| `PUT` | `/api/compare/profiles/{name}/rules` | Updated rules body | Updated rules | Writes to profile rules YAML |

### Page Layout

```
/compare
┌─────────────────────────────────────────────────────────────────┐
│  === New Comparison ===                                          │
│  Profile:    [ 810_invoice          ▼ ]                         │
│              "EDI 810 Invoice comparison"                        │
│              Match Key: BIG:BIG02 | Qualifiers: N1,REF,DTM,PER │
│  Source Dir: [________]  Target Dir: [________]                  │
│  [ Run Comparison ]  [ Export CSV ]                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  === Run History ===                                             │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Run  │ Date       │ Key    │ Pairs │ Match │ Diff │ UM │     │
│  │ #12  │ 2026-03-24 │ BIG02  │ 847   │ 812   │ 31   │ 4  │     │
│  │ #11  │ 2026-03-23 │ BIG02  │ 841   │ 808   │ 29   │ 4  │     │
│  │ #10  │ 2026-03-22 │ BEG03  │ 125   │ 125   │ 0    │ 0  │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  === Run #12 Detail ===  (click to expand)                      │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Source File          │ Target File          │ Status   │     │
│  │ NA_810_001.json      │ CA_810_001.json      │ MATCH    │     │
│  │ NA_810_002.json      │ CA_810_002.json      │ MISMATCH │     │
│  │ NA_810_003.json      │ —                    │ UNMATCHED│     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  === Pair Detail ===  (click MISMATCH row)                      │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Segment │ Field │ Severity │ Source      │ Target     │     │
│  │ N1*ST   │ N102  │ Hard     │ GFS Canada  │ GFS CANADA │     │
│  │ IT1*1   │ IT104 │ Hard     │ 70.00       │ 70.0300    │     │
│  │ REF*ZZ  │ REF02 │ Soft     │ ABC-123     │ (missing)  │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  === Rules Editor ===  (collapsible)                            │
│  Load and edit compare_rules.yaml inline                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## CSV Export Format

```csv
run_id,timestamp,source_file,target_file,match_value,status,segment,field,severity,source_value,target_value,description
12,2026-03-24T10:30:00,NA_810_001.json,CA_810_001.json,9031841147,MATCH,,,,,,
12,2026-03-24T10:30:00,NA_810_002.json,CA_810_002.json,9031841148,MISMATCH,N1*ST,N102,hard,GFS Canada,GFS CANADA,"Content mismatch: case difference"
12,2026-03-24T10:30:00,NA_810_002.json,CA_810_002.json,9031841148,MISMATCH,IT1*1,IT104,hard,70.00,70.0300,"Numeric mismatch within tolerance"
12,2026-03-24T10:30:00,NA_810_003.json,,9031841149,UNMATCHED,,,,,,No target file found
```

---

## What Gets Ported vs. Rewritten vs. Dropped

| json810Compare Module | Action | Notes |
|---|---|---|
| `comparator.py` — `compare_transactions()` | **Port** to `engine.py` | Remove Sheets refs, parameterize match key |
| `comparator.py` — `match_segments_by_qualifier()` | **Port** to `matcher.py` | Make qualifier dict configurable |
| `comparator.py` — `find_invoice_in_json()` | **Port** to `matcher.py` | Generalize from BIG02 to any segment/field |
| `comparator.py` — `find_target_file_for_invoice()` | **Rewrite** in `matcher.py` | Direct dir scan instead of Sheet lookup |
| `comparator.py` — Google Sheets I/O | **Replace** with `store.py` (SQLite) | All reads/writes become SQL |
| `comparator.py` — error classification loading | **Replace** with `rules.py` (YAML) | Same logic, YAML source instead of Sheet |
| `main.py` — invoice extraction to Sheet | **Drop** | pycoreEdi pipeline already produces JSON |
| `sheets_service.py` | **Drop** | No Google Sheets dependency |
| `drive_service.py` | **Drop** | No Google Drive dependency |
| `errorConfig.py` — error discovery | **Port** to `rules.py` | Auto-suggest rules for new error types seen |
| `setup_config.py` | **Drop** | Config is YAML, not a Sheet |
| `config.json` | **Merge** into `config.yaml` compare section | Directory paths move to config.yaml |

---

## Execution Order

### Phase 1: Core Engine (no UI, no API)
1. Create `pyedi_core/comparator/models.py` — dataclasses
2. Create `pyedi_core/comparator/rules.py` — YAML rule loading
3. Create `pyedi_core/comparator/matcher.py` — file pairing + match key extraction
4. Create `pyedi_core/comparator/engine.py` — port comparison logic
5. Create `pyedi_core/comparator/store.py` — SQLite CRUD
6. Create `pyedi_core/comparator/__init__.py` — public API: `compare()`, `export_csv()`
7. Add `compare` subparser to `pyedi_core/main.py`
8. Create `config/compare_rules.yaml` — default rules
9. Add `compare` section to `config/config.yaml`
10. Tests: `tests/test_comparator.py`

### Phase 2: Portal (after existing portal Phases A-C)
11. Add `portal/api/routes/compare.py` — API endpoints
12. Add `portal/frontend/src/pages/Compare.tsx` — UI page
13. Add route + nav link to existing portal shell

### Phase 3: Polish
14. Error discovery: auto-suggest rules for unclassified segment/field combos
15. Run-over-run diffing: compare Run #12 vs Run #11 to see what changed
16. Batch scheduling: `pyedi compare --watch` for continuous monitoring

---

## Resolved Design Decisions

| Question | Decision | Impact |
|---|---|---|
| Segment qualifiers per transaction type | **Each profile defines its own qualifier map** | No shared defaults — profiles are fully self-contained |
| Multi-transaction files | **Supported: >=1 ST/SE per file** | Matcher extracts all transactions, pairs at transaction level not file level |
| Numeric tolerance | **Exact float comparison, no epsilon** | `numeric: true` converts to float for format normalization (70.00 == 70.0300) but no tolerance band |
| Storage | **SQLite** (replaces Google Sheets) | Single file `data/compare.db`, queryable from CLI + portal |
| Output | **React portal page + CSV export** | Portal reads SQLite via API; CSV generated on demand |
| CLI integration | **`pyedi compare --profile <name>`** subcommand | Profile is required — explicit transaction type selection |

---

*This document lives at `instructions/compare_integration_plan.md`. It is an instruction artifact, not a runnable file.*
