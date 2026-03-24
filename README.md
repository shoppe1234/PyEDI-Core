# PyEDI-Core

**Configuration-driven EDI, CSV, and XML processing engine**

---

## A Day in the Life with PyEDI-Core

### 🌅 Morning: Your EDI Files Arrive

It's 8:00 AM and overnight batch jobs have dropped EDI 850 (Purchase Orders) and CSV invoices into your inbound directory:

```
inbound/
├── PO_850_001.x12
├── PO_850_002.x12
├── invoice_batch.csv
└── vendor_xml.xml
```

### ☕ 9:00 AM: Process Files with One Command

With PyEDI-Core, processing is effortless:

```bash
# Process all inbound files
pyedi --config config/config.yaml

# Or process a single file
pyedi --file inbound/PO_850_001.x12 --config config/config.yaml

# Test transformations without writing output
pyedi --file inbound/invoice_batch.csv --dry-run
```

### 📋 What Happens Automatically

PyEDI-Core orchestrates the entire pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│                     PyEDI-Core Pipeline                     │
├─────────────────────────────────────────────────────────────┤
│  1. DETECTION    → Scans inbound directory                │
│  2. DEDUPE       → Checks manifest (SHA-256)              │
│  3. READ         → CSV/X12/XML driver parses file          │
│  4. VALIDATE     → Schema validation                       │
│  5. TRANSFORM    → YAML mapping rules apply               │
│  6. WRITE        → JSON output to outbound                 │
│  7. MANIFEST     → Marks file as processed                │
└─────────────────────────────────────────────────────────────┘
```

### 🔄 10:30 AM: Review Transformed Output

The pipeline transforms your legacy formats to modern JSON:

**Input (CSV):**
```csv
Invoice Number,Invoice Date,Net Case Price,Item Number,Quantity
INV-001,01/15/2025,100.50,ITEM-001,5
```

**Output (JSON):**
```json
{
  "header": {
    "invoice_number": "INV-001",
    "invoice_date": "2025-01-15",
    "total_amount": 100.50
  },
  "lines": [
    {
      "item_id": "ITEM-001",
      "quantity": 5,
      "line_total": 502.50
    }
  ]
}
```

### 🛠️ 2:00 PM: Add a New Transaction Type

Need to support a new trading partner? Just add a YAML mapping rule:

```yaml
# rules/partner_850_map.yaml
transaction_type: "850_PO"
input_format: "x12"
mapping:
  header:
    po_number:
      source: "BEG.3"
      transform: "strip"
    order_date:
      source: "DTM.2"
      transform: "to_date"
  lines:
    - line_number:
        source: "PO1.1"
      quantity:
        source: "PO1.2"
        transform: "to_int"
```

Register in config.yaml:
```yaml
transaction_registry:
  partner_850: ./rules/partner_850_map.yaml
```

### 🐛 4:00 PM: Debug Failed Files

When something goes wrong, PyEDI-Core handles it gracefully:

```bash
# Check failed directory
ls failed/

# Review error details
cat failed/PO_850_001.error.json
```

Error output includes:
- Stage where failure occurred
- Correlation ID for tracing
- Exception details
- Timestamp

### 🌙 Evening: Batch Processing

Schedule automated processing via cron or Windows Task Scheduler:

```bash
# Run every hour
0 * * * * pyedi --config /etc/pyedi/config.yaml

# Or Windows Task Scheduler
schtasks /create /tn "PyEDI Processor" /tr "pyedi --config config.yaml" /sc hourly
```

---

## Quick Start

### Installation

```bash
# Clone and install
git clone https://github.com/yourorg/pyedi-core.git
cd pyedi-core
pip install -e .

# Or from PyPI (when published)
pip install pyedi-core
```

### Configuration

Edit `config/config.yaml`:

```yaml
system:
  source_system_id: my_company
  max_workers: 8
  dry_run: false
  return_payload: false

observability:
  log_level: INFO
  output: console
  format: pretty

directories:
  inbound:
    - ./inbound/x12
    - ./inbound/csv
    - ./inbound/xml
  outbound: ./outbound
  failed: ./failed
  processed: ./.processed

transaction_registry:
  '810': ./rules/gfs_810_map.yaml
  '850': ./rules/gfs_850_map.yaml
  '856': ./rules/gfs_856_map.yaml
  gfs_csv: ./rules/gfs_csv_map.yaml
  cxml_850: ./rules/cxml_850_map.yaml
  _default_x12: ./rules/default_x12_map.yaml
  _rules_dir: ./rules

