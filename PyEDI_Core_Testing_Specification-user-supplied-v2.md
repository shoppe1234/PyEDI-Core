# PyEDI-Core Testing Specification
## Code Review & Validation Protocol

**Version:** 2.0
**Target:** Phase 1-5 Implementation
**Date:** February 22, 2026
**Spec Baseline:** PyEDI Core Specification v2.3
**Purpose:** Systematic validation of PyEDI-Core implementation against specification

> **v2.0 Update Note:** This version incorporates testing requirements for the new Fixed-Length Positional File driver (Driver D), including schema registry validation, multi-document segmentation testing, and implied decimal type conversion.

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
- ✅ All drivers (X12, CSV, XML, Fixed-Length) process fixture files successfully
- ✅ Error handling routes to `./failed/` with proper `.error.json` files
- ✅ `dry-run` mode validates without writing files
- ✅ Manifest deduplication works via SHA-256 hash
- ✅ PipelineResult model returns correct structure
- ✅ CSV routing uses `csv_schema_registry` `inbound_dir` discriminator — schema never inferred from filename or extension alone
- ✅ Fixed-Length routing uses `fixed_length_schema_registry` `inbound_dir` discriminator
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
    "inbound/csv/gfs_ca"       # csv_schema_registry inbound_dir example
    "inbound/fixed/aramark_ca" # fixed_length_schema_registry inbound_dir example
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
    "pyedi_core/drivers/fixed_length_handler.py"
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

  - name: "Fixed Length Aramark Test"
    input_file: "inputs/aramark_test.txt"
    output_file: "outputs/aramark_test.json"
    expected_output: "expected_outputs/aramark_test.json"
    should_succeed: true
    dry_run: true
    transaction_type: "810"
    target_inbound_dir: "./inbound/fixed/aramark_ca"
    description: "Verify processing of Fixed-Length positional file"
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
│   ├── xml/
│   │   ├── valid_cxml_850.xml         # Valid cXML purchase order
│   │   ├── valid_generic.xml          # Generic XML format
│   │   ├── malformed.xml              # Broken XML structure
│   │   └── duplicate_cxml_850.xml     # Exact copy of valid_cxml_850.xml
│   ├── fixed/
│   │   ├── valid_aramark_810.txt      # Valid Fixed-Length invoice
│   │   ├── truncated_line.txt         # Line too short
│   │   └── bad_encoding.txt           # Non-UTF-8 characters
└── expected_outputs/
    ├── valid_810_expected.json
    ├── valid_gfs_810_expected.json
    ├── valid_cxml_850_expected.json
    ├── valid_generic_expected.json
    └── valid_aramark_810_expected.json
```

---

## Phase 1: Core Engine Tests

### Test Suite: core/ Modules

#### 1.1 logger.py Tests
(Same as v1 - omitted for brevity)

#### 1.2 manifest.py Tests
(Same as v1 - omitted for brevity)

#### 1.3 error_handler.py Tests
(Same as v1 - omitted for brevity)

#### 1.4 schema_compiler.py Tests
(Same as v1 - omitted for brevity)

#### 1.5 mapper.py Tests
(Same as v1 - omitted for brevity)

#### 1.6 Driver Tests

**Test Files:**
- `tests/unit/test_x12_handler.py`
- `tests/unit/test_csv_handler.py`
- `tests/unit/test_xml_handler.py`
- `tests/unit/test_fixed_length_handler.py`

Each driver test should verify `read()`, `transform()`, `write()`, and error handling.

**Additional fixed_length_handler.py tests (New in v2.0):**

```python
def test_fixed_length_read_parsing():
    """read() parses positional data using compiled schema"""
    # Provide fixed-length file
    # Provide mock compiled schema
    # Assert records parsed correctly based on field positions/lengths

def test_fixed_length_multi_document_segmentation():
    """Splits multiple invoices based on schema boundary record"""
    # Provide file with 2 invoices (header-lines-summary, header-lines-summary)
    # Assert 2 distinct documents returned

def test_fixed_length_implied_decimal():
    """Converts implied decimals (e.g. 001250 -> 12.50)"""
    # Test field with type 'implied_decimal' and fractionalDigits=2
    # Assert conversion correct

def test_fixed_length_routing_via_registry():
    """Routes by inbound_dir match in fixed_length_schema_registry"""
    # Place file in ./inbound/fixed/aramark_ca/
    # Assert correct schema loaded
```

### Test Suite: User-Supplied Data Validation
(Same as v1 - omitted for brevity)

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

- [ ] **CSV routing uses `csv_schema_registry` inbound_dir — never filename inference**
  - `config.yaml` contains `csv_schema_registry` block
  - Routing matches directory path
  - No silent schema guessing

- [ ] **Fixed-Length routing uses `fixed_length_schema_registry` inbound_dir**
  - `config.yaml` contains `fixed_length_schema_registry` block
  - Routing matches directory path
  - No hardcoded field lengths in Python (all schema-driven)

- [ ] **X12 routing delegated entirely to badx12**
  - `x12_handler.py` reads ST Transaction Set ID from badx12 parsed object
  - No manual ST segment text inspection

### Module Isolation

- [ ] **Each core/ module independently testable**
- [ ] **Drivers implement AbstractTransactionProcessor**
- [ ] **No circular dependencies**

### Testing Coverage

- [ ] **Unit tests for all core/ modules**
- [ ] **Integration tests with fixtures** (X12, CSV, XML, Fixed)
- [ ] **Coverage >= 85% on core/**

### Error Handling

- [ ] **All failures route to ./failed/**
- [ ] **.error.json sidecar created**
- [ ] **Manifest updated with FAILED status**

### Output Correctness

- [ ] **Envelope structure correct**
- [ ] **Payload structure correct**
- [ ] **Output files JSON parseable**

---

## Test Execution Plan

### Phase 1: Static Review (1-2 hours)
1. Clone repository & Review directory structure
2. Check code against checklist
3. Document findings

### Phase 2: Unit Tests (2-3 hours)
1. Run pytest on unit tests: `pytest tests/unit/ -v`
2. Generate coverage report
3. Review coverage and document failures

### Phase 3: Integration Tests (2-3 hours)
1. Set up user-supplied test data
2. Run user-supplied data tests: `pytest tests/integration/test_user_supplied_data.py`
3. Run standard integration tests: `pytest tests/integration/`
4. Test dry-run mode & duplicate detection

### Phase 4: Library Interface (1 hour)
(Same as v1)

### Phase 5: API Tests (Phase 3 only, 1-2 hours)
(Same as v1)

---

## Change Control

This section tracks all specification changes in reverse chronological order.

| Version | Date | Change Ref | Author | Summary |
|---|---|---|---|---|
| 2.0 | 2026-02-22 | PCR-2025-004 | Jules | Added Fixed-Length File support (Driver D) |
| 1.2 | 2026-02-22 | PCR-2025-003 | Sean | Phase 5 test harness refactor |
| 1.1 | 2026-02-21 | PCR-2025-001, PCR-2025-002 | Sean | X12 ST inspection and CSV inbound_dir routing rules |
| 1.0 | 2026-02-21 | — | Sean | Initial specification |
