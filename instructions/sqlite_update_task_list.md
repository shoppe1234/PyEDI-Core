# SQLite Comparator Update — Task List

**Date:** 2026-03-26
**Source:** `sqlLiteReport.md` gap analysis
**Scope:** 10 improvements across 4 phases, touching 12 files

---

## Phase A — Core Parity (HIGH)

### A3: Conditional Qualifier in Flat Compare
- [ ] Add conditional_qualifier logic to `_compare_flat_dict()` in `engine.py` (~5 lines, mirrors existing X12 logic at line 174)
- [ ] Test: flat pair with conditional_qualifier rule, verify skipped when qualifier field present

### A1: Error Discovery Table + Workflow
- [ ] A1.1: Add `DiscoveryRecord` dataclass to `models.py`
- [ ] A1.2: Add `wildcard_fallback: bool = False` field to `FieldDiff` dataclass
- [ ] A1.3: Add `is_wildcard_match()` helper to `rules.py`
- [ ] A1.4: Set `wildcard_fallback=True` in `compare_segment_fields()` and `_compare_flat_dict()` when wildcard matched
- [ ] A1.5: Add `error_discovery` table to `_SCHEMA` in `store.py` (12 columns + 2 indexes)
- [ ] A1.6: Add `insert_discoveries()`, `get_discoveries()`, `apply_discovery()` to `store.py`
- [ ] A1.7: Collect discoveries in `compare()` orchestrator, deduplicate by (segment, field), bulk-insert
- [ ] A1.8: Add `--show-discoveries` and `--apply-discovery ID` to compare subparser in `main.py`
- [ ] A1.9: Add `GET /api/compare/discoveries` and `POST /api/compare/discoveries/{id}/apply` endpoints
- [ ] A1.10: Add `DiscoveryResponse` Pydantic model to `portal/api/models.py`
- [ ] Test: run compare, verify discoveries inserted for wildcard-fallback fields, verify --show-discoveries output

### A2: Reclassification (New Run)
- [ ] A2.1: Add `reclassified_from` column migration to `store.py` (via `_migrate_db()`)
- [ ] A2.2: Add `get_all_diffs_for_run()`, `clone_run_for_reclassify()`, `clone_pairs_for_reclassify()` to `store.py`
- [ ] A2.3: Add `reclassified_from: int | None = None` to `RunSummary` dataclass
- [ ] A2.4: Add `reclassify()` function to `__init__.py` — creates new run, re-resolves severities, inserts diffs
- [ ] A2.5: Add `--reclassify-run RUN_ID` to compare subparser in `main.py`
- [ ] A2.6: Add `POST /api/compare/runs/{run_id}/reclassify` endpoint
- [ ] A2.7: Add `reclassified_from` to `CompareRunResponse` Pydantic model
- [ ] Test: compare run, change rules, reclassify, verify new run created with updated severities

---

## Phase B — Data Model Enrichment (MEDIUM)

### B1: Trading Partner + Transaction Type on compare_runs
- [ ] B1.1: Add `_migrate_db()` and `_add_column_if_missing()` to `store.py`
- [ ] B1.2: Migrate: `trading_partner TEXT`, `transaction_type TEXT`, `run_notes TEXT` on `compare_runs`
- [ ] B1.3: Add `trading_partner: str = ""`, `transaction_type: str = ""` to `CompareProfile` and `RunSummary`
- [ ] B1.4: Update `insert_run()` to accept and store new fields
- [ ] B1.5: Update `_row_to_run_summary()` to read new columns safely
- [ ] B1.6: Update `_parse_profile()` in `__init__.py` to read from config
- [ ] B1.7: Add `trading_partner` + `transaction_type` to all profiles in `config/config.yaml`
- [ ] B1.8: Update `CompareRunResponse` and `CompareProfileResponse` in `portal/api/models.py`
- [ ] B1.9: Thread new fields through portal route response construction
- [ ] Test: compare run, verify trading_partner/transaction_type stored and returned in API

