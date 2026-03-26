# SQLite Comparator — Gap Analysis & Improvement Report

**Date:** 2026-03-26
**Scope:** pyedi_core/comparator SQLite output vs json810Compare Google Sheets/CSV output
**Applies to:** All transaction types — 810 Invoice, 850 PO, 855 PO Ack, 856 ASN, 860 PO Change, 820 Payment, CSV flat files, cXML

---

## 1. Side-by-Side Schema Comparison

### json810Compare Output (Google Sheets CSV — 9 columns)

| # | Column | Example | Notes |
|---|--------|---------|-------|
| 1 | Timestamp | 2026-03-20 14:32:01 | Per-row, when comparison ran |
| 2 | Invoice # | CAN_94002504 | Match key value (invoice number) |
| 3 | Source File | GFSCA810AARS_e879...json | Full source filename |
| 4 | Target File | CAN_94002504_20260320.json | Full target filename |
| 5 | Status | Mismatch / Match / Target Missing | Per-pair result |
| 6 | Severity | Hard / Soft / Ignore / (empty) | Classification of the diff |
| 7 | Error Segment | N1\*ST, IT1\*position_0, SAC\*position_1 | Segment ID with qualifier |
| 8 | Error Field | N102, CTP03, DTM02 | Field within segment (empty for segment-level) |
| 9 | Description | Content mismatch: Source='X' vs Target='Y' | Human-readable detail |

**Additional Sheets in json810Compare:**
- **Error Classification** (6 cols): Segment, Field, Severity, Ignore Case, Numeric, Conditional Qualifier
- **Ignore Rules** (3 cols): Segment, Field, Reason
- **Error Discovery** (7 cols): Timestamp, Segment, Field, Source Value, Target Value, Suggested Severity, Applied

---

### pyedi_core/comparator SQLite (4 tables)

**compare_runs** (11 columns)

| Column | Type | Example |
|--------|------|---------|
| id | INTEGER PK | 33 |
| profile | TEXT | bevager_810 |
| started_at | TEXT | 2026-03-26T16:18:42Z |
| finished_at | TEXT | 2026-03-26T16:18:42Z |
| source_dir | TEXT | outbound/bevager/control |
| target_dir | TEXT | outbound/bevager/test |
| match_key | TEXT | json_path:header.InvoiceID |
| total_pairs | INTEGER | 22 |
| matched | INTEGER | 2 |
| mismatched | INTEGER | 20 |
| unmatched | INTEGER | 0 |

**compare_pairs** (9 columns)

| Column | Type | Example |
|--------|------|---------|
| id | INTEGER PK | 97 |
| run_id | INTEGER FK | 33 |
| source_file | TEXT | outbound/bevager/control/InvoiceID_9033674514.json |
| source_tx_index | INTEGER | 0 |
| target_file | TEXT | outbound/bevager/test/InvoiceID_9033674514.json |
| target_tx_index | INTEGER | 0 |
| match_value | TEXT | 9033674514 |
| status | TEXT | MISMATCH |
| diff_count | INTEGER | 14 |

**compare_diffs** (8 columns)

| Column | Type | Example |
|--------|------|---------|
| id | INTEGER PK | 380 |
| pair_id | INTEGER FK | 121 |
| segment | TEXT | line_0 |
| field | TEXT | DueDate |
| severity | TEXT | hard |
| source_value | TEXT | 04/24/2026 |
| target_value | TEXT | nan |
| description | TEXT | Content mismatch: Source='04/24/2026' vs Target='nan' |

**field_crosswalk** (9 columns)

| Column | Type | Example |
|--------|------|---------|
| id | INTEGER PK | 1 |
| profile | TEXT | bevager_810 |
| field_name | TEXT | Taxes |
| severity | TEXT | hard |
| numeric | BOOLEAN | 1 |
| ignore_case | BOOLEAN | 0 |
| amount_variance | REAL | 50.0 |
| updated_at | TEXT | 2026-03-26T16:19:22Z |
| updated_by | TEXT | test_phase6 |

**pyedi CSV Export** (12 columns): run_id, pair_id, source_file, target_file, match_value, status, segment, field, severity, source_value, target_value, description

