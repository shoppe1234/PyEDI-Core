1. Executive Summary
PyEDI-Core is a configuration-driven, white-labeled ingestion and transformation engine that normalizes X12 EDI, CSV flat files, and XML (generic + cXML) into a standard JSON intermediate format. The engine is designed for deterministic, rule-based processing where all business logic is injected via YAML configuration — no hardcoded transaction logic exists in the codebase.

Core Philosophy
Configuration over Convention. No if/else chains for transaction types. Every mapping, schema rule, and transformation is expressed in YAML. The Python engine is a generic executor — the YAML files are the business logic.

1.1 Design Principles
•	Strategy Pattern — dynamically loaded drivers per file type/transaction
•	Deterministic Processing — identical input always produces identical output
•	Modularity — every concern is an independently callable .py module
•	Assisted Workflow Ready — designed for LLM-assisted human-in-the-loop operation
•	Observable — structured logging with correlation IDs at every stage
•	Testable at Scale — tiered test suite from unit to 5,000-file load tests

1.2 Immediate Use Case
The primary goal of v1.0 is to take two normalized JSON outputs from the same or different source formats and compare them reliably. Every JSON output carries a consistent envelope (schema_version, source_system_id, transaction_type, batch_id, correlation_id, processed_at, source_file) enabling deterministic comparison without ambiguity.
 
2. System Architecture
2.1 File & Module Structure
Every concern is encapsulated as an independently callable module. main.py is the CLI entry point. pipeline.py is the orchestrator callable from CLI, external programs, or a REST API layer.

pyedi_core/
├── main.py                   # CLI entry point
├── pipeline.py               # Orchestrator — callable by any caller
├── pyproject.toml            # Installable package definition
├── config/
│   └── config.yaml           # Master configuration
├── core/
│   ├── error_handler.py      # Dead letter logic, multi-point injectable
│   ├── manifest.py           # .processed log, idempotency / dedup
│   ├── logger.py             # structlog setup, correlation ID generation
│   ├── mapper.py             # YAML-driven transformation engine
│   └── schema_compiler.py    # LegacySchemaCompiler (hash + version aware)
├── drivers/
│   ├── base.py               # Abstract TransactionProcessor (ABC)
│   ├── x12_handler.py        # badx12-based driver (open-ended ST segments)
│   ├── csv_handler.py        # pandas-based driver
│   └── xml_handler.py        # Generic + cXML driver
├── schemas/
│   ├── source/               # Raw .txt DSL files from trading partners
│   └── compiled/
│       ├── gfs_810_map.yaml  # Auto-compiled YAML maps
│       ├── *.meta.json       # Hash + version sidecar per compiled schema
│       └── archive/          # Previous schema versions with datestamp
├── rules/
│   ├── gfs_810_map.yaml      # Transaction mapping rules
│   └── default_x12_map.yaml  # Passthrough fallback for unknown ST segments
├── outbound/                 # Processed JSON output
├── failed/                   # Dead letter directory
│   └── *.error.json          # Sidecar error files
├── logs/
│   └── pyedi.log             # Structured log output (when file mode enabled)
└── .processed                # Flat manifest log — append-only

2.2 Interface Contracts
The system must be callable in two modes simultaneously:

Caller Type	Interface	Example
CLI	python main.py --config config.yaml	Direct invocation, dry-run testing
Python library	from pyedi_core import Pipeline	Called by any .py script or service
REST API (Phase 3)	POST /process, GET /status/{id}	Called by any HTTP-capable system
LLM Tool (Phase 4)	Tool schema definition	Assisted workflow via function calling

2.3 PipelineResult — The Return Contract
run() always returns a structured PipelineResult Pydantic model. This makes the output programmatically usable by any caller — not just a file written to disk.

