# Silver Retalix Fixed-Width: End-to-End Pipeline — Orchestration Prompt

**Purpose:** Walk the Retalix PI Invoice fixed-width data through the full pycoreEdi pipeline for the first time — DSL validation, config setup, pipeline run (controlled + test), field-level comparison, and final verification via pytest + Playwright.

**Controlled data (source of truth):** `artifacts/silver/ca-silver/` — 3 files, each containing multiple invoices
**Test data (comparison target):** `artifacts/silver/na-silver/` — same 3 filenames, known diffs in 2 of 3 files
**DSL schema:** `artifacts/RetalixPIInvoiceFileSchemaSacFF.ffSchema`
**Compiled schema:** `schemas/compiled/RetalixPIInvoiceFileSchemaSacFF_map.yaml`
**Config:** `config/config.yaml`
**Compare rules:** `config/compare_rules/retalix_p_i_invo.yaml`
**Coding standards:** `CLAUDE.md`

---

## Known Differences Between ca-silver and na-silver

File `CA_810_SILVR_20260210_063047_373-3072.txt` — **identical** (zero diffs expected).

File `CA_810_SILVR_20260210_070604_668-3071.txt` — 2 diffs:
- `OIN_BT1` line: `SILVERBIRCH HOTELS & RESO` → `SILVERBIRCH HOTEL  & RESO`
- `OIN_DTL2` line: `CHEESE CHED MILD SLCD NAT COL 14G` → `...27G`

File `CA_810_SILVR_20260210_080223_595-3060.txt` — 2 diffs:
- `OIN_RE2` line: `Gordon Food Service Canada` → `Gordon Food Service USA`
- `OIN_DTL2` line: `CEREAL SPECIAL K GRANOLA L/FAT` → `...L/LEAN`

---

## Rules of Engagement

1. **Sequential tasks** — complete each task fully (including its verification) before starting the next.
2. **Read before writing** — always read the target file before making any change.
3. **Minimal diffs** — change only what the task requires. No drive-by fixes.
4. **Stop on red** — if any step fails, diagnose and fix before proceeding.
5. **Match existing patterns** — follow conventions in the codebase exactly.
6. **Data-driven, zero hardcoding** — all config must be in YAML, not code.

---

## Pre-Flight

Before starting any task, verify the development environment:

```bash
cd ~/VS/pycoreEdi

# Verify clean baseline — all existing tests must pass
python -m pytest tests/ -v --tb=short 2>&1 | tail -30

# Verify pyedi CLI is functional
python -m pycoreedi compare --list-profiles --config config/config.yaml

# Verify DSL file and data files exist
ls artifacts/RetalixPIInvoiceFileSchemaSacFF.ffSchema
ls artifacts/silver/ca-silver/
ls artifacts/silver/na-silver/

# Verify compiled schema already exists
ls schemas/compiled/RetalixPIInvoiceFileSchemaSacFF_map.yaml
```

If any tests fail at baseline, **stop and fix them first**.

---

# TASK 1: Validate the DSL Schema

> **Goal:** Confirm the DSL parses correctly, the compiled YAML is current, and the schema aligns with sample data.

```bash
python -m pycoreedi validate \
  --dsl artifacts/RetalixPIInvoiceFileSchemaSacFF.ffSchema \
  --sample artifacts/silver/ca-silver/CA_810_SILVR_20260210_063047_373-3072.txt \
  --verbose
```

**Verification:**
- Command exits 0
- Output shows all record types recognized (O_TPID, OIN_DSTID, OIN_HDRA, TPM_HDR, OIN_HDR1-5, OIN_TRM1, OIN_ST1-3, OIN_BT1-3, OIN_RE1-3, OIN_DTL1-11, OIN_TTL1, etc.)
- Sample file alignment shows records parsed without position errors
- Compiled YAML is up-to-date (check `schemas/compiled/RetalixPIInvoiceFileSchemaSacFF_map.meta.json` timestamp)