csv_schema_registry:
  margin_edge_810:
    source_dsl: ./tpm810SourceFF.txt
    compiled_output: ./schemas/compiled/margin_edge_810_map.yaml
    inbound_dir: ./inbound/csv/margin_edge
    transaction_type: '810'
  gfs_ca_810:
    source_dsl: ./schemas/source/gfsGenericOut810FF.txt
    compiled_output: ./schemas/compiled/gfs_ca_810_map.yaml
    inbound_dir: ./inbound/csv/gfs_ca
    transaction_type: '810'
```

### Run

```bash
# Process all files
pyedi

# Single file
pyedi --file data/input.csv

# Dry run (validate only)
pyedi --dry-run --file data/input.csv

# Verbose logging
pyedi --verbose --file data/input.csv
```

### Validate DSL Schemas

The `validate` subcommand compiles a DSL schema, inspects the output, and optionally traces mappings against a sample file:

```bash
# Compile and inspect a DSL file
pyedi validate --dsl tpm810SourceFF.txt

# Validate with a sample data file (shows mapping coverage + field traces)
pyedi validate --dsl tpm810SourceFF.txt --sample data/sample.txt

# Machine-readable JSON output
pyedi validate --dsl tpm810SourceFF.txt --json

# Verbose mode (all columns + all field traces)
pyedi validate --dsl tpm810SourceFF.txt --sample data/sample.txt --verbose
```

### Web Portal

PyEDI Portal provides a FastAPI backend + React frontend for browser-based access to all CLI features:

```bash
# Development mode (API on :8000, Vite on :5173)
bash portal/dev.sh

# Production mode (serves static build from FastAPI)
cd portal/ui && npm run build
PYTHONPATH=. uvicorn portal.api.app:app --port 8000
```

Portal pages: Dashboard, Schema Validation, Pipeline Results, Test Harness, Compare, Configuration.

### Compare Source vs Target Outputs

The `compare` subcommand pairs source and target JSON outputs by a configurable match key, then compares them field-by-field with per-profile rules:

```bash
# List available profiles
pyedi compare --list-profiles

# Compare 810 invoices between two directories
pyedi compare --profile 810_invoice --source-dir /path/to/source --target-dir /path/to/target

# Verbose mode (show per-field diffs)
pyedi compare --profile 810_invoice --source-dir src/ --target-dir tgt/ --verbose