---

### Column-by-Column Mapping

| json810Compare Column | pyedi Equivalent | Present? | Gap |
|-----------------------|-----------------|----------|-----|
| Timestamp | compare_runs.started_at | Run-level only | No per-row timestamp |
| Invoice # | compare_pairs.match_value | YES | — |
| Source File | compare_pairs.source_file | YES | — |
| Target File | compare_pairs.target_file | YES | — |
| Status | compare_pairs.status | YES | Values differ: "Target Missing" vs "UNMATCHED" |
| Severity | compare_diffs.severity | YES | "Ignore" supported but unused in practice |
| Error Segment | compare_diffs.segment | YES | Different notation for flat files (line_0 vs IT1\*position_0) |
| Error Field | compare_diffs.field | YES | — |
| Description | compare_diffs.description | YES | Same format |
| (Trading Partner) | — | NO | Not stored anywhere |
| (Error Discovery) | — | NO | No equivalent table or workflow |
| (Reclassification) | — | NO | No equivalent command |

---

## 2. Gap Analysis

### G1: No Error Discovery Workflow

**json810Compare:** `errorConfig.py` scans the Comparison Report for `(segment, field)` combos not yet in the Error Classification sheet. It logs them to an Error Discovery tab with: Timestamp, Segment, Field, Source Value, Target Value, Suggested Severity, Applied. The user reviews and promotes discoveries into classification rules.

**pyedi today:** Unclassified fields silently hit the `(*, *)` wildcard rule (default: hard). There is no record that a new combo was seen, no suggestion mechanism, no tracking of review status.

**Impact:** Cannot distinguish "intentionally classified as hard" from "never reviewed." As new partners/transactions are onboarded, the classification silently becomes stale. This was the #1 pain point json810Compare solved.

---

### G2: No Reclassification Mode

**json810Compare:** `python comparator.py --reclassify` re-evaluates existing report rows against updated rules without re-running file pairing and field extraction. Severity tuning takes seconds.

**pyedi today:** Must re-run `pyedi compare --profile X --source-dir ... --target-dir ...` from scratch. Re-reads all files, re-pairs transactions, re-computes all diffs.

**Impact:** Rule tuning cycles are 10-100x slower. For the bevager run (22 pairs, 299 lines), this is ~30ms. For production runs with 800+ invoice pairs, the difference becomes significant.

---

### G3: No Timestamp per Diff Row

**json810Compare:** Every CSV row has a Timestamp column (column A).

**pyedi today:** `compare_diffs` has no timestamp. Only `compare_runs` has `started_at`/`finished_at`. The CSV export has no timestamp column.

**Impact:** Exported CSVs lack temporal context. A recipient cannot tell when each diff was generated without cross-referencing the DB.

---

### G4: No Trading Partner Context

**json810Compare:** `config.json` stores partner names (e.g., "Marketman") and maps partners to their directories.

**pyedi today:** `compare_runs` stores `profile` (e.g., "bevager_810"), `source_dir`, `target_dir`. No trading partner name, no partner metadata. `CompareProfile` has only name, description, match_key, segment_qualifiers, rules_file.

**Impact:** Reports cannot display who the trading partner is. As the system scales to many partners, runs are identified only by cryptic profile names and directory paths.

---

### G5: Sparse Crosswalk Table

**json810Compare:** Error Classification sheet has 20+ rows per partner, covering all known segment/field combos.

**pyedi today:** `field_crosswalk` has **1 row** (Taxes with 50.0 variance). The X12 profiles (810, 850, 856, 820) have rules YAML files with 3-4 entries + wildcard. No crosswalk entries seeded for any X12 profile.

**Impact:** The crosswalk table — designed to give the portal runtime-editable field overrides — is effectively empty. It creates ambiguity: was a field intentionally left at default, or was it never reviewed?

---

### G6: No "Ignore" Severity in Practice

**json810Compare:** Active use of Hard/Soft/Ignore. Date formatting differences get "Ignore" — they appear in reports for visibility but don't count as errors.

