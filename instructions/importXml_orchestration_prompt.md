# Orchestration Prompt: Import XML Pipeline

## Role
You are a precise Python engineer implementing XSD-based XML processing in pycoreEdi. Execute the task list in `instructions/importXml.md` sequentially. Follow pycoreEdi's CLAUDE.md coding standards strictly.

## Pre-Flight
1. Read `instructions/importXml.md` completely
2. Read `instructions/ffPostImplement.md` for lessons learned from the fixed-width implementation
3. Read `CLAUDE.md` for coding standards
4. Run `python -m pytest tests/ -v` to capture baseline test count

## Execution Rules
- **One task at a time.** Complete each task, verify it, then move to the next.
- **Read before write.** Always read the target file before modifying it.
- **Minimal diffs.** Change only what is necessary. Do not refactor, rename, or add comments to code you didn't write.
- **Match existing patterns.** The XSD compiler functions must mirror the structure and style of existing DSL compiler functions. The XML registry routing must mirror `_resolve_csv_schema` exactly.
- **No speculative fixes.** Only write code you can explain precisely.
- **Type hints on all functions.** Catch specific exceptions, never bare `except`.
- **ASCII-safe output.** No Unicode characters in console-printed strings (lesson from ffPostImplement Issue 3).
- **Verify after each task.** Run the verification command specified in the task. If it fails, fix before proceeding.

## Task Execution Order

### Task 0: Test Diffs
- Edit the 3 na-source XML files per the task spec
- Verify: `diff artifacts/darden/ca-source/ artifacts/darden/na-source/` shows diffs

### Task 1: Config Model
- Add XmlSchemaEntry to `pyedi_core/config/__init__.py`
- Verify: `python -m pytest tests/ -v` — all existing tests still pass

### Task 2: XSD Compiler
- Add `parse_xsd_file`, `_compile_xsd_to_yaml`, `compile_xsd` to `pyedi_core/core/schema_compiler.py`
- Use `defusedxml.ElementTree` (already a dependency — used in xml_handler.py)
- Follow the hash-check/archive pattern from existing `compile_dsl()`
- Verify: Run the inline Python test from the task spec

### Task 3: XML Handler
- Add schema-aware parsing to `pyedi_core/drivers/xml_handler.py`
- Namespace stripping: handle both `{uri}tag` and `prefix:tag` patterns
- Multi-ASBN support: detect multiple transaction elements, return list
- Verify: Run the inline Python test from the task spec

### Task 4: Pipeline Routing
- Add XML branch to `pyedi_core/pipeline.py`
- Verify: `python -m pyedi_core run --file ./artifacts/darden/ca-source/ASBN20260322T233555600_HS00.XML --dry-run --return-payload`

### Task 5: Validate Command
- Add `--xsd` flag to `pyedi_core/main.py`
- Add `validate_xsd()` to `pyedi_core/validator.py`
- Verify: `python -m pyedi_core validate --xsd ./artifacts/darden/DardenInvoiceASBN.xsd --verbose`

### Task 6: Config + Rules
- Add xml_schema_registry and compare profile to `config/config.yaml`
- Create `config/compare_rules/darden_asbn.yaml`
- Verify: Config loads without error

### Task 7: Onboard Wizard (lower priority)
- Extend `portal/api/routes/onboard.py` for XSD
- Extend wizard UI if time permits

### Task 8: Tests
- Add XSD/XML tests to existing test files
- Verify: `python -m pytest tests/ -v` — all pass

## End-to-End Compare Testing Process

After all tasks complete, execute the 7-phase testing process from `importXml.md`:

1. **Schema Compilation** — validate --xsd
2. **Single File Pipeline** — run --file --dry-run --return-payload
3. **Batch Processing** — run all 6 files (3 control + 3 test)
4. **JSON Structure Verification** — Python script to check header/lines
5. **Compare Run** — compare --profile darden_asbn --verbose --export-csv
6. **Regression** — pytest all tests
7. **Idempotency** — re-validate, confirm cache hit

**Critical compare assertions:**
- 3 pairs matched by InvoiceNumber
- Pair 1: hard diffs (InvoiceTotal, UnitPrice changed)
- Pair 2: soft diff (Description changed)
- Pair 3: structural diff (extra line item)
- No "unknown" or unmatched pairs
- CSV report generated

## If Blocked
- If XSD parsing hits unsupported features: raise clear `ValueError("XSD feature not supported: {feature}")` and document
- If namespace stripping fails: test with actual XML bytes, check both Clark `{uri}` and prefix patterns
- If pipeline can't find XML file in registry: check `inbound_dir` path resolution (use `Path().resolve()`)
- If compare shows 0 pairs: verify JSON files have `header.InvoiceNumber` populated and match_key path is correct
- If manifest blocks re-processing: delete `.processed` file or use `--dry-run`

## Definition of Done
- [ ] All 3 na-source files have intentional diffs vs ca-source
- [ ] XSD compiles to YAML with correct xml_config, columns, mapping
- [ ] XML files process through pipeline to correct JSON output
- [ ] Validate --xsd command works with and without --sample
- [ ] Compare produces 3 matched pairs with expected diff types
- [ ] All existing tests pass + new XSD/XML tests added
- [ ] Config is data-driven — zero hardcoded business logic
