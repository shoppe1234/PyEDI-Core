# Compare Run #89 — Root Cause & Proposed Fix

## Symptom

Comparison run #89 (`sean850` profile, `3brewers.txt` vs `3brewersnaFORMAT.txt`) completed in ~3ms with `total_pairs: 0`. No transactions matched, no diffs recorded.

---

## Root Cause (3 compounding issues)

### 1. `build_match_index` skips non-JSON files

**File:** `pyedi_core/comparator/matcher.py:139`

```python
if not filename.lower().endswith(".json"):
    continue   # ← raw X12 .txt files are silently skipped
```

The compare engine only scans `.json` files. The source/target directories (`ca/`, `na/`) contain raw X12 `.txt` files. They are never read, so `pair_transactions()` returns an empty list → `total_pairs: 0`.

---

### 2. `sean850` profile has empty `segment_qualifiers`

**File:** `config/config.yaml` (sean850 profile)

```yaml
sean850:
  segment_qualifiers: {}    # ← empty dict
```

In `pyedi_core/comparator/__init__.py:91`:

```python
is_flat = not profile.segment_qualifiers   # True when {}
```

An empty `segment_qualifiers` forces `compare_flat_pair()` (expects DSL-mapped flat JSON with `header`/`lines`/`summary` keys). Raw X12 parsed output uses `document.segments` format, which requires `compare_pair()`. Wrong compare function would be called even if files were found.

---

### 3. `sean850.yaml` rules use DSL field names, not raw X12 names

**File:** `config/compare_rules/sean850.yaml`

```yaml
- segment: BEG
  field: po_number     # ← DSL name; raw X12 field is BEG03
- segment: BEG
  field: po_date       # ← DSL name; raw X12 field is BEG05
- segment: TDS
  field: total_amount  # ← TDS does not exist in X12 850 (it's an 810 segment)
```

The 810 compare (e.g. `regional_health_810`) stores pipeline output as raw segment JSON: fields are named `BIG01`, `BIG02`, etc. The 850 compare rules must use the same convention (`BEG03`, `BEG05`, `PO101`, etc.).

---

## How the 810 Workflow Actually Works

```
raw X12 .txt  →  pipeline (x12_handler.read())  →  outbound/*.json  →  compare
```

The pipeline's `read()` stage produces:

```json
{
  "document": { "segments": [{ "segment": "BIG", "fields": [{ "name": "BIG02", "content": "2908167" }] }] },
  "_transaction_type": "810",
  "_is_unmapped": true
}
```

The compare engine reads those outbound JSON files (not the raw source `.txt`). The `sean850` profile was pointed directly at raw `.txt` files — a step the pipeline normally handles.

---

## Proposed Fix

### Fix 1 — Add raw X12 support to `build_match_index`

**File:** `pyedi_core/comparator/matcher.py`

Add `_parse_x12_to_doc(file_path)` that:
- Reads raw X12 text
- Detects delimiters from ISA segment (element separator at char[3], segment terminator at char[105])
- Splits into segments, names fields positionally (`BEG01`, `BEG02`, `BEG03`, ...)
- Returns `{"document": {"segments": [...]}, "_transaction_type": "850", ...}`

Extend `build_match_index` to scan `.txt`, `.edi`, `.x12` files in addition to `.json`, routing them through `_parse_x12_to_doc`.

X12 version is read from `ISA12` and used to locate the matching `.ediSchema` under `./standards/x12/{version}/schemas/Message{type}.ediSchema` for future validation (segment cardinality, element types).

---

### Fix 2 — Add `segment_qualifiers` to `sean850` profile

**File:** `config/config.yaml`

```yaml
sean850:
  segment_qualifiers:
    N1: N101
    REF: REF01
    DTM: DTM01
    PER: PER01
    PO1: null    # positional — line 1 matches line 1
    N3: null
    N4: null
```

This switches `is_flat → False`, routing compare through `compare_pair()` which handles `document.segments` format.

---

### Fix 3 — Fix field names in `sean850.yaml`

**File:** `config/compare_rules/sean850.yaml`

| Current (DSL name) | Correct (raw X12 name) | Segment |
|---|---|---|
| `po_number` | `BEG03` | BEG |
| `po_date` | `BEG05` | BEG |
| `sender_id` | `ISA06` | ISA |
| `receiver_id` | `ISA08` | ISA |
| `line_number` | `PO101` | PO1 |
| `quantity` | `PO102` | PO1 |
| `unit_price` | `PO104` | PO1 |
| `product_id` | `PO107` | PO1 |
| `total_amount` (TDS) | **remove** — TDS is not an X12 850 segment | — |

---

## Expected Result After Fix

- `build_match_index` reads `3brewers.txt` and `3brewersnaFORMAT.txt`
- Both parse BEG03 = `PO-3634-00906` → matched as 1 pair
- `compare_pair()` runs segment-by-segment comparison
- Diff detected: N1 segment — `3BREWERS-CENTROPOLIS` (source) vs `3BREWERS` (target)
- Run summary: `total_pairs: 1`, `mismatched: 1`

---

## Scope

All X12 transaction types (810, 850, 855, 856, etc.) can use this same raw-file path once Fix 1 is in place. No pipeline pre-processing step required when pointing compare directly at raw X12 directories.