**pyedi today:** The engine handles `severity == "ignore"` correctly (engine.py line 169: `continue`). However, no rules YAML uses `severity: "ignore"` in classification entries. The `ignore:` list in rules YAML is a separate concept — it skips fields entirely (no reporting).

**Impact:** No middle ground between "flag as error" and "completely invisible." json810Compare's Ignore severity lets fields appear in reports for audit while not being actionable items.

---

### G7: CSV Export Missing Context

**json810Compare:** 9-column self-contained report. Every row has timestamp, invoice number, partner context (via filename convention).

**pyedi today:** 12 columns but missing: timestamp per row, profile name, trading partner name, match_key configuration. A recipient of the CSV needs DB access to fully understand it.

**Impact:** CSVs shared with trading partners or internal teams require supplementary context. Not self-contained.

---

### G8: No Summary Statistics

**json810Compare:** Google Sheets reports support filtering and pivot tables. Users answer: "Which fields fail most?", "What % of errors are soft?", "Is partner X improving over time?"

**pyedi today:** `compare_runs` stores 4 aggregate counts (total_pairs, matched, mismatched, unmatched). No breakdown by severity, field, or segment. No trend queries.

**Impact:** Cannot answer basic analytical questions about comparison quality without writing ad-hoc SQL.

---

### G9: Segment Notation Inconsistency

**json810Compare:** Consistent EDI notation: `N1*ST`, `IT1*position_0`, `SAC*position_1`.

**pyedi today:** X12 mode uses `N1*ST` (matching json810Compare). Flat compare mode uses `header`, `line_0`, `line_1`, `summary`, `flat`. These are different notation systems.

**Impact:** Cross-format analysis is confusing. A user comparing X12 810 results and bevager flat file results sees inconsistent segment labels.

---

### G10: No Conditional Qualifier in Flat Compare

**json810Compare:** `conditional_qualifier` (e.g., skip IT109 if IT108 present) works in segment comparison.

**pyedi today:** `compare_segment_fields` (engine.py) implements conditional_qualifier for X12 mode. `_compare_flat_dict` does not — it has no conditional logic.

**Impact:** Flat file profiles (CSV, cXML, bevager) cannot use conditional rules. If a flat file has mutually exclusive fields, there is no way to express "skip field X if field Y is present."

---

## 3. Lessons Learned from json810Compare

### Lesson 1: Error Discovery is Essential for Onboarding
When json810Compare first ran against a new trading partner, dozens of previously unseen segment/field combos appeared. The Error Discovery tab reduced onboarding time per partner from hours to minutes. **Without auto-discovery, every new partner onboarding requires manual cross-referencing of diffs against classification rules.**

### Lesson 2: Reclassification Saves 80% of Tuning Time
After initial comparison runs, the team typically adjusted 10-15 classification rules. Without reclassification mode, each adjustment required a full re-run (2-5 min for 800+ pairs). With reclassification, the same tuning took seconds. **The ability to re-evaluate without re-running is a force multiplier for rule tuning.**

### Lesson 3: The Crosswalk Must Be Pre-Populated
An empty crosswalk is worse than no crosswalk. It creates ambiguity about whether a field was intentionally at default or never reviewed. **Every new profile should get its crosswalk pre-seeded on creation, either from the compiled schema or from the rules YAML.**

### Lesson 4: Self-Contained Exports Matter
Google Sheets reports included all context (timestamp, partner, classification) in every row. When shared with trading partners or internal teams, no additional context was needed. **pyedi CSVs currently require database access to be fully understood.**

### Lesson 5: Ignore Severity is Distinct from the Ignore List
The ignore list means "pretend this field doesn't exist." Ignore severity means "compare it, note it, but don't count it as an actionable error." **Both mechanisms are needed. The ignore list is for truly irrelevant fields (SE01 segment count). Ignore severity is for fields worth tracking but not acting on (date format variations).**

### Lesson 6: Summary Statistics Drive Decision-Making
The team used Sheets pivot tables to answer: "Which fields fail most?", "What percentage of errors are soft?", "Is partner X getting better over time?" **pyedi cannot answer any of these questions today without ad-hoc SQL.**

---

## 4. Improvement Task List

