# Fixed-Width DSL Support — Orchestration Prompt

**Purpose:** Add end-to-end support for fixed-width (positional) `.ffSchema` DSL files. The schema compiler will parse field `length` attributes, emit width metadata and per-record byte layouts in compiled YAML, and the CSV handler will gain a positional slicing parser. The onboarding wizard will display width metadata for imported fixed-width schemas.

**Example DSL:** `artifacts/RetalixPIPOAckFF.ffSchema`
**Coding standards:** `CLAUDE.md`
**Schema compiler:** `pyedi_core/core/schema_compiler.py`
**CSV handler:** `pyedi_core/drivers/csv_handler.py`
**Validator:** `pyedi_core/validator.py`
**Portal API models:** `portal/api/models.py`
**Portal validate routes:** `portal/api/routes/validate.py`
**Wizard UI:** `portal/ui/src/pages/Onboard.tsx`

---

## Key Design Decisions

1. **No delimiters in fixed-width files.** The `delimiter = "|"` in the `.ffSchema` example is a false positive. Fixed-width data files have NO delimiters — fields are extracted purely by byte position using cumulative `length` offsets.

2. **Format auto-detection.** If any field in the DSL has a `length` attribute, `input_format` is set to `"FIXED_WIDTH"`. Otherwise it remains `"CSV"`.

3. **`record_layouts` section.** The compiled YAML gains a `schema.record_layouts` section that preserves per-record field order with widths. This is essential for positional parsing — the reader needs to know byte offsets per record type.

4. **Strip `fieldIdentifier` values.** Padded identifiers like `"OPA_HDRA   "` are stripped to `"OPA_HDRA"` during compilation. The reader also strips the record ID field before lookup.

5. **Wizard: import only.** The onboarding wizard accepts `.ffSchema` file uploads and displays width metadata. No UI for authoring widths from scratch.

---

## Rules of Engagement

1. **Sequential within phases** — complete each task fully (including its test gate) before starting the next.
2. **Phase gates are hard stops** — do not start a phase until the prior phase gate passes.
3. **Read before writing** — always read the target file and its imports before making any change.
4. **Minimal diffs** — change only what the task requires. No drive-by fixes, no extra comments.
5. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
6. **Stop on red** — if any test gate fails, diagnose and fix before proceeding.
7. **Match existing patterns** — follow conventions in the codebase exactly.
8. **Backward compatible** — existing delimited DSL files must compile identically. No `width`, no `record_layouts`, `input_format: CSV`.

---

## Pre-Flight

Before starting any task, verify the development environment:

```bash
cd ~/VS/pycoreEdi

# Verify clean baseline — all existing tests must pass
python -m pytest tests/ -v --tb=short 2>&1 | tail -20

# Capture baseline test count
python -m pytest tests/ -v --tb=short 2>&1 | grep -E "passed|failed|error"

# Verify the .ffSchema example exists
cat artifacts/RetalixPIPOAckFF.ffSchema | head -30

# Verify current compilation of the .ffSchema (should already work, just no width metadata)
python -c "
from pyedi_core.core.schema_compiler import compile_dsl
result = compile_dsl('artifacts/RetalixPIPOAckFF.ffSchema')
print(f'input_format: {result[\"input_format\"]}')
print(f'columns: {len(result[\"schema\"][\"columns\"])}')
print(f'records: {list(result[\"schema\"][\"records\"].keys())[:3]}...')
# Should show input_format: CSV (the bug we're fixing)
# Should show padded keys like 'OPA_HDRA   ' (will be stripped)
"
```

If any tests fail at baseline, **stop and fix them first**.

---

# PHASE 1: Schema Compiler — Parse Field Attributes

> **Prerequisite:** Pre-flight green.
> **Deliverables:** `_parse_dsl_record()` extracts `length` and `readEmptyAsNull` from parenthesized field blocks.

---

## Task 1.1 — Parse parenthesized field attributes in `_parse_dsl_record()`

**Investigate:**
```bash
# Read the target function — focus on lines 48-118
cat pyedi_core/core/schema_compiler.py

# Read the .ffSchema to understand the attribute syntax
cat artifacts/RetalixPIPOAckFF.ffSchema | head -70
```