**If validation fails:** Read the error output. Common issues:
- DSL syntax errors → check the .ffSchema file
- Sample file misalignment → record widths may not match data; inspect the first few lines of sample vs schema

---

# TASK 2: Fix config/config.yaml — Schema Registry Entries

> **Goal:** Add two `csv_schema_registry` entries so the pipeline can route files from ca-silver and na-silver directories.

**Read first:** `config/config.yaml` (the `csv_schema_registry` section, lines ~148-173)

**Add these entries** (keep the existing `retalix_p_i_invo` entry as-is):

```yaml
  retalix_silver_control:
    source_dsl: ./artifacts/RetalixPIInvoiceFileSchemaSacFF.ffSchema
    compiled_output: ./schemas/compiled/RetalixPIInvoiceFileSchemaSacFF_map.yaml
    inbound_dir: ./artifacts/silver/ca-silver
    transaction_type: RETALIXPIINVOICEFILESCHEMASACFF
  retalix_silver_test:
    source_dsl: ./artifacts/RetalixPIInvoiceFileSchemaSacFF.ffSchema
    compiled_output: ./schemas/compiled/RetalixPIInvoiceFileSchemaSacFF_map.yaml
    inbound_dir: ./artifacts/silver/na-silver
    transaction_type: RETALIXPIINVOICEFILESCHEMASACFF
```

**Why:** The pipeline's `_resolve_csv_schema()` matches files to registry entries by comparing the file's parent directory to `inbound_dir`. Without these entries, the pipeline will raise `SchemaLookupError`.

**Critical:** The `transaction_type` must be `RETALIXPIINVOICEFILESCHEMASACFF` (matching the compiled schema), NOT `RETALIXPIINVOICEFILES` (the current broken value).

**Verification:**
```bash
python -c "
from pyedi_core.config import load_config
cfg = load_config('config/config.yaml')
for name, entry in cfg.csv_schema_registry.items():
    if 'silver' in name or 'retalix' in name.lower():
        print(f'{name}: inbound_dir={entry.inbound_dir}, tx_type={entry.transaction_type}')
"
```

---

# TASK 3: Fix config/config.yaml — Compare Profile

> **Goal:** Fix the `retalix_p_i_invo` compare profile with correct transaction_type and match_key.

**Read first:** `config/config.yaml` (the `compare.profiles.retalix_p_i_invo` section, lines ~140-147)

**Update to:**

```yaml
    retalix_p_i_invo:
      description: Retalix PI Invoice fixed-width comparison (Silverbirch)
      trading_partner: Silverbirch
      transaction_type: RETALIXPIINVOICEFILESCHEMASACFF
      match_key:
        json_path: header.invoiceNumber
      segment_qualifiers: {}
      rules_file: config/compare_rules/retalix_p_i_invo.yaml
```

**Why each fix matters:**
- `transaction_type`: Must match compiled schema (`RETALIXPIINVOICEFILESCHEMASACFF`), not the truncated `RETALIXPIINVOICEFILES`
- `match_key.json_path`: `header.recordID` is wrong — `recordID` is the record type prefix (e.g., `OIN_HDR1`), not a unique invoice identifier. `invoiceNumber` is the actual invoice number from OIN_HDR1 records, which `write_split` will promote into the header.
- `description`/`trading_partner`: Clean up placeholder text

**Verification:**
```bash
python -m pycoreedi compare --list-profiles --config config/config.yaml 2>&1 | grep -A2 retalix
```

---

# TASK 4: Scaffold Compare Rules

> **Goal:** Replace the bare wildcard catch-all rules with proper field-level classification.

```bash
python -m pycoreedi scaffold-rules \
  --schema schemas/compiled/RetalixPIInvoiceFileSchemaSacFF_map.yaml \
  --output config/compare_rules/retalix_p_i_invo.yaml \
  --profile retalix_p_i_invo \
  --db data/compare.db
```

