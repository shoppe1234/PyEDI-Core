# Bevager 810 End-to-End Compare — Task List

## Context

Test the full compare workflow: flat file → JSON → compare, using bevager 810 invoice data. Two controlled data sets (`controlSample` vs `testSample`), each with 2 root-level files. DSL (`bevager810FF.txt`) describes 18 fields. This onboarding process is the template for every future trading partner — zero hardcoding, everything data-driven.

---

## Decisions Made

| Decision | Value |
|----------|-------|
| File scope | 2 root-level files per directory |
| Match key | InvoiceID |
| JSON output | Split into separate files — 1 JSON per InvoiceID |
| Numeric fields | InvoiceAmount, WeightShipped, UnitPrice, QuantityShipped, Discount, Taxes, ExtendedPrice |
| Soft fields | ProductDescription (warning-only, ignore_case) |
| Hard fields | All remaining fields (default) |
| Compare rules | New bevager-specific YAML |
| Crosswalk table | SQLite for runtime severity overrides + amount variance |
| Automation | Manual first, then scaffold CLI command |

---

## Gaps Identified

| # | Gap | Current State | Fix |
|---|-----|---------------|-----|
| G1 | DSL not compiled | `bevager810FF.txt` exists, no compiled YAML | Compile via `validate --dsl` |
| G2 | No split-by-key output | Pipeline writes 1 JSON per input file | Add `--split-key` to split by InvoiceID |
| G3 | `compare_flat_pair` is shallow | Only compares top-level JSON keys | Enhance to walk `{header, lines, summary}` |
| G4 | No bevager config entries | No registry entry, no compare profile | Add to `config.yaml` |
| G5 | No crosswalk table | Field severity only in YAML files | Add SQLite `field_crosswalk` table |
| G6 | No rules scaffold | Rules YAML created manually | Add `scaffold-rules` CLI command |

---

## Phase 1: Data Preparation (config only, no code changes) — COMPLETE

- [x] **Task 1.1 — Compile DSL to YAML schema**
  - Command: `python -m pycoreedi validate --dsl testingData/Batch1/bevager810FF.txt --output-dir schemas/compiled`
  - Output: `schemas/compiled/bevager810FF_map.yaml` + `.meta.json`
  - Verified: 18 columns, InvoiceID=integer, money fields=float

- [x] **Task 1.2 — Register bevager in `config/config.yaml`**
  - Added to `csv_schema_registry` and `compare.profiles`

- [x] **Task 1.3 — Create `config/compare_rules/bevager_810.yaml`**
  - Numeric (hard): InvoiceAmount, WeightShipped, UnitPrice, QuantityShipped, Discount, Taxes, ExtendedPrice
  - Soft: ProductDescription (ignore_case: true)
  - Default wildcard: all remaining fields = hard

---

## Phase 2: Code Changes — Split Output — COMPLETE

- [x] **Task 2.1 — Add delimiter auto-detection** → `pyedi_core/drivers/csv_handler.py`
  - `_detect_delimiter()` sniffs first line, counts `|`, `,`, `\t`, picks the winner

- [x] **Task 2.2 — Add `write_split()` method** → `pyedi_core/drivers/csv_handler.py`
  - Groups `lines` by configurable `split_key` field, writes 1 JSON per group
  - Promotes split key into `header` so `json_path: "header.InvoiceID"` resolves

- [x] **Task 2.3 — Add `--split-key` and `--output-dir` to CLI**
  - `main.py` and `pipeline.py` updated with `--split-key` and `--output-dir` flags

---

## Phase 3: Code Changes — Compare Engine Enhancement — COMPLETE

- [x] **Task 3.1 — Enhance `compare_flat_pair` for structured JSON** → `pyedi_core/comparator/engine.py`
  - Extracted `_compare_flat_dict(src_dict, tgt_dict, segment_label, rules)`
  - Header, lines (positional matching), and summary comparison implemented
  - Backward-compatible with truly flat JSON

---

## Phase 4: Crosswalk Table (data-driven severity + variance) — COMPLETE

- [x] **Task 4.1 — Add `field_crosswalk` table** → `pyedi_core/comparator/store.py`
  - Table created with CRUD: `upsert_crosswalk()`, `get_crosswalk()`, `load_crosswalk_overrides()`