**Current behavior:** The field regex on line 87-89 matches `fieldName Type` (e.g., `recordType String`). The optional parenthesized block that follows (e.g., `(length = 10, maxLength = 10, ...)`) is completely ignored.

**What to change in `_parse_dsl_record()` (lines 48-118):**

After the existing `field_pattern.finditer()` loop (line 91), for each matched field:

1. Starting from `match.end()`, scan forward in `record_text` skipping whitespace.
2. If the next non-whitespace character is `(`, find the matching `)` using a simple character scan (no nesting in this DSL).
3. Extract the content between `(` and `)`.
4. Parse key-value pairs using a regex like `(\w+)\s*=\s*(\w+|"[^"]*")`.
5. Add to `field_def`:
   - `field_def["length"]` = `int(value)` if key is `"length"`
   - `field_def["read_empty_as_null"]` = `True` if key is `"readEmptyAsNull"` and value is `"true"`

Do NOT extract `maxLength` or `minLength` — they are redundant with `length` in this DSL.

**Also strip `fieldIdentifier` values.** On line 80, change:
```python
result["fieldIdentifier"] = identifier_match.group(1)
```
to:
```python
result["fieldIdentifier"] = identifier_match.group(1).strip()
```

**Test Gate:**
```bash
# Verify field attributes are now parsed
python -c "
from pyedi_core.core.schema_compiler import parse_dsl_file
record_defs, delimiter = parse_dsl_file('artifacts/RetalixPIPOAckFF.ffSchema')

# Check first record (OTpid)
otpid = record_defs[0]
print(f'Record: {otpid[\"name\"]}')
print(f'fieldIdentifier: \"{otpid[\"fieldIdentifier\"]}\" (should be stripped)')
assert otpid['fieldIdentifier'] == 'O_TPID', f'Expected O_TPID, got \"{otpid[\"fieldIdentifier\"]}\"'

# Check field attributes
rt_field = otpid['fields'][0]
print(f'Field: {rt_field[\"name\"]}, type: {rt_field[\"type\"]}, length: {rt_field.get(\"length\")}')
assert rt_field['length'] == 10, f'Expected length=10, got {rt_field.get(\"length\")}'
assert rt_field.get('read_empty_as_null') == True, 'Expected read_empty_as_null=True'

tpid_field = otpid['fields'][1]
assert tpid_field['length'] == 20, f'Expected length=20, got {tpid_field.get(\"length\")}'

# Check a record with padded identifier (OpaHdra had 'OPA_HDRA   ')
opa_hdra = record_defs[1]
assert opa_hdra['fieldIdentifier'] == 'OPA_HDRA', f'Expected OPA_HDRA, got \"{opa_hdra[\"fieldIdentifier\"]}\"'

print('ALL ATTRIBUTE PARSING CHECKS PASSED')
"

# Verify existing delimited DSL still works (no length attributes)
python -c "
from pyedi_core.core.schema_compiler import parse_dsl_file
record_defs, delimiter = parse_dsl_file('schemas/source/gfsGenericOut810FF.txt')
for rec in record_defs:
    for fld in rec['fields']:
        assert 'length' not in fld or fld['length'] is None, f'{fld[\"name\"]} should not have length'
print(f'Delimited DSL: {len(record_defs)} records, no length attributes — BACKWARD COMPAT OK')
"

# Full suite
python -m pytest tests/ -v --tb=short
```

**Commit:** `feat(compiler): parse length and readEmptyAsNull from DSL field attributes`

---

# PHASE 2: Schema Compiler — Emit Width Metadata in Compiled YAML

> **Prerequisite:** Phase 1 green.
> **Deliverables:** `parse_dsl_file()` returns format_type, `_compile_to_yaml()` emits `width`, `read_empty_as_null`, `record_layouts`, and correct `input_format`.

---

## Task 2.1 — Add `format_type` to `parse_dsl_file()` return value

**Investigate:**
```bash
# Find all callers of parse_dsl_file()
grep -rn "parse_dsl_file" pyedi_core/ tests/
# Expected callers:
#   pyedi_core/core/schema_compiler.py:409  — compile_dsl()
#   pyedi_core/validator.py:130             — compile_and_write()
#   tests/test_validator.py:67              — test_check_compilation_warnings_collision
```

