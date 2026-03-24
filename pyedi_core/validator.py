"""
Validator module — standalone DSL compilation, inspection, and mapping verification.

Provides compile-only validation and optional sample-file trace/coverage analysis
without requiring the full pipeline or config.yaml wiring.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .core import logger as core_logger
from .core.mapper import map_data
from .core.schema_compiler import (
    _compile_to_yaml,
    _parse_dsl_record,
    compute_file_hash,
    parse_dsl_file,
)
from .drivers.csv_handler import CSVHandler

logger = core_logger.get_logger()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ColumnInfo:
    name: str
    compiled_type: str
    dsl_type: Optional[str]
    record_name: str
    type_preserved: bool


@dataclass
class TypeWarning:
    field_name: str
    record_name: str
    dsl_type: str
    compiled_type: str


@dataclass
class FieldTrace:
    target_field: str
    source_path: str
    value: Any
    mapped: bool


@dataclass
class CoverageReport:
    source_fields_total: int
    source_fields_mapped: int
    source_fields_unmapped: List[str]
    target_fields_total: int
    target_fields_populated: int
    target_fields_empty: List[str]
    coverage_pct: float


@dataclass
class ValidationResult:
    dsl_path: str
    compiled_yaml: Dict[str, Any]
    compiled_yaml_path: Optional[str]
    columns: List[ColumnInfo]
    records: Dict[str, List[str]]
    type_warnings: List[TypeWarning]
    compilation_warnings: List[str]
    field_traces: Optional[List[List[FieldTrace]]] = None
    coverage: Optional[CoverageReport] = None
    sample_row_count: Optional[int] = None
    sample_errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def validate(
    dsl_path: str,
    sample_path: Optional[str] = None,
    compiled_dir: str = "./schemas/compiled",
) -> ValidationResult:
    """Top-level orchestrator: compile, inspect, optionally trace a sample."""
    compiled_yaml, yaml_path, record_defs = compile_and_write(dsl_path, compiled_dir)

    columns = _build_column_info(record_defs, compiled_yaml)
    type_warnings = check_type_preservation(record_defs, compiled_yaml)
    compilation_warnings = check_compilation_warnings(record_defs)
    records = compiled_yaml.get("schema", {}).get("records", {})

    result = ValidationResult(
        dsl_path=dsl_path,
        compiled_yaml=compiled_yaml,
        compiled_yaml_path=str(yaml_path),
        columns=columns,
        records=records,
        type_warnings=type_warnings,
        compilation_warnings=compilation_warnings,
    )

    if sample_path is not None:
        sample_errors: List[str] = []
        try:
            raw_data, mapped_data = run_sample(compiled_yaml, str(yaml_path), sample_path)
            result.sample_row_count = len(raw_data.get("lines", []))
            result.coverage = compute_coverage(raw_data, mapped_data, compiled_yaml)
            result.field_traces = compute_field_traces(raw_data, mapped_data, compiled_yaml)
        except (FileNotFoundError, ValueError, KeyError) as exc:
            sample_errors.append(str(exc))
        result.sample_errors = sample_errors

    return result


def compile_and_write(
    dsl_path: str,
    compiled_dir: str = "./schemas/compiled",
) -> Tuple[Dict[str, Any], str, List[Dict[str, Any]]]:
    """Parse DSL, compile to YAML, write to disk, return (yaml_dict, yaml_path, record_defs)."""
    record_defs, delimiter = parse_dsl_file(dsl_path)

    source_path = Path(dsl_path)
    compiled_yaml = _compile_to_yaml(record_defs, source_path.name, delimiter)

    compiled_path = Path(compiled_dir)
    compiled_path.mkdir(parents=True, exist_ok=True)

    yaml_filename = source_path.stem + "_map.yaml"
    yaml_path = compiled_path / yaml_filename

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(compiled_yaml, f, default_flow_style=False, sort_keys=False)

    # Write meta.json sidecar
    meta_filename = source_path.stem + "_map.meta.json"
    meta_path = compiled_path / meta_filename
    meta = {
        "source_file": source_path.name,
        "source_hash": compute_file_hash(str(source_path.absolute())),
        "compiled_at": datetime.now().isoformat(),
        "compiled_yaml": yaml_filename,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return compiled_yaml, str(yaml_path), record_defs


def check_type_preservation(
    record_defs: List[Dict[str, Any]],
    compiled_yaml: Dict[str, Any],
) -> List[TypeWarning]:
    """Compare DSL-declared types against compiled column types."""
    compiled_cols = {
        c["name"]: c["type"]
        for c in compiled_yaml.get("schema", {}).get("columns", [])
    }

    warnings: List[TypeWarning] = []
    for rec in record_defs:
        for fld in rec.get("fields", []):
            compiled_type = compiled_cols.get(fld["name"])
            if compiled_type is None:
                continue
            expected_type = fld["type"]  # already mapped (e.g. "float")
            if compiled_type != expected_type:
                warnings.append(TypeWarning(
                    field_name=fld["name"],
                    record_name=rec["name"],
                    dsl_type=fld.get("dsl_type", expected_type),
                    compiled_type=compiled_type,
                ))
    return warnings


def check_compilation_warnings(record_defs: List[Dict[str, Any]]) -> List[str]:
    """Detect structural issues like fieldIdentifier collisions."""
    warnings: List[str] = []
    fid_seen: Dict[str, str] = {}
    for rec in record_defs:
        fid = rec.get("fieldIdentifier")
        if fid is not None:
            if fid in fid_seen:
                warnings.append(
                    f"fieldIdentifier '{fid}' collision: "
                    f"'{fid_seen[fid]}' and '{rec['name']}' share the same value"
                )
            else:
                fid_seen[fid] = rec["name"]

    for rec in record_defs:
        if not rec.get("fields"):
            warnings.append(f"Record '{rec['name']}' has no fields")

    return warnings


def run_sample(
    compiled_yaml: Dict[str, Any],
    compiled_yaml_path: str,
    sample_path: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Read a sample file through CSVHandler, then map it."""
    handler = CSVHandler(compiled_yaml_path=compiled_yaml_path)
    raw_data = handler.read(sample_path)
    mapped_data = map_data(raw_data, compiled_yaml)
    return raw_data, mapped_data