### Phase A — Core Parity (HIGH priority)

- [ ] **A1: Error Discovery Table + Workflow**
  - Add `error_discovery` table to SQLite:
    ```
    error_discovery (
      id, run_id, profile, segment, field,
      source_value, target_value,
      suggested_severity DEFAULT 'hard',
      applied BOOLEAN DEFAULT 0,
      applied_at, applied_by, discovered_at,
      UNIQUE(profile, segment, field)
    )
    ```
  - In `engine.py`: when a diff is produced using the `(*, *)` wildcard fallback, emit a discovery record
  - In `rules.py`: add `is_classified(rules, segment, field) -> bool` helper
  - In `__init__.py`: bulk-insert discoveries after each compare run (INSERT OR IGNORE)
  - In `main.py`: add `--show-discoveries --profile X` and `--apply-discovery ID`
  - CLI output: "Discovered N new field combinations not yet classified"
  - **Files:** store.py, engine.py, rules.py, models.py, \_\_init\_\_.py, main.py

- [ ] **A2: Reclassification CLI Command**
  - Add `reclassify(run_id, db_path, profile)` to `__init__.py`:
    - Read all diffs for the run
    - Re-resolve severity via `get_field_rule()` with current rules + crosswalk
    - Update severity in `compare_diffs` in place
    - Recalculate diff_count per pair, matched/mismatched/unmatched on run
  - In `store.py`: add `get_all_diffs_for_run()`, `update_diff_severity()`, `update_pair_counts()`
  - In `main.py`: add `--reclassify-run RUN_ID` to compare subparser
  - **Files:** \_\_init\_\_.py, store.py, main.py

- [ ] **A3: Conditional Qualifier in Flat Compare**
  - In `_compare_flat_dict()` (engine.py), after the `severity == "ignore"` check, add:
    ```python
    if rule.conditional_qualifier:
        if key not in src_dict and src_dict.get(rule.conditional_qualifier):
            continue
        if key not in tgt_dict and tgt_dict.get(rule.conditional_qualifier):
            continue
    ```
  - **Files:** engine.py, tests/

---

### Phase B — Data Model Enrichment (MEDIUM priority)

- [ ] **B1: Add Trading Partner + Transaction Type to compare_runs**
  - Add columns: `trading_partner TEXT`, `transaction_type TEXT`, `run_notes TEXT`
  - Add to `CompareProfile` model and `config.yaml` profile definitions
  - Thread through `insert_run()`, `RunSummary`, `_row_to_run_summary()`
  - Migration: `ALTER TABLE ... ADD COLUMN` in `init_db()` with IF NOT EXISTS check
  - **Files:** store.py, models.py, config.yaml, \_\_init\_\_.py

- [ ] **B2: Pre-Seed Crosswalk for All Profiles**
  - Extend `scaffold.py` to support X12 profiles (not just flat schemas):
    - `scaffold_x12_crosswalk(profile_name, rules_path, db_path)` reads classification entries from rules YAML → inserts into field_crosswalk
  - Add CLI: `pyedi scaffold-rules --from-profile 810_invoice --db data/compare.db`
  - Auto-seed option: seed crosswalk on first compare run for a profile
  - **Files:** scaffold.py, store.py, main.py

- [ ] **B3: Add Segment Column to field_crosswalk**
  - Current schema uses `field_name` only (works for flat, breaks for X12 where (segment, field) is the key)
  - Add `segment TEXT DEFAULT '*'` column to field_crosswalk
  - Update `UNIQUE` constraint to `UNIQUE(profile, segment, field_name)`
  - Update `load_crosswalk_overrides()` to use (segment, field) lookup
  - Migration: ALTER TABLE with safe column addition
  - **Files:** store.py, rules.py, scaffold.py

---

### Phase C — Reporting (MEDIUM priority)

- [ ] **C1: Enrich CSV Export**
  - Add metadata header block (lines starting with `#`):
    ```
    # Profile: bevager_810
    # Trading Partner: Bevager
    # Run ID: 33
    # Started: 2026-03-26T16:18:42Z
    # Total Pairs: 22 | Matched: 2 | Mismatched: 20 | Unmatched: 0
    ```
  - Expand columns to 15: timestamp, profile, trading_partner, run_id, pair_id, source_file, target_file, match_value, status, segment, field, severity, source_value, target_value, description
  - Add summary footer row with aggregate counts by severity
  - **Files:** \_\_init\_\_.py

