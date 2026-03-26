# PyEDI-Core — Project Intent

This document captures the **purpose, philosophy, and intended capabilities** of PyEDI-Core. It is not a status report or implementation guide — it exists so that the codebase can be measured against the project's original and evolving intent.

---

## Problem Statement

Organizations receive business documents — invoices (810), purchase orders (850), shipping notices (856), payment advices (820) — from multiple trading partners in multiple legacy formats: X12 EDI, CSV flat files, XML, and cXML. Each partner uses its own field naming, layout, and structural conventions.

Without a normalization layer, downstream systems cannot reliably ingest, validate, compare, or act on these documents. Manual reconciliation is error-prone and unscalable. Existing ETL tools are general-purpose and require per-format code changes for each new trading partner or transaction type.

**PyEDI-Core exists to eliminate per-partner code changes** by providing a configuration-driven engine where adding a new trading partner, transaction type, or format variant requires only a YAML file — never a Python code change.

---

## Target Users

- **Operations teams** processing batch EDI files from trading partners
- **Integration engineers** onboarding new trading partners or transaction types
- **Developers** building downstream systems that consume normalized document data
- **AI-assisted workflows** where an LLM reads processing results, explains errors, and assists with rule authoring — but never writes directly to the pipeline

---

## Core Purpose

PyEDI-Core is a **configuration-driven EDI, CSV, and XML processing engine** that normalizes legacy file formats into a **standard JSON intermediate format**.

In plain terms: files go in (any supported format), JSON comes out (one consistent shape), and the rules that govern the transformation live in YAML configuration — not in application code.

The engine also provides:
- **Comparison** of normalized outputs across source systems (e.g., "does the 810 from System A match the 810 from System B?")
- **Schema validation** with a DSL compiler for legacy flat-file definitions
- **A regression test harness** driven by YAML metadata for deterministic verification
- **A web portal** for browser-based access to all engine operations

---

## Design Philosophy

These seven principles are **invariants** — they should hold true across all features and future development.

### 1. Configuration over Convention
All business logic is expressed in YAML. The Python code is a generic executor. There must be zero hardcoded transaction-type logic in `.py` files (no `if type == '810'`). Adding a new transaction type means adding a YAML mapping file and one registry entry — nothing else.

### 2. Deterministic Processing
Identical input always produces identical output. Every transformation is explicit, auditable, and reproducible. No heuristics, no probabilistic logic, no implicit defaults that change behavior silently.

### 3. Strategy Pattern
Format-specific handling (CSV, X12, XML) is implemented via dynamically loaded drivers that share a common interface. The pipeline does not know or care which driver is active — it calls the same methods regardless of format.

### 4. Modularity
Every concern — logging, error handling, deduplication, transformation, comparison — is an independently callable Python module. The CLI, the REST API, and the library interface all call the same underlying functions. No business logic lives in the API layer or the CLI layer.

### 5. Testability at Scale
The project must support testing from unit level (isolated module tests) through integration level (real file I/O) through regression level (YAML-driven golden-output comparison) through load level (thousands of files). The test harness itself is a first-class feature, not an afterthought.

### 6. Observability
Structured logging with correlation IDs on every event. Every file, every stage, every failure is traceable. No silent failures — errors are captured in a dead-letter queue with detailed sidecars. Logs are JSON-structured and ready for ingestion by observability platforms.

### 7. LLM-Readiness
The engine is designed for human-in-the-loop AI workflows. Read-only and dry-run endpoints allow an LLM to inspect results, explain errors, and suggest rule changes — but the LLM never writes directly to the pipeline. Approval boundaries are explicit.

---

## Scope Boundaries

### What PyEDI-Core IS