class PipelineResult(BaseModel):
    status: Literal['SUCCESS', 'FAILED', 'SKIPPED']
    correlation_id: str          # UUID per file processed
    source_file: str
    transaction_type: str
    output_path: Optional[str]   # None in dry_run mode
    payload: Optional[dict]      # In-memory JSON (available when return_payload=True)
    errors: List[str]
    processing_time_ms: int

 
3. Core Module Specifications
3.1 error_handler.py — Dead Letter Queue
The error handler is a shared injectable utility called at every stage boundary across all drivers. It is never duplicated — every driver imports the same module.

•	Exposes a single callable: handle_failure(file_path, stage, reason, exception)
•	Moves the failed file to ./failed/ directory
•	Writes a sidecar .error.json with: stage, reason, exception message, correlation_id, timestamp
•	Stage values: DETECTION | VALIDATION | TRANSFORMATION | WRITE
•	Updates the .processed manifest with status=FAILED
•	Emits a structured log event at ERROR level

Stage Coverage
error_handler.py is called at: (1) file detection/peek failures, (2) schema validation failures, (3) transformation/mapping failures, (4) output write failures. No failure escapes silently.

3.2 manifest.py — Idempotency & Dedup
Prevents reprocessing of duplicate files using a SHA-256 content hash. A renamed copy of the same file is still detected as a duplicate.

•	Format: {sha256_hash}|{filename}|{iso_timestamp}|{status} — one line per file
•	Status values: SUCCESS | FAILED | SKIPPED
•	File is append-only — never mutated, safe for concurrent reads
•	On invocation, pipeline filters inbound files against manifest before processing begins
•	dry_run mode does NOT update the manifest — re-runs against same files are safe

3.3 logger.py — Structured Observability
Wraps structlog and stamps every log event with a consistent set of fields. Three deployment tiers configured entirely via config.yaml — no code changes required.

Config Option	Values	Recommended Use
log_level	DEBUG | INFO | WARNING | ERROR	INFO for production, DEBUG for development
output	console | file | both	console for initial deploy, both for production
format	pretty | json	pretty for dev, json for log aggregator ingest
log_file	Any path	./logs/pyedi.log default

Every log event carries: correlation_id, file_name, stage, transaction_type, processing_time_ms. When format: json is enabled, output is ready for direct ingest by Datadog, Splunk, CloudWatch, or any structured log aggregator with zero additional configuration.

3.4 schema_compiler.py — Version-Aware Schema Compiler
Compiles two schema source types to standard PyEDI YAML map format. Both are idempotent and version-aware (SHA-256 hash check → archive on change → skip if unchanged).

DSL Compiler (compile_dsl):
•	Parses proprietary .txt DSL files (def record Header { ... } blocks)
•	Maps types (String→string, Decimal→float, Integer→integer), identifies Header/Detail/Summary structure
•	Output: standard _map.yaml + _map.meta.json sidecar

XSD Compiler (compile_xsd) — added 2026-03-27:
•	parse_xsd_file(): recursively walks xs:element/xs:complexType/xs:sequence tree, identifies transaction/header/line element hierarchy, maps XSD types (xs:float→float, xs:string→string, etc.), flattens nested elements to dot-notation paths
•	_compile_xsd_to_yaml(): emits xml_config section (root_element, transaction_element, header_path, line_container_path, line_element) plus schema.columns, schema.records, mapping sections
•	compile_xsd(): identical hash/archive/cache pattern as compile_dsl

 
4. Driver Specifications
All drivers implement the AbstractTransactionProcessor base class defined in drivers/base.py with three required methods: read(), transform(), and write(). All drivers call error_handler.py at each stage boundary.

4.1 Abstract Base Class (drivers/base.py)
class TransactionProcessor(ABC):
    @abstractmethod
    def read(self, file_path: str) -> dict: ...
    @abstractmethod
    def transform(self, raw_data: dict, map_yaml: dict) -> dict: ...
    @abstractmethod
    def write(self, payload: dict, output_path: str) -> None: ...