**What this does:** Reads every column from the compiled schema, determines if numeric (float/integer/decimal) or string, and writes a classification entry for each field. This gives the compare engine proper `numeric: true/false` flags for each field.

**Verification:**
```bash
# Check the generated rules have field-specific entries
python -c "
import yaml
with open('config/compare_rules/retalix_p_i_invo.yaml') as f:
    rules = yaml.safe_load(f)
print(f'Classification entries: {len(rules[\"classification\"])}')
numeric_fields = [r['field'] for r in rules['classification'] if r.get('numeric')]
print(f'Numeric fields: {numeric_fields[:10]}...')
"
```

Should show many classification entries (one per schema column) with proper numeric flags on fields like `invoiceNumber`, `orderNumber`, `percent`, etc.

---

# TASK 5: Run Pipeline — Controlled Data (ca-silver → JSON)

> **Goal:** Process all 3 controlled files through the pipeline, splitting by `invoiceNumber` so each invoice gets its own JSON output.

```bash
python -m pycoreedi run \
  --files \
    artifacts/silver/ca-silver/CA_810_SILVR_20260210_063047_373-3072.txt \
    artifacts/silver/ca-silver/CA_810_SILVR_20260210_070604_668-3071.txt \
    artifacts/silver/ca-silver/CA_810_SILVR_20260210_080223_595-3060.txt \
  --split-key invoiceNumber \
  --output-dir outbound/silver/control \
  --verbose
```

**What to expect:** Multiple JSON files in `outbound/silver/control/`, one per invoice (e.g., `invoiceNumber_4388989.json`). Each JSON has the structure:
```json
{
  "header": {"invoiceNumber": "4388989", ...},
  "lines": [{...}, ...],
  "summary": {}
}
```

**Verification:**
```bash
# Check output files were created
ls outbound/silver/control/

# Verify JSON structure of one file
python -c "
import json, glob
files = glob.glob('outbound/silver/control/*.json')
print(f'Total JSON files: {len(files)}')
with open(files[0]) as f:
    data = json.load(f)
print(f'Header keys: {list(data[\"header\"].keys())}')
print(f'Lines: {len(data[\"lines\"])}')
print(f'invoiceNumber in header: {\"invoiceNumber\" in data[\"header\"]}')
"
```

**If it fails:** Common issues:
- `SchemaLookupError` → Task 2 config not applied correctly, `inbound_dir` doesn't resolve
- No `invoiceNumber` in lines → Check compiled schema has this field in `record_layouts`
- Empty output → Check that `input_format: FIXED_WIDTH` is in the compiled schema

---

# TASK 6: Run Pipeline — Test Data (na-silver → JSON)

> **Goal:** Process all 3 test files identically.

```bash
python -m pycoreedi run \
  --files \
    artifacts/silver/na-silver/CA_810_SILVR_20260210_063047_373-3072.txt \
    artifacts/silver/na-silver/CA_810_SILVR_20260210_070604_668-3071.txt \
    artifacts/silver/na-silver/CA_810_SILVR_20260210_080223_595-3060.txt \
  --split-key invoiceNumber \
  --output-dir outbound/silver/test \
  --verbose
```

**Verification:**
```bash
# Same number of files as control
ls outbound/silver/control/ | wc -l
ls outbound/silver/test/ | wc -l

# Same filenames (invoiceNumber values should match)
diff <(ls outbound/silver/control/) <(ls outbound/silver/test/)
```

Both directories should have the same set of `invoiceNumber_*.json` files. If the file count differs, an invoice was parsed differently — investigate.

---

# TASK 7: Compare Source vs Target

> **Goal:** Run the comparison engine and verify it detects the known diffs.

```bash
python -m pycoreedi compare \
  --profile retalix_p_i_invo \
  --source-dir outbound/silver/control \
  --target-dir outbound/silver/test \
  --export-csv \
  --verbose
```

