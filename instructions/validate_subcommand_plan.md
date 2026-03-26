# Plan: `pyedi validate` — DSL Compilation, Bug Fixes & Mapping Verification

## Context

The schema compiler (`schema_compiler.py`) converts proprietary `.txt` DSL files into YAML map files consumed by the CSV driver. Today, compilation only happens **implicitly** during `pipeline.run()` — there is no way to compile a DSL, inspect the output, or verify mappings without wiring into `config.yaml` and running data through the full pipeline.

Additionally, the compiler has two known bugs that corrupt output for certain DSL files (notably `gfsGenericOut810FF.txt`).

**Goals:**
1. Fix compiler bugs (type loss + fieldIdentifier collision)
2. Add `pyedi validate` CLI subcommand for standalone DSL compilation, inspection, and mapping verification
3. Write compiled YAML to disk as part of validation
4. Show 3 rows of field trace by default when `--sample` is used

---

## Step 1: Fix compiler bugs in `schema_compiler.py`

**File:** `pyedi_core/core/schema_compiler.py`

### Bug 1: Type loss — Decimal/Integer fields compile as `string`

**Root cause:** In `_compile_to_yaml()` (lines 155-240), when `has_records=True`, every record's fields are appended to `schema.columns`. The deduplication at lines 233-240 keeps the **first occurrence** by name. If Header (all `String` fields) is parsed before Details (`Decimal`/`Integer` fields), the Header's `string` type wins for shared field names.

**Fix:** Change deduplication to prefer the **most specific type**. When a field appears in multiple records with different types, keep the non-string type (float, integer, date) over string. Concretely, replace the dedup block (lines 233-240) with logic that:
1. Groups columns by name
2. For each group, picks the type with highest specificity: `float` > `integer` > `date` > `boolean` > `string`

### Bug 2: fieldIdentifier collision — empty `records{}`

**Root cause:** In `_compile_to_yaml()` line 162, when a new record is processed, the code does:
```python
yaml_map["schema"]["records"][record_def["fieldIdentifier"]] = []
```
This **overwrites** any previous record with the same identifier value. When Header and Details both have `fieldIdentifier value = "0"`, only the last record's fields survive.

**Fix:** Change line 162 to **extend** instead of overwrite:
```python
fid = record_def["fieldIdentifier"]
if fid not in yaml_map["schema"]["records"]:
    yaml_map["schema"]["records"][fid] = []
```
And line 168 already appends, so it will accumulate fields from all records sharing that identifier.

**Note:** When multiple records share a fieldIdentifier, the CSV handler's manual parser (line 109 in csv_handler.py) uses `records[record_id]` to map columns by position. Merging field lists from different record types into one key makes positional mapping ambiguous. The fix should instead use **distinct keys per record** — e.g., store by record name (`Header`, `Details`) rather than by fieldIdentifier value when collisions exist. This preserves the positional mapping contract.

**Revised fix for Bug 2:** When fieldIdentifier values collide, fall back to using the **record name** as the key:
```python
fid = record_def.get("fieldIdentifier")
record_name = record_def["name"]
if fid and fid not in yaml_map["schema"]["records"]:
    yaml_map["schema"]["records"][fid] = []
    # ... append fields to records[fid]
elif fid:
    # Collision — use record name as key instead
    yaml_map["schema"]["records"][record_name] = []
    # ... append fields to records[record_name]
```

### Tests to verify fixes

- Recompile `gfsGenericOut810FF.txt` → verify `CaseSize` has `type: float`, `QuantityShort` has `type: integer`
- Recompile `gfsGenericOut810FF.txt` → verify `records` dict is non-empty with distinct keys per record type
- Existing tests in `test_core.py` (lines 284-395) must still pass

---

## Step 2: Extract `parse_dsl_file()` helper in `schema_compiler.py`

**File:** `pyedi_core/core/schema_compiler.py`

Extract lines 337-381 of `compile_dsl()` (read file → regex delimiter → brace-count records → parse each) into a new public function:

```python
def parse_dsl_file(source_file: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Parse a DSL file into record definitions and delimiter without writing any files.

    Args:
        source_file: Path to the .txt DSL file

    Returns:
        (record_definitions, delimiter)

    Raises:
        FileNotFoundError: If source file doesn't exist
        ValueError: If no valid records found
    """
```

Then refactor `compile_dsl()` to call `parse_dsl_file()` — replacing lines 337-381 with:
```python
record_defs, delimiter = parse_dsl_file(str(source_path))
yaml_map = _compile_to_yaml(record_defs, source_filename, delimiter)
```

