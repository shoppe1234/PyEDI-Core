# Import XML: XSD-Based XML Processing Pipeline

## Objective

Add end-to-end XSD-based XML processing to pycoreEdi: compile XSD schema to YAML mapping, process XML files through pipeline, compare control vs test invoices field-by-field using InvoiceNumber as match key.

## Data

- **XSD schema:** `artifacts/darden/DardenInvoiceASBN.xsd`
- **Control set:** `artifacts/darden/ca-source/` (3 XML files, 1 invoice each)
- **Test set:** `artifacts/darden/na-source/` (3 XML files — must introduce diffs before comparing)
- **Key field:** `InvoiceNumber` (in `ASBN/ASBNHeader`)
- **Namespace:** `http://DRI.iKitchen.BTS.Shared.Schemas.AdvancedShippingNotification.InBoundASN`

## XSD Structure Reference

```
ASBNS (root)
  ASBNTransmissionHeader: ASBNCount, TransmissionID, SenderID, ReceiverID, TimeStamp
  ASBN (transaction element — can repeat):
    ASBNHeader: Concept, Restaurant, PONumber, OrderDate, ShipDate, InvoiceDate,
                InvoiceNumber, InvoiceTotal, InvoiceType, DeliveryDate,
                TotalQtyShipped, CenterID,
                SpecialCharges/SpecialCharge(ChargeType, ChargeAmount),
                ASBNTotalLines
    ASBNItems:
      ASBNItem (0..unbounded): LineNumber, ItemID, UnitPrice, Description,
                               OrderUOM, OrderQty,
                               ShipDetail/ShipDetailItem(ShipUOM, ShipQty, Freight, ItemTotal)
```

---

## Task List

### Task 0: Introduce Test Diffs in na-source

The 3 XML files in ca-source and na-source are currently byte-for-byte identical. Modify na-source to create meaningful comparison data:

- **File 1** (`ASBN20260322T233555600_HS00.XML`): Change `InvoiceTotal` from 257.56 to 260.00 and `UnitPrice` from 18.91 to 19.50 (financial hard diff)
- **File 2** (`ASBN20260322T233556054_HS00.XML`): Change `Description` text to something slightly different (soft diff, case change)
- **File 3** (`ASBN20260322T233606247_HS00.XML`): Add a second `ASBNItem` element with new line item data (structural diff)

**Verify:** `diff artifacts/darden/ca-source/ artifacts/darden/na-source/` shows diffs in all 3 files.

---

### Task 1: Config Model — Add XmlSchemaEntry

**File:** `pyedi_core/config/__init__.py`

Add alongside existing `CsvSchemaEntry`:

```python
class XmlSchemaEntry(BaseModel):
    """Configuration entry for XML schema registry."""
    source_xsd: str = Field(..., description="Path to source XSD schema file")
    compiled_output: str = Field(..., description="Path to compiled YAML map")
    inbound_dir: str = Field(..., description="Inbound directory for XML files")
    transaction_type: str = Field(..., description="Transaction type (e.g., DARDEN_ASBN)")
    namespace: Optional[str] = Field(None, description="XML namespace URI to strip")
```

Add to `AppConfig`:

```python
xml_schema_registry: Dict[str, XmlSchemaEntry] = Field(
    default_factory=dict,
    description="XML schema registry entries"
)
```

**Verify:** Existing tests pass — `python -m pytest tests/ -v`

---

### Task 2: XSD Compiler

**File:** `pyedi_core/core/schema_compiler.py`

Add three functions (DO NOT modify existing DSL functions):

#### 2a: `parse_xsd_file(source_file: str) -> Tuple[List[Dict], Dict]`

- Use `defusedxml.ElementTree` to parse XSD
- Walk `xs:element`/`xs:complexType`/`xs:sequence` tree recursively
- Identify elements with `maxOccurs="unbounded"` as line items (ASBNItem)
- Map XSD types: `xs:string`->string, `xs:float`->float, `xs:decimal`->float, `xs:integer`->integer, `xs:int`->integer, `xs:boolean`->boolean, `xs:date`->date, `xs:dateTime`->date
- Handle nested complex types (SpecialCharges/SpecialCharge, ShipDetail/ShipDetailItem) — flatten field names with dot-notation paths
- Return: `(record_defs, hierarchy_metadata)`
  - `record_defs`: list of `{"name": "ASBNHeader", "type": "header"|"line"|"transmission", "fields": [{"name": "InvoiceNumber", "type": "string"}, ...]}`
  - `hierarchy_metadata`: `{"root_element": "ASBNS", "transaction_element": "ASBN", "header_path": "ASBN/ASBNHeader", "line_container_path": "ASBN/ASBNItems", "line_element": "ASBNItem", "transmission_header_path": "ASBNTransmissionHeader"}`