4.2 Driver A — X12 Handler (x12_handler.py)
•	Detection: peek at file header, extract ST segment Transaction ID (e.g., '810', '850', '856')
•	Uses badx12 library for all X12 parsing — loop awareness and segment hierarchy are handled by the library
•	Open-ended transaction support: look up Transaction ID in transaction_registry
•	If no match found: fall back to default_x12_map.yaml for raw passthrough JSON, log as UNMAPPED_TRANSACTION at WARNING level
•	Apply YAML mapping rules from matched map file via mapper.py

X12 Open-Ended Design
The transaction_registry in config.yaml is the only place transaction types are enumerated. The engine never hard-fails on an unknown ST segment — it processes generically and flags it. New transaction types are added by dropping a new map YAML and adding one line to config.yaml.

4.3 Driver B — CSV Handler (csv_handler.py)
•	Detection: file extension .csv or naming convention defined in config
•	Triggers LegacySchemaCompiler check before processing begins
•	Uses pandas to read CSV, enforcing data types and headers from compiled YAML schema
•	Row-level iteration mapped to lines[] array in output JSON
•	Missing required fields and type mismatches route to error_handler.py at VALIDATION stage

4.4 Driver C — XML Handler (xml_handler.py)
•	Detection: file extension .xml or .cxml
•	Auto-detect cXML: check root element or DOCTYPE declaration on file peek
•	Schema-aware (XSD-driven): when compiled_yaml_path is set via xml_schema_registry, uses _parse_schema_aware_xml() — namespace stripping, hierarchy-aware extraction, nested element support with dot-notation paths
•	Generic XML: uses Python built-in xml.etree.ElementTree (fallback when no registry entry)
•	cXML: adds XPath-style source path awareness for cXML-specific hierarchy (fallback)
•	write_split(): writes one JSON per transaction keyed by header field (e.g., InvoiceNumber) — enables per-transaction compare workflow
•	Fully parallel to X12 and CSV handlers — same map.yaml structure, config-driven routing

 
5. Configuration Specification
5.1 Master config.yaml Structure
All config is loaded via a Pydantic BaseSettings model at startup. Type errors and missing required fields produce clear, human-readable errors before any file is touched.

system:
  source_system_id: 'gfs'          # Stamped in every JSON envelope
  max_workers: 8                   # ThreadPoolExecutor concurrency
  dry_run: false                   # Override with --dry-run CLI flag
  return_payload: false            # Return JSON in memory vs disk-only

observability:
  log_level: INFO
  output: console                  # console | file | both
  log_file: ./logs/pyedi.log
  format: pretty                   # pretty | json

directories:
  inbound:
    - ./inbound/x12
    - ./inbound/csv
    - ./inbound/xml
  outbound: ./outbound
  failed:  ./failed
  manifest: ./.processed

transaction_registry:
  '810': ./rules/gfs_810_map.yaml
  '850': ./rules/gfs_850_map.yaml
  gfs_csv: ./rules/gfs_csv_map.yaml
  cxml_850: ./rules/cxml_850_map.yaml
  _default_x12: ./rules/default_x12_map.yaml

5.2 Map YAML Structure — Reference Example
# rules/gfs_810_map.yaml
transaction_type: '810_INVOICE'
input_format: 'CSV'
schema:
  delimiter: ','
  columns:
    - name: 'Invoice Number'
      type: string
      required: true
    - name: 'Invoice Date'
      type: date
      format: '%m/%d/%Y'
    - name: 'Net Case Price'
      type: float
      default: 0.0
mapping:
  header:
    invoice_id:
      source: 'Invoice Number'
    date:
      source: 'Invoice Date'
  lines:
    item_id:
      source: 'Item Number'
    unit_price:
      source: 'Net Case Price'
      transform: to_float

5.3 Output JSON Envelope — Standard Structure
Every output file shares this envelope regardless of source format. Enables reliable downstream comparison.