**What to change in `parse_dsl_file()` (line 254):**

1. Update return type from `Tuple[List[Dict[str, Any]], str]` to `Tuple[List[Dict[str, Any]], str, str]`.
2. After parsing all records (line 313), detect format type:
   ```python
   has_lengths = any(
       fld.get("length") is not None
       for rec in record_defs
       for fld in rec.get("fields", [])
   )
   format_type = "FIXED_WIDTH" if has_lengths else "CSV"
   ```
3. Return `record_defs, delimiter, format_type`.
4. Update docstring to reflect the new return value.

**What to change in `compile_dsl()` (line 409):**
```python
# Change from:
record_defs, delimiter = parse_dsl_file(source_file)
# To:
record_defs, delimiter, format_type = parse_dsl_file(source_file)
```

Pass `format_type` to `_compile_to_yaml()` (see Task 2.2).

**Test Gate:**
```bash
# Verify the new return value
python -c "
from pyedi_core.core.schema_compiler import parse_dsl_file
# Fixed-width
defs, delim, fmt = parse_dsl_file('artifacts/RetalixPIPOAckFF.ffSchema')
assert fmt == 'FIXED_WIDTH', f'Expected FIXED_WIDTH, got {fmt}'
print(f'ffSchema: format_type={fmt}')

# Delimited
defs, delim, fmt = parse_dsl_file('schemas/source/gfsGenericOut810FF.txt')
assert fmt == 'CSV', f'Expected CSV, got {fmt}'
print(f'Delimited: format_type={fmt}')
print('FORMAT DETECTION OK')
"
```

**Do NOT commit yet** — complete Task 2.2 first (they must ship together).

---

## Task 2.2 — Emit `width`, `read_empty_as_null`, and `record_layouts` in `_compile_to_yaml()`

**What to change in `_compile_to_yaml()` (line 121):**

1. **Function signature** — add parameter `format_type: str = "CSV"`:
   ```python
   def _compile_to_yaml(record_defs: List[Dict], source_filename: str, delimiter: str = ",", format_type: str = "CSV") -> Dict[str, Any]:
   ```

2. **Set `input_format`** (line 143) — change from hardcoded `"CSV"` to `format_type`.

3. **Conditionally omit `delimiter`** — when `format_type == "FIXED_WIDTH"`, do not include `delimiter` in `schema`. Change line 145:
   ```python
   schema_section = {"columns": [], "records": {}}
   if format_type != "FIXED_WIDTH":
       schema_section["delimiter"] = delimiter
   ```

4. **Add `record_layouts`** — initialize an empty dict in `schema`:
   ```python
   if format_type == "FIXED_WIDTH":
       schema_section["record_layouts"] = {}
   ```

5. **Include `width` and `read_empty_as_null` on column entries** — in all 4 places where `yaml_map["schema"]["columns"].append(...)` is called (lines 191, 201, 218, 230), build the column entry with optional attributes:
   ```python
   col_entry = {
       "name": field_name,
       "type": field.get("type", "string"),
       "required": field.get("required", True),
   }
   if field.get("length") is not None:
       col_entry["width"] = field["length"]
   if field.get("read_empty_as_null"):
       col_entry["read_empty_as_null"] = True
   yaml_map["schema"]["columns"].append(col_entry)
   ```

6. **Populate `record_layouts`** — inside the `if "fieldIdentifier" in record_def:` block (line 162), when `format_type == "FIXED_WIDTH"`, also build the layout entry:
   ```python
   if format_type == "FIXED_WIDTH" and "fieldIdentifier" in record_def:
       layout = []
       for field in record_def.get("fields", []):
           entry = {"name": field["name"], "width": field.get("length", 0)}
           layout.append(entry)
       yaml_map["schema"]["record_layouts"][record_key] = layout
   ```