#### 2b: `_compile_xsd_to_yaml(record_defs, hierarchy, source_filename) -> Dict`

Output structure:
```yaml
transaction_type: DARDEN_ASBN  # derived from filename
input_format: XML
xml_config:
  namespace: null  # filled by caller if known
  root_element: ASBNS
  transaction_element: ASBN
  header_path: ASBN/ASBNHeader
  line_container_path: ASBN/ASBNItems
  line_element: ASBNItem
  transmission_header_path: ASBNTransmissionHeader
schema:
  columns:
    - name: InvoiceNumber
      type: string
    - name: InvoiceTotal
      type: float
    # ... all fields from all records
  records:
    ASBNTransmissionHeader: [ASBNCount, TransmissionID, ...]
    ASBNHeader: [Concept, Restaurant, InvoiceNumber, ...]
    ASBNItem: [LineNumber, ItemID, UnitPrice, ...]
mapping:
  header:
    InvoiceNumber: {source: InvoiceNumber}
    InvoiceTotal: {source: InvoiceTotal}
    SpecialCharges.SpecialCharge.ChargeType: {source: SpecialCharges.SpecialCharge.ChargeType}
    # ... all ASBNHeader + ASBNTransmissionHeader fields
  lines:
    LineNumber: {source: LineNumber}
    ItemID: {source: ItemID}
    ShipDetail.ShipDetailItem.ShipUOM: {source: ShipDetail.ShipDetailItem.ShipUOM}
    # ... all ASBNItem fields
  summary: {}
```

#### 2c: `compile_xsd(source_file, compiled_dir, correlation_id, target_yaml_path, namespace) -> Dict`

Follow the EXACT same pattern as existing `compile_dsl()`:
1. Compute SHA-256 hash of XSD file
2. Check `.meta.json` for existing hash
3. If match: load and return existing YAML
4. If changed: archive old version, parse XSD, compile to YAML, write YAML + meta.json

**Verify:** Quick test:
```python
from pyedi_core.core.schema_compiler import compile_xsd
result = compile_xsd("./artifacts/darden/DardenInvoiceASBN.xsd")
assert result["input_format"] == "XML"
assert "InvoiceNumber" in [c["name"] for c in result["schema"]["columns"]]
assert result["xml_config"]["line_element"] == "ASBNItem"
```

---

### Task 3: XML Handler — Schema-Aware Parsing

**File:** `pyedi_core/drivers/xml_handler.py`

#### 3a: `set_compiled_yaml_path(self, compiled_yaml_path: str) -> None`
Store path on instance (mirrors CSVHandler pattern).

#### 3b: `_strip_namespace(self, element: Element) -> None`
Recursively strip namespace from all element tags:
- Clark notation: `{http://...}TagName` -> `TagName`
- Prefix notation: `ns0:TagName` -> `TagName`
- Apply to element and ALL descendants

#### 3c: `_parse_schema_aware_xml(self, content: bytes, xml_config: Dict) -> Dict`
1. Parse XML with `defusedxml.ElementTree`
2. Call `_strip_namespace()` on root
3. Navigate to `transmission_header_path` -> extract fields with `transmission_` prefix into `header`
4. Navigate to `header_path` -> extract all child elements into `header` (handle nested elements like SpecialCharges as nested dicts)
5. Navigate to `line_container_path` -> find all `line_element` children -> each becomes a dict in `lines` (handle nested ShipDetail as nested dict)
6. Return `{"header": {...}, "lines": [...], "summary": {}}`

#### 3d: Multi-ASBN split support
When `xml_config.transaction_element` is set:
- Find ALL `transaction_element` children under root
- If >1 found: process each as separate transaction, return list
- If 1 found: process normally, return single dict
- Pipeline's existing `write_split` with InvoiceNumber handles the rest