**What to expect:**
- Invoices from file 3072: **MATCH** (identical data)
- Invoices from files 3071 & 3060: **MISMATCH** with specific field diffs:
  - String field changes (product descriptions, company names)
- CSV report written to `reports/compare/`
- Results stored in SQLite at `data/compare.db`

**Verification:**
```bash
# Check the run was recorded
python -c "
from pyedi_core.comparator.store import get_runs, init_db
init_db('data/compare.db')
runs = get_runs('data/compare.db')
latest = runs[-1]
print(f'Run {latest.run_id}: profile={latest.profile}, matched={latest.matched_count}, mismatched={latest.mismatched_count}')
"

# Check CSV report exists
ls -la reports/compare/compare_run_*.csv | tail -1

# View summary
python -m pycoreedi compare --summary $(python -c "
from pyedi_core.comparator.store import get_runs, init_db
init_db('data/compare.db')
runs = get_runs('data/compare.db')
print(runs[-1].run_id)
")
```

**Expected result:** Some invoices match (from file 3072), some mismatch (from files 3071/3060). The mismatches should be on string fields (product descriptions, company names), NOT on invoice numbers or record structure.

---

# TASK 8: Run Full Test Suite

> **Goal:** Confirm nothing was broken by the config changes.

```bash
# Run all Python tests
python -m pytest tests/ -v --tb=short 2>&1 | tail -40

# Verify comparator tests specifically
python -m pytest tests/test_comparator.py -v --tb=short

# Verify API tests
python -m pytest tests/test_api.py -v --tb=short

# Verify the CLI still works for other profiles
python -m pycoreedi compare --list-profiles --config config/config.yaml
```

**All tests must pass.** If any test fails, diagnose and fix before proceeding to Task 9.

---

# TASK 9: Launch Portal and Run Playwright

> **Goal:** Verify the portal UI still works correctly with the new config, especially the Compare and Rules pages.

### 9a: Start the backend API

```bash
cd ~/VS/pycoreEdi/portal
uvicorn api.main:app --reload --port 8000 &
API_PID=$!
echo "API started on :8000 (PID=$API_PID)"
```

### 9b: Start the frontend dev server

```bash
cd ~/VS/pycoreEdi/portal/ui
npm run dev &
UI_PID=$!
echo "UI started on :5173 (PID=$UI_PID)"
```

### 9c: Wait for servers, then run Playwright

```bash
# Wait for both servers to be ready
sleep 5

# Run Playwright tests (if test files exist)
cd ~/VS/pycoreEdi/portal/ui
npx playwright test --reporter=list 2>&1

# If no Playwright test files exist yet, launch the Playwright CLI for manual verification:
npx playwright open http://localhost:5173
```

### 9d: Manual verification checklist (if using Playwright CLI)

When the browser opens, verify these pages:

1. **Dashboard** (`/`) — loads without errors, shows infographic
2. **Compare** (`/compare`) — shows the `retalix_p_i_invo` profile in the dropdown, can view the latest run results
3. **Rules** (`/rules`) — shows the scaffolded rules for `retalix_p_i_invo` profile with field-level entries
4. **Onboard Wizard** (`/onboard`) — can select/view the Retalix schema

### 9e: Cleanup

```bash
kill $API_PID $UI_PID 2>/dev/null
```

---

## Success Criteria

All of the following must be true:

- [ ] DSL validates cleanly (Task 1)
- [ ] Config has two schema registry entries for silver data (Task 2)
- [ ] Compare profile has correct `transaction_type` and `match_key` (Task 3)
- [ ] Compare rules are scaffolded with field-level entries (Task 4)
- [ ] Controlled JSON output exists in `outbound/silver/control/` (Task 5)
- [ ] Test JSON output exists in `outbound/silver/test/` (Task 6)
- [ ] Compare run completes with expected match/mismatch counts (Task 7)
- [ ] All existing tests pass (Task 8)
- [ ] Portal UI loads and shows new profile/rules correctly (Task 9)