7. **Dedup logic** (lines 238-249) — preserve `width` and `read_empty_as_null` during dedup. When merging, keep the non-None width:
   ```python
   if name not in seen:
       seen[name] = col
   else:
       existing_rank = type_specificity.get(seen[name]["type"], 0)
       new_rank = type_specificity.get(col["type"], 0)
       if new_rank > existing_rank:
           seen[name] = col
       # Preserve width from whichever has it
       if col.get("width") and not seen[name].get("width"):
           seen[name]["width"] = col["width"]
       if col.get("read_empty_as_null") and not seen[name].get("read_empty_as_null"):
           seen[name]["read_empty_as_null"] = col["read_empty_as_null"]
   ```

8. **Update the call site in `compile_dsl()`** (line 412):
   ```python
   yaml_map = _compile_to_yaml(record_defs, source_filename, delimiter, format_type)
   ```

**Test Gate:**
```bash
# Compile the .ffSchema and verify output structure
python -c "
from pyedi_core.core.schema_compiler import compile_dsl
import yaml, os

# Remove any cached compiled version first
for f in ['schemas/compiled/RetalixPIPOAckFF_map.yaml', 'schemas/compiled/RetalixPIPOAckFF_map.meta.json']:
    if os.path.exists(f): os.remove(f)

result = compile_dsl('artifacts/RetalixPIPOAckFF.ffSchema')

# 1. input_format should be FIXED_WIDTH
assert result['input_format'] == 'FIXED_WIDTH', f'Got {result[\"input_format\"]}'
print(f'input_format: {result[\"input_format\"]}')

# 2. No delimiter key in schema
assert 'delimiter' not in result['schema'], 'delimiter should not be present for FIXED_WIDTH'
print('No delimiter in schema: OK')

# 3. Columns have width
cols_with_width = [c for c in result['schema']['columns'] if 'width' in c]
print(f'Columns with width: {len(cols_with_width)} / {len(result[\"schema\"][\"columns\"])}')
assert len(cols_with_width) == len(result['schema']['columns']), 'All columns should have width'

# 4. record_layouts exists and has entries
layouts = result['schema'].get('record_layouts', {})
print(f'record_layouts: {list(layouts.keys())[:3]}...')
assert len(layouts) > 0, 'record_layouts should not be empty'

# 5. Keys are stripped (no padding)
for key in result['schema']['records']:
    assert key == key.strip(), f'Record key \"{key}\" has padding'
print('Record keys stripped: OK')

# 6. Verify a specific layout
opa_hdra_layout = layouts.get('OPA_HDRA', [])
assert len(opa_hdra_layout) == 6, f'OPA_HDRA should have 6 fields, got {len(opa_hdra_layout)}'
assert opa_hdra_layout[0] == {'name': 'recordType', 'width': 10}
assert opa_hdra_layout[1] == {'name': 'companyNumber', 'width': 3}
print(f'OPA_HDRA layout verified: {len(opa_hdra_layout)} fields')

print('ALL COMPILED YAML CHECKS PASSED')
"

# Verify backward compatibility with delimited DSL
python -c "
from pyedi_core.core.schema_compiler import compile_dsl
import os

for f in ['schemas/compiled/gfs_ca_810_map.yaml', 'schemas/compiled/gfs_ca_810_map.meta.json']:
    if os.path.exists(f): os.remove(f)

result = compile_dsl('schemas/source/gfsGenericOut810FF.txt', target_yaml_path='schemas/compiled/gfs_ca_810_map.yaml')
assert result['input_format'] == 'CSV', f'Got {result[\"input_format\"]}'
assert 'delimiter' in result['schema'], 'delimiter should be present for CSV'
assert 'record_layouts' not in result['schema'], 'record_layouts should not be present for CSV'
cols_with_width = [c for c in result['schema']['columns'] if 'width' in c]
assert len(cols_with_width) == 0, f'{len(cols_with_width)} columns have width — should be 0'
print('BACKWARD COMPATIBILITY OK')
"

# Full suite
python -m pytest tests/ -v --tb=short
```

**Commit:** `feat(compiler): emit width metadata and record_layouts for fixed-width schemas`

---

## Task 2.3 — Update callers of `parse_dsl_file()` for 3-value return

**Investigate:**
```bash
# Callers to update:
grep -n "parse_dsl_file" pyedi_core/validator.py tests/test_validator.py
```

**What to change:**

1. **`pyedi_core/validator.py` line 130:**
   ```python
   # Change from:
   record_defs, delimiter = parse_dsl_file(dsl_path)
   # To:
   record_defs, delimiter, format_type = parse_dsl_file(dsl_path)
   ```

