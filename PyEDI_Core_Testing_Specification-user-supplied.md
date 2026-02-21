# PyEDI-Core Testing Specification
## Code Review & Validation Protocol

**Version:** 1.0  
**Target:** Phase 1-4 Implementation  
**Date:** February 21, 2026  
**Purpose:** Systematic validation of PyEDI-Core implementation against specification

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
│   ├── README.md                      # Your documentation of what each file is
│   ├── inputs/
│   │   ├── production_810_sample.edi  # Real X12 invoice from production
│   │   ├── production_850_sample.edi  # Real X12 PO from production
│   │   ├── gfs_invoice_2025.csv       # Real CSV invoice
│   │   ├── partner_cxml_po.xml        # Real cXML from trading partner
│   │   └── edge_case_1.csv            # Known problematic file
│   ├── expected_outputs/
│   │   ├── production_810_sample.json # What you EXPECT output to be
│   │   ├── production_850_sample.json # What you EXPECT output to be
│   │   ├── gfs_invoice_2025.json      # What you EXPECT output to be
│   │   ├── partner_cxml_po.json       # What you EXPECT output to be
│   │   └── edge_case_1.json           # Expected output (or error)
│   └── metadata.yaml                  # Describes each test case
```

#### metadata.yaml Format

Create a `tests/user_supplied/metadata.yaml` describing your test cases:

```yaml
test_cases:
  - name: "Production 810 Invoice - January 2025"
    input_file: "inputs/production_810_sample.edi"
    expected_output: "expected_outputs/production_810_sample.json"
    should_succeed: true
    transaction_type: "810"
    description: "Real invoice from GFS, January 2025. Should process without errors."
    notes: "This file has all required fields and follows standard format."
    
  - name: "Edge Case - Missing PO Number"
    input_file: "inputs/edge_case_1.csv"
    expected_output: "expected_outputs/edge_case_1.json"
    should_succeed: false
    expected_error_stage: "VALIDATION"
    description: "CSV with missing required PO Number field."
    notes: "Should fail validation and route to ./failed/"
    
  - name: "Partner cXML Purchase Order"
    input_file: "inputs/partner_cxml_po.xml"
    expected_output: "expected_outputs/partner_cxml_po.json"
    should_succeed: true
    transaction_type: "850"
    description: "Real cXML from trading partner XYZ Corp."
    notes: "Uses non-standard nested structure in ItemOut elements."
```

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

**Structure:**
```csv
Invoice Number,Invoice Date,PO Number,Item Number,Description,Quantity,Unit Price,Net Case Price,Extended Price
INV001,02/21/2025,PO001,12345,Sample Item,10,25.00,24.00,240.00
INV001,02/21/2025,PO001,67890,Another Item,5,50.00,48.00,240.00
```

**Expected Behavior:**
- Triggers `schema_compiler.py` check
- Compiles or loads `gfs_810_map.yaml`
- Validates data types (dates, floats)
- Maps to `lines[]` array in JSON

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

### Test Suite: User-Supplied Data Validation

**Test File:** `tests/integration/test_user_supplied_data.py`

This test suite validates your real-world production data against your expected outputs.

```python
import pytest
import yaml
import json
from pathlib import Path
from pyedi_core import Pipeline

# Load user-supplied test cases
def load_test_cases():
    """Load test cases from metadata.yaml"""
    metadata_path = Path('tests/user_supplied/metadata.yaml')
    if not metadata_path.exists():
        pytest.skip("No user-supplied test data found")
    
    with open(metadata_path) as f:
        metadata = yaml.safe_load(f)
    
    return metadata['test_cases']