#### 3e: Modify `read()` method
```python
def read(self, file_path: str) -> Dict[str, Any]:
    # ... existing file reading ...

    # Schema-aware parsing (when compiled YAML available)
    if hasattr(self, '_compiled_yaml_path') and self._compiled_yaml_path:
        import yaml
        with open(self._compiled_yaml_path) as f:
            compiled = yaml.safe_load(f)
        xml_config = compiled.get("xml_config")
        if xml_config:
            parsed = self._parse_schema_aware_xml(content, xml_config)
            parsed["_source_file"] = Path(file_path).name
            return parsed

    # Fall through to existing generic/cxml parsing
    # ... existing code ...
```

**Verify:** Quick test with a ca-source file:
```python
from pyedi_core.drivers.xml_handler import XMLHandler
handler = XMLHandler()
handler.set_compiled_yaml_path("./schemas/compiled/DardenInvoiceASBN_map.yaml")
result = handler.read("./artifacts/darden/ca-source/ASBN20260322T233555600_HS00.XML")
assert result["header"]["InvoiceNumber"] == "12006852"
assert len(result["lines"]) == 1
assert result["lines"][0]["ItemID"] == "6950100"
```

---

### Task 4: Pipeline — XML Schema Registry Routing

**File:** `pyedi_core/pipeline.py`

#### 4a: Modify `__init__`
```python
self._xml_schema_registry = self._config.xml_schema_registry
```

#### 4b: Add `_resolve_xml_schema(self, file_path: Path) -> XmlSchemaEntry`
Mirror `_resolve_csv_schema` exactly — match by `inbound_dir`.

#### 4c: Modify `_process_single` (~line 255)
Add XML branch BEFORE the else clause:
```python
elif Path(file_path).suffix.lower() in ('.xml', '.cxml'):
    try:
        xml_entry = self._resolve_xml_schema(Path(file_path))
        compiled_yaml_path = xml_entry.compiled_output

        # Compile or load XSD
        schema_compiler.compile_xsd(
            xml_entry.source_xsd,
            compiled_dir=str(Path(compiled_yaml_path).parent),
            correlation_id=correlation_id,
            target_yaml_path=compiled_yaml_path,
            namespace=xml_entry.namespace,
        )

        # Load compiled map
        map_yaml = mapper.load_map(compiled_yaml_path)
        transaction_type = xml_entry.transaction_type

        # Set compiled path on handler
        if hasattr(driver, 'set_compiled_yaml_path'):
            driver.set_compiled_yaml_path(compiled_yaml_path)
    except Exception:
        # No registry match — fall through to generic mapping
        map_yaml = self._get_mapping_rules(file_path, driver)
        if map_yaml:
            transaction_type = map_yaml.get("transaction_type", "unknown")
```

**Verify:** `python -m pyedi_core run --file ./artifacts/darden/ca-source/ASBN20260322T233555600_HS00.XML --dry-run --return-payload` succeeds.

---

### Task 5: Validate Command — Add --xsd Flag

#### 5a: `pyedi_core/main.py`
- Change `--dsl` to `required=False`
- Add `--xsd` argument: `validate_parser.add_argument("--xsd", default=None, help="Path to XSD schema file")`
- In `_handle_validate`: validate exactly one of `--dsl`/`--xsd` provided; branch accordingly

#### 5b: `pyedi_core/validator.py`
Add `validate_xsd(xsd_path, sample_path, compiled_dir) -> ValidationResult`:
- Call `parse_xsd_file()` and `compile_xsd()`
- Report: record count, field count, types breakdown
- If `sample_path` provided: read XML with schema-aware handler, trace field values
- Return same `ValidationResult` structure as existing `validate()`

**Verify:**
```bash
python -m pyedi_core validate --xsd ./artifacts/darden/DardenInvoiceASBN.xsd --verbose
python -m pyedi_core validate --xsd ./artifacts/darden/DardenInvoiceASBN.xsd --sample ./artifacts/darden/ca-source/ASBN20260322T233555600_HS00.XML --verbose
```

---

### Task 6: Config + Compare Rules

#### 6a: `config/config.yaml`

