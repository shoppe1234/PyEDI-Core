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

## Phase 1: Data Preparation (config only, no code changes)

- [ ] **Task 1.1 — Compile DSL to YAML schema**
  - Command: `python -m pycoreedi validate --dsl testingData/Batch1/bevager810FF.txt --output-dir schemas/compiled`
  - Output: `schemas/compiled/bevager810FF.yaml` + `.meta.json`
  - Verify: 18 columns, InvoiceID=integer, money fields=float

- [ ] **Task 1.2 — Register bevager in `config/config.yaml`**
  - Add to `csv_schema_registry`:
    ```yaml
    bevager_810:
      source_dsl: ./testingData/Batch1/bevager810FF.txt
      compiled_output: ./schemas/compiled/bevager810FF.yaml
      inbound_dir: ./testingData/Batch1
      transaction_type: '810'
    ```
  - Add to `compare.profiles`:
    ```yaml
    bevager_810:
      description: "Bevager 810 Invoice flat file comparison"
      match_key:
        json_path: "header.InvoiceID"
      segment_qualifiers: {}
      rules_file: "config/compare_rules/bevager_810.yaml"
    ```

- [ ] **Task 1.3 — Create `config/compare_rules/bevager_810.yaml`**
  - Numeric (hard): InvoiceAmount, WeightShipped, UnitPrice, QuantityShipped, Discount, Taxes, ExtendedPrice
  - Soft: ProductDescription (ignore_case: true)
  - Default wildcard: all remaining fields = hard
  - Ignore: none

---

## Phase 2: Code Changes — Split Output

- [ ] **Task 2.1 — Add delimiter auto-detection** → `pyedi_core/drivers/csv_handler.py`
  - `_detect_delimiter()` — sniff first line, count `|`, `,`, `\t`, pick the winner
  - Keeps system data-driven: no hardcoded delimiter per partner

- [ ] **Task 2.2 — Add `write_split()` method** → `pyedi_core/drivers/csv_handler.py`
  - Groups `lines` by configurable `split_key` field (e.g., InvoiceID)
  - Writes 1 JSON per group: `{header: {InvoiceID: X, ...}, lines: [...], summary: {}}`
  - Promotes split key into `header` so `json_path: "header.InvoiceID"` resolves

- [ ] **Task 2.3 — Add `--split-key` and `--output-dir` to CLI**
  - Files: `pyedi_core/main.py`, `pyedi_core/pipeline.py`
  - `run` subcommand gets `--split-key InvoiceID` and `--output-dir outbound/bevager/control`
  - Pipeline calls `write_split()` instead of `write()` when `split_key` is set

---

## Phase 3: Code Changes — Compare Engine Enhancement

- [ ] **Task 3.1 — Enhance `compare_flat_pair` for structured JSON** → `pyedi_core/comparator/engine.py`
  - Extract logic into `_compare_flat_dict(src_dict, tgt_dict, segment_label, rules)`
  - When JSON has `lines` key: compare header fields, match lines positionally, compare each line pair, compare summary
  - Backward-compatible: falls back to current behavior for truly flat JSON

---

## Phase 4: Crosswalk Table (data-driven severity + variance)

- [ ] **Task 4.1 — Add `field_crosswalk` table** → `pyedi_core/comparator/store.py`
  ```sql
  field_crosswalk (
    id              INTEGER PRIMARY KEY,
    profile         TEXT NOT NULL,
    field_name      TEXT NOT NULL,
    severity        TEXT DEFAULT 'hard',       -- hard | soft | ignore
    numeric         BOOLEAN DEFAULT 0,
    ignore_case     BOOLEAN DEFAULT 0,
    amount_variance REAL DEFAULT NULL,         -- e.g., 0.01 for penny tolerance
    updated_at      TEXT NOT NULL,
    updated_by      TEXT DEFAULT 'system',
    UNIQUE(profile, field_name)
  )
  ```
  - CRUD: `upsert_crosswalk()`, `get_crosswalk()`, `get_crosswalk_field()`

- [ ] **Task 4.2 — Add `amount_variance` to `FieldRule`** → `pyedi_core/comparator/models.py`
  - `amount_variance: float | None = None`

- [ ] **Task 4.3 — Wire crosswalk into rule resolution** → `pyedi_core/comparator/rules.py`
  - `get_field_rule()` checks crosswalk (cached per-profile at run start), falls back to YAML
  - Engine uses `amount_variance`: `abs(src - tgt) <= variance` → pass

---

## Phase 5: Scaffold CLI Command

- [ ] **Task 5.1 — Add `scaffold-rules` subcommand**
  - Files: `pyedi_core/main.py`, new `pyedi_core/scaffold.py`
  - Reads compiled schema YAML → generates starter rules YAML with correct `numeric` flags
  - Optionally seeds crosswalk table entries
  - Usage: `python -m pycoreedi scaffold-rules --schema schemas/compiled/bevager810FF.yaml`

---

## Phase 6: Execute the Test

- [ ] **Task 6.1 — Process control files**
  ```bash
  python -m pycoreedi run --file "testingData/Batch1/controlSample-FlatFile-Target/CA_810_BEVAGER_20260324_060426_620-3072.txt" --split-key InvoiceID --output-dir outbound/bevager/control
  python -m pycoreedi run --file "testingData/Batch1/controlSample-FlatFile-Target/CA_810_BEVAGER_20260325_040235_483-3054.txt" --split-key InvoiceID --output-dir outbound/bevager/control
  ```

- [ ] **Task 6.2 — Process test files**
  ```bash
  python -m pycoreedi run --file "testingData/Batch1/testSample-FlatFile-Target/CA_810_BEVAGER_20260324_060426_620-3072.txt" --split-key InvoiceID --output-dir outbound/bevager/test
  python -m pycoreedi run --file "testingData/Batch1/testSample-FlatFile-Target/CA_810_BEVAGER_20260325_040235_483-3054.txt" --split-key InvoiceID --output-dir outbound/bevager/test
  ```

- [ ] **Task 6.3 — Run comparison**
  ```bash
  python -m pycoreedi compare --profile bevager_810 --source-dir outbound/bevager/control --target-dir outbound/bevager/test --verbose --export-csv
  ```

- [ ] **Task 6.4 — Validate crosswalk override**
  - Insert a variance row: `sqlite3 data/compare.db "INSERT INTO field_crosswalk (profile, field_name, severity, numeric, amount_variance, updated_at) VALUES ('bevager_810', 'Taxes', 'hard', 1, 0.05, datetime('now'))"`
  - Re-run comparison — Taxes diffs within 0.05 should now pass

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
