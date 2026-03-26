# TODO

## Completed (2026-03-26)

### SQLite Comparator Parity (from sqlLiteReport.md)

All 11 improvement tasks from the SQLite gap analysis have been implemented:

- [x] **A1: Error discovery table + workflow** — `error_discovery` SQLite table, auto-detection of unclassified `(segment, field)` combos during compare runs, `--show-discoveries` / `--apply-discovery` CLI commands. Portal: discoveries tab with apply workflow.
- [x] **A2: Reclassification mode** — `reclassify()` re-evaluates existing diffs against current rules + crosswalk without re-running file pairing. CLI: `--reclassify-run RUN_ID`. Portal: reclassify button with `re:N` badge.
- [x] **B1: Trading partner + transaction type on compare_runs** — Added `trading_partner`, `transaction_type`, `run_notes` columns. Threaded through insert/query/summary.
- [x] **B2: Pre-seed crosswalk for all profiles** — `scaffold-rules --from-profile` seeds crosswalk from rules YAML. Auto-seed on first compare run.
- [x] **B3: Segment column on field_crosswalk** — Added `segment TEXT DEFAULT '*'`, updated UNIQUE constraint to `(profile, segment, field_name)`.
- [x] **C1: Enriched CSV export** — Metadata header block (`# Profile:`, `# Trading Partner:`, etc.), expanded to 15 columns, summary footer with severity counts.
- [x] **C2: Summary statistics queries** — `get_severity_breakdown()`, `get_segment_breakdown()`, `get_field_breakdown()`, `get_top_errors()` in store.py. CLI: `--summary RUN_ID`. Portal: summary panel with inline bar charts.
- [x] **D1: 855 PO Ack + 860 PO Change profiles** — New rules YAMLs + config entries.
- [x] **D2: Run comparison view** — `compare_two_runs()` reports new/resolved/changed/unchanged errors. Portal: checkbox-based run diff with metric cards.

### Portal UI — SQLite Integration

- [x] **5 new API methods** — `compareReclassify`, `compareRunDiff`, `compareRunSummary`, `compareDiscoveries`, `compareApplyDiscovery` added to `api.ts`.
- [x] **Runs/Discoveries tab toggle** — Tab UI on Compare page.
- [x] **Reclassify button + badge** — Reclassify run action, purple `re:N` badge on reclassified runs.
- [x] **Summary statistics panel** — 4-quadrant panel (severity bars, segment bars, field bars, top errors table).
- [x] **Run diff via checkboxes** — Select 2 runs, diff them, see new/resolved/changed/unchanged metrics.
- [x] **Discoveries panel** — Filter by all/pending/applied, apply discoveries to promote to classification.
- [x] **State cleanup** — Edge cases for tab switching, profile changes, run selection.

### Matcher Fix

- [x] **Bidirectional matching** — `pair_transactions()` now detects target-only unmatched pairs (previously silently ignored). `MatchPair.source` is now optional. Guards in engine and store for `source is None`.

### Bevager 810 Workflow (Phases 1-5)

- [x] **Bevager 810 end-to-end compare workflow** — First real trading partner onboarded. DSL compiled, config registered, bevager-specific compare rules created. See `BeveragerTaskList.md` for full task list.
- [x] **Delimiter auto-detection** — `csv_handler.py` `_detect_delimiter()` sniffs first line.
- [x] **Split-by-key output** — `write_split()` groups lines by configurable key, 1 JSON per group.
- [x] **`--split-key` / `--output-dir` CLI flags** — Split output during pipeline run.
- [x] **Flat file compare (`_compare_flat_dict`)** — Structured JSON `{header, lines, summary}` comparison with positional line matching.
- [x] **`scaffold-rules` CLI subcommand** — Auto-generate compare rules YAML from compiled schemas.
- [x] **`field_crosswalk` SQLite table** — Runtime-editable severity overrides with `amount_variance`.
- [x] **Crosswalk-aware rule resolution** — Crosswalk checked before YAML fallback.
- [x] **Bevager-specific compare rules** — `bevager_810.yaml` with numeric/soft/hard rules.

### Documentation (2026-03-26)

- [x] **SQLite gap analysis** — `sqlLiteReport.md` — 10 gaps identified, all 11 improvement tasks now completed.
- [x] **Project assessment** — README updated with success criteria scorecard.
- [x] **Orchestration prompts** — `instructions/` directory with bevager, compare, portal, and e2e testing prompts.
- [x] **Compiled schemas** — `schemas/compiled/` with meta.json sidecars.

## Completed (2026-03-24)

- [x] **Fix compiler type loss bug** — `_compile_to_yaml()` dedup now prefers the most specific type.
- [x] **Fix compiler fieldIdentifier collision** — Fallback key for shared `fieldIdentifier` values.
- [x] **Extract `parse_dsl_file()` helper** — Public function for DSL parsing without file writes.
- [x] **Create `pyedi_core/validator.py`** — DSL compilation, type checks, mapping trace, coverage.
- [x] **Add `pyedi validate` CLI subcommand** — `--dsl`, `--sample`, `--json`, `--verbose`, `--output-dir`.
- [x] **Add validator tests** — 9 unit + integration tests.
- [x] **Build PyEDI Portal (FastAPI backend)** — Health, validate, pipeline, test, manifest, config, compare endpoints.
- [x] **Build PyEDI Portal (React frontend)** — Dashboard, Validate, Pipeline, Tests, Compare, Config pages.
- [x] **Compare engine — core** — Profile-driven comparison with models, rules, matcher, engine, SQLite store, CLI.
- [x] **Compare engine — portal** — 14 compare API routes, React Compare page with full workflow.
- [x] **Playwright E2E test suite** — 29 headed browser tests across all portal pages.

## Open

### Next Up

- [ ] **Bevager 810 Phase 6 re-run** — Process control/test files, run comparison with bidirectional matcher, validate crosswalk, verify portal UI displays all results. See `instructions/bevager_e2e_testing_prompt.md`.

### Medium Priority

- [ ] **Add `react-router-dom` routing** — Replace manual page state in `App.tsx` with URL-based routing. Enables browser back/forward and deep linking.
- [ ] **Portal: file upload on Pipeline page** — Wire `POST /api/pipeline/upload` to drag-and-drop UI.
- [ ] **Portal: Manifest page** — Dedicated page with search, status filter, pagination.
- [ ] **Compare: conditional qualifier in flat compare** — `_compare_flat_dict()` does not support `conditional_qualifier`. See `sqlLiteReport.md` Gap A3.

### Low Priority

- [ ] **Standardize YAML quoting conventions** — 11 files with mixed quoting.
- [ ] **Portal: authentication** — Basic auth or API key middleware.
- [ ] **Portal: config editing UI** — Inline editing for csv_schema_registry entries.
- [ ] **Compare: "ignore" severity in practice** — No rules YAML uses `severity: ignore`. Consider adding for date formatting diffs.
