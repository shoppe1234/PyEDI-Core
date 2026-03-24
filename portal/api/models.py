"""Pydantic request/response models for the PyEDI Portal API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

class ValidateRequest(BaseModel):
    dsl_path: str
    sample_path: Optional[str] = None
    output_dir: Optional[str] = "./schemas/compiled"


class ColumnInfoModel(BaseModel):
    name: str
    compiled_type: str
    dsl_type: Optional[str] = None
    record_name: str
    type_preserved: bool


class TypeWarningModel(BaseModel):
    field_name: str
    record_name: str
    dsl_type: str
    compiled_type: str


class FieldTraceModel(BaseModel):
    target_field: str
    source_path: str
    value: Any = None
    mapped: bool


class CoverageReportModel(BaseModel):
    source_fields_total: int
    source_fields_mapped: int
    source_fields_unmapped: List[str]
    target_fields_total: int
    target_fields_populated: int
    target_fields_empty: List[str]
    coverage_pct: float


class ValidateResponse(BaseModel):
    dsl_path: str
    compiled_yaml_path: Optional[str] = None
    transaction_type: Optional[str] = None
    columns: List[ColumnInfoModel] = []
    records: Dict[str, List[str]] = {}
    type_warnings: List[TypeWarningModel] = []
    compilation_warnings: List[str] = []
    field_traces: Optional[List[List[FieldTraceModel]]] = None
    coverage: Optional[CoverageReportModel] = None
    sample_row_count: Optional[int] = None
    sample_errors: List[str] = []


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class PipelineRunRequest(BaseModel):
    file: Optional[str] = None
    files: Optional[List[str]] = None
    dry_run: bool = False


class PipelineResponse(BaseModel):
    status: str
    correlation_id: str
    source_file: str
    transaction_type: str
    output_path: Optional[str] = None
    errors: List[str] = []
    processing_time_ms: int = 0


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

class TestRunRequest(BaseModel):
    metadata_path: Optional[str] = "tests/user_supplied/metadata.yaml"
    verbose: bool = False


class TestCaseResult(BaseModel):
    name: str
    status: str
    details: Optional[str] = None


class TestRunResponse(BaseModel):
    total: int
    passed: int
    failed: int
    warned: int
    cases: List[TestCaseResult] = []


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

class ManifestEntry(BaseModel):
    hash: str
    filename: str
    timestamp: str
    status: str


class ManifestStatsResponse(BaseModel):
    total: int
    success: int
    failed: int
    skipped: int


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class ConfigResponse(BaseModel):
    config: Dict[str, Any] = {}
