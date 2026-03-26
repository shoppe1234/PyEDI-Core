# TODO

## Completed (2026-03-26)

- [x] **Bevager 810 end-to-end compare workflow** — First real trading partner onboarded. DSL compiled, config registered, bevager-specific compare rules created. 22 invoice pairs compared across control/test directories. Results stored in SQLite (`data/compare.db`). CSV export generated. Crosswalk override validated (Taxes with amount_variance). See `BeveragerTaskList.md` for full task list.

### Code Refactoring (2026-03-25/26)

- [x] **Delimiter auto-detection** — `csv_handler.py` now auto-detects delimiters (`|`, `,`, `\t`) by sniffing the first line. No hardcoded delimiter per partner.
- [x] **Split-by-key output** — `csv_handler.py` `write_split()` groups `lines` by a configurable key (e.g., InvoiceID), writes 1 JSON per group with the key promoted into `header`.
- [x] **`--split-key` and `--output-dir` CLI flags** — `main.py` and `pipeline.py` support `--split-key InvoiceID --output-dir outbound/bevager/control` to split output into per-key JSON files.
- [x] **Flat file compare (`_compare_flat_dict`)** — `engine.py` enhanced to compare structured JSON (`{header, lines, summary}`) by matching lines positionally after comparing header and summary fields. Backward-compatible with truly flat JSON.
- [x] **`scaffold-rules` CLI subcommand** — New `pyedi_core/scaffold.py` reads compiled schema YAML and generates starter compare rules YAML with correct `numeric` flags. Seeds crosswalk table entries.
- [x] **`field_crosswalk` SQLite table** — `store.py` added runtime-editable severity overrides with `amount_variance` support. CRUD: `upsert_crosswalk()`, `get_crosswalk()`, `load_crosswalk_overrides()`.
- [x] **Crosswalk-aware rule resolution** — `rules.py` `get_field_rule()` checks crosswalk overrides (cached per-profile at run start) before falling back to YAML rules.
- [x] **Bevager-specific compare rules** — `config/compare_rules/bevager_810.yaml` with numeric fields (InvoiceAmount, WeightShipped, UnitPrice, etc.), soft fields (ProductDescription), and sensible defaults.
- [x] **Compare rules normalization** — `config/compare_rules/810_invoice.yaml` YAML formatting normalized (consistent quoting, explicit defaults for all fields).

### Documentation (2026-03-26)

- [x] **SQLite gap analysis** — `sqlLiteReport.md` comparing pyedi comparator SQLite output against json810Compare Google Sheets/CSV output. 10 gaps identified with improvement task list (4 phases, 11 tasks).
- [x] **Project assessment** — README updated with success criteria scorecard, architectural strengths, known weaknesses, risks, and enhancement roadmap.
- [x] **Orchestration prompts + plans** — `instructions/` directory with compare integration, portal, validate subcommand plans and orchestration prompts.
- [x] **Compiled schemas committed** — `schemas/compiled/gfsGenericOut810FF_map.yaml`, `tpm810SourceFF_map.yaml` with meta.json sidecars.
- [x] **Artifact documents** — `artifacts/` with specification, gap analysis, autocertify blueprint, and comparison examples.

## Completed (2026-03-24)

