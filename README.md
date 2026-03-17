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
  _default_x12: ./rules/default_x12_map.yaml
  _rules_dir: ./rules
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
├── main.py             # CLI entry point
├── pipeline.py         # Orchestration
├── config/
│   └── __init__.py     # Pydantic config models
├── core/               # Core processing modules
│   ├── __init__.py
│   ├── error_handler.py # Dead-letter queue
│   ├── logger.py       # Structured logging
│   ├── manifest.py     # Deduplication
│   ├── mapper.py       # Data transformation
│   └── schema_compiler.py # DSL → YAML compiler
├── drivers/            # Format-specific handlers
│   ├── __init__.py
│   ├── base.py         # Driver registry & base class
│   ├── csv_handler.py
│   ├── x12_handler.py
│   └── xml_handler.py
config/
└── config.yaml         # Runtime configuration
```

---

## Testing

```bash
# Run all tests
pytest

# Unit tests only (fast)
pytest -m unit

# Integration tests only
pytest -m integration

# With coverage
pytest --cov=pyedi_core --cov-report=term-missing
```

---

## License

MIT License - See LICENSE file for details