- [ ] **C2: Summary Statistics Queries**
  - Add to `store.py`:
    - `get_severity_breakdown(db_path, run_id) -> dict[str, int]`
    - `get_segment_breakdown(db_path, run_id) -> dict[str, int]`
    - `get_field_breakdown(db_path, run_id) -> dict[str, int]`
    - `get_top_errors(db_path, run_id, limit=10) -> list[dict]`
  - Start with on-the-fly queries; materialized table can come later if needed
  - **Files:** store.py

---

### Phase D — Polish (LOW priority)

- [ ] **D1: Add 855 PO Ack + 860 PO Change Profiles**
  - Create `config/compare_rules/855_po_ack.yaml` with BAK segment rules
  - Create `config/compare_rules/860_po_change.yaml` with BCH segment rules
  - Add profiles to `config.yaml`:
    - 855: match_key `BAK:BAK03`, qualifiers for N1, REF, DTM, PO1
    - 860: match_key `BCH:BCH03`, qualifiers for N1, REF, DTM, POC
  - **Files:** config.yaml, new YAML files

- [ ] **D2: Run Comparison View (Diff Two Runs)**
  - Add `compare_two_runs(db_path, run_id_a, run_id_b)` to `store.py`:
    - For each match_value in both runs, compare diff sets
    - Report: new errors (in B not A), resolved (in A not B), changed severity, unchanged
  - Enables "before/after" analysis when rules change
  - **Files:** store.py, models.py

---

## 5. Files Reference

| File | Improvements |
|------|-------------|
| `pyedi_core/comparator/store.py` | A1, A2, B1, B2, B3, C2, D2 |
| `pyedi_core/comparator/engine.py` | A1, A3 |
| `pyedi_core/comparator/rules.py` | A1, B3 |
| `pyedi_core/comparator/models.py` | A1, B1, D2 |
| `pyedi_core/comparator/__init__.py` | A1, A2, B1, C1 |
| `pyedi_core/main.py` | A1, A2, B2 |
| `pyedi_core/scaffold.py` | B2, B3 |
| `config/config.yaml` | B1, D1 |
| `config/compare_rules/*.yaml` | D1 (new 855, 860 files) |

---

## 6. Current SQLite Data Summary (as of 2026-03-26)

| Table | Total Rows | Bevager Rows | Key Observations |
|-------|-----------|-------------|-----------------|
| compare_runs | 34 | 2 | Run #33 (before crosswalk), Run #34 (after crosswalk) |
| compare_pairs | 140 | 44 | 22 pairs per run, status: 36 MATCH / 72 MISMATCH / 32 UNMATCHED |
| compare_diffs | 692 | 660 | DueDate: 594 (86%), Taxes: 34 (5%), InvoiceDate: 28 (4%), N102: 32 (5%), UnitofMeasure: 4 (0.6%) |
| field_crosswalk | 1 | 1 | Only Taxes (variance=50.0). All other fields unclassified in crosswalk. |

### json810Compare Example Files (artifacts/examples/)

| File | Rows | Invoices | Key Patterns |
|------|------|----------|-------------|
| Marketman-810 - aramark-1st pass.csv | 53+ | 8 | N1 name mismatches, CTP/IT1 price diffs, YNQ missing segments |
| Marketman-810 - Beaudry - 2026-02-11.csv | 71+ | Multiple | Missing DTM02 dates, extra SAC service charge segments |
| Marketman-810 - Comparison Report.csv | 75+ | 2 | PO4/MEA numeric diffs, multi-position segment comparisons |

**Common patterns across json810Compare examples:**
- Segment-level issues (missing/extra segments) are common during onboarding
- Name mismatches (N102) consistently appear as Soft severity
- Numeric precision differences (PO4, MEA, CTP) need numeric comparison mode
- Date fields (DTM02) frequently missing in target — indicates mapping gaps