2. **`pyedi_core/validator.py` line 133:**
   ```python
   # Change from:
   compiled_yaml = _compile_to_yaml(record_defs, source_path.name, delimiter)
   # To:
   compiled_yaml = _compile_to_yaml(record_defs, source_path.name, delimiter, format_type)
   ```

3. **`tests/test_validator.py` line 67:**
   ```python
   # Change from:
   record_defs, _ = parse_dsl_file("schemas/source/gfsGenericOut810FF.txt")
   # To:
   record_defs, _, _ = parse_dsl_file("schemas/source/gfsGenericOut810FF.txt")
   ```

**Test Gate:**
```bash
# Full suite — this is the critical backward-compat check
python -m pytest tests/ -v --tb=short

# Verify validator works with .ffSchema
python -m pycoreedi validate --dsl artifacts/RetalixPIPOAckFF.ffSchema --verbose 2>&1 | head -30
```

**Commit:** `fix(validator): update parse_dsl_file callers for 3-value return`

---

# PHASE 3: CSV Handler — Fixed-Width Reader

> **Prerequisite:** Phase 2 green.
> **Deliverables:** `CSVHandler` gains `_read_fixed_width()` method for positional parsing.

---

## Task 3.1 — Add `_read_fixed_width()` method to CSVHandler

**Investigate:**
```bash
# Read csv_handler.py — focus on the read() method and existing multi-record parsing
cat pyedi_core/drivers/csv_handler.py
```

**What to add in `CSVHandler` class (after `_detect_delimiter()`, before `read()`):**

New private method `_read_fixed_width(self, file_path: str, schema: Dict[str, Any]) -> Dict[str, Any]`:

```python
def _read_fixed_width(self, file_path: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a fixed-width positional file using record_layouts from compiled schema."""
    record_layouts = schema.get("schema", {}).get("record_layouts", {})
    columns_meta = {
        c["name"]: c
        for c in schema.get("schema", {}).get("columns", [])
    }

    if not record_layouts:
        raise ValueError(f"No record_layouts in schema for fixed-width file: {file_path}")

    # Build a quick lookup: determine the width of the record identifier field
    # (first field in every layout — always 'recordType' in this DSL)
    # Find the max width of the first field across all layouts to read the record ID
    id_width = max(
        layout[0]["width"] for layout in record_layouts.values() if layout
    )

    result: Dict[str, Any] = {"header": {}, "lines": [], "summary": {}}

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n\r")
            if not line:
                continue

            # Extract record identifier from the first id_width characters
            record_id = line[:id_width].strip()

            if record_id not in record_layouts:
                self.logger.debug(f"Unknown record type: '{record_id}', skipping line")
                continue

            layout = record_layouts[record_id]
            row: Dict[str, Any] = {}
            pos = 0

            for field_spec in layout:
                field_name = field_spec["name"]
                width = field_spec["width"]
                raw = line[pos:pos + width]

                # Strip padding
                value = raw.strip()

                # Handle read_empty_as_null
                col_meta = columns_meta.get(field_name, {})
                if col_meta.get("read_empty_as_null") and not value:
                    value = None

                row[field_name] = value
                pos += width

            result["lines"].append(row)

    self.logger.info(
        f"Fixed-width file parsed",
        lines=len(result["lines"]),
        file_path=file_path,
    )
    return result
```

**What to change in `read()` method (after line 111):**

Insert a conditional check before the existing `if records_schema:` branch:

```python
# After line 111: records_schema = schema.get("schema", {}).get("records", {}) if schema else {}
input_format = schema.get("input_format", "CSV") if schema else "CSV"
if input_format == "FIXED_WIDTH":
    return self._read_fixed_width(file_path, schema)

# Existing code continues: if records_schema: ...
```

