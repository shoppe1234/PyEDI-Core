# Regional Health 810 — Orchestration Prompt: Staging, Config, Generalization, and Compare Run

> **Scope:** Stage X12 810 test data, generalize the `_global_810` rules tier, add a `match_key_normalize` feature to the matcher, create the Regional Health partner profile, and run the comparison.
> **Execute tasks sequentially. Read every target file before editing. Run tests after code changes.**

---

## Context

Two X12 810 datasets from Bluewater Health (GFS → WINMET):
- **Control (ca-target):** `C:\Users\SeanHoppe\Downloads\regionalHealth\ca-target\` — 3 files
- **Sample (na-target):** `C:\Users\SeanHoppe\Downloads\regionalHealth\na-target\` — 5 files (3 matched, 2 unmatched)

Both use `~` element separator, `|` segment terminator, X12 v00401.

### Resolved Decisions
| ID | Decision |
|----|----------|
| D1 | Pair on BIG02. na prepends `903` — strip via regex normalization. |
| D2 | N3 ship-to address: **soft diff** (ca omits, na populates). |
| D3 | BIG04 PO format (`bwd` vs `-BWD`): **hard diff**. |
| D4 | 2 unmatched na invoices: **expected**, ignore. |
| D5 | Price/amount tolerance: **exact match**, zero variance. |

### Task list reference
`C:\Users\SeanHoppe\Downloads\regionalHealth\regional_health_compare_tasks.md`

---

## Pre-Flight

```bash
cd C:/Users/SeanHoppe/VS/pycoreEdi
python -m pytest tests/ -x -q 2>&1 | tail -5
```
Note baseline test count. All tasks must leave it passing or better.

---

## TASK-1 — Stage test data

Copy the X12 files into the project artifacts directory.

```bash
mkdir -p artifacts/regionalHealth/ca-target artifacts/regionalHealth/na-target
cp "C:/Users/SeanHoppe/Downloads/regionalHealth/ca-target/"*.810 artifacts/regionalHealth/ca-target/
cp "C:/Users/SeanHoppe/Downloads/regionalHealth/na-target/"*.810 artifacts/regionalHealth/na-target/
```

**Verify:** `ls artifacts/regionalHealth/ca-target/` shows 3 files, `ls artifacts/regionalHealth/na-target/` shows 5 files.

---

## TASK-2 — Generalize `_global_810.yaml` (transaction-type tier)

**File:** `config/compare_rules/_global_810.yaml`

This file is currently empty. Populate it with generic 810 rules that ALL 810 trading partners inherit. These rules should NOT contain partner-specific logic (no N3 soft override, no BIG02 normalization references).

**Replace the entire file contents with:**

```yaml
# Transaction-type rules for EDI 810 (Invoice).
# Apply to all 810 profiles. Partner rules override these.

classification:
  # Line item — unit price (numeric)
  - segment: IT1
    field: IT104
    severity: hard
    ignore_case: false
    numeric: true
    conditional_qualifier: null
    amount_variance: null

  # Line item — quantity (numeric)
  - segment: IT1
    field: IT102
    severity: hard
    ignore_case: false
    numeric: true
    conditional_qualifier: null
    amount_variance: null

  # Line item — vendor number (conditional on qualifier)
  - segment: IT1
    field: IT107
    severity: hard
    ignore_case: false
    numeric: false
    conditional_qualifier: IT106
    amount_variance: null

  # Party name — case insensitive
  - segment: N1
    field: N102
    severity: hard
    ignore_case: true
    numeric: false
    conditional_qualifier: null
    amount_variance: null

  # Product description — soft (truncation/rewording possible)
  - segment: PID
    field: PID05
    severity: soft
    ignore_case: true
    numeric: false
    conditional_qualifier: null
    amount_variance: null

  # Tax amount — numeric
  - segment: TXI
    field: TXI02
    severity: hard
    ignore_case: false
    numeric: true
    conditional_qualifier: null
    amount_variance: null

  # Total monetary summary — numeric
  - segment: TDS
    field: TDS01
    severity: hard
    ignore_case: false
    numeric: true
    conditional_qualifier: null
    amount_variance: null

  # Wildcard fallback — everything else is hard match
  - segment: '*'
    field: '*'
    severity: hard
    ignore_case: false
    numeric: false
    conditional_qualifier: null
    amount_variance: null

ignore:
  # ST control number — varies by batch
  - segment: ST
    field: ST02
    reason: "Transaction set control number — batch-dependent"
```

**Why this matters for reuse:** Any future 810 trading partner (not just Regional Health) automatically inherits these rules. They only need a thin partner-specific overlay for their unique differences.

---

## TASK-3 — Add `match_key_normalize` to the compare engine

The matcher (`pyedi_core/comparator/matcher.py`) pairs transactions by exact `match_value` string equality. Regional Health's BIG02 values differ by a `903` prefix between ca and na. We need a configurable regex normalization on the match key.

### TASK-3A — Update `MatchKeyConfig` model

**File:** `pyedi_core/comparator/models.py`

Add an optional `normalize` field to the `MatchKeyConfig` dataclass:

```python
@dataclass
class MatchKeyConfig:
    """Defines how to extract the pairing key from a document."""

    segment: str | None = None       # X12 segment ID (e.g., "BIG")
    field: str | None = None         # X12 field (e.g., "BIG02")
    json_path: str | None = None     # Dot-notation for flat JSON (e.g., "header.invoice_number")
    normalize: str | None = None     # Optional regex substitution: "pattern|replacement"