def compute_coverage(
    raw_data: Dict[str, Any],
    mapped_data: Dict[str, Any],
    compiled_yaml: Dict[str, Any],
) -> CoverageReport:
    """Compute mapping coverage statistics."""
    # Collect all source field names seen in raw lines
    source_fields: set[str] = set()
    for line in raw_data.get("lines", []):
        source_fields.update(line.keys())

    # Target fields from compiled schema columns
    target_cols = [c["name"] for c in compiled_yaml.get("schema", {}).get("columns", [])]
    target_fields_set = set(target_cols)

    # Mapped = source fields that appear in target
    mapped_fields = source_fields & target_fields_set
    unmapped = sorted(source_fields - target_fields_set)

    # Populated = target fields that have at least one non-None value in mapped lines
    populated: set[str] = set()
    for line in mapped_data.get("lines", []):
        for k, v in line.items():
            if v is not None and v != "":
                populated.add(k)
    # Also check header and summary
    for k, v in mapped_data.get("header", {}).items():
        if v is not None and v != "":
            populated.add(k)
    for k, v in mapped_data.get("summary", {}).items():
        if v is not None and v != "":
            populated.add(k)

    empty = sorted(target_fields_set - populated)

    total = len(target_fields_set) if target_fields_set else 1
    pct = (len(populated) / total) * 100.0

    return CoverageReport(
        source_fields_total=len(source_fields),
        source_fields_mapped=len(mapped_fields),
        source_fields_unmapped=unmapped,
        target_fields_total=len(target_fields_set),
        target_fields_populated=len(populated),
        target_fields_empty=empty,
        coverage_pct=pct,
    )


def compute_field_traces(
    raw_data: Dict[str, Any],
    mapped_data: Dict[str, Any],
    compiled_yaml: Dict[str, Any],
    max_rows: int = 3,
) -> List[List[FieldTrace]]:
    """Build per-row field traces for the first *max_rows* mapped lines."""
    mapping_lines = compiled_yaml.get("mapping", {}).get("lines", [])
    raw_lines = raw_data.get("lines", [])
    mapped_lines = mapped_data.get("lines", [])

    traces: List[List[FieldTrace]] = []
    for row_idx in range(min(max_rows, len(mapped_lines))):
        row_traces: List[FieldTrace] = []
        mapped_row = mapped_lines[row_idx]
        raw_row = raw_lines[row_idx] if row_idx < len(raw_lines) else {}

        for rule in mapping_lines:
            if isinstance(rule, dict):
                for target_field, field_rule in rule.items():
                    source_path = target_field
                    if isinstance(field_rule, dict):
                        source_path = field_rule.get("source", target_field)
                    value = mapped_row.get(target_field)
                    row_traces.append(FieldTrace(
                        target_field=target_field,
                        source_path=source_path,
                        value=value,
                        mapped=value is not None and value != "",
                    ))
        traces.append(row_traces)
    return traces


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_column_info(
    record_defs: List[Dict[str, Any]],
    compiled_yaml: Dict[str, Any],
) -> List[ColumnInfo]:
    """Build ColumnInfo list from record defs and compiled schema."""
    compiled_cols = {
        c["name"]: c["type"]
        for c in compiled_yaml.get("schema", {}).get("columns", [])
    }

    infos: List[ColumnInfo] = []
    seen: set[str] = set()
    for rec in record_defs:
        for fld in rec.get("fields", []):
            name = fld["name"]
            if name in seen:
                continue
            seen.add(name)
            compiled_type = compiled_cols.get(name, "string")
            dsl_type = fld.get("dsl_type")
            infos.append(ColumnInfo(
                name=name,
                compiled_type=compiled_type,
                dsl_type=dsl_type,
                record_name=rec["name"],
                type_preserved=compiled_type == fld["type"],
            ))
    return infos
