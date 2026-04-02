# TODO

## Completed (2026-04-02)

### Retalix PI Invoice Schema Onboarding

- [x] **Retalix PI Invoice ffSchema** — `artifacts/RetalixPIInvoiceFileSchemaSacFF.ffSchema` and `artifacts/RetalixPIPOAckFF.ffSchema` added as schema source artifacts.
- [x] **Compiled Retalix schemas** — `schemas/compiled/RetalixPIInvoiceFileSchemaSacFF_map.yaml` + `.meta.json` and `RetalixPIPOAckFF.yaml` + `.meta.json` compiled.
- [x] **GFS Generic Out 810 compiled** — `schemas/compiled/gfsGenericOut810FF_map.yaml` + `.meta.json`.
- [x] **Retalix compare rules** — `config/compare_rules/retalix_p_i_invo.yaml` with field-level severity classification.
- [x] **Silver data artifacts** — `artifacts/silver/ca-silver/` and `artifacts/silver/na-silver/` for Retalix PI Invoice comparison workflow.
- [x] **tpm810SourceFF record_inventory** — `record_inventory` block added to `tpm810SourceFF_map.yaml` enumerating 7 record types (HDR, DTL, TP, D_HIST, SUM, INV_TR, FILE_TR) with expected field counts.

### Compare Rules Normalization

- [x] **amount_variance in all rules** — `amount_variance: null` field added to all classification entries in `810_invoice.yaml`, `bevager_810.yaml`, and other profiles. Normalizes rule schema so crosswalk overrides work uniformly.
- [x] **bevager_810.yaml GTIN → ignore** — GTIN field added with `severity: ignore`. Rules reformatted to flat YAML style matching all other profiles.

### Portal UI Improvements

- [x] **Compare.tsx split loading states** — `loading` split into `pairsLoading` and `diffsLoading` so pair list and diff panel have independent loading indicators.
- [x] **Compare.tsx empty state for filtered pairs** — Table body shows "No pairs match the current filter." row instead of empty tbody when `filteredPairs.length === 0`.
- [x] **Compare.tsx diffs panel always shown** — Diff section renders whenever a pair is selected (not just when `diffs.length > 0`). Header changed to "Diffs — Pair #{id}".
- [x] **Infographic themes testability** — `data-testid` attributes added to all nav and tip buttons in all 4 themes (RetroArcade, StickyNotes, Watercolor, Whiteboard). Connector decorators (SVG/span) marked `pointer-events-none` to prevent click interception.
- [x] **Playwright added as dev dependency** — `@playwright/test` + `playwright` v1.58.2 added to `portal/ui/package.json`.

### Documentation

- [x] **rulesApproach.MD** — New root-level document describing the 3-tier rules architecture (universal → transaction → partner), strengths, trade-offs, opportunities, and summary matrix.

## Completed (2026-03-27)

### XSD-Driven XML Import Pipeline (`364c66d`)

- [x] **XmlSchemaEntry config model** — `pyedi_core/config/__init__.py`. Mirrors `CsvSchemaEntry`. Fields: `source_xsd`, `compiled_output`, `inbound_dir`, `transaction_type`, `namespace`.
- [x] **XSD Compiler** — `parse_xsd_file()`, `_compile_xsd_to_yaml()`, `compile_xsd()` added to `schema_compiler.py`. Recursively walks xs:element tree, identifies transmission/header/line hierarchy, flattens nested elements to dot-notation paths. Same SHA-256 hash/archive/cache pattern as `compile_dsl()`.
- [x] **XMLHandler schema-aware parsing** — `set_compiled_yaml_path()`, `_strip_namespace()` (handles both Clark `{uri}Tag` and `prefix:Tag` notation), `_parse_schema_aware_xml()` (navigates xml_config paths, returns `{header, lines, summary}`), `write_split()` (writes one JSON per transaction keyed by header field).
- [x] **Pipeline XML registry routing** — `_resolve_xml_schema()` mirrors `_resolve_csv_schema()`. `.xml`/`.cxml` branch in `_process_single()` calls `compile_xsd()`, loads compiled map, sets compiled path on driver.
- [x] **`pyedi validate --xsd` command** — `--dsl` made optional, `--xsd` added. `validate_xsd()` in `validator.py` compiles XSD, returns `ValidationResult` with optional sample XML field tracing.
- [x] **Config: `xml_schema_registry`** — Two entries (darden_asbn_control, darden_asbn_test) in `config/config.yaml`.
- [x] **Config: `darden_asbn` compare profile** — `json_path: header.InvoiceNumber` match key, `config/compare_rules/darden_asbn.yaml` rules.
- [x] **Darden ASBN test artifacts** — `artifacts/darden/DardenInvoiceASBN.xsd` + 3 ca-source (control) + 3 na-source (test) XML invoices. na-source diffs: File 1 financial (InvoiceTotal/UnitPrice), File 2 case-only Description, File 3 extra line item.
- [x] **8 new tests** — `TestXsdCompiler` (3), `TestXmlHandler` (3), `TestValidateXsd` (2). Total: 205 passing.
- [x] **End-to-end compare verified** — 3 pairs matched by InvoiceNumber, correct hard/structural diffs detected, CSV exported to `reports/compare/compare_run_85.csv`.

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
- [ ] **Compare: "ignore" severity broader use** — `severity: ignore` added to `bevager_810.yaml` for GTIN. Consider applying to other profiles for date formatting diffs and envelope-only fields.