No behavior change to `compile_dsl()`. ~20 lines added, ~15 lines replaced.

---

## Step 3: Create `pyedi_core/validator.py` (new file, ~280 lines)

All validation logic — compile, inspect, trace, report. Pure functions returning typed dataclasses.

### Data structures

```python
@dataclass
class ColumnInfo:
    name: str
    compiled_type: str
    dsl_type: Optional[str]       # original DSL type (e.g., "Decimal")
    record_name: str              # which DSL record this came from
    type_preserved: bool

@dataclass
class TypeWarning:
    field_name: str
    record_name: str
    dsl_type: str
    compiled_type: str

@dataclass
class FieldTrace:
    target_field: str
    source_path: str
    value: Any
    mapped: bool

@dataclass
class CoverageReport:
    source_fields_total: int
    source_fields_mapped: int
    source_fields_unmapped: List[str]
    target_fields_total: int
    target_fields_populated: int
    target_fields_empty: List[str]
    coverage_pct: float

@dataclass
class ValidationResult:
    dsl_path: str
    compiled_yaml: Dict[str, Any]
    compiled_yaml_path: Optional[str]   # path where YAML was written
    columns: List[ColumnInfo]
    records: Dict[str, List[str]]
    type_warnings: List[TypeWarning]
    compilation_warnings: List[str]
    field_traces: Optional[List[List[FieldTrace]]]  # first 3 rows
    coverage: Optional[CoverageReport]
    sample_row_count: Optional[int]
    sample_errors: List[str]
```

### Key functions

| Function | Reuses |
|---|---|
| `validate(dsl_path, sample_path=None, compiled_dir=...) -> ValidationResult` | Top-level orchestrator |
| `compile_and_write(dsl_path, compiled_dir) -> (compiled_yaml, yaml_path, record_defs)` | `schema_compiler.parse_dsl_file()`, `schema_compiler._compile_to_yaml()`, writes YAML + meta.json to disk |
| `check_type_preservation(record_defs, compiled_yaml) -> List[TypeWarning]` | Compares DSL types vs compiled types |
| `check_compilation_warnings(record_defs) -> List[str]` | Detects fieldIdentifier collisions, empty records, etc. |
| `run_sample(compiled_yaml, compiled_yaml_path, sample_path) -> (raw_data, mapped_data)` | `CSVHandler.read()` via `set_compiled_yaml_path()`, `mapper.map_data()` |
| `compute_coverage(raw_data, mapped_data, compiled_yaml) -> CoverageReport` | — |
| `compute_field_traces(raw_data, mapped_data, compiled_yaml, max_rows=3) -> List[List[FieldTrace]]` | — |

### `compile_and_write` detail

This replaces the "no side effects" approach. It:
1. Calls `parse_dsl_file()` to get record_defs + delimiter
2. Calls `_compile_to_yaml()` to get the YAML dict
3. Writes YAML to `{compiled_dir}/{stem}_map.yaml` using `yaml.dump()`
4. Writes `.meta.json` sidecar with source hash
5. Returns `(compiled_yaml, yaml_path, record_defs)`

### `run_sample` detail

Uses the already-written compiled YAML path (from `compile_and_write`). Instantiates `CSVHandler()`, calls `set_compiled_yaml_path(yaml_path)`, then `handler.read(sample_path)`, then `mapper.map_data(raw_data, compiled_yaml)`. No temp files needed since we're writing to disk anyway.

---

## Step 4: Add `validate` subcommand to `main.py`

**File:** `pyedi_core/main.py`

### CLI interface

```
pyedi validate --dsl path/to/schema.txt                       # compile + inspect
pyedi validate --dsl path/to/schema.txt --sample data.csv     # + test against sample
pyedi validate --dsl path/to/schema.txt --json                # machine-readable output
pyedi validate --dsl path/to/schema.txt --verbose             # full field traces
pyedi validate --dsl path/to/schema.txt --output-dir ./out    # custom compiled output dir
```

### Changes

1. Add `validate` subparser after `test_parser` (~15 lines):
   - `--dsl` (required) — path to DSL .txt file
   - `--sample` — path to sample data file
   - `--json` — JSON output flag
   - `--verbose` / `-v` — show all field traces (not just 3 rows)
   - `--output-dir` — compiled YAML output directory (default: `./schemas/compiled`)

2. Add dispatch in `main()`: `if parsed.command == "validate": return _handle_validate(parsed)`

3. Add `_handle_validate(parsed)` (~20 lines)

