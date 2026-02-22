# PyEDI-Core Testing Specification
## Code Review & Validation Protocol

**Version:** 1.2  
**Target:** Phase 1-5 Implementation  
**Date:** February 22, 2026  
**Spec Baseline:** PyEDI_Core_Specification_v2.1  
**Purpose:** Systematic validation of PyEDI-Core implementation against specification

> **v1.2 Update Note:** This version reflects the Phase 5 test harness refactor (PCR-2025-003). The user-supplied test harness now supports physical output writing to `tests/user_supplied/outputs/`, per-test-case `dry_run`, `skip_fields`, and `strict` controls, pre-run cleanup of the `outputs/` directory, and a non-hard-failure discrepancy reporting model. See [Change Control](#change-control) for the full history.

---

## Table of Contents

1. [Testing Approach Overview](#testing-approach-overview)
2. [Pre-Testing Setup](#pre-testing-setup)
3. [Test Data Requirements](#test-data-requirements)
4. [Phase 1: Core Engine Tests](#phase-1-core-engine-tests)
5. [Phase 2: Library Interface Tests](#phase-2-library-interface-tests)
6. [Phase 3: REST API Tests](#phase-3-rest-api-tests)
7. [Phase 4: LLM Tool Layer Tests](#phase-4-llm-tool-layer-tests)
8. [Expected Output Specifications](#expected-output-specifications)
9. [Code Review Checklist](#code-review-checklist)
10. [Test Execution Plan](#test-execution-plan)

---

## Testing Approach Overview

### Strategy
This specification defines a **three-tier validation approach**:

1. **Static Code Review**: Verify implementation against architectural requirements
2. **Automated Test Execution**: Run existing pytest suite and validate coverage
3. **Integration Validation**: End-to-end testing with real-world data samples

### Success Criteria
- ✅ All non-negotiable implementation rules followed (Section 10.2 of spec)
- ✅ 85%+ test coverage on `core/` modules
- ✅ All three drivers process fixture files successfully
- ✅ Error handling routes to `./failed/` with proper `.error.json` files
- ✅ `dry-run` mode validates without writing files
- ✅ Manifest deduplication works via SHA-256 hash
- ✅ PipelineResult model returns correct structure
- ✅ CSV routing uses `csv_schema_registry` `inbound_dir` discriminator — schema never inferred from filename or extension alone
- ✅ X12 routing relies on badx12 envelope parsing — `x12_handler.py` performs no independent ST segment inspection

---

## Pre-Testing Setup

### 1. Repository Clone & Environment Setup

```bash
# Clone the repository
git clone [your-github-repo-url] pyedi-core-review
cd pyedi-core-review

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Verify installation
python -c "from pyedi_core import Pipeline; print('Import successful')"
```

### 2. Environment Verification

Run this verification script:

```python
# verify_environment.py
import sys
import importlib

required_packages = [
    ('badx12', 'badx12'),
    ('pandas', 'pandas'),
    ('yaml', 'pyyaml'),
    ('pydantic', 'pydantic'),
    ('structlog', 'structlog'),
    ('fastapi', 'fastapi'),  # Phase 3
    ('uvicorn', 'uvicorn'),  # Phase 3
]

print("Verifying Python environment...")
print(f"Python version: {sys.version}")

missing = []
for import_name, package_name in required_packages:
    try:
        mod = importlib.import_module(import_name)
        version = getattr(mod, '__version__', 'unknown')
        print(f"✓ {package_name}: {version}")
    except ImportError:
        missing.append(package_name)
        print(f"✗ {package_name}: NOT FOUND")

if missing:
    print(f"\n⚠️  Missing packages: {', '.join(missing)}")
    sys.exit(1)
else:
    print("\n✓ All required packages installed")
```

### 3. Directory Structure Verification

```bash
# verify_structure.sh
#!/bin/bash

echo "Verifying PyEDI-Core directory structure..."

required_dirs=(
    "pyedi_core"
    "pyedi_core/core"
    "pyedi_core/drivers"
    "pyedi_core/schemas/source"
    "pyedi_core/schemas/compiled"
    "pyedi_core/rules"
    "tests"
    "tests/fixtures"
    "config"
    "inbound/csv/gfs_ca"       # csv_schema_registry inbound_dir for GFS Canada 810
)

required_files=(
    "pyproject.toml"
    "pyedi_core/__init__.py"
    "pyedi_core/main.py"
    "pyedi_core/pipeline.py"
    "pyedi_core/core/logger.py"
    "pyedi_core/core/manifest.py"
    "pyedi_core/core/error_handler.py"
    "pyedi_core/core/mapper.py"
    "pyedi_core/core/schema_compiler.py"
    "pyedi_core/drivers/base.py"
    "pyedi_core/drivers/x12_handler.py"
    "pyedi_core/drivers/csv_handler.py"
    "pyedi_core/drivers/xml_handler.py"
    "config/config.yaml"
)

missing_dirs=()
missing_files=()

for dir in "${required_dirs[@]}"; do
    if [ ! -d "$dir" ]; then
        missing_dirs+=("$dir")
    fi
done

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        missing_files+=("$file")
    fi
done

if [ ${#missing_dirs[@]} -eq 0 ] && [ ${#missing_files[@]} -eq 0 ]; then
    echo "✓ Directory structure complete"
else
    echo "⚠️  Missing directories: ${missing_dirs[*]}"
    echo "⚠️  Missing files: ${missing_files[*]}"
    exit 1
fi
```

---

## Test Data Requirements

### User-Supplied Test Data

**This section is for YOU to populate with your actual test data.**

Before running tests, create a `tests/user_supplied/` directory and place your real-world files there:

```
tests/
├── user_supplied/
│   ├── inputs/
│   │   ├── 200220261215033.dat          # Raw X12 EDI from production
│   │   ├── UnivT701_small.csv           # Real GFS Canada CSV invoice
│   │   └── NA_810_MARGINEDGE_20260129.txt  # Real MarginEdge TXT file
│   ├── expected_outputs/               # CONTROLLED baseline — do not overwrite manually
│   │   ├── 200220261215033.json
│   │   ├── UnivT701_small.json
│   │   └── NA_810_MARGINEDGE_20260129.json
│   ├── outputs/                        # GENERATED — cleared on every test run
│   │   ├── 200220261215033.json        # Actual pipeline output (for diffing)
│   │   ├── UnivT701_small.json
│   │   └── NA_810_MARGINEDGE_20260129.json
│   └── metadata.yaml                   # Describes each test case
```

#### metadata.yaml Format

Create a `tests/user_supplied/metadata.yaml` describing your test cases:

```yaml
# tests/user_supplied/metadata.yaml
test_cases:
  - name: "UnivT701 Demo Invoice CSV"
    input_file: "inputs/UnivT701_small.csv"
    output_file: "outputs/UnivT701_small.json"         # where actual output is written
    expected_output: "expected_outputs/UnivT701_small.json"
    should_succeed: true
    dry_run: true                                      # uses in-memory pipeline payload
    skip_fields: ["id", "timestamp", "correlation_id", "_source_file"]
    transaction_type: "gfs_ca_810"
    target_inbound_dir: "./inbound/csv/gfs_ca"
    description: "Verify processing of GFS Canada CSV using gfsGenericOut810FF schema."

  - name: "MarginEdge 810 Text File"
    input_file: "inputs/NA_810_MARGINEDGE_20260129.txt"
    output_file: "outputs/NA_810_MARGINEDGE_20260129.json"
    expected_output: "expected_outputs/NA_810_MARGINEDGE_20260129.json"
    should_succeed: true
    dry_run: true
    skip_fields: ["id", "timestamp", "correlation_id", "_source_file"]
    transaction_type: "810"
    target_inbound_dir: "./inbound/csv/margin_edge"
    description: "Verify processing of Margin Edge TXT using tpm810SourceFF schema."

  - name: "x12 Data Comparison 200220261215033"
    input_file: "inputs/200220261215033.dat"
    output_file: "outputs/200220261215033.json"
    expected_output: "expected_outputs/200220261215033.json"
    should_succeed: true
    dry_run: false                                     # pipeline writes file physically
    strict: false                                      # discrepancies warned, not failed
    skip_fields: ["id", "timestamp", "correlation_id", "_source_file"]
    transaction_type: "x12"
    description: "User supplied data comparison test"
```

#### metadata.yaml Field Reference

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | ✅ | — | Human-readable test case name |
| `input_file` | string | ✅ | — | Path relative to `tests/user_supplied/` |
| `output_file` | string | ✅ | — | Where actual output is written (relative to `tests/user_supplied/`) |
| `expected_output` | string | ✅ | — | Controlled baseline to compare against |
| `should_succeed` | bool | ✅ | — | Whether the pipeline should succeed |
| `dry_run` | bool | ❌ | `true` | `false` = pipeline writes to filesystem; `true` = in-memory only |
| `skip_fields` | list[str] | ❌ | `[]` | Field names skipped at any nesting depth (runtime-generated values) |
| `strict` | bool | ❌ | `true` | `false` = discrepancies are warned not failed |
| `transaction_type` | string | ❌ | — | `"x12"` triggers direct `X12Handler` bypass when no `target_inbound_dir` |
| `target_inbound_dir` | string | ❌ | — | Directory to place file for `csv_schema_registry` routing |
| `expected_error_stage` | string | ❌ | — | Required when `should_succeed: false` |
| `description` | string | ❌ | — | Human-readable description of the test |

### Standard Test Data (Synthetic)

The following are **synthetic test files** for basic validation:

```
tests/
├── fixtures/
│   ├── x12/
│   │   ├── valid_810.edi              # Valid invoice
│   │   ├── valid_850.edi              # Valid purchase order
│   │   ├── malformed_810.edi          # Missing required segments
│   │   ├── unknown_transaction.edi    # ST segment not in registry
│   │   └── duplicate_810.edi          # Exact copy of valid_810.edi
│   ├── csv/
│   │   ├── valid_gfs_810.csv          # Valid GFS invoice format
│   │   ├── missing_required_field.csv # Missing Invoice Number column
│   │   ├── wrong_type.csv             # String in numeric column
│   │   └── duplicate_gfs_810.csv      # Exact copy of valid_gfs_810.csv
│   └── xml/
│       ├── valid_cxml_850.xml         # Valid cXML purchase order
│       ├── valid_generic.xml          # Generic XML format
│       ├── malformed.xml              # Broken XML structure
│       └── duplicate_cxml_850.xml     # Exact copy of valid_cxml_850.xml
├── expected_outputs/
│   ├── valid_810_expected.json
│   ├── valid_850_expected.json
│   ├── valid_gfs_810_expected.json
│   ├── valid_cxml_850_expected.json
│   └── valid_generic_expected.json
└── schemas/
    └── source/
        └── gfs_810_schema.txt          # DSL schema for CSV
```

### Sample Test Data Specifications

#### 1. X12 EDI Valid Invoice (valid_810.edi)

**Minimum Required Structure:**
```
ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250221*1430*U*00401*000000001*0*P*>~
GS*IN*SENDER*RECEIVER*20250221*1430*1*X*004010~
ST*810*0001~
BIG*20250221*INV001*20250220*PO001~
N1*BY*Buyer Name*92*123456~
N1*SE*Seller Name*92*654321~
IT1*1*10*EA*25.00**UP*12345~
TDS*250.00~
CTT*1~
SE*9*0001~
GE*1*1~
IEA*1*000000001~
```

**Expected Behavior:**
- Detects as transaction type 810
- Looks up mapping in `rules/gfs_810_map.yaml`
- Extracts header, line items, summary
- Produces normalized JSON with envelope

#### 2. CSV Valid Invoice (valid_gfs_810.csv)

> **PCR-2025-002:** CSV files must be placed in the `inbound_dir` registered in `csv_schema_registry` (e.g., `./inbound/csv/gfs_ca/`). The pipeline matches schema by directory — not by filename or extension. The fixture `valid_gfs_810.csv` should be placed in `./inbound/csv/gfs_ca/` for the `gfs_ca_810` registry entry to match.

**Structure:**
```csv
Invoice Number,Invoice Date,PO Number,Item Number,Description,Quantity,Unit Price,Net Case Price,Extended Price
INV001,02/21/2025,PO001,12345,Sample Item,10,25.00,24.00,240.00
INV001,02/21/2025,PO001,67890,Another Item,5,50.00,48.00,240.00
```

**Expected Behavior:**
- `pipeline.py` scans `csv_schema_registry` and matches the file's directory to the `gfs_ca_810` entry via `inbound_dir` (`./inbound/csv/gfs_ca/`)
- Triggers `schema_compiler.py` check using `source_dsl` path from registry entry
- Compiles or loads `gfs_ca_810_map.yaml` (SHA-256 hash checked for idempotency)
- Validates data types (dates, floats)
- Maps to `lines[]` array in JSON with `transaction_type` stamped from registry entry

#### 3. cXML Valid Purchase Order (valid_cxml_850.xml)

**Minimum Structure:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML version="1.2.014" xml:lang="en-US">
  <Header>
    <From><Credential domain="NetworkID"><Identity>buyer123</Identity></Credential></From>
    <To><Credential domain="NetworkID"><Identity>supplier456</Identity></Credential></To>
    <Sender><Credential domain="NetworkID"><Identity>buyer123</Identity></Credential></Sender>
  </Header>
  <Request>
    <OrderRequest>
      <OrderRequestHeader orderID="PO001" orderDate="2025-02-21">
        <Total><Money currency="USD">500.00</Money></Total>
        <ShipTo><Address><Name>Ship Name</Name></Address></ShipTo>
        <BillTo><Address><Name>Bill Name</Name></Address></BillTo>
      </OrderRequestHeader>
      <ItemOut quantity="10">
        <ItemID><SupplierPartID>ITEM001</SupplierPartID></ItemID>
        <ItemDetail><UnitPrice><Money currency="USD">50.00</Money></UnitPrice></ItemDetail>
      </ItemOut>
    </OrderRequest>
  </Request>
</cXML>
```

**Expected Behavior:**
- Auto-detects cXML via DOCTYPE
- Uses XPath notation from `rules/cxml_850_map.yaml`
- Extracts nested hierarchy
- Produces normalized JSON

#### 4. Error Cases

**malformed_810.edi:**
```
ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250221*1430*U*00401*000000001*0*P*>~
GS*IN*SENDER*RECEIVER*20250221*1430*1*X*004010~
ST*810*0001~
BIG*20250221*INV001~
SE*4*0001~
GE*1*1~
IEA*1*000000001~
```
**Expected:** Missing required BIG segment fields → VALIDATION stage failure

**missing_required_field.csv:**
```csv
Invoice Date,PO Number,Item Number,Description
02/21/2025,PO001,12345,Sample Item
```
**Expected:** Missing "Invoice Number" column → VALIDATION stage failure

**malformed.xml:**
```xml
<?xml version="1.0"?>
<root>
  <unclosed>
</root>
```
**Expected:** XML parsing error → DETECTION stage failure

---

## Phase 1: Core Engine Tests

### Test Suite: core/ Modules

#### 1.1 logger.py Tests

**Test File:** `tests/unit/test_logger.py`

```python
def test_logger_initialization():
    """Verify logger initializes with correct config"""
    # Assert structlog configured
    # Assert correlation_id stamping works
    # Assert format switching (pretty/json)

def test_log_levels():
    """Verify all log levels work"""
    # Test DEBUG, INFO, WARNING, ERROR
    # Verify filtering based on config

def test_correlation_id_propagation():
    """Verify correlation_id appears in all log events"""
    # Generate correlation_id
    # Emit multiple log events
    # Assert ID present in all

def test_json_output_structure():
    """When format=json, verify parseable output"""
    # Configure json format
    # Emit log event
    # Parse as JSON and validate fields
```

**Expected Output:**
```json
{
  "event": "file_processed",
  "level": "info",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_name": "test.csv",
  "stage": "TRANSFORMATION",
  "transaction_type": "810",
  "processing_time_ms": 142,
  "timestamp": "2025-02-21T14:30:00.000Z"
}
```

#### 1.2 manifest.py Tests

**Test File:** `tests/unit/test_manifest.py`

```python
def test_first_time_processing():
    """File not in manifest → returns True for should_process"""
    # Create temp manifest
    # Check file not seen before
    # Assert should_process() returns True

def test_duplicate_detection_by_hash():
    """Renamed file with same content → detected as duplicate"""
    # Process file once
    # Rename file
    # Assert should_process() returns False

def test_manifest_format():
    """Verify manifest line format"""
    # Process file
    # Read .processed
    # Assert format: {hash}|{filename}|{timestamp}|{status}

def test_status_values():
    """Verify all status types written correctly"""
    # Write SUCCESS, FAILED, SKIPPED
    # Assert correct values in manifest

def test_dry_run_no_manifest_update():
    """dry_run mode does not update manifest"""
    # Enable dry_run
    # Process file
    # Assert manifest unchanged
```

**Expected Manifest Format:**
```
a1b2c3d4e5f6...|GENSB_810.csv|2025-02-21T14:30:00Z|SUCCESS
a1b2c3d4e5f6...|RENAMED_810.csv|2025-02-21T14:35:00Z|SKIPPED
f6e5d4c3b2a1...|INVALID.csv|2025-02-21T14:40:00Z|FAILED
```

#### 1.3 error_handler.py Tests

**Test File:** `tests/unit/test_error_handler.py`

```python
def test_moves_file_to_failed():
    """Failed file moved to ./failed/ directory"""
    # Trigger failure
    # Assert file in ./failed/

def test_creates_error_json():
    """Sidecar .error.json created with details"""
    # Trigger failure
    # Assert .error.json exists
    # Validate JSON structure

def test_all_stages_covered():
    """Error handler callable at each stage"""
    # Test DETECTION, VALIDATION, TRANSFORMATION, WRITE
    # Assert correct stage in .error.json

def test_manifest_updated_with_failed():
    """Manifest shows FAILED status"""
    # Trigger failure
    # Check manifest
    # Assert status=FAILED

def test_structured_log_emitted():
    """ERROR level log event emitted"""
    # Capture logs
    # Trigger failure
    # Assert ERROR level event with correlation_id
```

**Expected Error JSON:**
```json
{
  "stage": "VALIDATION",
  "reason": "Missing required field: Invoice Number",
  "exception": "KeyError: 'Invoice Number'",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-02-21T14:30:00Z",
  "source_file": "missing_required_field.csv"
}
```

#### 1.4 schema_compiler.py Tests

**Test File:** `tests/unit/test_schema_compiler.py`

```python
def test_compiles_new_schema():
    """First compile creates YAML and meta.json"""
    # Provide .txt DSL
    # Run compiler
    # Assert YAML created
    # Assert meta.json with hash

def test_idempotent_on_unchanged():
    """Recompile with same source → no changes"""
    # Compile once
    # Compile again
    # Assert YAML unchanged
    # Assert meta.json hash matches

def test_recompiles_on_source_change():
    """Changed .txt source → recompile + archive old"""
    # Compile original
    # Modify .txt
    # Compile again
    # Assert new YAML
    # Assert old version in archive/ with datestamp

def test_dsl_parsing():
    """Correct parsing of DSL format"""
    # Test field extraction
    # Test type mapping (String→string, Decimal→float)
    # Test structure detection (Header/Details/Summary)
```

**Expected Compiled Output:**
```yaml
transaction_type: 'gfs_810'
input_format: 'CSV'
schema:
  delimiter: ','
  columns:
    - name: 'Invoice Number'
      type: string
      required: true
    - name: 'Net Case Price'
      type: float
      default: 0.0
mapping:
  header:
    invoice_id:
      source: 'Invoice Number'
  lines:
    unit_price:
      source: 'Net Case Price'
      transform: to_float
```

**Expected meta.json:**
```json
{
  "source_file": "gfs_810_schema.txt",
  "source_hash": "a1b2c3d4e5f6...",
  "compiled_at": "2025-02-21T14:30:00Z",
  "schema_version": "1.0"
}
```

#### 1.5 mapper.py Tests

**Test File:** `tests/unit/test_mapper.py`

```python
def test_simple_field_mapping():
    """Source → target mapping works"""
    # Provide source dict + map.yaml
    # Run mapper
    # Assert target field populated

def test_transform_operations():
    """All transforms work: strip, to_float, to_integer, date_format"""
    # Test each operation
    # Assert correct transformation

def test_nested_source_paths():
    """XPath-style paths extracted correctly"""
    # Test './/OrderRequest/@orderID'
    # Assert correct value extracted

def test_missing_optional_field():
    """Missing optional field → default value or omitted"""
    # Map with optional field
    # Source missing field
    # Assert default applied or field omitted

def test_missing_required_field():
    """Missing required field → raises exception"""
    # Map with required field
    # Source missing field
    # Assert exception raised
```

#### 1.6 Driver Tests

**Test Files:**
- `tests/unit/test_x12_handler.py`
- `tests/unit/test_csv_handler.py`
- `tests/unit/test_xml_handler.py`

Each driver test should verify:

```python
def test_read_method():
    """read() parses file correctly"""
    # Mock file I/O
    # Call read()
    # Assert dict structure

def test_transform_method():
    """transform() applies mapping rules"""
    # Provide raw data + map.yaml
    # Call transform()
    # Assert normalized dict

def test_write_method():
    """write() produces valid JSON with envelope"""
    # Provide payload
    # Call write()
    # Assert JSON file exists
    # Validate envelope structure

def test_error_handler_called():
    """Error handler invoked on failure"""
    # Mock error condition
    # Assert error_handler.handle_failure called
```

**Additional x12_handler.py tests (PCR-2025-001 — Input Sanitization & badx12 Parsing):**

```python
def test_input_sanitization_newline_stripping():
    """x12_handler strips newlines only from non-ISA-newline-delimited files"""
    # Provide EDI with embedded newlines (non-delimiter format)
    # Assert newlines stripped before parse
    # Provide EDI with newline as segment delimiter (ISA-newline format)
    # Assert newlines preserved

def test_isa_segment_length_guarantee():
    """ISA segment is exactly 106 characters"""
    # Inspect parsed ISA segment
    # Assert length == 106 before any processing

def test_badx12_parse_api():
    """x12_handler uses the 3-line badx12 parse API"""
    # Verify: document = badx12.read(content) or equivalent 3-line sequence
    # Assert no custom segment-splitting or ST-reading code exists in x12_handler.py

def test_normalized_segment_output_format():
    """Parsed output is a flat ordered segment list with X12 field naming"""
    # Parse valid_810.edi
    # Assert result is a list of segment dicts
    # Assert field naming convention: BIG01, BIG02, etc. (not positional indices)

def test_x12_handler_does_not_inspect_st_segment():
    """x12_handler.py reads transaction type from badx12 parsed object — never inspects ST segment directly"""
    # Parse an EDI document
    # Assert no code path reads raw ST segment text for routing
    # Transaction type should be accessed from badx12 document object attributes

def test_routing_via_transaction_registry():
    """x12_handler routes to map YAML via transaction_registry lookup after badx12 parse"""
    # Parse valid_810.edi
    # Assert routing lookup uses ST ID surfaced by badx12 — not manual segment read
    # Assert correct map YAML selected (gfs_810_map.yaml for ST*810)

def test_unknown_transaction_uses_default_fallback():
    """ST segment not in transaction_registry → routes to _default_x12 fallback"""
    # Parse unknown_transaction.edi (ST segment not in registry)
    # Assert _default_x12 entry selected
    # Assert UNMAPPED_TRANSACTION WARNING log emitted
```

**Additional csv_handler.py tests (PCR-2025-002 — csv_schema_registry Routing):**

```python
def test_csv_routing_uses_inbound_dir_not_filename():
    """CSV schema is resolved by inbound_dir match in csv_schema_registry — not by filename"""
    # Place valid_gfs_810.csv in ./inbound/csv/gfs_ca/
    # Assert pipeline matches gfs_ca_810 entry by directory
    # Rename file to arbitrary_name.csv in same directory
    # Assert same schema still selected (routing is directory-based, not filename-based)

def test_csv_routing_unknown_directory_raises_error():
    """CSV file in unregistered directory → error, not silent schema guessing"""
    # Place CSV file in ./inbound/csv/unknown_partner/
    # Assert pipeline raises error or routes to failed/ with informative message
    # Assert no attempt to infer schema from filename or extension

def test_csv_handler_receives_explicit_compiled_yaml_path():
    """csv_handler.py receives compiled YAML path from pipeline.py via registry lookup"""
    # Confirm csv_handler.py does not perform its own schema discovery
    # Compiled YAML path must be passed in as an explicit argument from pipeline.py

def test_csv_schema_compiler_called_with_registry_source_dsl():
    """schema_compiler.py is called with source_dsl path from csv_schema_registry entry"""
    # Run pipeline with a CSV in ./inbound/csv/gfs_ca/
    # Assert schema_compiler receives gfsGenericOut810FF.txt (source_dsl from registry)
    # Assert compiled output written to path specified in compiled_output registry field
```

### Test Suite: User-Supplied Data Validation

**Test File:** `tests/integration/test_user_supplied_data.py`

This test suite validates your real-world production data against your expected outputs.

```python
import pytest
import yaml
import json
import shutil
import os
import math
import warnings
from pathlib import Path
from pyedi_core import Pipeline

# ── Session-scoped fixture: wipe and recreate outputs/ before entire test run ──
@pytest.fixture(scope="session", autouse=True)
def clear_outputs():
    outputs_dir = Path("tests/user_supplied/outputs")
    if outputs_dir.exists():
        shutil.rmtree(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)

def load_test_cases():
    """Load test cases from metadata.yaml"""
    metadata_path = Path('tests/user_supplied/metadata.yaml')
    if not metadata_path.exists():
        return []
    with open(metadata_path) as f:
        metadata = yaml.safe_load(f)
    return metadata.get('test_cases', [])

@pytest.mark.parametrize("test_case", load_test_cases())
def test_user_supplied_file(test_case):
    """Test each user-supplied file against expected output"""
    input_path    = Path('tests/user_supplied') / test_case['input_file']
    expected_path = Path('tests/user_supplied') / test_case['expected_output']
    output_path   = Path('tests/user_supplied') / test_case['output_file']
    output_path.parent.mkdir(parents=True, exist_ok=True)

    from pyedi_core.drivers.x12_handler import X12Handler
    pipeline     = Pipeline(config_path='./config/config.yaml')
    dry_run      = test_case.get('dry_run', True)
    skip_fields  = set(test_case.get('skip_fields', []))
    target_inbound_dir = test_case.get('target_inbound_dir')
    run_path     = input_path
    copied_path  = None

    try:
        actual_payload = None
        status = 'SUCCESS'
        errors = []

        if target_inbound_dir:
            # CSV/TXT: must be placed in the registered inbound_dir (PCR-2025-002)
            target_dir   = Path(target_inbound_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            copied_path  = target_dir / input_path.name
            shutil.copy(input_path, copied_path)
            run_path     = copied_path
            result       = pipeline.run(file=str(run_path), return_payload=True, dry_run=dry_run)
            status       = result.status
            errors       = result.errors
            actual_payload = result.payload
        else:
            # Direct handler bypass for unmapped X12 structural comparisons
            if test_case.get('transaction_type') == 'x12':
                driver         = X12Handler()
                actual_payload = driver.read(str(input_path))
            else:
                pytest.fail("Test case lacks target_inbound_dir and is not a direct x12 comparison.")

        # Always write actual output — even on failure — for diffing
        with open(output_path, 'w') as f:
            json.dump(actual_payload, f, indent=2)

        if test_case['should_succeed']:
            if status != 'SUCCESS':
                pytest.fail(f"Expected success but got {status}. Errors: {errors}")

            with open(expected_path) as f:
                expected = json.load(f)
            with open(output_path) as f:
                actual = json.load(f)

            discrepancies = []
            compare_outputs(actual, expected, skip_fields, test_case['name'], discrepancies)

            # File size check (warns if > 1% diff)
            actual_size   = output_path.stat().st_size
            expected_size = expected_path.stat().st_size
            if abs(actual_size - expected_size) / expected_size > 0.01:
                diff_pct = ((actual_size - expected_size) / expected_size) * 100
                discrepancies.append(
                    f"Size diff: expected={expected_size}b, actual={actual_size}b ({diff_pct:+.1f}%)"
                )

            if discrepancies:
                print(f"\nDISCREPANCY REPORT — {test_case['name']}")
                for d in discrepancies:
                    print(f"  - {d}")

                field_diffs = [d for d in discrepancies if not d.startswith("Size diff")]
                is_strict   = test_case.get('strict', True)
                if field_diffs and is_strict:
                    pytest.fail(f"Found {len(field_diffs)} field discrepancies.")
                else:
                    warnings.warn(
                        f"Non-fatal discrepancies for {test_case['name']}:\n" +
                        "\n".join(discrepancies)
                    )
        else:
            if status != 'FAILED':
                pytest.fail(f"Expected failure but got {status}")
            if 'expected_error_stage' in test_case:
                error_json_path = Path('./failed') / f"{run_path.stem}.error.json"
                if not error_json_path.exists():
                    pytest.fail("No error.json found")
                with open(error_json_path) as f:
                    error_data = json.load(f)
                if error_data.get('stage') != test_case['expected_error_stage']:
                    pytest.fail(
                        f"Expected error at {test_case['expected_error_stage']} "
                        f"but got {error_data.get('stage')}"
                    )
    finally:
        if copied_path and copied_path.exists():
            os.remove(copied_path)

def compare_outputs(actual, expected, skip_fields, context, discrepancies, path=""):
    """Recursively collect discrepancies without asserting."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        for k in set(expected.keys()) | set(actual.keys()):
            if k in skip_fields:
                continue
            current_path = f"{path}.{k}" if path else k
            if k not in actual:
                discrepancies.append(f"Missing key in actual: '{current_path}'")
                continue
            if k not in expected:
                discrepancies.append(f"Unexpected key in actual: '{current_path}'")
                continue
            compare_outputs(actual[k], expected[k], skip_fields, context, discrepancies, current_path)
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(actual) != len(expected):
            discrepancies.append(f"List length mismatch at '{path}': expected {len(expected)}, got {len(actual)}")
        else:
            for i, (a, e) in enumerate(zip(actual, expected)):
                compare_outputs(a, e, skip_fields, context, discrepancies, f"{path}[{i}]")
    else:
        if isinstance(actual, float) and isinstance(expected, float) and math.isnan(actual) and math.isnan(expected):
            return
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)) and type(actual) == type(expected):
            if abs(actual - expected) >= 0.01:
                discrepancies.append(f"Value mismatch at '{path}': expected {expected}, got {actual}")
        elif actual != expected:
            discrepancies.append(f"Value mismatch at '{path}': expected '{expected}', got '{actual}'")
```

### Running User-Supplied Tests

```bash
# Run only user-supplied data tests
pytest tests/integration/test_user_supplied_data.py -v

# Run with verbose output showing which test case is running
pytest tests/integration/test_user_supplied_data.py -v -s

# Generate a detailed report
pytest tests/integration/test_user_supplied_data.py \
  --tb=long \
  --html=user_test_report.html \
  --self-contained-html
```

### Troubleshooting User-Supplied Test Failures

When a user-supplied test fails or emits discrepancies, the output will tell you:
1. **Which test case** (name from `metadata.yaml`)
2. **What was different** — specific field path and values in the `DISCREPANCY REPORT` block
3. **Actual output** written to `tests/user_supplied/outputs/{filename}.json` (always, even on failure)

**Common failure reasons:**
- `output_file` path doesn't match `input_file` stem
- Expected output has wrong format (check JSON syntax)
- Expected output doesn't match `map.yaml` rules
- Numeric precision differences (cents vs dollars)
- Pipeline returned extra internal keys (add to `skip_fields` or set `strict: false`)

**How to fix:**
```bash
# Compare actual vs expected using jq
jq '.' tests/user_supplied/outputs/UnivT701_small.json
jq '.' tests/user_supplied/expected_outputs/UnivT701_small.json

# Diff the two
fc tests\user_supplied\outputs\UnivT701_small.json tests\user_supplied\expected_outputs\UnivT701_small.json
```

**Non-fatal discrepancies** (when `strict: false`):
- Test will still `PASS` but emit a `UserWarning` to stdout with the discrepancy list
- Use `pytest -s` to see the discrepancy report inline
- Actual output is always in `tests/user_supplied/outputs/` for manual review

---

## Integration Tests with Standard Fixtures

**Test File:** `tests/integration/test_pipeline_end_to_end.py`

```python
def test_valid_810_edi():
    """Valid X12 810 → success output"""
    # Run pipeline on valid_810.edi
    # Assert output JSON matches expected
    # Assert manifest updated with SUCCESS

def test_valid_csv():
    """Valid CSV in registered inbound_dir → success output"""
    # Place valid_gfs_810.csv in ./inbound/csv/gfs_ca/ (registered inbound_dir)
    # Run pipeline
    # Assert pipeline resolved schema via csv_schema_registry (not filename)
    # Assert schema compiled or loaded from cached YAML
    # Assert output JSON matches expected
    # Assert transaction_type stamped from registry entry ('810')

def test_valid_cxml():
    """Valid cXML → success output"""
    # Run pipeline on valid_cxml_850.xml
    # Assert output JSON matches expected

def test_malformed_file_to_failed():
    """Malformed file → ./failed/ with error.json"""
    # Run pipeline on malformed_810.edi
    # Assert file in ./failed/
    # Assert .error.json exists
    # Assert manifest shows FAILED

def test_duplicate_file_skipped():
    """Duplicate file → skipped"""
    # Run pipeline on valid_810.edi twice
    # Assert second run skipped
    # Assert manifest shows SKIPPED

def test_unknown_transaction_fallback():
    """Unknown X12 transaction → default_x12_map.yaml via badx12 ST ID lookup"""
    # Run pipeline on unknown_transaction.edi
    # Assert processed via _default_x12 fallback entry in transaction_registry
    # Assert UNMAPPED_TRANSACTION WARNING log emitted
    # Assert x12_handler did not manually inspect ST segment text

def test_dry_run_mode():
    """dry_run → no files written"""
    # Run with --dry-run
    # Assert no output files
    # Assert no manifest update
    # Assert result returned with payload
```

---

## Phase 2: Library Interface Tests

### Test Suite: Importable Package

**Test File:** `tests/integration/test_library_interface.py`

```python
def test_package_import():
    """Can import from pyedi_core"""
    from pyedi_core import Pipeline
    assert Pipeline is not None

def test_pipeline_initialization():
    """Pipeline initializes with config"""
    from pyedi_core import Pipeline
    pipeline = Pipeline(config_path='./config/config.yaml')
    assert pipeline is not None

def test_run_returns_pipeline_result():
    """run() returns PipelineResult model"""
    from pyedi_core import Pipeline, PipelineResult
    pipeline = Pipeline(config_path='./config/config.yaml')
    result = pipeline.run(file='valid_810.edi')
    assert isinstance(result, PipelineResult)

def test_pipeline_result_structure():
    """PipelineResult has all required fields"""
    # Run pipeline
    # Assert fields: status, correlation_id, source_file, 
    #                transaction_type, output_path, payload,
    #                errors, processing_time_ms

def test_return_payload_option():
    """return_payload=True → result.payload populated"""
    # Run with return_payload=True
    # Assert result.payload is dict
    # Assert contains envelope + payload

def test_concurrent_processing():
    """ThreadPoolExecutor handles multiple files"""
    # Place 50 files in inbound/
    # Run pipeline
    # Assert all processed
    # Assert max_workers config respected
```

**Expected PipelineResult:**
```python
PipelineResult(
    status='SUCCESS',
    correlation_id='550e8400-e29b-41d4-a716-446655440000',
    source_file='GENSB_810.csv',
    transaction_type='810',
    output_path='./outbound/GENSB_810.json',
    payload={
        'envelope': {...},
        'payload': {...}
    },
    errors=[],
    processing_time_ms=142
)
```

---

## Phase 3: REST API Tests

### Test Suite: FastAPI Endpoints

**Test File:** `tests/integration/test_api_endpoints.py`

```python
from fastapi.testclient import TestClient

def test_post_process():
    """POST /process → returns PipelineResult JSON"""
    # Upload file or provide path
    # Assert 200 response
    # Assert response matches PipelineResult schema

def test_get_status():
    """GET /status/{correlation_id} → returns processing status"""
    # Process file
    # Query status by correlation_id
    # Assert status returned

def test_get_manifest():
    """GET /manifest → returns processing history"""
    # Process multiple files
    # Query manifest
    # Assert all entries returned

def test_post_dry_run():
    """POST /dry-run → validates without writing"""
    # Submit file
    # Assert validation response
    # Assert no files written

def test_concurrent_requests():
    """Multiple POST /process → handled concurrently"""
    # Submit 10 requests
    # Assert all complete
    # Assert no race conditions

def test_error_handling():
    """Malformed file → proper error response"""
    # Submit invalid file
    # Assert 400 or 422 response
    # Assert error details in response
```

**Expected API Response:**
```json
{
  "status": "SUCCESS",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "source_file": "GENSB_810.csv",
  "transaction_type": "810",
  "output_path": "./outbound/GENSB_810.json",
  "payload": null,
  "errors": [],
  "processing_time_ms": 142
}
```

---

## Phase 4: LLM Tool Layer Tests

### Test Suite: Tool Schema & Assisted Workflow

**Test File:** `tests/integration/test_llm_tools.py`

```python
def test_tool_schema_definition():
    """Tool schema correctly defined"""
    # Verify tool JSON schema
    # Assert parameters match API

def test_query_failed_files():
    """Can query manifest for FAILED entries"""
    # Process files with some failures
    # Query via tool
    # Assert FAILED files returned

def test_triage_error():
    """Can read .error.json and explain"""
    # Trigger failure
    # Read .error.json via tool
    # Assert content accessible

def test_validate_new_file_dry_run():
    """Can run dry-run on new file"""
    # Submit new file via tool
    # Assert validation response
    # Assert no files written

def test_human_approval_boundary():
    """LLM cannot directly trigger POST /process"""
    # Attempt to call /process via tool
    # Assert requires human approval step
    # Tool should draft but not execute
```

**Expected Tool Schema:**
```json
{
  "name": "query_failed_files",
  "description": "Query manifest for failed files",
  "parameters": {
    "type": "object",
    "properties": {
      "limit": {"type": "integer", "default": 10}
    }
  },
  "returns": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "filename": {"type": "string"},
        "hash": {"type": "string"},
        "timestamp": {"type": "string"},
        "status": {"type": "string"}
      }
    }
  }
}
```

---

## Expected Output Specifications

### Standard JSON Envelope

Every output file must conform to this structure:

```json
{
  "envelope": {
    "schema_version": "1.0",
    "source_system_id": "gfs",
    "transaction_type": "810",
    "input_format": "CSV",
    "batch_id": "550e8400-e29b-41d4-a716-446655440000",
    "correlation_id": "550e8400-e29b-41d4-a716-446655440001",
    "processed_at": "2025-02-21T14:30:00Z",
    "source_file": "GENSB_810.csv"
  },
  "payload": {
    "header": {
      "invoice_id": "INV001",
      "invoice_date": "2025-02-21",
      "po_number": "PO001"
    },
    "lines": [
      {
        "item_id": "12345",
        "description": "Sample Item",
        "quantity": 10,
        "unit_price": 25.00,
        "extended_price": 250.00
      }
    ],
    "summary": {
      "total_amount": 250.00,
      "line_count": 1
    }
  }
}
```

### Validation Rules

1. **Envelope fields (all required):**
   - `schema_version`: Must be "1.0"
   - `source_system_id`: From config.yaml
   - `transaction_type`: From driver detection
   - `input_format`: "X12_EDI" | "CSV" | "XML" | "cXML"
   - `batch_id`: UUID, same for all files in batch
   - `correlation_id`: UUID, unique per file
   - `processed_at`: ISO 8601 timestamp
   - `source_file`: Original filename

2. **Payload structure:**
   - Must have `header`, `lines`, `summary` keys
   - `lines` must be array (even if empty)
   - All mapped fields present (or default values)

3. **File naming:**
   - Output: `{source_filename_without_ext}.json`
   - Error: `{source_filename}.error.json`

---

## Code Review Checklist

### Architecture Compliance

- [ ] **No hardcoded transaction logic in .py files**
  - All transaction types in `config.yaml` registry only
  - No if/else chains for transaction types in drivers

- [ ] **error_handler.py called at every stage boundary**
  - DETECTION failures
  - VALIDATION failures
  - TRANSFORMATION failures
  - WRITE failures

- [ ] **Config via Pydantic models only**
  - No raw `yaml.safe_load()` dict access
  - Type validation on startup

- [ ] **correlation_id stamped on every log event**
  - Check logger.py implementation
  - Verify structlog configuration

- [ ] **dry_run mode correct behavior**
  - No files written to outbound/
  - No manifest updates
  - Payload returned in result

- [ ] **ThreadPoolExecutor max_workers configurable**
  - Not hardcoded
  - Loaded from config.yaml

- [ ] **schema_compiler hash check before recompile**
  - Compares SHA-256 hash
  - Only recompiles if changed
  - Archives old version

- [ ] **CSV routing uses `csv_schema_registry` inbound_dir — never filename inference** *(PCR-2025-002)*
  - `config.yaml` contains a `csv_schema_registry` block (parallel to `transaction_registry`)
  - Each registry entry defines: `source_dsl`, `compiled_output`, `inbound_dir`, `transaction_type`
  - `pipeline.py` matches incoming CSV files by directory against `inbound_dir` values
  - `csv_handler.py` receives the compiled YAML path as an explicit argument — does not self-discover schema
  - A CSV file in an unregistered directory fails with an informative error (no silent schema guessing)

- [ ] **X12 routing delegated entirely to badx12 — no manual ST segment inspection** *(PCR-2025-001 / PCR-2025-002)*
  - `x12_handler.py` reads ST Transaction Set ID from the badx12 parsed document object
  - No code in `x12_handler.py` reads or splits the raw ST segment text for routing purposes
  - `transaction_registry` comment in `config.yaml` reads `# X12 only — badx12 handles ST detection`
  - `_default_x12` fallback entry present with comment `# Fallback for unmapped ST segments`

- [ ] **x12_handler.py input sanitization implemented** *(PCR-2025-001)*
  - ISA segment validated as 106 characters
  - Conditional newline stripping applied for non-newline-delimited EDI format
  - Newlines preserved when used as segment delimiter (ISA-newline format)

### Module Isolation

- [ ] **Each core/ module independently testable**
  - logger.py has no dependencies (except structlog)
  - manifest.py depends only on logger
  - error_handler.py depends on logger + manifest
  - mapper.py depends on logger + error_handler

- [ ] **Drivers implement AbstractTransactionProcessor**
  - read(), transform(), write() methods present
  - All drivers import from base.py

- [ ] **No circular dependencies**
  - Module import order matches spec section 10.1

### Testing Coverage

- [ ] **Unit tests for all core/ modules**
  - logger.py: 10+ tests
  - manifest.py: 10+ tests
  - error_handler.py: 10+ tests
  - schema_compiler.py: 10+ tests
  - mapper.py: 10+ tests

- [ ] **Integration tests with fixtures**
  - Valid files for each format
  - Negative path fixtures
  - Output validation against expected JSON

- [ ] **Coverage >= 85% on core/**
  - Run `pytest --cov=pyedi_core/core --cov-report=html`
  - Check htmlcov/index.html

### Error Handling

- [ ] **All failures route to ./failed/**
  - Malformed files
  - Validation errors
  - Transformation errors
  - Write errors

- [ ] **.error.json sidecar created**
  - Contains stage, reason, exception, correlation_id
  - JSON is parseable

- [ ] **Manifest updated with FAILED status**
  - Check .processed file
  - Assert correct status value

### Output Correctness

- [ ] **Envelope structure correct**
  - All required fields present
  - UUIDs are valid
  - Timestamps are ISO 8601

- [ ] **Payload structure correct**
  - header, lines, summary keys present
  - Data types match map.yaml

- [ ] **Output files JSON parseable**
  - Valid JSON syntax
  - No trailing commas

---

## Creating Expected Outputs from Your Real Data

If you have real input files but **don't yet have the expected outputs**, here's how to create them:

### Workflow: Generate Expected Outputs

1. **Process your file with the implementation**:
   ```bash
   # Run in dry-run mode first to see if it works
   python main.py --config config/config.yaml --dry-run
   
   # If successful, process for real
   python main.py --config config/config.yaml
   ```

2. **Review the output**:
   ```bash
   # View the generated output
   cat outbound/your_file.json | jq '.'
   ```

3. **Manually verify correctness**:
   - Open the original input file
   - Compare each field in the JSON to the source
   - Verify all mappings are correct
   - Check data types (strings, numbers, dates)
   - Verify line items are complete

4. **If output is CORRECT**, save it as expected:
   ```bash
   # Copy to expected outputs
   cp outbound/your_file.json tests/user_supplied/expected_outputs/your_file.json
   ```

5. **If output is WRONG**, note what's wrong:
   - Document the issue (wrong field mapping? wrong data type? missing data?)
   - Fix your map.yaml or schema
   - Re-process
   - Repeat until correct

6. **Document in metadata.yaml**:
   ```yaml
   test_cases:
     - name: "Your Real File Test"
       input_file: "inputs/your_file.csv"
       expected_output: "expected_outputs/your_file.json"
       should_succeed: true
       transaction_type: "810"
       description: "Real invoice from production, verified 2025-02-21"
       notes: "Manually verified all line items match source CSV"
   ```

### Creating Expected Outputs for Error Cases

If you have a file that **should fail**:

1. **Process it and let it fail**:
   ```bash
   python main.py --config config/config.yaml
   ```

2. **Check the error**:
   ```bash
   cat failed/your_file.error.json | jq '.'
   ```

3. **If the error is CORRECT**, document it:
   ```yaml
   test_cases:
     - name: "Known Bad File"
       input_file: "inputs/bad_file.csv"
       expected_output: null  # No output expected
       should_succeed: false
       expected_error_stage: "VALIDATION"
       description: "Missing required Invoice Number field"
       notes: "This file came from Partner XYZ and always fails"
   ```

---

## Test Execution Plan


### Phase 1: Static Review (1-2 hours)

1. Clone repository
2. Review directory structure
3. Check code against checklist
4. Document findings

### Phase 2: Unit Tests (2-3 hours)

1. Run pytest on unit tests:
   ```bash
   pytest tests/unit/ -v --tb=short
   ```

2. Generate coverage report:
   ```bash
   pytest --cov=pyedi_core/core --cov-report=html
   ```

3. Review coverage report:
   ```bash
   open htmlcov/index.html
   ```

4. Document any failing tests or low coverage areas

### Phase 3: Integration Tests (2-3 hours)

1. **Set up user-supplied test data** (if you have it):
   ```bash
   mkdir -p tests/user_supplied/{inputs,expected_outputs}
   # Copy your real files to tests/user_supplied/inputs/
   # Copy your expected outputs to tests/user_supplied/expected_outputs/
   # Create tests/user_supplied/metadata.yaml
   ```

2. Create standard test fixture files (if not present)

3. **Run user-supplied data tests first**:
   ```bash
   pytest tests/integration/test_user_supplied_data.py -v --tb=long
   ```
   
   If failures occur:
   ```bash
   # View actual output
   cat outbound/{your_file}.json | jq '.' > actual_output.json
   
   # View expected output
   cat tests/user_supplied/expected_outputs/{your_file}.json | jq '.' > expected_output.json
   
   # Compare them
   diff actual_output.json expected_output.json
   ```

4. Run standard integration tests:
   ```bash
   pytest tests/integration/ -v --tb=long
   ```

5. Manually verify outputs:

   ```bash
   # Process a file
   python main.py --config config/config.yaml
   
   # Check output
   cat outbound/GENSB_810.json | jq '.'
   
   # Check manifest
   cat .processed
   
   # Check failed directory
   ls -la failed/
   ```

4. Test dry-run mode:
   ```bash
   python main.py --config config/config.yaml --dry-run
   ```

5. Test duplicate detection:
   ```bash
   # Process same file twice
   python main.py --config config/config.yaml
   python main.py --config config/config.yaml
   # Second should skip
   ```

### Phase 4: Library Interface (1 hour)

```python
# Test script: test_library.py
from pyedi_core import Pipeline

pipeline = Pipeline(config_path='./config/config.yaml')

# Test single file
result = pipeline.run(file='tests/fixtures/csv/valid_gfs_810.csv', return_payload=True)
print(f"Status: {result.status}")
print(f"Correlation ID: {result.correlation_id}")
print(f"Processing time: {result.processing_time_ms}ms")
print(f"Payload keys: {result.payload.keys()}")

# Test batch processing
results = []
for i in range(10):
    r = pipeline.run(file=f'tests/fixtures/csv/test_{i}.csv')
    results.append(r)

print(f"Processed {len([r for r in results if r.status == 'SUCCESS'])} successfully")
```

### Phase 5: API Tests (Phase 3 only, 1-2 hours)

1. Start API server:
   ```bash
   uvicorn api.app:app --reload
   ```

2. Test endpoints with curl:
   ```bash
   # POST /process
   curl -X POST http://localhost:8000/process \
     -F "file=@tests/fixtures/csv/valid_gfs_810.csv"
   
   # GET /status/{id}
   curl http://localhost:8000/status/{correlation_id}
   
   # GET /manifest
   curl http://localhost:8000/manifest
   
   # POST /dry-run
   curl -X POST http://localhost:8000/dry-run \
     -F "file=@tests/fixtures/csv/test.csv"
   ```

3. Run automated API tests:
   ```bash
   pytest tests/integration/test_api_endpoints.py -v
   ```

### Phase 6: Scale Tests (Optional, 2-3 hours)

1. Generate synthetic test data:
   ```python
   # Generate 1000 CSV files
   python tests/generate_fixtures.py --format csv --count 1000
   ```

2. Run benchmark tests:
   ```bash
   pytest tests/scale/test_benchmark.py --benchmark-only
   ```

3. Run Locust load tests (if Phase 3 API exists):
   ```bash
   locust -f tests/scale/locustfile.py --host=http://localhost:8000
   ```

---

## Test Results Documentation

### Results Template

Create a file `TEST_RESULTS.md` with findings:

```markdown
# PyEDI-Core Test Results

**Date:** YYYY-MM-DD
**Tester:** [Name]
**Commit:** [git hash]

## Summary

- **Total Tests:** XXX
- **Passed:** XXX
- **Failed:** XXX
- **Skipped:** XXX
- **Coverage:** XX%

## Phase 1: Core Engine

### Unit Tests
- ✅ logger.py: 12/12 passed
- ✅ manifest.py: 10/10 passed
- ❌ error_handler.py: 8/10 passed (2 failures)
  - Failure detail: ...
- ✅ schema_compiler.py: 15/15 passed
- ✅ mapper.py: 12/12 passed

### Integration Tests
- ✅ Valid X12 810 processing
- ✅ Valid CSV processing
- ❌ cXML processing (parser error)
  - Issue: XPath expression incorrect
- ✅ Duplicate detection
- ✅ Dry-run mode

### Code Review Findings
- ⚠️ Transaction type check in x12_handler.py line 45 (should use registry)
- ⚠️ Hardcoded path in mapper.py line 123
- ✅ All other checklist items passed

> **Items to add from v2.1 spec (PCR-2025-002):**
> - [ ] `csv_schema_registry` block present in `config.yaml`
> - [ ] `pipeline.py` routes CSV by `inbound_dir` match (not filename)
> - [ ] `csv_handler.py` receives compiled YAML path as explicit argument
> - [ ] `x12_handler.py` contains no ST segment inspection logic

## Phase 2: Library Interface

- ✅ Package imports correctly
- ✅ PipelineResult structure correct
- ✅ return_payload option works
- ❌ Concurrent processing test timeout
  - Note: max_workers set too high for test environment

## Phase 3: REST API

- ✅ All endpoints functional
- ✅ Error handling correct
- ⚠️ Missing rate limiting (not in spec, but recommended)

## Phase 4: LLM Tools

- ✅ Tool schemas valid
- ✅ Read-only operations work
- ✅ Human approval boundary enforced

## Recommendations

1. Fix error_handler.py test failures
2. Correct cXML XPath expression
3. Adjust concurrent processing test for lower max_workers
4. Remove hardcoded paths
5. Consider adding rate limiting to API

## Coverage Report

[Attach htmlcov/index.html or screenshot]

## Output Samples

[Attach sample JSON outputs showing correct structure]
```

---

## Next Steps After Testing

1. **Fix failing tests**
   - Address all ❌ items in results
   - Re-run affected tests

2. **Address code review findings**
   - Refactor per checklist violations
   - Update documentation if needed

3. **Update documentation**
   - Add any missing details to README
   - Document any deviations from spec

4. **Prepare for production**
   - Add monitoring/observability hooks
   - Set up CI/CD pipeline
   - Create deployment guide

5. **Plan next phases**
   - If Phase 1-4 solid, begin Phase 5 (Comparison Engine)
   - Consider additional features from roadmap

---

## Appendix: Quick Command Reference

```bash
# Setup
git clone [repo] && cd pyedi-core-review
python -m venv venv && source venv/bin/activate
pip install -e .

# Run all tests
pytest -v

# Run specific test tier
pytest tests/unit/ -v
pytest tests/integration/ -v

# Coverage
pytest --cov=pyedi_core/core --cov-report=html

# Single file test
python main.py --config config/config.yaml --dry-run

# API server (Phase 3)
uvicorn api.app:app --reload

# Generate test data
python tests/generate_fixtures.py --format csv --count 100

# View outputs
cat outbound/*.json | jq '.'
cat failed/*.error.json | jq '.'
cat .processed

# Clean up
rm -rf outbound/* failed/* .processed logs/*
```

---

## Change Control

This section tracks all specification changes in reverse chronological order.

| Version | Date | Change Ref | Author | Summary |
|---|---|---|---|---|
| 1.2 | 2026-02-22 | PCR-2025-003 | Sean | Phase 5 test harness refactor |
| 1.1 | 2026-02-21 | PCR-2025-001, PCR-2025-002 | Sean | X12 ST inspection and CSV inbound_dir routing rules |
| 1.0 | 2026-02-21 | — | Sean | Initial specification |

---

### PCR-2025-003 — Phase 5 User-Supplied Test Harness Refactor
**Date:** 2026-02-22  
**Files Changed:**
- `tests/integration/test_user_supplied_data.py` — full rewrite
- `tests/user_supplied/metadata.yaml` — new fields added

**Changes:**

#### 1. `outputs/` directory — physical file writing
- A new `tests/user_supplied/outputs/` directory now receives the actual payload written by the test harness on every run.
- Actual output is **always written** — even when the comparison fails — so you can diff `outputs/` against `expected_outputs/` manually.
- The `outputs/` directory is **automatically cleared** before each test session (via a `session`-scoped autouse pytest fixture).

#### 2. Controlled baseline in `expected_outputs/`
- `expected_outputs/` is the **controlled, do-not-overwrite** baseline.
- Tests read both `outputs/<file>.json` (actual) and `expected_outputs/<file>.json` (expected) and compare them.
- Test authors must manually promote `outputs/` → `expected_outputs/` when they accept a new baseline.

#### 3. Per-test `dry_run` control
- `metadata.yaml` gains a `dry_run` boolean field (default: `true`).
- `dry_run: true` → pipeline returns in-memory payload; test serializes to `output_file`.
- `dry_run: false` → pipeline writes to filesystem; test still captures payload to `output_file`.
- The `00220261215033.dat` test case is set to `dry_run: false` (X12 handler writes natively).

#### 4. `skip_fields` — runtime-generated field exclusion
- `metadata.yaml` gains a `skip_fields` list (default: `[]`).
- Fields in `skip_fields` are excluded at **any nesting depth** during recursive comparison.
- Recommended default: `["id", "timestamp", "correlation_id", "_source_file"]`.

#### 5. Non-hard-failure discrepancy reporting
- Replaced `assert_output_matches` (which raised on first failure) with `compare_outputs` (which collects all discrepancies into a list).
- All discrepancies are printed as a **DISCREPANCY REPORT** block to stdout (use `pytest -s` to see them).
- File size differences > 1% are also included in the discrepancy list.
- `metadata.yaml` gains a `strict` boolean field (default: `true`):
  - `strict: true` → field discrepancies cause `pytest.fail()` (hard failure)
  - `strict: false` → field discrepancies emit `warnings.warn()` (test still passes)
  - Size differences are always non-fatal (warn only), regardless of `strict`.

#### 6. Direct X12Handler bypass for unmapped structural comparisons
- Test cases with `transaction_type: "x12"` and no `target_inbound_dir` bypass the full Pipeline and call `X12Handler.read()` directly.
- This supports raw structural comparison of X12 EDI files that have no active map.yaml routing.

#### 7. `output_file` is now a required field
- Each test case in `metadata.yaml` must now include an `output_file` key pointing to where the actual output should be written within `tests/user_supplied/`.
- Convention: output filename **must match input filename stem** (e.g., `inputs/foo.csv` → `outputs/foo.json`).

---

**End of Testing Specification**

This document should be updated as testing progresses and new findings emerge.