- A **normalization engine** that converts EDI, CSV, and XML into a standard JSON envelope
- A **comparison engine** that pairs and diffs normalized outputs across source systems
- A **schema compiler** that converts legacy flat-file DSL definitions into structured YAML
- A **test harness** for deterministic regression testing of transformation rules
- A **web portal** providing browser-based access to all engine operations
- A **CLI tool** (`pyedi`) with subcommands: `run`, `test`, `validate`, `compare`
- A **Python library** callable programmatically (`from pyedi_core import Pipeline`)
- **White-labeled** — one codebase handles unlimited trading partners and transaction types via configuration

### What PyEDI-Core IS NOT

- Not a general-purpose ETL or data pipeline tool
- Not a message broker or queue system — it processes files, not streams (unless extended)
- Not a trading-partner communication layer (no AS2, no SFTP — it processes files after they arrive)
- Not a rules engine for arbitrary business logic — it maps fields, it does not make business decisions
- Not a database — SQLite is used for audit trails and comparison history, not as a primary data store

---

## Capability Intent

These are the capabilities the project intends to provide. Each capability should be fully realized in the codebase.

### Multi-Format Ingestion
- **X12 EDI** (.x12, .edi) — parse any X12 transaction type using segment/element structure
- **CSV** (.csv) — parse flat files using compiled schema definitions (DSL-to-YAML)
- **XML** (.xml) — parse generic XML and cXML using XPath-aware extraction
- Format detection is automatic based on file extension and content inspection

### Pipeline Orchestration
A seven-stage pipeline: Detection, Deduplication (SHA-256), Read, Validation, Transform, Write, Manifest. Each stage is independently testable. Failures at any stage route the file to a dead-letter queue with a detailed error sidecar.

### Standard JSON Output
Every processed file produces a JSON envelope with: `schema_version`, `source_system_id`, `transaction_type`, `batch_id`, `correlation_id`, `processed_at`, `source_file`, and a `payload` containing `header`, `lines`, and `summary`.

### Comparison Engine
Profile-driven comparison of normalized outputs. Each profile defines match keys (how to pair files), segment qualifiers (how to match segments within a transaction), and field-level rules (severity, tolerance, ignore patterns). Adding a new transaction type to the comparator requires only a new profile YAML — no code changes.

### Schema Validation and DSL Compilation
A compiler that reads proprietary flat-file schema definitions (`.txt` DSL files), compiles them to structured YAML with metadata sidecars, and provides: type preservation checks, field mapping coverage analysis, and sample row tracing.

### Test Harness
YAML-driven regression testing with: per-test-case controls (dry-run, strict mode, expected error stages), baseline generation (`--generate-expected`), sequential execution, and environment verification.

### Web Portal
A FastAPI backend + React frontend providing browser-based access to: pipeline processing, schema validation, test harness execution, comparison workflows, configuration inspection, and system health dashboard.

### CLI Interface
The `pyedi` command with subcommands:
- `run` — process files through the pipeline
- `test` — execute the regression test harness
- `validate` — compile and inspect DSL schemas
- `compare` — compare normalized outputs across source systems

### Library Interface
All engine capabilities are callable programmatically via `from pyedi_core import Pipeline` (and similar imports). The CLI and API are thin wrappers — they contain no business logic.

---

## Success Criteria

The project fulfills its intent when:

1. **Zero code changes for new transaction types** — a new trading partner or transaction type is onboarded by adding YAML configuration files only
2. **Format-agnostic output** — the same downstream consumer can process JSON from X12, CSV, and XML sources without knowing or caring about the original format
3. **Deterministic results** — running the same input through the pipeline twice produces byte-identical output
4. **Full traceability** — every processed file can be traced from inbound to outbound (or to dead-letter) via correlation ID and manifest
5. **No silent failures** — every error is captured, logged with context, and routed to the dead-letter queue
6. **Comparison confidence** — two normalized outputs from different source systems can be paired and diffed at the field level with configurable severity
7. **Test coverage matches capability** — every intended capability has regression tests that verify it works correctly
8. **Portal parity** — every CLI operation is also available through the web portal
9. **Business logic lives in YAML** — no `if transaction_type == ...` patterns exist in Python code