### B3: Segment Column on field_crosswalk
- [ ] B3.1: Add `segment TEXT DEFAULT '*'` column via `_migrate_db()`
- [ ] B3.2: Rebuild table for new UNIQUE constraint `UNIQUE(profile, segment, field_name)` if needed
- [ ] B3.3: Update `upsert_crosswalk()` — add `segment: str = "*"` param
- [ ] B3.4: Update `get_crosswalk()` / `get_crosswalk_field()` to include segment
- [ ] B3.5: Update `load_crosswalk_overrides()` in `rules.py` for segment-aware lookup
- [ ] B3.6: Update `_apply_crosswalk()` in `engine.py` for segment-aware entries
- [ ] Test: upsert crosswalk with segment, verify lookup resolves correctly

### B2: Pre-Seed Crosswalk for All Profiles
- [ ] B2.1: Add `scaffold_crosswalk_from_rules()` to `scaffold.py`
- [ ] B2.2: Add `--from-profile PROFILE` option to `scaffold-rules` subparser in `main.py`
- [ ] B2.3: Auto-seed in `compare()` when crosswalk is empty on first run
- [ ] Test: scaffold crosswalk from rules YAML, verify rows created in DB

---

## Phase C — Reporting (MEDIUM)

### C1: Enrich CSV Export
- [ ] C1.1: Rewrite `export_csv()` — add `#`-prefixed metadata header block
- [ ] C1.2: Expand to 15 columns (add timestamp, profile, trading_partner)
- [ ] C1.3: Add summary footer with severity counts
- [ ] Test: export CSV, verify header/footer present, 15 columns, self-contained

### C2: Summary Statistics Queries
- [ ] C2.1: Add `get_severity_breakdown()`, `get_segment_breakdown()`, `get_field_breakdown()`, `get_top_errors()` to `store.py`
- [ ] C2.2: Add `--summary RUN_ID` flag to compare subparser in `main.py`
- [ ] C2.3: Add `GET /api/compare/runs/{run_id}/summary` endpoint
- [ ] C2.4: Add `CompareSummaryResponse` Pydantic model
- [ ] Test: run compare, verify breakdown counts match expected

---

## Phase D — Polish (LOW)

### D1: 855 PO Ack + 860 PO Change Profiles
- [ ] D1.1: Create `config/compare_rules/855_po_ack.yaml` (BAK segment, N1/REF/DTM/PO1 rules)
- [ ] D1.2: Create `config/compare_rules/860_po_change.yaml` (BCH segment, N1/REF/DTM/POC rules)
- [ ] D1.3: Add profile entries to `config/config.yaml`
- [ ] Test: `--list-profiles` shows new profiles, rules load without error

### D2: Run Comparison View (Diff Two Runs)
- [ ] D2.1: Add `RunDiffResult` dataclass to `models.py`
- [ ] D2.2: Add `compare_two_runs()` to `store.py`
- [ ] D2.3: Add `--diff-runs RUN_A RUN_B` flag to compare subparser
- [ ] D2.4: Add `GET /api/compare/runs/{run_id_a}/diff/{run_id_b}` endpoint
- [ ] Test: two runs with rule changes, verify new/resolved/changed counts correct

---

## Files Modified

| File | Steps |
|------|-------|
| `pyedi_core/comparator/models.py` | A1, A2, B1, D2 |
| `pyedi_core/comparator/rules.py` | A1, B3 |
| `pyedi_core/comparator/engine.py` | A1, A3, B3 |
| `pyedi_core/comparator/store.py` | A1, A2, B1, B3, C2, D2 |
| `pyedi_core/comparator/__init__.py` | A1, A2, B1, B2, C1 |
| `pyedi_core/main.py` | A1, A2, B2, C2, D2 |
| `pyedi_core/scaffold.py` | B2 |
| `portal/api/models.py` | A1, A2, B1, C2 |
| `portal/api/routes/compare.py` | A1, A2, C2, D2 |
| `config/config.yaml` | B1, D1 |
| `config/compare_rules/855_po_ack.yaml` | D1 (new) |
| `config/compare_rules/860_po_change.yaml` | D1 (new) |

## New Test Files

| File | Covers |
|------|--------|
| `tests/test_comparator_discovery.py` | A1: discovery emission, store CRUD, dedup |
| `tests/test_comparator_reclassify.py` | A2: new run, severity re-eval, counts |
| `tests/test_comparator_enrichments.py` | A3, B1, B3: conditional qualifier, new columns, segment crosswalk |
| `tests/test_comparator_reporting.py` | C1, C2: enriched CSV, summary queries |
| `portal/tests/test_compare_api.py` | Extend: discovery + reclassify + summary endpoints |