- [x] **Fix compiler type loss bug** — `_compile_to_yaml()` dedup now prefers the most specific type (`float` > `integer` > `date` > `boolean` > `string`) instead of keeping the first occurrence.
- [x] **Fix compiler fieldIdentifier collision** — When multiple DSL records share the same `fieldIdentifier` value, the compiler now uses the record name as a fallback key to preserve distinct column lists.
- [x] **Extract `parse_dsl_file()` helper** — Public function in `schema_compiler.py` for parsing DSL files without triggering file writes. Used by both `compile_dsl()` and the validator.
- [x] **Create `pyedi_core/validator.py`** — Standalone module for DSL compilation, type preservation checks, sample-file mapping trace, and coverage analysis.
- [x] **Add `pyedi validate` CLI subcommand** — `--dsl`, `--sample`, `--json`, `--verbose`, `--output-dir` flags. Human-readable report and JSON output modes.
- [x] **Add validator tests** — 9 unit + integration tests in `tests/test_validator.py`.
- [x] **Build PyEDI Portal (FastAPI backend)** — `portal/api/` with health, validate, pipeline, test, manifest, and config endpoints. 7 API integration tests.
- [x] **Build PyEDI Portal (React frontend)** — `portal/ui/` with Vite + React + TypeScript + Tailwind CSS. Dashboard, Validate, Pipeline, Tests, and Config pages. Static build served by FastAPI.
- [x] **Compare engine — Phase D (core)** — Ported `json810Compare/comparator.py` into `pyedi_core/comparator/` module. Profile-driven comparison with models, rules (YAML), matcher, engine, SQLite store, and `pyedi compare` CLI subcommand. 6 transaction profiles (810, 850, 856, 820, CSV, cXML). 22 comparator tests.
- [x] **Compare engine — Phase E (portal)** — `/api/compare` endpoints (9 routes: profiles, run, runs, pairs, diffs, export, rules read/write). React `/compare` page with profile dropdown, run history, pair list, diff viewer, rules editor. 5 API integration tests.
- [x] **Playwright E2E test suite** — 29 headed browser tests across all 6 portal pages using pytest-playwright + page object pattern. Covers navigation, health indicator, DSL validation, test harness run, compare full workflow (profile select, run comparison, view pairs/diffs, rules editor round-trip, export CSV). Auto-starts uvicorn on port 8321 per session.

## Open

### Medium Priority

- [ ] **Add `react-router-dom` routing** — Replace manual page state in `App.tsx` with proper URL-based routing (`/validate`, `/pipeline`, `/test`, `/config`, `/compare`). Enables browser back/forward and deep linking.
- [ ] **Portal: file upload on Pipeline page** — Wire the `POST /api/pipeline/upload` endpoint to a drag-and-drop upload component on the Pipeline page.
- [ ] **Portal: Manifest page** — Add a dedicated `/manifest` page with search, status filter, and pagination (API endpoints already exist).
- [ ] **Compare: error discovery** — Port `errorConfig.py` auto-detect pattern from json810Compare to suggest new rules when unknown field mismatches appear. See `sqlLiteReport.md` Gap G1 and Task A1.
- [ ] **Compare: reclassification mode** — Re-evaluate existing diffs against updated rules without re-running file pairing. See `sqlLiteReport.md` Gap G2 and Task A2.
- [ ] **Compare: enrich CSV export** — Add per-row timestamps, profile name, trading partner, summary footer. See `sqlLiteReport.md` Gap G7 and Task C1.
- [ ] **Compare: summary statistics queries** — Severity/segment/field breakdowns, top errors. See `sqlLiteReport.md` Gap G8 and Task C2.

### Low Priority

- [ ] **Standardize YAML quoting conventions** — 11 YAML files use mixed quoting styles (single, double, unquoted). Proposed convention: single quotes for numeric-looking strings/delimiters, no quotes for plain strings, double quotes only for escapes. Requires before/after `yaml.safe_load()` comparison per file to avoid type-coercion breakage. See `instructions/tier3_tier4_remaining_tasks.md` Task 4 for full details.
- [ ] **Portal: authentication** — Add basic auth or API key middleware to the portal API before exposing outside localhost.
- [ ] **Portal: config editing UI** — The `PUT /api/config/registry/{entry_name}` endpoint exists but the frontend Config page is read-only. Add inline editing for csv_schema_registry entries.
- [ ] **Pre-seed crosswalk for all profiles** — Empty crosswalk creates ambiguity between "intentionally default" and "never reviewed." See `sqlLiteReport.md` Gap G5 and Task B2.
- [ ] **Add trading partner context to compare_runs** — Store partner name and transaction type for human-readable reports. See `sqlLiteReport.md` Gap G4 and Task B1.
- [ ] **Add 855 PO Ack + 860 PO Change profiles** — See `sqlLiteReport.md` Task D1.
