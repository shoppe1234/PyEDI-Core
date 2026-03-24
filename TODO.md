# TODO

## Completed (2026-03-24)

- [x] **Fix compiler type loss bug** — `_compile_to_yaml()` dedup now prefers the most specific type (`float` > `integer` > `date` > `boolean` > `string`) instead of keeping the first occurrence.
- [x] **Fix compiler fieldIdentifier collision** — When multiple DSL records share the same `fieldIdentifier` value, the compiler now uses the record name as a fallback key to preserve distinct column lists.
- [x] **Extract `parse_dsl_file()` helper** — Public function in `schema_compiler.py` for parsing DSL files without triggering file writes. Used by both `compile_dsl()` and the validator.
- [x] **Create `pyedi_core/validator.py`** — Standalone module for DSL compilation, type preservation checks, sample-file mapping trace, and coverage analysis.
- [x] **Add `pyedi validate` CLI subcommand** — `--dsl`, `--sample`, `--json`, `--verbose`, `--output-dir` flags. Human-readable report and JSON output modes.
- [x] **Add validator tests** — 9 unit + integration tests in `tests/test_validator.py`.
- [x] **Build PyEDI Portal (FastAPI backend)** — `portal/api/` with health, validate, pipeline, test, manifest, and config endpoints. 7 API integration tests.
- [x] **Build PyEDI Portal (React frontend)** — `portal/ui/` with Vite + React + TypeScript + Tailwind CSS. Dashboard, Validate, Pipeline, Tests, and Config pages. Static build served by FastAPI.

## Open

### Medium Priority

- [ ] **Add `react-router-dom` routing** — Replace manual page state in `App.tsx` with proper URL-based routing (`/validate`, `/pipeline`, `/test`, `/config`). Enables browser back/forward and deep linking.
- [ ] **Portal: file upload on Pipeline page** — Wire the `POST /api/pipeline/upload` endpoint to a drag-and-drop upload component on the Pipeline page.
- [ ] **Portal: Manifest page** — Add a dedicated `/manifest` page with search, status filter, and pagination (API endpoints already exist).

### Low Priority

- [ ] **Standardize YAML quoting conventions** — 11 YAML files use mixed quoting styles (single, double, unquoted). Proposed convention: single quotes for numeric-looking strings/delimiters, no quotes for plain strings, double quotes only for escapes. Requires before/after `yaml.safe_load()` comparison per file to avoid type-coercion breakage. See `instructions/tier3_tier4_remaining_tasks.md` Task 4 for full details.
- [ ] **Portal: authentication** — Add basic auth or API key middleware to the portal API before exposing outside localhost.
- [ ] **Portal: config editing UI** — The `PUT /api/config/registry/{entry_name}` endpoint exists but the frontend Config page is read-only. Add inline editing for csv_schema_registry entries.
