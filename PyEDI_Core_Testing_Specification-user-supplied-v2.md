# PyEDI-Core Testing Specification
## Code Review & Validation Protocol

**Version:** 2.0
**Target:** Phase 1-5 Implementation
**Date:** February 22, 2026
**Spec Baseline:** PyEDI_Core_Specification_v2.3
**Purpose:** Systematic validation of PyEDI-Core implementation against specification

> **v2.0 Update Note:** This version adds verification for Fixed-Length positional file support (`FixedLengthHandler`), including `fixed_length_schema_registry` routing logic and multi-document invoice boundary segmentation tests. It builds upon the Phase 5 test harness refactor from v1.2.

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
- ✅ All four drivers (X12, CSV, XML, Fixed-Length) process fixture files successfully
- ✅ Error handling routes to `./failed/` with proper `.error.json` files
- ✅ `dry-run` mode validates without writing files
- ✅ Manifest deduplication works via SHA-256 hash
- ✅ PipelineResult model returns correct structure
- ✅ CSV routing uses `csv_schema_registry` `inbound_dir` discriminator
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
    "inbound/csv/gfs_ca"       # csv_schema_registry inbound_dir for GFS Canada 810
    "inbound/fixed/aramark_ca" # fixed_length_schema_registry inbound_dir
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
│   │   ├── NA_810_MARGINEDGE_20260129.txt  # Real MarginEdge TXT file
│   │   └── aramark_810_sample.txt       # Real Aramark Fixed-Length file
│   ├── expected_outputs/               # CONTROLLED baseline — do not overwrite manually
│   │   ├── 200220261215033.json
│   │   ├── UnivT701_small.json
│   │   ├── NA_810_MARGINEDGE_20260129.json
│   │   └── aramark_810_sample.json
│   ├── outputs/                        # GENERATED — cleared on every test run
│   │   ├── 200220261215033.json
│   │   ├── UnivT701_small.json
│   │   ├── NA_810_MARGINEDGE_20260129.json
│   │   └── aramark_810_sample.json
│   └── metadata.yaml                   # Describes each test case
```

#### metadata.yaml Format

Create a `tests/user_supplied/metadata.yaml` describing your test cases:

```yaml
# tests/user_supplied/metadata.yaml
test_cases:
  - name: "UnivT701 Demo Invoice CSV"
    input_file: "inputs/UnivT701_small.csv"
    output_file: "outputs/UnivT701_small.json"
    expected_output: "expected_outputs/UnivT701_small.json"
    should_succeed: true
    dry_run: true
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

  - name: "Aramark Fixed-Length 810"
    input_file: "inputs/aramark_810_sample.txt"
    output_file: "outputs/aramark_810_sample.json"
    expected_output: "expected_outputs/aramark_810_sample.json"
    should_succeed: true
    dry_run: true
    skip_fields: ["id", "timestamp", "correlation_id", "_source_file"]
    transaction_type: "810"
    target_inbound_dir: "./inbound/fixed/aramark_ca"
    description: "Verify processing of Aramark Fixed-Length file using Retalix-810-schema."

  - name: "x12 Data Comparison 200220261215033"
    input_file: "inputs/200220261215033.dat"
    output_file: "outputs/200220261215033.json"
    expected_output: "expected_outputs/200220261215033.json"
    should_succeed: true
    dry_run: false
    strict: false
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
| `target_inbound_dir` | string | ❌ | — | Directory to place file for `csv_schema_registry` or `fixed_length_schema_registry` routing |
| `expected_error_stage` | string | ❌ | — | Required when `should_succeed: false` |
| `description` | string | ❌ | — | Human-readable description of the test |

### Standard Test Data (Synthetic)

The following are **synthetic test files** for basic validation:

```
tests/
├── fixtures/
│   ├── x12/
│   │   ├── valid_810.edi
│   │   └── ...
│   ├── csv/
│   │   ├── valid_gfs_810.csv
│   │   └── ...
│   ├── fixed/
│   │   ├── valid_aramark_810.txt      # Valid Fixed-Length invoice
│   │   ├── short_record.txt           # Record shorter than expected ID length
│   │   └── unknown_record_type.txt    # File containing unmapped record types
│   └── xml/
│       ├── valid_cxml_850.xml
│       └── ...
├── expected_outputs/
│   ├── valid_810_expected.json
│   ├── valid_gfs_810_expected.json
│   └── valid_aramark_810_expected.json
└── schemas/
    └── source/
        ├── gfs_810_schema.txt         # DSL schema for CSV
        └── Retalix-810-schema.txt     # DSL schema for Fixed-Length
```

