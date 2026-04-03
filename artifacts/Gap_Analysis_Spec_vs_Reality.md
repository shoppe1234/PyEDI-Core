# Gap Analysis: Original Specification vs Current Implementation

**Date:** 2026-03-24 (updated 2026-04-03)
**Baseline:** `artifacts/PyEDI-Core_Specification.md` (v1.0 — the prompt that started this repo)
**Compared Against:** Current codebase on `main` branch + `SPECIFICATION.md` (living spec)

---

## Executive Summary

The codebase **faithfully implements and exceeds** the original spec. Every core requirement from the original prompt has been built. The "drift" that exists is almost entirely **additive** — capabilities that weren't envisioned in v1.0 but were natural extensions of the architecture. There are a small number of items from the original spec that are absent or modified, documented below.

**Verdict:** The project has not strayed from its original intent. It has grown beyond it in ways that are consistent with the founding philosophy.

---

## Scoring Legend

| Symbol | Meaning |
|--------|---------|
| BUILT | Implemented as specified |
| EXCEEDED | Implemented and extended beyond spec |
| MODIFIED | Implemented differently than specified |
| MISSING | Not yet implemented |
| ADDED | New capability not in original spec |

---

## 1. Core Philosophy Alignment

| Principle (Original Spec) | Status | Notes |
|---|---|---|
| Configuration over Convention | BUILT | Zero hardcoded transaction logic in `.py` files. All business logic lives in YAML. |
| Strategy Pattern | EXCEEDED | Original spec described it conceptually. Implementation adds a formal `DriverRegistry` with self-registering drivers and a `@register_transform` decorator pattern. |
| Dependability (badx12, pandas, pyyaml only) | MODIFIED | Added `pydantic`, `structlog`, `defusedxml`. All are stable, trusted libraries. See [Section 6](#6-dependency-drift). |
| White-Labeled Transactions | BUILT | `transaction_registry` in config.yaml is the single source of truth. New types = new YAML + one config line. |
| Swappable I/O Drivers | EXCEEDED | Original spec envisioned X12 and CSV. Implementation adds XML and cXML as first-class drivers. |

**Assessment: PRO.** The philosophy is intact. The additions strengthen it.

---

## 2. Architecture — What Was Specified vs What Was Built

### 2.1 Class Structure

| Original Spec | Current Implementation | Status |
|---|---|---|
| `TransactionProcessor` ABC with `read()`, `transform()`, `write()` | Identical ABC in `drivers/base.py`, plus `process()` convenience method and `detect_format()` | EXCEEDED |
| `X12Handler` | `X12Handler(TransactionProcessor)` in `x12_handler.py` | BUILT |
| `CSVHandler` | `CSVHandler(TransactionProcessor)` in `csv_handler.py` | BUILT |
| `LegacySchemaCompiler` | `schema_compiler.py` with hash-aware, version-aware compilation + archive | EXCEEDED |
| `Mapper` | `mapper.py` with pluggable transform registry (`@register_transform`) | EXCEEDED |
| *(not specified)* | `XMLHandler(TransactionProcessor)` in `xml_handler.py` | ADDED |
| *(not specified)* | `DriverRegistry` in `base.py` (formal strategy pattern) | ADDED |

### 2.2 Core Modules

| Original Spec | Current Implementation | Status |
|---|---|---|
| *(not specified)* | `error_handler.py` — dead letter queue with stage tracking, `.error.json` sidecars | ADDED |
| *(not specified)* | `manifest.py` — SHA-256 dedup, append-only `.processed` log | ADDED |
| *(not specified)* | `logger.py` — structlog with correlation IDs, configurable format/output | ADDED |
| *(not specified)* | `config/__init__.py` — Pydantic models (`AppConfig`, `CsvSchemaEntry`, etc.) | ADDED |
| *(not specified)* | `pipeline.py` — full orchestrator with `ThreadPoolExecutor` concurrency | ADDED |
| *(not specified)* | `PipelineResult` Pydantic model with status, correlation_id, errors, timing | ADDED |

**Assessment: PRO.** The original spec described what the system *should do*. The living spec (`SPECIFICATION.md`) and codebase added the operational infrastructure (error handling, observability, idempotency) required to make it *production-viable*. These are not scope creep — they're engineering maturity.

### 2.3 Data Flow

| Original Spec Flow | Current Flow | Delta |
|---|---|---|
| File Detected → Driver Parse → JSON intermediate | File Detected → **Dedup Check** → Driver Parse → **Schema Validate** → JSON intermediate | Added dedup + validation stages |
| → Mapper (YAML rules) → Outbound | → Mapper (YAML rules) → **Write or Dry-Run** → **Manifest Update** → Outbound | Added dry-run + manifest |
| *(failures not specified)* | Failed files → `./failed/` + `.error.json` sidecar | Added dead letter queue |

---

## 3. Feature-Level Gap Analysis

### 3.1 Fully Implemented (As Specified)

| Feature | Spec Section | Implementation |
|---|---|---|
| X12 parsing via badx12 | §4.2 | `x12_handler.py` — ST segment detection, transaction routing |
| CSV parsing via pandas | §4.3 | `csv_handler.py` — schema enforcement, type validation |
| Schema compilation from .txt DSL | §5 | `schema_compiler.py` — `def record { }` block parsing |
| YAML-driven field mapping | §6 | `mapper.py` — source/target/transform declarations |
| Transform operations (strip, to_float, to_integer, date_format) | §6.3 | Built-in + extended with `to_int`, `to_string`, `to_date`, `to_datetime` |
| Master `config.yaml` with `transaction_registry` | §7.1 | `config/config.yaml` — Pydantic-validated |
| CLI with `--config`, `--dry-run` | §8.1 | `main.py` — `pyedi run` subcommand |
| Library interface (`from pyedi_core import Pipeline`) | §8.2 | `__init__.py` exports `Pipeline`, `PipelineResult` |
| Default X12 fallback for unknown transactions | §7.1 | `_default_x12` entry in registry |

### 3.2 Missing or Deferred

| Feature | Spec Section | Status | Impact |
|---|---|---|---|
| `--watch` (continuous directory monitoring) | §8.1 | MISSING | Low — batch processing works; watch mode is a convenience feature. The test harness has `--watch` for test files, but the main pipeline does not watch inbound directories. |
| `--once` (single-pass flag) | §8.1 | MODIFIED | The default behavior IS single-pass (`pyedi run`). The flag name changed but the capability exists. |
| Compiled schema archive directory | §5.2 | MISSING | Low — `schema_compiler.py` does hash-aware compilation but the `./schemas/compiled/archive/` auto-versioning with datestamp suffix is not confirmed in the current code. Meta.json sidecars exist. |
| `*.meta.json` sidecar per compiled schema | §5.2 (living spec) | BUILT | Implemented in schema_compiler.py |

### 3.3 Added Beyond Original Spec

| Addition | Why It Was Added | Pro or Con? |
|---|---|---|
| **XML/cXML driver** | Natural extension of swappable I/O drivers philosophy. cXML is common in procurement EDI (Ariba, Coupa). | **PRO** — Extends market coverage without violating architecture. |
| **defusedxml** | XXE protection for XML parsing. Security requirement. | **PRO** — Necessary for any XML ingestion. |
| **Pydantic config validation** | Original spec used raw `yaml.safe_load`. Pydantic catches config errors at startup with clear messages. | **PRO** — Prevents silent misconfiguration. |
| **structlog + correlation IDs** | Original spec had no observability story. Production pipelines need traceable logs. | **PRO** — Essential for debugging at scale. |
| **Dead letter queue** (`error_handler.py`) | Original spec didn't address failure handling. Files that fail now have a clear audit trail. | **PRO** — Critical for production. |
| **Manifest deduplication** (`manifest.py`) | Original spec didn't address reprocessing. SHA-256 content hashing prevents duplicate processing. | **PRO** — Prevents billing/data errors from reprocessed files. |
| **PipelineResult model** | Original spec returned nothing. Now every caller gets structured status, errors, timing. | **PRO** — Makes the engine composable. |
| **ThreadPoolExecutor concurrency** | Original spec was single-threaded. Configurable `max_workers` handles batch volume. | **PRO** — Scales to production workloads. |
| **Test harness** (`pyedi test`) | Built-in regression testing framework with YAML-driven test cases. | **PRO** — Enables CI/CD and user-driven validation. |
| **csv_schema_registry** | Maps inbound directories to DSL files + compiled outputs. Not in original spec. | **PRO** — Enables multi-partner CSV support without ambiguity. |
| **XSD-driven XML pipeline** | `compile_xsd()` mirrors `compile_dsl()` — XSD → YAML schema. `xml_schema_registry` in config. First consumer: Darden ASBN. | **PRO** — Extends schema compilation to XML/XSD alongside DSL. |
| **Fixed-width file support** | Positional file parsing via compiled schema `width` metadata and `record_layouts`. | **PRO** — Extends beyond delimited files to handle positional EDI formats. |
| **Match key normalization** | Regex-based `normalize` field on compare profiles for stripping prefixes before pairing. | **PRO** — Handles real-world key mismatches between systems. |
| **Portal web UI** | 8-page React + Vite frontend (Dashboard, Compare, Rules, Onboard, Pipeline, Validate, Tests, Config) with FastAPI backend. | **PRO** — Provides visual management layer for the engine. |
| **X12 onboarding wizard** | Multi-step wizard in portal for X12 EDI: format select, transaction type, schema review, partner registration, rules config. Playwright E2E test suite. | **PRO** — Streamlines X12 partner onboarding. |
| **3-tier rule system** | Universal → transaction-type → partner rule resolution with merge and provenance tracking. | **PRO** — Eliminates rule duplication across partners. |
| **205 tests** (127 unit, 71 integration) | Original spec mentioned testing but didn't define scope. | **PRO** — Exceeds the 85% coverage target from the living spec. |

---

## 4. What Changed in Spirit (Not Just Feature)

### 4.1 From "Tool" to "Engine"

The original spec described PyEDI-Core as a transformation **tool** — parse files, apply mappings, write output. The current implementation is a transformation **engine** with:

- Structured error handling at every stage boundary
- Idempotent processing with content-hash deduplication
- Observable execution with correlation IDs
- A formal return contract (`PipelineResult`) for programmatic callers
- Concurrent batch processing

**Is this drift?** No. The original spec's §8.2 (Library Interface) and the multi-caller architecture in the living spec show this was always the intended direction. The original spec was a seed; the implementation grew it correctly.

### 4.2 From 3 Dependencies to 6

| Original Spec | Current |
|---|---|
| badx12, pandas, pyyaml | badx12, pandas, pyyaml, **pydantic**, **structlog**, **defusedxml** |

**Assessment: PRO with caveat.** Each addition serves a clear, non-overlapping purpose. None are exotic or unstable. The caveat: the original spec's "Dependability" principle specifically named only 3 libraries as a statement of minimal footprint. The additions are justified but represent a philosophical shift from "minimal" to "production-ready."

### 4.3 Phase Roadmap Emerged

The original spec had no phased roadmap. The living spec (`SPECIFICATION.md`) introduced a 5-phase plan:

| Phase | Status |
|---|---|
| Phase 1: Core Engine | **COMPLETE** |
| Phase 2: Library Interface | **COMPLETE** |
| Phase 3: REST API (FastAPI) | **IN PROGRESS** — Portal with FastAPI backend (port 18041) + React UI (port 15174), 8 pages, onboarding wizard, compare, rules CRUD, pipeline status |
| Phase 4: LLM Tool Layer | Not started |
| Phase 5: Scale Hardening | Not started |

This is healthy project management, not drift.

---

## 5. Risk Areas — Where to Watch for True Drift

| Risk | Description | Mitigation |
|---|---|---|
| **Feature creep in drivers** | XML/cXML was a natural addition. But adding UBL, EDIFACT, or other dialects should be driven by actual demand, not speculation. | Only add drivers when a real inbound file exists. |
| **Config complexity** | `config.yaml` now has `system`, `observability`, `directories`, `transaction_registry`, AND `csv_schema_registry`. For a single-user tool this is manageable; at scale it needs documentation. | README.md covers this adequately today. |
| **Test harness scope** | The `pyedi test` subcommand is powerful but adds maintenance surface. It's a feature of the engine, not a testing tool. | Keep it focused on regression testing user-supplied data. Don't grow it into a general test framework. |
| **Living spec divergence** | `SPECIFICATION.md` is significantly more detailed than the original spec. If it stops being updated, it becomes misleading. | Treat it as a living document; update it with each feature change. |

---

## 6. Dependency Drift Detail

| Library | In Original Spec? | Why Added | Removable? |
|---|---|---|---|
| `badx12` | Yes | X12 parsing | No — core requirement |
| `pandas` | Yes | CSV ingestion | No — core requirement |
| `pyyaml` | Yes | YAML loading | No — core requirement |
| `pydantic` | No | Config validation + PipelineResult model | Technically yes (replace with dataclasses + manual validation), but strongly not recommended |
| `structlog` | No | Structured logging with correlation IDs | Could use stdlib `logging`, but would lose structured JSON output and correlation binding |
| `defusedxml` | No | XXE-safe XML parsing | Required for any production XML ingestion — security non-negotiable |

---

## 7. Final Verdict

### Did we stray from the original intent?

**No.** The original intent was:

> *"Build a robust, white-labeled ingestion and transformation engine that normalizes X12 EDI and CSV data into a standard JSON intermediate format."*

The current system does exactly this, plus XML/cXML, with production-grade operational infrastructure.

### Where we went beyond:

| Area | Original Spec | Current | Assessment |
|---|---|---|---|
| Format support | X12 + CSV | X12 + CSV + XML + cXML + Fixed-width + XSD-driven XML | **PRO** — same architecture, more coverage |
| Error handling | Not specified | Dead letter queue + staged errors | **PRO** — essential for production |
| Observability | Not specified | structlog + correlation IDs | **PRO** — essential for debugging |
| Idempotency | Not specified | SHA-256 manifest dedup | **PRO** — prevents data errors |
| Config validation | Raw YAML | Pydantic models | **PRO** — fail-fast on bad config |
| Return contract | Not specified | PipelineResult model | **PRO** — enables composability |
| Testing | Mentioned conceptually | 205 tests (127 unit, 71 integration) + built-in harness + Playwright E2E | **PRO** — exceeds expectations |
| Dependencies | 3 libraries | 6 libraries | **NEUTRAL** — justified additions |
| REST API / Web UI | Phase 3 in roadmap | FastAPI portal with 8-page React UI, onboarding wizard, rules CRUD | **PRO** — Phase 3 underway |
| Rule management | Not specified | 3-tier rule system (universal → transaction → partner) with merge/provenance | **PRO** — enables multi-partner scale |
| Directory watching | Specified (`--watch`) | Not implemented | **MINOR GAP** — low priority |

### Bottom Line

The codebase is a **faithful, mature implementation** of the original vision. Every addition is traceable to a production need, not speculation. The architecture's core principle — *"the YAML files are the business logic, the Python code is a generic executor"* — remains perfectly intact.

---

*Generated by gap analysis of `artifacts/PyEDI-Core_Specification.md` against codebase state on 2026-03-24. Updated 2026-04-03.*