- [x] **Task 4.2 — Add `amount_variance` to `FieldRule`** → `pyedi_core/comparator/models.py`

- [x] **Task 4.3 — Wire crosswalk into rule resolution** → `pyedi_core/comparator/rules.py`
  - `get_field_rule()` checks crosswalk (cached per-profile at run start), falls back to YAML
  - Engine uses `amount_variance`: `abs(src - tgt) <= variance` → pass

---

## Phase 5: Scaffold CLI Command — COMPLETE

- [x] **Task 5.1 — Add `scaffold-rules` subcommand**
  - `pyedi_core/scaffold.py` created, wired into `main.py`
  - Reads compiled schema YAML → generates starter rules YAML with correct `numeric` flags
  - Seeds crosswalk table entries

---

## Phase 6: Execute the Test — NEEDS RE-RUN

Previous run (pre-matcher-fix) produced 22 pairs with 0 unmatched. The matcher has since been fixed to detect target-only unmatched pairs (commit `c4af119`). Output directories were cleaned up. Phase 6 needs re-execution with the bidirectional matcher.

- [x] **Task 6.1 — Process control files** — Previously: 22 JSON files in `outbound/bevager/control/`. Needs re-run.
- [x] **Task 6.2 — Process test files** — Previously: 22 JSON files in `outbound/bevager/test/`. Needs re-run with BOTH test files (3054 + 3072) to generate target-only InvoiceIDs.
- [x] **Task 6.3 — Run comparison** — Previously: Run #33 (22 pairs, 0 unmatched). Re-run should show unmatched > 0 (target-only pairs from 3072 file).
- [x] **Task 6.4 — Validate crosswalk override** — Previously: Taxes with amount_variance=50.0.

**Re-run orchestration prompt:** `instructions/bevager_e2e_testing_prompt.md`

---

## Verification Checklist

| # | Check | How to Verify |
|---|-------|---------------|
| V1 | DSL compiles | `schemas/compiled/bevager810FF.yaml` has 18 columns |
| V2 | Split works | `outbound/bevager/control/` has N JSON files (1 per unique InvoiceID) |
| V3 | JSON structure | Each file has `header.InvoiceID`, `lines` array with matching rows |
| V4 | Pairing works | Compare run `total_pairs` = count of unique InvoiceIDs |
| V5 | Expected diffs | DueDate (populated vs empty = hard), Taxes (0.03 vs 0 = hard numeric) |
| V6 | Soft severity | ProductDescription shows as soft, not hard |
| V7 | Crosswalk override | After inserting variance row, Taxes within tolerance pass |
| V8 | CSV export | `reports/compare/` has readable diff report |
| V9 | SQLite records | `data/compare.db` has run/pair/diff/crosswalk entries |
| V10 | Scaffold command | Generates correct rules YAML from compiled schema |

---

## Files Modified/Created

| File | Action |
|------|--------|
| `config/config.yaml` | Edit — add bevager_810 to csv_schema_registry + compare.profiles |
| `config/compare_rules/bevager_810.yaml` | **Create** — bevager-specific field rules |
| `schemas/compiled/bevager810FF.yaml` | **Generated** — compiled from DSL |
| `pyedi_core/drivers/csv_handler.py` | Edit — add `_detect_delimiter()` + `write_split()` |
| `pyedi_core/pipeline.py` | Edit — add `split_key` / `output_dir` params |
| `pyedi_core/main.py` | Edit — add `--split-key`, `--output-dir`, `scaffold-rules` subcommand |
| `pyedi_core/comparator/engine.py` | Edit — enhance `compare_flat_pair` for structured JSON |
| `pyedi_core/comparator/models.py` | Edit — add `amount_variance` to `FieldRule` |
| `pyedi_core/comparator/store.py` | Edit — add `field_crosswalk` table + CRUD |
| `pyedi_core/comparator/rules.py` | Edit — wire crosswalk into `get_field_rule()` |
| `pyedi_core/scaffold.py` | **Create** — scaffold-rules logic |
| `pyedi_core/comparator/matcher.py` | Edit — add target-only unmatched pair detection |
| `pyedi_core/comparator/models.py` | Edit — make `MatchPair.source` optional |
| `instructions/bevager_e2e_testing_prompt.md` | **Create** — combined e2e test + portal UI verification |