@pytest.mark.parametrize("test_case", load_test_cases())
def test_user_supplied_file(test_case):
    """Test each user-supplied file against expected output"""
    
    # Setup
    input_path = Path('tests/user_supplied') / test_case['input_file']
    expected_path = Path('tests/user_supplied') / test_case['expected_output']
    
    pipeline = Pipeline(config_path='./config/config.yaml')
    
    # Run pipeline
    result = pipeline.run(file=str(input_path), return_payload=True)
    
    # Validate success/failure expectation
    if test_case['should_succeed']:
        assert result.status == 'SUCCESS', \
            f"Expected success but got {result.status}. Errors: {result.errors}"
        
        # Load expected output
        with open(expected_path) as f:
            expected = json.load(f)
        
        # Compare actual vs expected
        assert_output_matches(result.payload, expected, test_case['name'])
        
    else:
        # Should fail
        assert result.status == 'FAILED', \
            f"Expected failure but got {result.status}"
        
        # Check error stage if specified
        if 'expected_error_stage' in test_case:
            error_json_path = Path('./failed') / f"{input_path.stem}.error.json"
            assert error_json_path.exists(), "No error.json found"
            
            with open(error_json_path) as f:
                error_data = json.load(f)
            
            assert error_data['stage'] == test_case['expected_error_stage'], \
                f"Expected error at {test_case['expected_error_stage']} " \
                f"but got {error_data['stage']}"

def assert_output_matches(actual, expected, test_name):
    """Deep comparison of actual vs expected output"""
    
    # Compare envelope
    assert actual['envelope']['schema_version'] == expected['envelope']['schema_version']
    assert actual['envelope']['transaction_type'] == expected['envelope']['transaction_type']
    assert actual['envelope']['input_format'] == expected['envelope']['input_format']
    # Note: Don't compare UUIDs and timestamps as they're generated
    
    # Compare payload structure
    assert set(actual['payload'].keys()) == set(expected['payload'].keys()), \
        f"Payload keys don't match for {test_name}"
    
    # Compare header
    if 'header' in expected['payload']:
        assert_dict_matches(
            actual['payload']['header'],
            expected['payload']['header'],
            f"{test_name} header"
        )
    
    # Compare lines
    if 'lines' in expected['payload']:
        assert len(actual['payload']['lines']) == len(expected['payload']['lines']), \
            f"Line count mismatch for {test_name}"
        
        for i, (actual_line, expected_line) in enumerate(
            zip(actual['payload']['lines'], expected['payload']['lines'])
        ):
            assert_dict_matches(
                actual_line,
                expected_line,
                f"{test_name} line {i}"
            )
    
    # Compare summary
    if 'summary' in expected['payload']:
        assert_dict_matches(
            actual['payload']['summary'],
            expected['payload']['summary'],
            f"{test_name} summary"
        )

def assert_dict_matches(actual, expected, context):
    """Compare two dicts with helpful error messages"""
    for key, expected_value in expected.items():
        assert key in actual, f"Missing key '{key}' in {context}"
        
        actual_value = actual[key]
        
        # Handle numeric comparisons with tolerance
        if isinstance(expected_value, (int, float)) and isinstance(actual_value, (int, float)):
            assert abs(actual_value - expected_value) < 0.01, \
                f"Value mismatch for '{key}' in {context}: " \
                f"expected {expected_value}, got {actual_value}"
        else:
            assert actual_value == expected_value, \
                f"Value mismatch for '{key}' in {context}: " \
                f"expected {expected_value}, got {actual_value}"
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

When a user-supplied test fails, the error message will tell you:
1. **Which test case failed** (name from metadata.yaml)
2. **What was different** (specific field and values)
3. **Where to find the actual output** (./outbound/ directory)

**Common failure reasons:**
- Expected output has wrong format (check JSON syntax)
- Expected output doesn't match map.yaml rules
- Input file has data your expected output doesn't account for
- Numeric precision differences (cents vs dollars)

**How to fix:**
1. Check the actual output: `cat outbound/{filename}.json | jq '.'`
2. Compare to your expected: `cat tests/user_supplied/expected_outputs/{filename}.json | jq '.'`
3. Update your expected output OR fix your map.yaml if the actual output is wrong

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
    """Valid CSV → success output"""
    # Run pipeline on valid_gfs_810.csv
    # Assert schema compiled
    # Assert output JSON matches expected

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
    """Unknown X12 transaction → default_x12_map.yaml"""
    # Run pipeline on unknown_transaction.edi
    # Assert processed via fallback
    # Assert WARNING log emitted

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

**End of Testing Specification**

This document should be updated as testing progresses and new findings emerge.
