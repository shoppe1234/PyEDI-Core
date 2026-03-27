# Fixed-Width Multi-Record Pipeline — Post-Implementation Review

## Date: 2026-03-27
## Executed by: Claude Code + Sean Hoppe

---

## Summary

First end-to-end run of Retalix PI Invoice fixed-width files through pycoreEdi revealed 5 issues. All 5 have been resolved. The critical fix — transaction-level decomposition of batch files — enables invoice-by-invoice comparison across control and test data sets.

**Data set:** Silverbirch Hotels — 3 batch files (ca-silver control, na-silver test), 6 invoices total
**DSL schema:** `RetalixPIInvoiceFileSchemaSacFF.ffSchema` — 39 record types, 134 fields
**Key field:** `TPM_HDR.invoiceNumber` (String, width 10)

---

## Issue 1: Multi-Record Split-Key Produced Orphaned Records

**Severity:** Critical — blocked transaction-level comparison

**Observed behavior:**
`--split-key invoiceNumber` on batch files produced:
- 12 invoice JSONs with only 1 line each (OIN_HDR1 or TPM_HDR records)
- Duplicate groups: `invoiceNumber_2102602` (7-char from OIN_HDR1) AND `invoiceNumber_9032102602` (10-char from TPM_HDR)
- 1 `unknown.json` (263 KB) containing ALL detail, address, and trailer records
- `unknown.json` had a JSON encoding error

**Root cause:**
Two problems compounded:

1. **Schema compiler ignored DSL hierarchy.** The DSL file defines `recordSequence` blocks (lines 1474-1520) with `groupOnRecord = true` declaring which records belong to the same invoice transaction. The compiler's `parse_dsl_file()` only extracted `def record` blocks, completely skipping `def recordSequence`. The compiled YAML had no grouping metadata.

2. **Reader flattened all records.** `_read_fixed_width()` in `csv_handler.py` parsed every line independently into a flat `lines` array. Without knowing that OIN_DTL1 records belong to the preceding TPM_HDR, `write_split()` could only group records that already had `invoiceNumber` in their own fields.

**Solution — 3 changes:**

1. **`_parse_record_sequences()` in `schema_compiler.py`** — New function that parses `def recordSequence` blocks from DSL text, extracts `groupOnRecord`/`groupType` metadata, member records, nested group references, and resolves DSL class names to actual record IDs (e.g., `TpmHdr` → `TPM_HDR`). Identifies the boundary record (`TPM_HDR`) and its key field (`invoiceNumber`) by inspecting which member record contains an invoice-identifying field.

2. **`record_groups` in compiled YAML** — `_compile_to_yaml()` now calls `_parse_record_sequences()` and emits a `record_groups` section with: `group_on_record`, `boundary_record`, `key_field`, `member_records` (flattened across nested groups), and `nested_groups`.

3. **`_group_by_transaction()` in `csv_handler.py`** — After `_read_fixed_width()` builds the flat `lines` list, this new method reads `record_groups` from the schema, finds the group with `group_on_record: true`, and propagates the boundary record's key field value to ALL subsequent lines until the next boundary record. This means every line in a transaction gets the same `invoiceNumber`, so `write_split()` groups them correctly.

**Backward compatibility:** If `record_groups` is absent (CSV schemas, Bevager, etc.), grouping is skipped entirely.

**Verification:**
- `--split-key invoiceNumber` produces 6 invoice JSONs + 1 small `unknown.json` (3 file-level records)
- Each invoice JSON has 29-32 record types (TPM_HDR + OIN_HDR1-5 + OIN_DTL1-11 + OIN_TTL1 + address + tax records)
- Compare Run #81: 6 invoice pairs, 4 matched, 2 mismatched, 0 unmatched (unknown excluded)
- All 192 existing tests pass

---

## Issue 2: JSON Double-Colon Encoding

**Severity:** Medium — corrupted JSON output

**Observed behavior:**
`unknown.json` (from Issue 1) contained malformed JSON:
```json
"quantityDifference": : "0002"
```

**Root cause:**
The bug was a side effect of Issue 1. When all 2000+ records from multiple invoices were crammed into a single `unknown.json` (263 KB), field alignment errors accumulated because different record types have different field sets. With records properly grouped by transaction (Issue 1 fix), each JSON file contains correctly aligned records and no double-colon appears.