{
  "envelope": {
    "schema_version": "1.0",
    "source_system_id": "gfs",
    "transaction_type": "810",
    "input_format": "CSV",
    "batch_id": "<uuid>",
    "correlation_id": "<uuid>",
    "processed_at": "2025-01-15T14:23:00Z",
    "source_file": "GENSB_810_20250115.csv"
  },
  "payload": {
    "header": {},
    "lines": [],
    "summary": {}
  }
}

 
6. Multi-Caller Architecture
PyEDI-Core is designed from the ground up to be callable by any system. The core engine never changes — only thin interface layers are added per caller type.

6.1 Layer 1 — Python Library (Phase 2)
The lowest-effort upgrade. Any Python script can import and call the pipeline directly:

from pyedi_core import Pipeline

result = Pipeline(config_path='./config/config.yaml').run(
    file='GENSB_810.csv',
    return_payload=True
)

if result.status == 'SUCCESS':
    compare_json(result.payload, other_payload)

•	Requires pyproject.toml for pip install -e . (local) or private PyPI (distributed)
•	Clean __init__.py exposes only public interface: Pipeline, PipelineResult

6.2 Layer 2 — REST API (Phase 3, FastAPI)
A thin api/ layer wraps the library. Zero changes to core engine required.

Endpoint	Method	Description
POST /process	POST	Submit file path or upload. Returns PipelineResult JSON.
GET /status/{correlation_id}	GET	Look up processing status from manifest.
GET /manifest	GET	Return full processing history log.
POST /dry-run	POST	Validate + transform without writing output.

Concurrency at 50–5,000 files is handled by FastAPI's async request handling combined with the ThreadPoolExecutor inside pipeline.py. max_workers in config.yaml is the tuning knob.

6.3 Layer 3 — LLM Assisted Workflow (Phase 4)
Design Decision: Assisted, Not Autonomous
The LLM never writes to the pipeline or mutates config directly. It reads results, explains them, and helps draft artifacts that a human reviews and approves. The pipeline remains a closed, deterministic system. This is the correct boundary for financial document processing.

The LLM tool definition wraps the read-only and dry-run API endpoints:

LLM Tool Action	Underlying Call	Human Value
Query failed files	GET /manifest (filter FAILED)	Plain English error summary
Triage error	GET /status/{id} + read .error.json	Explain what failed and why
Validate new file	POST /dry-run	Schema gap analysis in plain English
Draft map YAML	No API call — LLM reasoning	Human reviews before committing
Run pipeline	POST /process	Human triggers — LLM never auto-runs

 
7. Testing Strategy
Three tiers of test coverage provide confidence at every scale level. Tests are structured so each tier can run independently.

7.1 Test Stack
Tool	Purpose	When It Runs
pytest + pytest-mock	Unit and integration tests	Every commit (CI)
pytest-benchmark	Performance benchmarking per stage	Every commit (CI)
Locust	API load testing at 50–5,000 file volume	Pre-release / scheduled
pytest-cov	Line coverage reporting (target: 85%+ core)	Every commit (CI)
File generator utility	Synthetic fixture generation at scale	Scale test runs

7.2 Tier 1 — Unit Tests
Every module with logic gets isolated unit tests. I/O is mocked. Runs in seconds.

•	manifest.py — duplicate detection via hash, status write correctness
•	schema_compiler.py — known .txt DSL input produces exact expected YAML output
•	mapper.py — known input dict + known map.yaml produces exact expected JSON
•	error_handler.py — correct .error.json written, file moved to ./failed/
•	Each driver in isolation — mock file I/O, test parse and transform logic

7.3 Tier 2 — Integration Tests (Fixture Files)
Full pipeline end-to-end against real representative files. Output validated against known-good expected JSON.