```

### TASK-3B — Apply normalization in matcher

**File:** `pyedi_core/comparator/matcher.py`

Add a helper function and apply it in `extract_match_values()`:

```python
import re

def _normalize_value(value: str, normalize: str | None) -> str:
    """Apply optional regex normalization to a match value.
    
    Format: "pattern|replacement" — applies re.sub(pattern, replacement, value).
    """
    if not normalize:
        return value
    parts = normalize.split("|", 1)
    if len(parts) != 2:
        logger.warning("Invalid normalize format (expected 'pattern|replacement'): %s", normalize)
        return value
    pattern, replacement = parts
    try:
        return re.sub(pattern, replacement, value)
    except re.error as exc:
        logger.warning("Normalize regex error: %s", exc)
        return value
```

Then in `extract_match_values()`, apply normalization to the `value` before appending. Two locations:

1. **Flat JSON path mode** (around line 76–83): After `value = _resolve_json_path(...)`, add:
   ```python
   value = _normalize_value(value, match_key.normalize)
   ```

2. **X12 segment/field mode** (around line 96–104): After `value = _get_field_content(seg, match_key.field)`, add:
   ```python
   value = _normalize_value(value, match_key.normalize)
   ```

### TASK-3C — Wire normalization through profile parsing

**File:** `pyedi_core/comparator/__init__.py`

In `_parse_profile()`, add `normalize` to the `MatchKeyConfig` constructor:

Find:
```python
match_key=MatchKeyConfig(
    segment=mk.get("segment"),
    field=mk.get("field"),
    json_path=mk.get("json_path"),
),
```

Replace with:
```python
match_key=MatchKeyConfig(
    segment=mk.get("segment"),
    field=mk.get("field"),
    json_path=mk.get("json_path"),
    normalize=mk.get("normalize"),
),
```

### TASK-3D — Verify

```bash
python -m pytest tests/ -x -q 2>&1 | tail -5
```

All existing tests must still pass. The `normalize` field is optional (`None` by default), so existing profiles are unaffected.

---

## TASK-4 — Create Regional Health partner compare rules

**File:** `config/compare_rules/regional_health_810.yaml` (NEW)

This is the thin partner-specific overlay. It only contains rules that **override** or **add to** the `_global_810.yaml` tier. Thanks to tiered rule resolution (universal → transaction → partner), everything in `_global_810.yaml` is inherited automatically.

```yaml
# Partner-specific rules: Regional Health (Bluewater) 810 Invoice
# Inherits from: _universal.yaml → _global_810.yaml
# Only overrides/additions below.

classification:
  # Ship-to address — soft diff (D2: ca-target omits, na-target populates)
  - segment: N3
    field: N301
    severity: soft
    ignore_case: true
    numeric: false
    conditional_qualifier: null
    amount_variance: null

  # PO number format — hard diff (D3: bwd vs -BWD is a real difference)
  - segment: BIG
    field: BIG04
    severity: hard
    ignore_case: false
    numeric: false
    conditional_qualifier: null
    amount_variance: null

ignore: []
```

---

## TASK-5 — Register compare profile in `config/config.yaml`

**File:** `config/config.yaml`

Add the `regional_health_810` profile under `compare.profiles`. Place it after the `retalix_p_i_invo` entry.

```yaml
    regional_health_810:
      description: Regional Health (Bluewater) 810 Invoice X12 comparison
      trading_partner: RegionalHealth
      transaction_type: '810'
      match_key:
        segment: BIG
        field: BIG02
        normalize: "^903|"
      segment_qualifiers:
        N1: N101
        REF: REF01
        DTM: DTM01
        PER: PER01
        IT1: IT101
        QTY: null
        TXI: null
        PID: null
        PKG: null
        N3: null
        N4: null
      rules_file: config/compare_rules/regional_health_810.yaml
```

**Key detail:** `normalize: "^903|"` means `re.sub("^903", "", value)` — strips the leading `903` prefix from BIG02 before pairing. The `|` separates pattern from replacement (empty string).

**Verify:** Read back the file and confirm YAML indentation is correct (profile is nested under `compare.profiles`).

---

## TASK-6 — Process X12 files through the pipeline

The compare engine reads **JSON** files (the output of the X12 handler), not raw `.810` files. We need to run the pipeline first to produce JSON in outbound directories.

```bash
# Process ca-target (control)
python -m pyedi_core run \
  --inbound artifacts/regionalHealth/ca-target \
  --outbound outbound/regionalHealth-ca \
  --transaction-type 810

# Process na-target (sample)
python -m pyedi_core run \
  --inbound artifacts/regionalHealth/na-target \
  --outbound outbound/regionalHealth-na \
  --transaction-type 810