**Solution:** Fixed by Issue 1's grouping fix. No separate code change needed.

**Verification:**
- All 13 JSON files (6 control + 6 test + 1 unknown each) pass `json.load()` validation
- `grep '": :' outbound/silver/` returns zero matches

---

## Issue 3: Windows Unicode Crash in Validate Report

**Severity:** Low — cosmetic, only affects `--verbose` output on Windows

**Observed behavior:**
```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2205' in position 69
```

**Root cause:**
`_print_validate_report()` in `main.py:464` used `∅` (empty set, U+2205) as a marker for unmapped fields and `—` (em dash, U+2014) for missing values. Windows Python defaults to cp1252 encoding for console output, which doesn't support these characters.

**Solution:** Replaced Unicode markers with ASCII equivalents:
- `∅` → `-` (unmapped field marker)
- `—` → `N/A` (missing value)

**File changed:** `pyedi_core/main.py:464-465`

**Verification:** `validate --verbose` completes without error on Windows.

---

## Issue 4: Compare Rules All Hard Severity

**Severity:** Low — usability issue, all diffs treated equally

**Observed behavior:**
All 135 scaffolded compare rules defaulted to `severity: hard`. Description fields like `itemDescription`, `billToName`, `remitToCareOf` were treated as critical failures alongside financial fields like `invoiceNumber` and `totalWeight`.

**Root cause:**
`scaffold-rules` generates one entry per schema column and sets all to `hard`. It detects `numeric: true/false` from types but has no logic to distinguish business-critical fields from descriptive text.

**Solution:**
- Reclassified 22 description/name/address fields as `soft` with `ignore_case: true` in YAML rules
- Reclassified `recordID` and `ignore` as `severity: ignore`
- Updated SQLite `field_crosswalk` table to match (crosswalk overrides YAML at runtime)

**Fields reclassified as soft:** itemDescription, billToCareOf, remitToCareOf, shipToName, billToName, remitToName, chainDescription, brand, vendorName, priceBookFamilyDescription, orderGuideCategoryDes, allowChargeDesc, creditCodeDescription, classDescription, pricebookHeadingDescription, termsDescription, extraItemDescription2, extraItemDescription3, remitToAddress, billToAddress1, shiptoAddress1, shiptoAddress2

**Verification:**
- Compare Run #83: 2 mismatched invoice pairs (4 field-level diffs total) now show `[soft]` instead of `[hard]`
- Hard: 110, Soft: 22, Ignore: 2

---

## Issue 5: Whole-File Comparison Workaround

**Severity:** Design — violated transaction-level comparison principle

**Observed behavior:**
With split-key broken (Issue 1), we fell back to whole-file comparison using injected `header.source_file` as the match key.

**Root cause:** Transaction-level comparison requires working split-key.

**Solution:** Once Issue 1 was fixed, this workaround was no longer needed. Proper flow:
1. Process with `--split-key invoiceNumber`
2. Compare with `--profile retalix_p_i_invo` (match_key: `header.invoiceNumber`)
3. No manual header injection needed

---

## Metrics

| Metric | Before Fix | After Fix |
|--------|-----------|-----------|
| Tests passing | 192 | 192 |
| Split-key output | 13 files (12 single-line + unknown.json 263KB) | 7 files (6 full invoices + unknown.json 3 lines) |
| Compare pairs | 3 (whole-file workaround) | 6 (transaction-level, unknown excluded) |
| Compare matched | 1 | 4 |
| Compare mismatched | 2 | 2 |
| Mismatched invoices | 2 | 2 (4 field-level diffs across 2 pairs) |
| Hard diffs | 4 | 0 |
| Soft diffs | 0 | 4 |

---

## Files Changed

| File | Change |
|------|--------|
| `pyedi_core/core/schema_compiler.py` | Added `_parse_record_sequences()`, updated `parse_dsl_file()` (4th return value), `_compile_to_yaml()` (dsl_content param + record_groups emission) |
| `pyedi_core/drivers/csv_handler.py` | Added `_group_by_transaction()`, called from `_read_fixed_width()` |
| `pyedi_core/main.py:464-465` | Replaced Unicode markers with ASCII |
| `pyedi_core/validator.py:131` | Updated `parse_dsl_file()` unpacking (4 values) |
| `tests/test_core.py:630` | Updated `parse_dsl_file()` unpacking |
| `tests/test_validator.py:67` | Updated `parse_dsl_file()` unpacking |
| `config/compare_rules/retalix_p_i_invo.yaml` | 22 fields → soft, 2 fields → ignore |
| `config/config.yaml` | Schema registry entries + compare profile fix (done in prior session) |