**Test Gate:**
```bash
# Create a synthetic fixed-width test file and verify parsing
python -c "
import tempfile, os, yaml
from pyedi_core.drivers.csv_handler import CSVHandler

# Create a synthetic fixed-width data file
# Record layout: recordType(10) + value1(5) + value2(3)
lines = [
    'HDR       Hello  42',
    'DTL       World  99',
    'DTL       Test  100',
]
tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
tmp.write('\n'.join(lines))
tmp.close()

# Create a matching schema
schema = {
    'transaction_type': 'TEST',
    'input_format': 'FIXED_WIDTH',
    'schema': {
        'columns': [
            {'name': 'recordType', 'type': 'string', 'required': True, 'width': 10, 'read_empty_as_null': True},
            {'name': 'value1', 'type': 'string', 'required': True, 'width': 5},
            {'name': 'value2', 'type': 'integer', 'required': True, 'width': 3},
        ],
        'records': {
            'HDR': ['recordType', 'value1', 'value2'],
            'DTL': ['recordType', 'value1', 'value2'],
        },
        'record_layouts': {
            'HDR': [
                {'name': 'recordType', 'width': 10},
                {'name': 'value1', 'width': 5},
                {'name': 'value2', 'width': 3},
            ],
            'DTL': [
                {'name': 'recordType', 'width': 10},
                {'name': 'value1', 'width': 5},
                {'name': 'value2', 'width': 3},
            ],
        },
    },
    'mapping': {'header': {}, 'lines': [], 'summary': {}},
}

# Write schema to temp file
schema_tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8')
yaml.dump(schema, schema_tmp, default_flow_style=False)
schema_tmp.close()

# Parse
handler = CSVHandler()
handler.set_compiled_yaml_path(schema_tmp.name)
result = handler.read(tmp.name)

print(f'Lines parsed: {len(result[\"lines\"])}')
assert len(result['lines']) == 3

# Verify padding was stripped
assert result['lines'][0]['recordType'] == 'HDR', f'Got: {result[\"lines\"][0][\"recordType\"]}'
assert result['lines'][0]['value1'] == 'Hello', f'Got: {result[\"lines\"][0][\"value1\"]}'
assert result['lines'][0]['value2'] == '42', f'Got: {result[\"lines\"][0][\"value2\"]}'
assert result['lines'][1]['value1'] == 'World', f'Got: {result[\"lines\"][1][\"value1\"]}'

print('ALL FIXED-WIDTH READ CHECKS PASSED')

os.unlink(tmp.name)
os.unlink(schema_tmp.name)
"

# Full suite
python -m pytest tests/ -v --tb=short
```

**Commit:** `feat(csv-handler): add positional fixed-width file reader`

---

# PHASE 4: Portal — Width Metadata in API and Wizard UI

> **Prerequisite:** Phase 3 green.
> **Deliverables:** API returns `width` field, wizard displays width column and format badge.

---

## Task 4.1 — Add `width` to ColumnInfo dataclass and ColumnInfoModel

**Investigate:**
```bash
# Read the dataclass
grep -A 10 "class ColumnInfo" pyedi_core/validator.py
# Read the Pydantic model
grep -A 10 "class ColumnInfoModel" portal/api/models.py
# Read where ColumnInfo is built
grep -A 30 "_build_column_info" pyedi_core/validator.py
# Read where ColumnInfoModel is constructed
grep -A 15 "_to_response" portal/api/routes/validate.py
```

**What to change:**

1. **`pyedi_core/validator.py` — `ColumnInfo` dataclass (line 34):**
   Add field: `width: Optional[int] = None`

2. **`pyedi_core/validator.py` — `_build_column_info()` (line 307):**
   Change the `compiled_cols` dict (line 312-315) to store the full column dict, not just the type:
   ```python
   compiled_cols = {
       c["name"]: c
       for c in compiled_yaml.get("schema", {}).get("columns", [])
   }
   ```
   Then on line 325:
   ```python
   col_data = compiled_cols.get(name, {})
   compiled_type = col_data.get("type", "string") if isinstance(col_data, dict) else col_data
   ```
   And on line 327, add `width`:
   ```python
   infos.append(ColumnInfo(
       name=name,
       compiled_type=compiled_type,
       dsl_type=dsl_type,
       record_name=rec["name"],
       type_preserved=compiled_type == fld["type"],
       width=col_data.get("width") if isinstance(col_data, dict) else None,
   ))
   ```

3. **`portal/api/models.py` — `ColumnInfoModel` (line 18):**
   Add field: `width: Optional[int] = None`
   (Add `from typing import Optional` if not already imported.)