# Export results to CSV
pyedi compare --profile 810_invoice --source-dir src/ --target-dir tgt/ --export-csv
```

Profiles are defined in `config/config.yaml` under `compare.profiles`. Each profile specifies a match key (e.g., `BIG:BIG02` for 810 invoices), segment qualifiers, and a rules YAML file. Adding a new transaction type is a config change — no code changes required.

Built-in profiles: `810_invoice`, `850_purchase_order`, `856_asn`, `820_payment`, `csv_generic`, `cxml_generic`.

Results are stored in SQLite (`data/compare.db`) and queryable from both CLI and portal.

---

## Supported Formats

| Format | Extension | Driver |
|--------|-----------|--------|
| CSV | .csv | CSVHandler |
| X12 EDI | .x12, .edi | X12Handler |
| XML | .xml | XMLHandler |
| cXML | .cxml | XMLHandler |

---

## Architecture

```
pyedi_core/
├── __init__.py
├── main.py              # CLI entry point (pyedi run/test/validate/compare)
├── pipeline.py          # Orchestration engine
├── test_harness.py      # Test harness (pyedi test)
├── validator.py         # DSL validation, trace, coverage (pyedi validate)
├── comparator/          # Compare engine (pyedi compare)
│   ├── __init__.py      # Public API: compare(), export_csv(), load/list_profiles()
│   ├── models.py        # Dataclasses: MatchPair, FieldDiff, CompareResult, RunSummary
│   ├── rules.py         # YAML rule loading + wildcard resolution
│   ├── matcher.py       # File pairing + transaction extraction
│   ├── engine.py        # Segment matching + field comparison
│   └── store.py         # SQLite CRUD for runs/pairs/diffs
├── config/
│   └── __init__.py      # Pydantic config models
├── core/                # Core processing modules
│   ├── __init__.py
│   ├── error_handler.py # Dead-letter queue + typed exceptions
│   ├── logger.py        # Structured logging (structlog)
│   ├── manifest.py      # SHA-256 deduplication
│   ├── mapper.py        # Data transformation engine
│   └── schema_compiler.py # DSL → YAML compiler (parse_dsl_file, compile_dsl)
├── drivers/             # Format-specific handlers
│   ├── __init__.py
│   ├── base.py          # Driver registry & abstract base
│   ├── csv_handler.py
│   ├── x12_handler.py
│   └── xml_handler.py
├── rules/               # YAML mapping rules
portal/                  # Web portal (FastAPI + React)
├── api/
│   ├── app.py           # FastAPI app factory + static serving
│   ├── models.py        # Pydantic request/response models
│   └── routes/          # validate, pipeline, test, manifest, config, compare
├── ui/                  # React + Vite + Tailwind frontend
│   └── src/pages/       # Dashboard, Validate, Pipeline, Tests, Compare, Config
├── tests/
│   ├── test_compare_api.py  # Compare API integration tests
│   └── e2e/                 # Playwright E2E browser tests (29 tests)
│       ├── conftest.py      # Server lifecycle, test data fixtures
│       ├── pages/           # Page objects (base, dashboard, validate, etc.)
│       ├── test_navigation.py
│       ├── test_dashboard.py
│       ├── test_validate.py
│       ├── test_pipeline.py
│       ├── test_tests.py
│       ├── test_config.py
│       └── test_compare.py  # 14 tests — full compare workflow
├── dev.sh               # Dev startup script (API + Vite)
└── pyproject.toml
config/
├── config.yaml          # Runtime configuration (incl. compare profiles)
└── compare_rules/       # Per-profile comparison rules YAMLs
    ├── 810_invoice.yaml
    ├── 850_po.yaml
    ├── 856_asn.yaml
    ├── 820_payment.yaml
    ├── csv_generic.yaml
    └── cxml_generic.yaml
data/
└── compare.db           # SQLite database (compare run history)
schemas/
├── source/              # DSL source files
└── compiled/            # Compiled YAML maps + meta.json
tests/
├── conftest.py          # Shared fixtures, singleton resets
├── test_core.py         # Unit: logger, manifest, error_handler, schema, mapper
├── test_core_extended.py # Unit: extended coverage
├── test_drivers.py      # Integration: CSV, X12, XML, pipeline
├── test_harness.py      # Unit + integration: test harness
├── test_main.py         # Unit: CLI entry point
├── test_validator.py    # Unit + integration: validator module
├── test_comparator.py   # Unit + integration: compare engine (22 tests)
├── test_api.py          # Integration: portal API endpoints
└── integration/
    └── test_user_supplied_data.py  # YAML-driven regression tests
```

---

## Testing

**221 tests** (110+ unit, 80+ integration, 29 E2E browser), 0 failures.

```bash
# Run all unit + integration tests
pytest tests/ -v --tb=short              # 187 engine tests
pytest portal/tests/test_compare_api.py  # 5 portal API tests

# Unit tests only (fast, no I/O)
pytest -m unit

# Integration tests only (real files, pipeline)
pytest -m integration

# With coverage
pytest --cov=pyedi_core --cov-report=term-missing
```

### E2E Browser Tests (Playwright)

29 Playwright tests run a real browser against the full portal stack (FastAPI + React):

```bash
# Headed mode (visible browser, 200ms slow-mo)
pytest portal/tests/e2e/ --headed --slowmo=200 -v

# Headless (CI mode)
pytest portal/tests/e2e/ -v

# Single test file
pytest portal/tests/e2e/test_compare.py --headed --slowmo=200 -v
```

Tests auto-start uvicorn on port 8321 and use synthetic X12 JSON data for compare workflows. Page object pattern in `portal/tests/e2e/pages/`.

### Test Harness

The built-in test harness (`pyedi test`) runs YAML-driven regression tests against user-supplied data:

```bash
# Run test cases from metadata.yaml
pyedi test --metadata tests/user_supplied/metadata.yaml

# Regenerate expected outputs after schema changes
pyedi test --generate-expected

# Verify project structure and test setup
pyedi test --verify
```

Test cases are defined in `tests/user_supplied/metadata.yaml` with per-case controls for dry-run, skip-fields, strict mode, and expected error stages.

---

## License

MIT License - See LICENSE file for details