Add `xml_schema_registry` section (after `csv_schema_registry`):
```yaml
xml_schema_registry:
  darden_asbn_control:
    source_xsd: ./artifacts/darden/DardenInvoiceASBN.xsd
    compiled_output: ./schemas/compiled/DardenInvoiceASBN_map.yaml
    inbound_dir: ./artifacts/darden/ca-source
    transaction_type: DARDEN_ASBN
    namespace: "http://DRI.iKitchen.BTS.Shared.Schemas.AdvancedShippingNotification.InBoundASN"
  darden_asbn_test:
    source_xsd: ./artifacts/darden/DardenInvoiceASBN.xsd
    compiled_output: ./schemas/compiled/DardenInvoiceASBN_map.yaml
    inbound_dir: ./artifacts/darden/na-source
    transaction_type: DARDEN_ASBN
    namespace: "http://DRI.iKitchen.BTS.Shared.Schemas.AdvancedShippingNotification.InBoundASN"
```

Add compare profile under `compare.profiles`:
```yaml
    darden_asbn:
      description: Darden ASBN Invoice XML comparison
      trading_partner: Darden
      transaction_type: DARDEN_ASBN
      match_key:
        json_path: header.InvoiceNumber
      segment_qualifiers: {}
      rules_file: config/compare_rules/darden_asbn.yaml
```

#### 6b: `config/compare_rules/darden_asbn.yaml` (new file)

```yaml
classification:
  # Financial fields — hard, numeric
  - segment: '*'
    field: InvoiceTotal
    severity: hard
    numeric: true
  - segment: '*'
    field: UnitPrice
    severity: hard
    numeric: true
  - segment: '*'
    field: ChargeAmount
    severity: hard
    numeric: true
  - segment: '*'
    field: ItemTotal
    severity: hard
    numeric: true
  # Description fields — soft
  - segment: '*'
    field: Description
    severity: soft
    ignore_case: true
  - segment: '*'
    field: SenderID
    severity: soft
    ignore_case: true
  - segment: '*'
    field: ReceiverID
    severity: soft
    ignore_case: true
  # Catch-all
  - segment: '*'
    field: '*'
    severity: hard
    ignore_case: false
    numeric: false
ignore: []
```

---

### Task 7: Onboard Wizard — XML Support

#### 7a: `portal/api/routes/onboard.py`
- Add `source_xsd: Optional[str]` and `namespace: Optional[str]` to `RegisterPartnerRequest`
- When `source_xsd` is provided, write to `xml_schema_registry` instead of `csv_schema_registry`
- Split suggestion endpoint: detect `xml_config.transaction_element` from compiled YAML

#### 7b: `portal/ui/src/pages/Onboard.tsx`
- In StepRegister: detect `.xsd` file upload -> show XML-specific fields (namespace, transaction element)
- Key field auto-suggestion from compiled YAML header fields

---

### Task 8: Tests

**Extend existing test files:**

In `tests/test_core.py`:
- `test_parse_xsd_file`: Parse Darden XSD, verify 3 records, correct field types
- `test_compile_xsd_to_yaml`: Verify output structure, xml_config, columns, mapping
- `test_compile_xsd_idempotent`: Compile twice, verify hash check skips recompile

In `tests/test_validator.py`:
- `test_validate_xsd`: Verify validate_xsd returns correct field/record counts
- `test_validate_xsd_with_sample`: Verify sample tracing extracts values

In `tests/test_drivers.py` (or appropriate test file):
- `test_xml_namespace_stripping`: Verify {uri} and prefix removal
- `test_xml_schema_aware_parse`: Parse ca-source file with compiled YAML, verify header/lines
- `test_xml_multi_asbn`: Create XML with 2 ASBN elements, verify both extracted

---

## Testing Process — Compare Verification

This is the critical end-to-end validation sequence. Run these IN ORDER after all tasks complete:

### Test Phase 1: Schema Compilation
```bash
python -m pyedi_core validate --xsd ./artifacts/darden/DardenInvoiceASBN.xsd --verbose
```
**Expected:** Report shows 3 records (ASBNTransmissionHeader, ASBNHeader, ASBNItem), correct XSD type mappings, xml_config section populated.