### Sample Test Data Specifications

#### 1. X12 EDI Valid Invoice (valid_810.edi)
*See v1.2 spec for details.*

#### 2. CSV Valid Invoice (valid_gfs_810.csv)
*See v1.2 spec for details.*

#### 3. Fixed-Length Valid Invoice (valid_aramark_810.txt)

> **Fixed-Length Routing:** Files must be placed in the `inbound_dir` registered in `fixed_length_schema_registry` (e.g., `./inbound/fixed/aramark_ca/`).

**Structure (Conceptual):**
```
OIN_HDR1  INV001    20250222...
OIN_DTL1  ITEM123   10        ...
OIN_DTL2  DESC      25.00     ...
OIN_TTL1  250.00    ...
```

**Expected Behavior:**
- `pipeline.py` matches file directory to `aramark_ca_810` registry entry via `inbound_dir`.
- `fixed_length_handler.py` reads the compiled YAML schema.
- Segments file into documents based on "invoice_boundary" record defined in schema.
- Maps fields using positional lengths from schema.
- Produces normalized JSON with envelope.

#### 4. cXML Valid Purchase Order (valid_cxml_850.xml)
*See v1.2 spec for details.*

---

## Phase 1: Core Engine Tests

### Test Suite: core/ Modules

*Tests for logger, manifest, error_handler, schema_compiler, mapper remain as defined in v1.2.*

#### 1.6 Driver Tests

**Test Files:**
- `tests/unit/test_x12_handler.py`
- `tests/unit/test_csv_handler.py`
- `tests/unit/test_xml_handler.py`
- `tests/unit/test_fixed_length_handler.py`

**Additional fixed_length_handler.py tests:**

```python
def test_fixed_length_routing_uses_inbound_dir():
    """Fixed-Length schema resolved by inbound_dir match in registry"""
    # Place file in ./inbound/fixed/aramark_ca/
    # Assert pipeline matches aramark_ca_810 entry
    # Assert correct compiled schema loaded

def test_fixed_length_invoice_boundary_segmentation():
    """Multi-invoice file segmented correctly by boundary record"""
    # Create file with 2 invoices (boundary record: OIN_HDR1)
    # Run read()
    # Assert returns list of 2 document dicts

def test_fixed_length_record_id_detection():
    """Record type detected by first N chars defined in schema"""
    # Schema defines record ID length = 10
    # Line: "OIN_HDR1  DATA..."
    # Assert detected type is "OIN_HDR1  "

def test_fixed_length_implied_decimal_conversion():
    """Implied decimal fields converted correctly"""
    # Field: "00012345", fractionalDigits=2
    # Assert converted to 123.45 float
```

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
  - `pipeline.py` matches incoming CSV files by directory
  - `csv_handler.py` receives compiled YAML path explicitly

- [ ] **Fixed-Length routing uses `fixed_length_schema_registry` inbound_dir**
  - `config.yaml` contains `fixed_length_schema_registry` block
  - `pipeline.py` matches incoming Fixed-Length files by directory
  - `fixed_length_handler.py` receives compiled YAML path explicitly

- [ ] **X12 routing delegated entirely to badx12 — no manual ST segment inspection**
  - `x12_handler.py` reads ST Transaction Set ID from badx12 parsed document object
  - `transaction_registry` comment in `config.yaml` reads `# X12 only — badx12 handles ST detection`
  - `_default_x12` fallback entry present

- [ ] **x12_handler.py input sanitization implemented**
  - ISA segment validated as 106 characters
  - Conditional newline stripping applied for non-newline-delimited EDI format

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
  - Valid files for each format (X12, CSV, XML, Fixed-Length)
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

## Change Control

| Version | Date | Change Ref | Author | Summary |
|---|---|---|---|---|
| 2.0 | 2026-02-22 | — | Sean | Added Fixed-Length verification support |
| 1.2 | 2026-02-22 | PCR-2025-003 | Sean | Phase 5 test harness refactor |
| 1.1 | 2026-02-21 | PCR-2025-001, PCR-2025-002 | Sean | X12 ST inspection and CSV inbound_dir routing rules |
| 1.0 | 2026-02-21 | — | Sean | Initial specification |

---

**End of Testing Specification**
