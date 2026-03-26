# PyEDI-Core: Configuration-Driven EDI & Flat File Engine
**Product Requirements & Developer Specification**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Core Philosophy](#2-core-philosophy)
3. [System Architecture](#3-system-architecture)
4. [Ingestion Layer — Strategy Pattern](#4-ingestion-layer--strategy-pattern)
5. [The Schema Compiler Service](#5-the-schema-compiler-service)
6. [Transformation Layer — YAML-Logic](#6-transformation-layer--yaml-logic)
7. [Configuration Reference](#7-configuration-reference)
8. [CLI & Library Interface](#8-cli--library-interface)
9. [Reference Artifacts & Q&A](#9-reference-artifacts--qa)

---

## 1. Project Overview

**Project Title:** PyEDI-Core
**Role:** Senior Python Architect
**Objective:** Build a robust, white-labeled ingestion and transformation engine that normalizes X12 EDI and CSV data into a standard JSON intermediate format.

PyEDI-Core is designed to act as an **interface**, not merely a tool — callable from CLI or imported by other Python scripts. All business logic and transaction definitions are injected via YAML configuration, keeping the codebase agnostic to any specific EDI transaction type (810, 850, 855, 856, etc.).

---

## 2. Core Philosophy

| Principle | Description |
|---|---|
| **Configuration over Convention** | No hardcoded transaction logic (e.g., `if type == '810'`). All logic injected via YAML. |
| **Strategy Pattern** | A registry dynamically loads handlers based on file type or transaction ID at runtime. |
| **Dependability** | Relies exclusively on standard, trusted Python libraries: `badx12`, `pandas`, `pyyaml`. |
| **White-Labeled Transactions** | The same codebase handles 810, 850, 855, 856, or any future transaction type without code changes. |
| **Swappable I/O Drivers** | X12 and CSV are treated as interchangeable input/output drivers. The core pipeline centers on JSON. |

---

## 3. System Architecture

### 3.1 Technology Stack

| Library | Purpose |
|---|---|
| `badx12` | X12 EDI parsing → Python dict/JSON |
| `pandas` | CSV ingestion and schema enforcement |
| `pyyaml` | Configuration and schema loading |

### 3.2 Class Structure

```
TransactionProcessor (ABC)
├── read()         # Knows HOW to read a file
├── transform()    # Applies YAML-defined mapping rules
└── write()        # Knows HOW to write output

Concrete Drivers:
├── X12Handler     # Implements TransactionProcessor for X12
└── CSVHandler     # Implements TransactionProcessor for CSV

Supporting Services:
├── LegacySchemaCompiler   # Parses .txt DSL → YAML schema
└── Mapper                 # Applies transformation rules from map.yaml
```

### 3.3 Data Flow

```
Inbound Directory
      │
      ▼
 File Detected
      │
      ├─── .edi / .x12 ──► X12Handler ──► badx12 parse ──► JSON (intermediate)
      │
      └─── .csv ──────────► CSVHandler ──► pandas + schema ──► JSON (intermediate)
                                                │
                                         LegacySchemaCompiler
                                    (if compiled schema not found)
                                                │
                                                ▼
                                    Mapper (YAML rules applied)
                                                │
                                                ▼
                                       Outbound Directory
```

---

## 4. Ingestion Layer — Strategy Pattern

### 4.1 Abstract Base Class

Create a generic `TransactionProcessor` class. It defines **how** to read and write, but remains completely unaware of **what** the data contains.

```python
from abc import ABC, abstractmethod

class TransactionProcessor(ABC):

    @abstractmethod
    def read(self, file_path: str) -> dict:
        """Read source file and return intermediate JSON dict."""
        pass

    @abstractmethod
    def transform(self, data: dict, mapping_config: dict) -> dict:
        """Apply YAML-defined transformation rules."""
        pass

    @abstractmethod
    def write(self, data: dict, output_path: str) -> None:
        """Write normalized output to target directory."""
        pass
```

### 4.2 Driver A — X12 Handler (`badx12`)

**Detection:** Peek at the file header (`ST` segment) to extract the Transaction Set ID (e.g., `"810"`).

**Runtime Resolution:**
1. File arrives in a watched directory.
2. System reads the `ST` segment header.
3. Extracts Transaction ID (e.g., `"810"`).
4. Looks up the ID in `transaction_registry` (defined in `config.yaml`).
5. Loads the specific mapping YAML dynamically.
6. Applies transformation rules to normalize the data.

> **Reference:** Use `parsex12.py` as a working model showing how X12 810 data is parsed via `badx12`. Treat it as a reference guide only — do not copy logic directly into core modules.

### 4.3 Driver B — CSV Handler (`pandas`)

**Detection:** File extension `.csv` or a naming convention defined in `config.yaml`.

**Schema Enforcement:**
- Input CSVs are schema-less by default.
- Validate against a YAML schema derived from the flat-file definition (e.g., `gfsGenericOut810FF.txt`).
- Use `pandas` to enforce data types and column headers defined in the schema YAML.

---

## 5. The Schema Compiler Service

### 5.1 Purpose

`LegacySchemaCompiler` runs **before** CSV file processing. It converts proprietary `.txt` flat-file DSL definitions into a standard PyEDI YAML schema that `pandas` and the `Mapper` can consume.

### 5.2 Execution Logic

```
CSV file detected in watched directory
          │
          ▼
Does a compiled YAML schema exist in ./schemas/compiled/?
          │
     ┌────┴────┐
    YES        NO
     │          │
     ▼          ▼
 Load YAML   Run Compilation Step
 → proceed   → generate YAML → proceed
```

### 5.3 Compilation Step — Parsing Rules

**Input:** Proprietary `.txt` DSL file (e.g., `gfsGenericOut810FF.txt`) containing `def record Header { ... }` blocks.

**Parsing Logic:**
- Extract field names (e.g., `SourceWarehouse`)
- Extract and map data types: `String → string`, `Decimal → float`, `Integer → integer`
- Identify structural groupings: `Header`, `Details`, `Summary`

**Output:** Auto-generated YAML in `./schemas/compiled/`

```yaml
# Auto-Compiled from gfsGenericOut810FF.txt
structure:
  header:
    - name: "SourceWarehouse"
      type: "string"
    - name: "InvoiceNumber"
      type: "string"
  details:
    - name: "ItemNumber"
      type: "string"
    - name: "NetCasePrice"
      type: "float"
```

---

## 6. Transformation Layer — YAML-Logic

### 6.1 Design Principle

The `Mapper` class reads a `map.yaml` file. **No hardcoded Python mapping logic is permitted.** All field-level transformations are defined declaratively in YAML.

### 6.2 Reference Map — `gfs_810_map.yaml`

```yaml
# rules/gfs_810_map.yaml
transaction_type: "810_INVOICE"
input_format: "CSV"

# Schema: replaces gfsGenericOut810FF.txt
# Used by pandas to validate types before processing
schema:
  delimiter: ","
  columns:
    - name: "Source Warehouse"
      type: "string"
    - name: "Invoice Number"
      type: "string"
      required: true
    - name: "Invoice Date"
      type: "date"
      format: "%m/%d/%Y"
    - name: "Case Price"
      type: "float"
      default: 0.0

# Transformation Map
# Maps CSV columns (Source) → Standard JSON Structure (Target)
mapping:
  header:
    invoice_id:
      source: "Invoice Number"
    date:
      source: "Invoice Date"
    warehouse_id:
      source: "Source Warehouse"

  lines:
    item_id:
      source: "Item Number"
    description:
      source: "Item Description"
    quantity:
      source: "Quantity Shipped"
      transform: "to_integer"
    unit_price:
      source: "Net Case Price"
      transform: "to_float"
```

### 6.3 Supported Transform Operations

| Operation | Description |
|---|---|
| `strip` | Remove leading/trailing whitespace |
| `to_float` | Cast string to float |
| `to_integer` | Cast string to integer |
| `date_format` | Reformat date using defined format string |

---

## 7. Configuration Reference

### 7.1 Master `config.yaml`

```yaml
# config.yaml — Master Configuration (The "Brain")

inbound_directories:
  - "./data/inbound/x12"
  - "./data/inbound/csv"

outbound_directories:
  - "./data/outbound"

# Supported dataset types: x12, csv, xml
dataset_type: "x12"

# File matching pattern per directory
file_pattern: "*.edi"

# Transaction Registry
# Maps Transaction ID or source type → schema/map YAML
transaction_registry:
  "810":
    map_file: "./rules/x12_810_map.yaml"
    format: "x12"
  "850":
    map_file: "./rules/x12_850_map.yaml"
    format: "x12"
  "gfs_csv":
    map_file: "./rules/gfs_810_map.yaml"
    format: "csv"
    schema_source: "./schemas/gfsGenericOut810FF.txt"

# Schema compilation output directory
compiled_schema_dir: "./schemas/compiled/"
```

---

## 8. CLI & Library Interface

### 8.1 CLI Usage

```bash
python main.py --config config.yaml
python main.py --config config.yaml --watch         # continuous directory monitoring
python main.py --config config.yaml --once          # single-pass processing
python main.py --config config.yaml --dry-run       # validate config without processing
```

### 8.2 Library / Script Interface

```python
from pyedi import Pipeline

# Instantiate and run
pipeline = Pipeline(config_path="./config.yaml")
pipeline.run()

# Or pass config as dict (for programmatic use)
pipeline = Pipeline(config={
    "inbound_directories": ["./data/in"],
    "outbound_directories": ["./data/out"],
    "transaction_registry": { ... }
})
pipeline.run()
```

### 8.3 Entry Point Pattern (`main.py`)

```python
import argparse
from pyedi import Pipeline

def main():
    parser = argparse.ArgumentParser(description="PyEDI-Core Engine")
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("--watch", action="store_true", help="Monitor directories continuously")
    parser.add_argument("--once", action="store_true", help="Single-pass run")
    parser.add_argument("--dry-run", action="store_true", help="Validate config only")
    args = parser.parse_args()

    pipeline = Pipeline(config_path=args.config)
    pipeline.run(watch=args.watch, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
```

---

## 9. Reference Artifacts & Q&A

### 9.1 Input Artifacts

| Artifact | Role |
|---|---|
| `GENSB_EDOCSV741_040226_09235825.csv` | Sample CSV input source data |
| `gfsGenericOut810FF.txt` | Flat-file schema DSL — input to `LegacySchemaCompiler` |
| `parsex12.py` | Reference implementation showing `badx12` parsing of X12 810 — **reference only** |

### 9.2 Q: Is there enough context to formulate instructions?

**Yes.** The provided artifacts establish a clear before/after:

- **Input:** `GENSB_...csv` shows the raw flat-file structure.
- **Schema:** `gfsGenericOut810FF.txt` defines field types (`String`, `Decimal`) and structure (`Header`, `Details`) — translatable directly to YAML.
- **Output target:** `parsex12.py` reveals the desired JSON structure (`document → segments`) the system should produce or consume.

### 9.3 Q: Can a transformation YAML provide history and working examples?

**Yes.** The proprietary `.txt` schema format should be "modernized" into the PyEDI YAML format at compile time. The `LegacySchemaCompiler` handles this automatically. The compiled YAML in `./schemas/compiled/` serves as a living history of processed schemas and can be version-controlled for auditability.

### 9.4 Q: How to handle white-labeling across transaction types?

Use the **Registry + Strategy Pattern**:
1. The `config.yaml` `transaction_registry` maps Transaction IDs to schema files.
2. At runtime, the system reads the `ST` segment, resolves the ID, and loads the correct handler — no `if/else` logic anywhere in the core.
3. Adding support for an 856 (ASN) requires only adding one entry to `transaction_registry` and a corresponding `map.yaml`.

### 9.5 Q: How to handle CSV as an alternate input?

CSV is treated as a **peer input driver** alongside X12:
- Supply a `.yaml` schema (or a `.txt` DSL that gets compiled to one).
- The system enforces column types via `pandas` before any transformation runs.
- The output is the same standard JSON intermediate format regardless of input driver.

---

*PyEDI-Core — Configuration-Driven EDI & Flat File Engine*
*Architecture Specification v1.0*