### Test Phase 2: Single File Pipeline
```bash
python -m pyedi_core run --file ./artifacts/darden/ca-source/ASBN20260322T233555600_HS00.XML --dry-run --return-payload
```
**Expected:** STATUS=SUCCESS, payload JSON has `header.InvoiceNumber = "12006852"`, `header.InvoiceTotal = "257.56"`, `lines[0].ItemID = "6950100"`, `lines[0].ShipDetail.ShipDetailItem.ShipQty = "13.2"`.

### Test Phase 3: Batch Processing
```bash
# Process control set
python -m pyedi_core run --files "artifacts/darden/ca-source/ASBN20260322T233555600_HS00.XML" "artifacts/darden/ca-source/ASBN20260322T233556054_HS00.XML" "artifacts/darden/ca-source/ASBN20260322T233606247_HS00.XML" --output-dir ./outbound/darden-ca

# Process test set
python -m pyedi_core run --files "artifacts/darden/na-source/ASBN20260322T233555600_HS00.XML" "artifacts/darden/na-source/ASBN20260322T233556054_HS00.XML" "artifacts/darden/na-source/ASBN20260322T233606247_HS00.XML" --output-dir ./outbound/darden-na
```
**Expected:** 6 JSON files total (3 per directory). Each JSON has correct header/lines structure.

### Test Phase 4: JSON Structure Verification
```bash
# Verify JSON files are valid and have expected structure
python -c "
import json, glob
for f in sorted(glob.glob('outbound/darden-ca/*.json')):
    d = json.load(open(f))
    inv = d.get('header', {}).get('InvoiceNumber', 'MISSING')
    lines = len(d.get('lines', []))
    print(f'{f}: InvoiceNumber={inv}, lines={lines}')
for f in sorted(glob.glob('outbound/darden-na/*.json')):
    d = json.load(open(f))
    inv = d.get('header', {}).get('InvoiceNumber', 'MISSING')
    lines = len(d.get('lines', []))
    print(f'{f}: InvoiceNumber={inv}, lines={lines}')
"
```
**Expected:** All 6 files have InvoiceNumber populated, control and test have matching invoice numbers, line counts match (except File 3 which has an extra line in na-source).

### Test Phase 5: Compare Run
```bash
python -m pyedi_core compare --profile darden_asbn --source-dir ./outbound/darden-ca --target-dir ./outbound/darden-na --verbose --export-csv
```
**Expected:**
- 3 pairs matched by InvoiceNumber
- Pair 1: hard diffs on InvoiceTotal and UnitPrice (financial changes)
- Pair 2: soft diff on Description (case/text change)
- Pair 3: structural diff (extra line item in target)
- CSV report written to `reports/compare/`

### Test Phase 6: Regression
```bash
python -m pytest tests/ -v
```
**Expected:** ALL existing tests pass + new XSD/XML tests pass.

### Test Phase 7: Idempotency
```bash
# Re-run validate — should load from cache, not recompile
python -m pyedi_core validate --xsd ./artifacts/darden/DardenInvoiceASBN.xsd --verbose
# Verify: "Schema unchanged, loading existing" message in output
```

---

## Lessons from Fixed-Width Implementation (ffPostImplement.md)

Apply these lessons:
1. **Transaction-level matching is the design principle** — each invoice compared individually
2. **Schema hierarchy metadata matters** — xml_config must preserve XSD structure
3. **Key field from correct element** — InvoiceNumber from ASBNHeader, not elsewhere
4. **Crosswalk and YAML rules must sync** — after scaffold-rules, seed crosswalk table
5. **Scaffold rules need manual tuning** — financial fields hard, descriptions soft
6. **Windows ASCII-safe output** — no Unicode markers in console output

## Risks

| Risk | Mitigation |
|------|-----------|
| Namespace stripping misses elements | Test with actual Darden XML; handle both `{uri}` and `prefix:` patterns |
| Nested elements produce wrong JSON paths | Keep nested dicts; mapper's `_get_nested_value` resolves dot paths |
| XSD features beyond Darden (choice, import, union) | Raise clear ValueError for unsupported features |
| Multi-ASBN files with shared TransmissionHeader | Copy TransmissionHeader into each split transaction's header |
| Pipeline manifest marks files as processed (blocks re-run) | Use `--dry-run` during development or clear manifest |