tests/
├── fixtures/
│   ├── x12/valid_810.edi, malformed_810.edi, unknown_transaction.edi
│   ├── csv/valid_gfs_810.csv, missing_required_field.csv, wrong_type.csv
│   └── xml/valid_cxml_850.xml, malformed.xml
└── expected_outputs/
    ├── valid_810_expected.json
    └── valid_gfs_810_expected.json

Negative Path Testing is Mandatory
Files that are supposed to fail must be tested explicitly. Assert that malformed files land in ./failed/ with the correct stage and reason in the sidecar .error.json. Testing failure paths is as important as testing success paths in a pipeline.

7.4 Tier 3 — Scale & Load Tests
•	File generator utility creates N synthetic files parameterized by transaction type, row count, and error injection rate
•	pytest-benchmark measures per-stage performance to catch regressions
•	Locust tests FastAPI layer under concurrent load simulating real-time file drop volume
•	Scale tests run on a schedule or manually before releases — not on every commit

7.5 Test Configuration
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
markers = [
    'unit: fast, no I/O, runs in seconds',
    'integration: uses fixture files, runs in under a minute',
    'scale: heavy, run before releases only'
]

pytest -m unit          # CI — every commit
pytest -m integration   # CI — every commit
pytest -m scale         # Manual — pre-release
pytest --cov=pyedi_core --cov-report=html   # Coverage report

 
8. Dependencies & Environment

Package	Version / Pin	Purpose
badx12	latest stable	X12 EDI parsing, loop/segment hierarchy
pandas	>=2.0	CSV ingestion, schema enforcement
pyyaml	>=6.0	YAML config and map file loading
pydantic	>=2.0	Config validation, PipelineResult model
structlog	>=23.0	Structured logging with correlation IDs
fastapi	>=0.110 (Phase 3)	REST API wrapper layer
uvicorn	>=0.27 (Phase 3)	ASGI server for FastAPI
pytest	>=8.0 (dev)	Test runner
pytest-mock	latest (dev)	Mocking for unit tests
pytest-benchmark	latest (dev)	Performance benchmarking
pytest-cov	latest (dev)	Coverage reporting
locust	latest (dev)	Load / scale testing

 
9. Development Roadmaps

9.1 Build Sequence Roadmap
Each phase builds on the previous. No phase requires rework of prior phases — only additive layers.

Phase	Name	Key Deliverables	Duration
Phase 1	Core Engine	All core/ modules, all 3 drivers, config.yaml + Pydantic validation, CLI via main.py, .processed manifest, dead letter queue, dry-run mode	Weeks 1–3
Phase 2	Library Interface	pyproject.toml, clean __init__.py, PipelineResult model, pip install -e . support, ThreadPoolExecutor concurrency, 85%+ test coverage	Week 4
Phase 3	REST API	FastAPI app, /process /status /manifest /dry-run endpoints, Pydantic request/response models, API integration tests	Week 5
Phase 4	LLM Tool Layer	Tool schema definitions (read-only + dry-run), assisted workflow documentation, human-approval boundary enforcement	Week 6
Phase 5	Scale Hardening	Locust load tests at 5,000 files, benchmark regressions resolved, max_workers tuning guide, monitoring dashboard config	Week 7

9.2 Feature Roadmap
Post-v1.0 features prioritized by operational value:

