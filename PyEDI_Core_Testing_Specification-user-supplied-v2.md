# PyEDI-Core Testing Specification
## Code Review & Validation Protocol

**Version:** 2.0
**Target:** Phase 1-5 Implementation
**Date:** February 22, 2026
**Spec Baseline:** PyEDI_Core_Specification_v2.3
**Purpose:** Systematic validation of PyEDI-Core implementation against specification

> **v2.0 Update Note:** This version adds comprehensive testing strategies for the Fixed-Length Handler (Driver D), including schema-driven parsing, type conversion tests, and `fixed_length_schema_registry` routing verification. It also reflects the v2.3 Core Specification.

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
- ✅ X12 routing relies on badx12 envelope parsing

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
    "inbound/csv/gfs_ca"
    "inbound/fixed/aramark_ca" # fixed_length_schema_registry inbound_dir for Aramark
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
    "pyedi_core/drivers/fixed_length_handler.py" # Driver D
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
│   │   └── aramark_invoice.txt          # Real Aramark Fixed-Length file
│   ├── expected_outputs/               # CONTROLLED baseline — do not overwrite manually
│   │   ├── 200220261215033.json
│   │   ├── UnivT701_small.json
│   │   ├── NA_810_MARGINEDGE_20260129.json
│   │   └── aramark_invoice.json
│   ├── outputs/                        # GENERATED — cleared on every test run
│   │   ├── 200220261215033.json        # Actual pipeline output
│   │   ├── UnivT701_small.json
│   │   ├── NA_810_MARGINEDGE_20260129.json
│   │   └── aramark_invoice.json
│   └── metadata.yaml                   # Describes each test case
```

#### metadata.yaml Format

```yaml
# tests/user_supplied/metadata.yaml
test_cases:
  # ... existing cases ...

  - name: "Aramark Fixed Length Invoice"
    input_file: "inputs/aramark_invoice.txt"
    output_file: "outputs/aramark_invoice.json"
    expected_output: "expected_outputs/aramark_invoice.json"
    should_succeed: true
    dry_run: true
    skip_fields: ["id", "timestamp", "correlation_id", "_source_file"]
    transaction_type: "aramark_ca_810"
    target_inbound_dir: "./inbound/fixed/aramark_ca"
    description: "Verify processing of Aramark fixed-length file."
```

### Standard Test Data (Synthetic)

The following are **synthetic test files** for basic validation:

```
tests/
├── fixtures/
│   ├── fixed/
│   │   ├── valid_aramark.txt          # Valid fixed-length file
│   │   ├── short_line.txt             # Line shorter than record ID
│   │   └── unknown_record.txt         # Unmapped record type
# ... other fixtures ...
```

### Sample Test Data Specifications

#### 5. Fixed-Length Valid Invoice (valid_aramark.txt)

**Structure:**
(Uses positional columns defined in `schemas/source/Retalix-810-schema.txt`)

```text
O_TPID    SENDER    RECEIVER  20250222
TPM_HDR   INV001    20250222  PO001
OIN_DTL1  ITEM001   Desc      10   2500
OIN_TTL1  25000     1
```

**Expected Behavior:**
- `pipeline.py` scans `fixed_length_schema_registry` and matches the file's directory to `aramark_ca_810`.
- Uses compiled YAML schema to parse fixed-length records.
- Converts types (e.g., `2500` -> `25.00` implied decimal).
- Groups records into hierarchical structure (Header/Lines/Summary).
- Maps to standard JSON output.

---

## Phase 1: Core Engine Tests

### Test Suite: core/ Modules
*See v1.2 specification for core module tests (logger, manifest, error_handler, schema_compiler, mapper).*

### 1.6 Driver Tests (Existing)
*See v1.2 specification for X12, CSV, and XML driver tests.*

### 1.7 Fixed-Length Handler Tests (New)

**Test File:** `tests/unit/test_fixed_length_handler.py`

```python
def test_read_parses_positional_records():
    """read() parses lines based on compiled schema lengths"""
    # Provide compiled schema with record definitions
    # Provide file content
    # Assert records parsed correctly with field values extracted

def test_multi_document_segmentation():
    """File with multiple invoices is split into multiple documents"""
    # Provide file with 2 invoices (based on group_on_record trigger)
    # Assert read() returns list of 2 documents

def test_type_conversion_implied_decimal():
    """transform() converts implied decimals correctly"""
    # Input: "000009942" with fractionalDigits=2
    # Assert Output: 99.42 (float)

def test_type_conversion_integer():
    """transform() converts integers correctly"""
    # Input: "000010"
    # Assert Output: 10 (int)

def test_registry_routing():
    """Pipeline routes to FixedLengthHandler based on inbound_dir"""
    # Place file in ./inbound/fixed/aramark_ca/
    # Assert schema loaded from registry
    # Assert processing succeeds

def test_unmapped_record_warning():
    """Unknown record types log warning but do not crash"""
    # Provide file with unknown record ID
    # Assert WARNING log "UNMAPPED_RECORD"
    # Assert valid records still processed
```

---

## Code Review Checklist

### Architecture Compliance
*   [ ] **Fixed-Length routing uses `fixed_length_schema_registry` inbound_dir**
    *   `config.yaml` contains `fixed_length_schema_registry`.
    *   `pipeline.py` matches incoming files by directory against registry.
    *   `fixed_length_handler.py` relies on schema for parsing — NO hardcoded positions.

### Module Isolation
*   [ ] **FixedLengthHandler implements AbstractTransactionProcessor**
    *   `read()`, `transform()`, `write()` implemented.
    *   Imports `TransactionProcessor` from `drivers.base`.

---

## Change Control

This section tracks all specification changes in reverse chronological order.

| Version | Date | Change Ref | Author | Summary |
|---|---|---|---|---|
| 2.0 | 2026-02-22 | PCR-2025-004 | Jules | Fixed-Length Handler support (Driver D) |
| 1.2 | 2026-02-22 | PCR-2025-003 | Sean | Phase 5 test harness refactor |
| 1.1 | 2026-02-21 | PCR-2025-001, PCR-2025-002 | Sean | X12 ST inspection and CSV inbound_dir routing rules |
| 1.0 | 2026-02-21 | — | Sean | Initial specification |

---

### PCR-2025-004 — Fixed-Length Handler Support (Driver D)
**Date:** 2026-02-22
**Files Changed:**
- `Pyedi core specification v2.3.md` (Updated from v1.0/v2.1)
- `PyEDI_Core_Testing_Specification-user-supplied-v2.md` (Updated from v1.2)

**Changes:**
#### 1. Fixed-Length Driver
- Added `fixed_length_handler.py` to support positional flat files.
- Uses `fixed_length_schema_registry` in `config.yaml` for routing.
- Purely schema-driven parsing (YAML compiled from DSL).
- Support for implied decimals and integer type conversions.

#### 2. Test Coverage
- Added unit tests for `fixed_length_handler.py`.
- Added integration tests for directory-based routing.
- Added synthetic test fixtures for fixed-length files.

---

**End of Testing Specification**