4. **`portal/api/routes/validate.py` — `_to_response()` (line 29):**
   Add `width=c.width` to the `ColumnInfoModel` constructor:
   ```python
   ColumnInfoModel(
       name=c.name,
       compiled_type=c.compiled_type,
       dsl_type=c.dsl_type,
       record_name=c.record_name,
       type_preserved=c.type_preserved,
       width=c.width,
   )
   ```

**Test Gate:**
```bash
# Verify via API
cd ~/VS/pycoreEdi

# Start backend if not running
# python -m uvicorn portal.api.app:create_app --factory --port 8000 &

# Validate the .ffSchema via API
curl -s -X POST http://localhost:8000/api/validate \
  -H "Content-Type: application/json" \
  -d '{"dsl_path": "artifacts/RetalixPIPOAckFF.ffSchema"}' | python -m json.tool | head -30

# Verify width appears in response columns
curl -s -X POST http://localhost:8000/api/validate \
  -H "Content-Type: application/json" \
  -d '{"dsl_path": "artifacts/RetalixPIPOAckFF.ffSchema"}' | python -c "
import json, sys
data = json.load(sys.stdin)
cols = data.get('columns', [])
cols_with_width = [c for c in cols if c.get('width') is not None]
print(f'Columns with width: {len(cols_with_width)} / {len(cols)}')
assert len(cols_with_width) > 0, 'No columns have width'
print(f'Sample: {cols_with_width[0]}')
print('API WIDTH RESPONSE OK')
"

# Verify delimited DSL has no width in response
curl -s -X POST http://localhost:8000/api/validate \
  -H "Content-Type: application/json" \
  -d '{"dsl_path": "schemas/source/gfsGenericOut810FF.txt"}' | python -c "
import json, sys
data = json.load(sys.stdin)
cols = data.get('columns', [])
cols_with_width = [c for c in cols if c.get('width') is not None]
assert len(cols_with_width) == 0, f'{len(cols_with_width)} columns have width — should be 0'
print('DELIMITED RESPONSE HAS NO WIDTH: OK')
"

# Full suite
python -m pytest tests/ -v --tb=short
```

**Commit:** `feat(api): expose field width in validation response`

---

## Task 4.2 — Add width column and format badge to wizard UI

**Investigate:**
```bash
# Read the Onboard component — focus on the columns table in StepCompile
cat portal/ui/src/pages/Onboard.tsx
# Focus on lines 297-327 (columns table) and the CardHeader badge area
```

**What to change in `portal/ui/src/pages/Onboard.tsx`:**

1. **Columns table header** (around line 303-308) — add a "Width" column header after "Compiled Type":
   ```tsx
   <Th>Compiled Type</Th>
   <Th align="center">Width</Th>
   <Th align="center">Preserved</Th>
   ```

2. **Columns table body** (around line 313-321) — add a width cell after the compiled_type cell:
   ```tsx
   <td className="px-3 py-1.5 text-gray-500">{c.compiled_type}</td>
   <td className="px-3 py-1.5 text-center font-mono text-xs text-gray-500">
     {c.width || '\u2014'}
   </td>
   ```

3. **Format badge** — in the result summary area (around line 260-270), add a badge that shows the detected format:
   ```tsx
   <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
     result.transaction_type?.includes('FIXED') || result.columns?.some((c: any) => c.width)
       ? 'bg-violet-100 text-violet-700'
       : 'bg-blue-100 text-blue-700'
   }`}>
     {result.columns?.some((c: any) => c.width) ? 'Fixed-Width' : 'Delimited'}
   </span>
   ```
   Place this near the existing `transaction_type` badge or column count.

4. **TypeScript check:**
   ```bash
   cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
   ```

**Test Gate:**
```bash
# Verify TypeScript compiles
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit

# Manual verification:
# 1. Open http://localhost:5173 → Onboard tab
# 2. Enter path: artifacts/RetalixPIPOAckFF.ffSchema → Compile
# 3. Verify: "Fixed-Width" badge visible, Width column in table shows numbers
# 4. Enter path: schemas/source/gfsGenericOut810FF.txt → Compile
# 5. Verify: "Delimited" badge visible, Width column shows dashes