```

**Verify:** `ls outbound/regionalHealth-ca/` shows 3 JSON files, `ls outbound/regionalHealth-na/` shows 5 JSON files.

**If the CLI flags differ from the above:** Read `pyedi_core/main.py` to find the correct subcommand and argument names. The key requirement is: raw X12 → JSON in two separate outbound directories.

**IMPORTANT:** If the pipeline uses `config.yaml` `directories.inbound` and `directories.outbound` rather than CLI flags, temporarily update those values or use whatever mechanism the CLI provides. Read `pyedi_core/main.py` and `pyedi_core/pipeline.py` before running.

---

## TASK-7 — Run the comparison

```bash
python -m pyedi_core compare \
  --profile regional_health_810 \
  --source outbound/regionalHealth-ca \
  --target outbound/regionalHealth-na
```

**If the CLI flags differ:** Read `pyedi_core/main.py` to find the correct compare subcommand syntax.

**Expected results:**
- 3 matched pairs (BIG02 values: 2908167, 3934987, 3685808 after normalization)
- 2 unmatched (na-only: 9033175055 → normalized 3175055, 9033430670 → normalized 3430670)
- Hard diffs expected: BIG02 raw values (pre-normalization values are compared in engine), BIG04 format on some pairs
- Soft diffs expected: N3 address, PID05 descriptions (if any truncation)

**Verify:** Check the CSV output:
```bash
ls reports/compare/compare_run_*.csv | tail -1
```
Read the latest CSV and confirm pair counts and diff severities.

---

## TASK-8 — Export and verify portal visibility

The compare results are now in `data/compare.db`. The portal's Compare page reads from this database.

```bash
# If portal is running, verify the API returns the new run:
curl -s http://localhost:8000/compare/runs | python -m json.tool | tail -20
```

If the portal is not running, skip this step and note it. The data is in SQLite and will be visible next time the portal starts.

**What the portal displays for X12 diffs:**
- Segment column: `IT1`, `N1*ST`, `BIG`, `N3`, etc.
- Field column: `IT104`, `N102`, `BIG02`, `N301`, etc.
- Severity: `hard` / `soft`
- Source and target values side by side

---

## TASK-9 — Verify generalization

Confirm that the existing `810_invoice` profile (the generic one) still works and now inherits the populated `_global_810.yaml` rules.

```bash
# If test data exists for the generic 810 profile, run it:
python -m pyedi_core compare --profile 810_invoice --source <existing_810_source> --target <existing_810_target>
```

If no existing 810 test data is available, verify by reading the tiered rule resolution:

1. Read `config/compare_rules/_universal.yaml` — confirms ISA/GS/SE/GE/IEA are ignored
2. Read `config/compare_rules/_global_810.yaml` — confirms generic 810 classification rules exist
3. Read `config/compare_rules/810_invoice.yaml` — confirms partner-level rules remain unchanged

The tiered system resolves: universal → `_global_810` → `810_invoice`. Any 810 profile now inherits the generic numeric/case/soft rules without duplicating them.

---

## Summary of Generalization Architecture

```
Tier 1: _universal.yaml
  └─ Ignores: ISA/*, GS/*, SE/SE01, GE/*, IEA/*
  └─ Applies to: ALL profiles (810, 850, 856, flat, XML, etc.)

Tier 2: _global_810.yaml          ← POPULATED BY THIS PROMPT
  └─ Classification: IT104 numeric, IT102 numeric, IT107 conditional,
  │   N102 ignore_case, PID05 soft, TXI02 numeric, TDS01 numeric, * wildcard
  └─ Ignores: ST/ST02
  └─ Applies to: ALL 810 profiles

Tier 3: regional_health_810.yaml  ← NEW PARTNER OVERLAY
  └─ Overrides: N3/N301 soft, BIG/BIG04 hard (case-sensitive)
  └─ Applies to: Regional Health only

Future 810 partners only need a Tier 3 file for their unique differences.
```

---

## Files Created / Modified

| File | Action | Task |
|------|--------|------|
| `artifacts/regionalHealth/ca-target/*.810` | Created (copy) | 1 |
| `artifacts/regionalHealth/na-target/*.810` | Created (copy) | 1 |
| `config/compare_rules/_global_810.yaml` | Modified (populated) | 2 |
| `pyedi_core/comparator/models.py` | Modified (normalize field) | 3A |
| `pyedi_core/comparator/matcher.py` | Modified (normalization) | 3B |
| `pyedi_core/comparator/__init__.py` | Modified (parse normalize) | 3C |
| `config/compare_rules/regional_health_810.yaml` | Created | 4 |
| `config/config.yaml` | Modified (new profile) | 5 |

---

## Rollback

If anything breaks:
```bash
git checkout -- config/compare_rules/_global_810.yaml
git checkout -- pyedi_core/comparator/models.py
git checkout -- pyedi_core/comparator/matcher.py
git checkout -- pyedi_core/comparator/__init__.py
git checkout -- config/config.yaml
rm -rf artifacts/regionalHealth/ outbound/regionalHealth-ca/ outbound/regionalHealth-na/
rm config/compare_rules/regional_health_810.yaml
```