4. Add `_print_validate_report(result, verbose)` (~70 lines) — console output:

```
=== DSL Compilation Report ===
Source:           path/to/schema.txt
Compiled To:      ./schemas/compiled/tpm810SourceFF_map.yaml
Transaction Type: 810_INVOICE
Delimiter:        "|"
Records Found:    3 (Header, Detail, FileTrailer)

=== Schema Columns (45 fields) ===
  Name                       Type      DSL Type    OK?
  RecordId                   string    String      YES
  HDRInvoiceTotalNetAmount   float     Decimal     YES
  DTLOrderQuantity           float     Decimal     YES

=== Type Preservation ===
  All types preserved correctly.
  (or: 12 warnings — use --verbose for full list)

=== Record Definitions ===
  HDR -> 25 fields [RecordId, HDRInvoiceNumber, ...]
  DTL -> 18 fields [RecordId, DTLDistributorItemNumber, ...]

=== Sample File: data.txt (47 rows parsed) ===

=== Mapping Coverage ===
  Source fields: 45 total, 41 mapped, 4 unmapped
  Target fields: 45 total, 41 populated, 4 empty
  Coverage: 91.1%

  Unmapped: [ReservedField1, ReservedField2, ...]
  Empty:    [discount_code, tax_amount, ...]

=== Field Trace (first 3 rows) ===
  Row 1 (HDR):
    RecordId         <- RecordId         = "HDR"
    HDRInvoiceNumber <- HDRInvoiceNumber = "INV-001"
```

5. Add `_print_validate_json(result)` (~10 lines) — JSON serialization via `dataclasses.asdict()`.

~115 lines added to main.py.

---

## Step 5: Add tests

**File:** `tests/test_validator.py` (new, ~120 lines)

| Test | What it verifies |
|---|---|
| `test_compile_and_write_produces_yaml` | DSL compiles to valid YAML dict with schema + mapping sections; file written to disk |
| `test_type_preservation_correct_tpm` | tpm810SourceFF.txt: Decimal→float, Integer→integer preserved |
| `test_type_preservation_fixed_gfs` | gfsGenericOut810FF.txt: Decimal→float after bug fix (was string) |
| `test_fieldidentifier_collision_handled` | gfsGenericOut810FF.txt: records{} is non-empty after bug fix |
| `test_run_sample_produces_traces` | DSL + sample file → field_traces has 3 rows |
| `test_coverage_report_counts` | Coverage percentages and unmapped field lists correct |
| `test_validate_missing_dsl` | FileNotFoundError for nonexistent DSL |
| `test_validate_json_serializable` | ValidationResult round-trips through JSON |
| `test_existing_compiled_schemas_unchanged` | Regression: recompile both DSLs, compare against existing expected outputs |

---

## Step 6: Update `__init__.py` exports

**File:** `pyedi_core/__init__.py`

Add `from .validator import validate` to public API.

---

## Files Changed Summary

| File | Action | Est. Lines |
|---|---|---|
| `pyedi_core/core/schema_compiler.py` | Fix 2 bugs + extract `parse_dsl_file()` | ~50 changed/added |
| `pyedi_core/validator.py` | **NEW** — validation logic | ~280 |
| `pyedi_core/main.py` | Add `validate` subparser + handler + formatters | ~115 |
| `pyedi_core/__init__.py` | Add validator export | ~2 |
| `tests/test_validator.py` | **NEW** — unit + integration tests | ~120 |

## Execution Order

1. **Step 1** first (compiler fixes) — everything downstream depends on correct compilation
2. **Step 2** (extract helper) — validator needs `parse_dsl_file()`
3. **Step 3** (validator.py) — core logic
4. **Step 4** (main.py) — CLI wiring
5. **Step 5** (tests) — verify everything
6. **Step 6** (exports) — cleanup

## Verification

1. `pytest tests/test_core.py -v` — existing compiler tests still pass
2. `pytest tests/test_validator.py -v` — new tests pass
3. `pytest` — all 143+ tests pass (no regressions)
4. `pyedi validate --dsl tpm810SourceFF.txt` — report shows correct types, HDR/DTL records
5. `pyedi validate --dsl schemas/source/gfsGenericOut810FF.txt` — report shows Decimal→float (fixed), non-empty records{}
6. `pyedi validate --dsl tpm810SourceFF.txt --sample tests/user_supplied/inputs/NA_810_MARGINEDGE_20260129.txt` — shows 3-row field trace + coverage stats
7. `pyedi validate --dsl tpm810SourceFF.txt --json` — valid JSON output
