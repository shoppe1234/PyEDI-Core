# PyEDI-Core Testing Specification
## Code Review & Validation Protocol

**Version:** 2.0
**Target:** Phase 1-5 Implementation
**Date:** February 22, 2026
**Spec Baseline:** PyEDI_Core_Specification_v2.3
**Purpose:** Systematic validation of PyEDI-Core implementation against specification

> **v2.0 Update Note:** This version incorporates validation for the new **Fixed-Length Handler (Driver D)**. It includes unit tests for positional parsing, invoice boundary detection, and implied decimal conversion, as well as integration tests for `fixed_length_schema_registry` routing.

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

Before running tests, create a `tests/user_supplied/` directory and place your real-world files there.

#### metadata.yaml Format

Create a `tests/user_supplied/metadata.yaml` describing your test cases. Add Fixed-Length test cases as needed.

```yaml
# tests/user_supplied/metadata.yaml
test_cases:
  - name: "Aramark CA Fixed Length Invoice"
    input_file: "inputs/aramark_810_sample.txt"
    output_file: "outputs/aramark_810_sample.json"
    expected_output: "expected_outputs/aramark_810_sample.json"
    should_succeed: true
    transaction_type: "810"
    target_inbound_dir: "./inbound/fixed/aramark_ca"
    description: "Verify processing of Aramark Fixed-Length file."
```

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
│   │   ├── valid_aramark_810.txt      # Valid Fixed-Length file
│   │   ├── malformed_record.txt       # Record too short
│   │   └── unknown_record.txt         # Unknown record ID
│   └── xml/
│       ├── valid_cxml_850.xml
│       └── ...
└── schemas/
    └── source/
        ├── gfs_810_schema.txt         # DSL for CSV
        └── Retalix-810-schema.txt     # DSL for Fixed-Length
```

### Sample Test Data Specifications

#### 5. Fixed-Length Valid Invoice (valid_aramark_810.txt)

**Expected Behavior:**
- `pipeline.py` matches directory `./inbound/fixed/aramark_ca/` to `aramark_ca_810` entry in `fixed_length_schema_registry`.
- Compiles `Retalix-810-schema.txt`.
- Parses positional records.
- Detects invoice boundaries using `group_on_record`.
- Handles implied decimals (e.g., "0012345" -> 123.45).
- Produces normalized JSON using `rules/aramark_ca_810_map.yaml`.

---

## Phase 1: Core Engine Tests

### Test Suite: core/ Modules

(Logger, Manifest, Error Handler, Schema Compiler, Mapper tests remain the same as v1.2)

#### 1.6 Driver Tests

**Test Files:**
- `tests/unit/test_x12_handler.py`
- `tests/unit/test_csv_handler.py`
- `tests/unit/test_xml_handler.py`
- `tests/unit/test_fixed_length_handler.py`

**Additional fixed_length_handler.py tests:**

```python
def test_fixed_length_routing_uses_inbound_dir():
    """Fixed-Length schema is resolved by inbound_dir match in registry"""
    # Place valid_aramark_810.txt in ./inbound/fixed/aramark_ca/
    # Assert pipeline matches aramark_ca_810 entry

def test_positional_parsing_from_schema():
    """Records are parsed using start/length from compiled schema"""
    # Provide sample line and compiled schema
    # Assert fields extracted correctly

def test_invoice_boundary_detection():
    """Multi-document files split correctly based on schema boundary trigger"""
    # Provide file with 2 invoices
    # Assert read() returns 2 documents

def test_implied_decimal_conversion():
    """Implied decimal fields converted correctly"""
    # Input: "0012345" with fractionalDigits=2
    # Assert Output: 123.45 (float)

def test_read_empty_as_null():
    """Fields with readEmptyAsNull=true return None for empty strings"""
    # Input: "   "
    # Assert Output: None (not "")
```

---

## Code Review Checklist

### Architecture Compliance

- [ ] **No hardcoded transaction logic in .py files**
  - All transaction types in `config.yaml` registry only

- [ ] **Fixed-Length Routing via Registry**
  - `config.yaml` contains `fixed_length_schema_registry` block.
  - `pipeline.py` routes by `inbound_dir`.
  - `fixed_length_handler.py` uses compiled schema for parsing.

- [ ] **CSV routing uses `csv_schema_registry` inbound_dir**
  - No filename inference.

### Module Isolation

- [ ] **Drivers implement AbstractTransactionProcessor**
  - `fixed_length_handler.py` implements read/transform/write.

### Testing Coverage

- [ ] **Unit tests for all drivers including Fixed-Length**
- [ ] **Integration tests cover all formats**

---

## Test Execution Plan

### Phase 1: Static Review

1. Verify directory structure includes `pyedi_core/drivers/fixed_length_handler.py`.
2. Verify `config/config.yaml` has `fixed_length_schema_registry`.

### Phase 2: Unit Tests

1. Run unit tests:
   ```bash
   pytest tests/unit/test_fixed_length_handler.py -v
   ```

### Phase 3: Integration Tests

1. Run end-to-end tests:
   ```bash
   pytest tests/integration/test_pipeline_end_to_end.py -v
   ```
2. Verify Fixed-Length processing using `tests/user_supplied/` if data available.

(Rest of the plan remains similar to v1.2)

---

## Change Control

| Version | Date | Change Ref | Author | Summary |
|---|---|---|---|---|
| 2.0 | 2026-02-22 | PCR-2025-004 | Jules | Added Fixed-Length Handler validation |
| 1.2 | 2026-02-22 | PCR-2025-003 | Sean | Phase 5 test harness refactor |
| 1.1 | 2026-02-21 | PCR-2025-001, PCR-2025-002 | Sean | X12 ST inspection and CSV inbound_dir routing rules |
| 1.0 | 2026-02-21 | — | Sean | Initial specification |

---

**End of Testing Specification**