# Full suite
cd ~/VS/pycoreEdi
python -m pytest tests/ -v --tb=short
```

**Commit:** `feat(wizard-ui): display field widths and format badge for fixed-width schemas`

---

# PHASE 5: Tests

> **Prerequisite:** Phase 4 green.
> **Deliverables:** New test cases for fixed-width compilation and parsing.

---

## Task 5.1 — Add fixed-width compilation and parsing tests

**Investigate:**
```bash
# Read existing test files for patterns
cat tests/test_validator.py | head -80
cat tests/test_core.py | head -80
ls tests/
```

**What to add — new tests in appropriate test file(s):**

1. **`test_compile_fixed_width_schema`** — compile `artifacts/RetalixPIPOAckFF.ffSchema`, assert:
   - `input_format == "FIXED_WIDTH"`
   - All columns have `width`
   - `record_layouts` exists with correct field counts per record
   - No `delimiter` in schema
   - Record keys are stripped (no trailing whitespace)

2. **`test_compile_delimited_backward_compat`** — compile `schemas/source/gfsGenericOut810FF.txt`, assert:
   - `input_format == "CSV"`
   - No columns have `width`
   - No `record_layouts`
   - `delimiter` present

3. **`test_field_attribute_parsing`** — call `_parse_dsl_record()` on a crafted record string with `(length = 10, readEmptyAsNull = true)`, assert attributes are extracted.

4. **`test_read_fixed_width_file`** — create synthetic fixed-width file + schema in a temp dir, call `CSVHandler.read()`, assert fields are correctly sliced and padding stripped.

5. **`test_read_empty_as_null`** — create a fixed-width line with whitespace-only fields where column has `read_empty_as_null: true`, assert those fields are `None`.

**Test Gate:**
```bash
# Run new tests
python -m pytest tests/ -v --tb=short -k "fixed_width"

# Full suite
python -m pytest tests/ -v --tb=short
```

**Commit:** `test: add fixed-width schema compilation and parsing tests`

---

# Final Verification

```bash
cd ~/VS/pycoreEdi

# 1. Full test suite
python -m pytest tests/ -v --tb=short

# 2. End-to-end: compile .ffSchema
python -m pycoreedi validate --dsl artifacts/RetalixPIPOAckFF.ffSchema --verbose

# 3. Inspect compiled YAML
cat schemas/compiled/RetalixPIPOAckFF_map.yaml | head -40

# 4. Verify delimited schemas unchanged
python -m pycoreedi validate --dsl schemas/source/gfsGenericOut810FF.txt

# 5. TypeScript clean
cd portal/ui && npx tsc --noEmit

# 6. API smoke test
curl -s -X POST http://localhost:8000/api/validate \
  -H "Content-Type: application/json" \
  -d '{"dsl_path": "artifacts/RetalixPIPOAckFF.ffSchema"}' | python -c "
import json, sys
data = json.load(sys.stdin)
assert any(c.get('width') for c in data['columns']), 'No width in API response'
print('FINAL E2E CHECK: PASSED')
"
```

## Completion Checklist

- [ ] `_parse_dsl_record()` extracts `length` and `readEmptyAsNull` from `(...)` blocks
- [ ] `fieldIdentifier` values are `.strip()`-ed during compilation
- [ ] `parse_dsl_file()` returns 3-tuple with `format_type`
- [ ] All 3 callers updated for 3-tuple return
- [ ] `_compile_to_yaml()` emits `width`, `read_empty_as_null`, `record_layouts` for FIXED_WIDTH
- [ ] `_compile_to_yaml()` omits `delimiter` for FIXED_WIDTH
- [ ] Delimited DSL compilation unchanged (backward compat)
- [ ] `CSVHandler._read_fixed_width()` parses by byte position
- [ ] `CSVHandler.read()` routes to `_read_fixed_width()` when `input_format == "FIXED_WIDTH"`
- [ ] `ColumnInfo` and `ColumnInfoModel` include `width`
- [ ] API validate response includes `width` for fixed-width schemas
- [ ] Wizard UI shows Width column and format badge
- [ ] All existing tests pass
- [ ] New fixed-width tests pass