Feature	Priority	Description
JSON Comparison Engine	DONE — v1.1	Built-in diff tool ported from json810Compare. Profile-driven comparison engine in `pyedi_core/comparator/`, `pyedi compare` CLI, portal `/compare` page. SQLite storage with field_crosswalk table for runtime severity overrides + amount_variance. 7 profiles (810, 850, 856, 820, CSV, cXML, bevager_810). Flat file compare mode (`_compare_flat_dict`) for structured JSON. Scaffold-rules CLI generates compare rules from compiled schemas. First real trading partner (Bevager) onboarded end-to-end (2026-03-26). SQLite gap analysis (10 gaps vs json810Compare) documented in `sqlLiteReport.md`
Output Schema Versioning	HIGH — v1.1	Define and enforce a canonical JSON schema contract. Version the envelope schema_version field. Downstream consumers declare version dependency.
Private PyPI Publishing	MEDIUM — v1.2	Publish pyedi_core as an installable package to a private registry for distribution across projects
MCP Server Wrapper	MEDIUM — v1.2	Expose pipeline as a Model Context Protocol server for native integration with MCP-compatible LLM clients
Webhook / Event Triggers	MEDIUM — v2.0	Optional event-driven trigger layer (S3 events, message queue) as an alternative to on-demand CLI/API invocation
Web Operator Dashboard	DONE — v1.0	PyEDI Portal: FastAPI backend + React frontend. Dashboard, Validate, Pipeline, Tests, Compare, Config pages. `bash portal/dev.sh` for dev mode
XSD-Driven XML Processing	DONE — v1.2	`parse_xsd_file` + `compile_xsd` in schema_compiler.py. XMLHandler schema-aware path with namespace stripping. `xml_schema_registry` config block mirrors csv_schema_registry. `pyedi validate --xsd`. First trading partner: Darden ASBN (2026-03-27, commit 364c66d).
Additional XML Dialects	LOW — v2.0	Extend xml_handler.py to support UBL, EDIFACT, or other dialects via additional driver sub-classes
Streaming Large Files	LOW — v2.0	Chunked processing for CSV files exceeding memory limits (>1M rows)

9.3 Observability Maturity Roadmap
Stage	Config	Capability Unlocked
Initial Deploy	format: pretty, output: console	Human-readable logs for development and initial testing
Production v1	format: json, output: both	Structured logs ready for aggregator ingest. File log as backup.
Production v2	Pipe json log to aggregator	Full correlation ID trace across files. Alerting on ERROR events. Dashboard.
Scale	Add metrics endpoint to FastAPI	Prometheus/Grafana metrics: files/min, failure rate, stage latencies

 
10. Coding Agent Handoff Instructions
Instructions for the Coding Agent
Build Phase 1 first. Do not skip ahead to FastAPI or LLM layers. Every module in core/ is independently testable — build and test each one before wiring them into pipeline.py. The YAML map files are the business logic. The Python code is a generic executor. Never hardcode transaction type logic in .py files.

10.1 Build Order Within Phase 1
Follow this exact sequence to avoid circular dependencies:

•	1. logger.py — everything else will call this first
•	2. manifest.py — needs logger only
•	3. error_handler.py — needs logger and manifest
•	4. schema_compiler.py — needs logger and error_handler
•	5. mapper.py — needs logger and error_handler
•	6. drivers/base.py — abstract class, no dependencies
•	7. drivers/csv_handler.py — needs schema_compiler, mapper, error_handler
•	8. drivers/x12_handler.py — needs mapper, error_handler
•	9. drivers/xml_handler.py — needs mapper, error_handler
•	10. pipeline.py — wires all drivers, manifest, logger together
•	11. main.py — CLI entry point, calls pipeline.py only

10.2 Non-Negotiable Implementation Rules
•	No hardcoded transaction type logic anywhere in .py files
•	error_handler.py must be called at every stage boundary in every driver
•	All config loaded via Pydantic — no raw dict access from yaml.safe_load
•	logger.py must stamp correlation_id on every log event
•	dry_run mode must not write any files and must not update .processed manifest
•	ThreadPoolExecutor max_workers must be configurable — never hardcoded
•	schema_compiler must check hash before recompiling — never blindly overwrite

10.3 Definition of Done — Phase 1
•	All modules in core/ have unit tests passing
•	All three drivers process their respective fixture files successfully
•	Negative path fixtures route correctly to ./failed/ with populated .error.json
•	dry-run mode validates and transforms without writing any output files
•	pytest-cov reports 85%+ coverage on all core/ modules
•	A single unknown X12 transaction type is processed via default_x12_map.yaml fallback without crashing
•	pip install -e . completes without errors