---

## Lessons Learned

1. **Transaction-level matching is the design principle.** Batch files must decompose to individual transactions. Whole-file comparison is a workaround, not the design.

2. **DSL hierarchy metadata matters.** The `recordSequence` blocks define real business structure — which records belong to which transaction. The schema compiler must preserve this.

3. **The key field must come from the boundary record.** For Retalix, `TPM_HDR.invoiceNumber` (10-char) is the canonical value. `OIN_HDR1.invoiceNumber` (7-char) is a different representation. Propagating the boundary record's value to all lines ensures consistent grouping.

4. **Crosswalk overrides YAML rules.** When `scaffold-rules` seeds the `field_crosswalk` table, subsequent YAML edits don't take effect until the crosswalk is also updated. Both must stay in sync.

5. **Scaffold rules need manual tuning.** Auto-generated rules can't distinguish financial fields from description text. Human review is required after scaffolding.

6. **Windows console encoding requires ASCII-safe output.** Any character beyond cp1252 (like ∅, —) will crash on Windows. Use ASCII fallbacks.

---

## Issue 6: Split Key Not Registered During Onboarding (Post-Run #83 Fix)

**Severity:** Design — configuration gap caused phantom "unknown" compare pair

**Observed behavior:**
Compare Run #83 showed 7 pairs instead of 6. Pair 405 (`match_value: "unknown"`) paired two `invoiceNumber_unknown.json` files — file-level metadata records (O_TPID, OIN_DSTID, OIN_HDRA) that don't belong to any invoice. Initially fixed with a hardcoded `value != "unknown"` filter in `matcher.py`.

**Root cause:**
The onboard wizard collects `match_key` (for compare pairing) but never collects or infers `split_key` (for splitting batch files into individual transactions). These are two sides of the same coin. The `split_key` was only a transient CLI parameter (`--split-key invoiceNumber`), not persisted in config. The compiled schema already contains `record_groups` metadata with `boundary_record` and `key_field` — but this knowledge wasn't surfaced during onboarding.

**Solution — 6 changes:**

1. **`_is_split_remainder` flag in `csv_handler.py`** — `write_split()` now sets `_is_split_remainder: true` in the header of unknown group files. This makes remainder files self-describing.

2. **Config-aware exclusion in `matcher.py`** — `extract_match_values()` checks `_is_split_remainder` flag instead of hardcoded `"unknown"` string. Data-driven, not magic-string-dependent.

3. **`split_key` in `CsvSchemaEntry` config model** — New optional field so the pipeline can auto-split without CLI arg.

4. **Pipeline fallback chain in `pipeline.py`** — `split_key` resolution: CLI arg → registry `split_key` → None.

5. **`_detect_split_config()` + `GET /api/onboard/split-suggestion`** in `onboard.py` — Reads compiled YAML `record_groups`, extracts `key_field` and `boundary_record`, returns suggestion to wizard UI.

6. **Split key UI in wizard Step 2** — StepRegister now shows auto-detected split key (from `record_groups`) or manual dropdown. Persists `split_config` to both compare profile and `csv_schema_registry`.

**Files changed:**
- `pyedi_core/comparator/matcher.py` — `_is_split_remainder` check replaces hardcoded filter
- `pyedi_core/drivers/csv_handler.py` — `write_split()` flags remainder groups
- `pyedi_core/config/__init__.py` — `CsvSchemaEntry.split_key` field
- `pyedi_core/pipeline.py` — split_key fallback from config
- `portal/api/routes/onboard.py` — `_detect_split_config()`, split-suggestion endpoint, split_config in register
- `portal/ui/src/api.ts` — `onboardSplitSuggestion()`, `split_config` in register payload
- `portal/ui/src/pages/Onboard.tsx` — Split key section in StepRegister
- `tests/test_comparator.py` — 2 new tests for remainder exclusion
- `tests/test_drivers.py` — 3 new tests for remainder flag and config model

**Verification:** Run #84 confirmed 6 pairs (unknown excluded), 197 tests pass.
