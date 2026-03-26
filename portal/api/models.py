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


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

class CompareMatchKeyModel(BaseModel):
    segment: Optional[str] = None
    field: Optional[str] = None
    json_path: Optional[str] = None


class CompareProfileResponse(BaseModel):
    name: str
    description: str
    match_key: CompareMatchKeyModel
    segment_qualifiers: Dict[str, Optional[str]] = {}
    rules_file: str
    trading_partner: str = ""
    transaction_type: str = ""


class CompareRunRequest(BaseModel):
    profile: str
    source_dir: str
    target_dir: str
    match_json_path: Optional[str] = None


class CompareRunResponse(BaseModel):
    run_id: int
    profile: str
    total_pairs: int
    matched: int
    mismatched: int
    unmatched: int
    started_at: str
    finished_at: str
    reclassified_from: Optional[int] = None
    trading_partner: str = ""
    transaction_type: str = ""


class ComparePairResponse(BaseModel):
    id: int
    run_id: int
    source_file: str
    source_tx_index: int
    target_file: Optional[str] = None
    target_tx_index: int = 0
    match_value: str
    status: str
    diff_count: int = 0


class CompareFieldDiffResponse(BaseModel):
    segment: str
    field: str
    severity: str
    source_value: Optional[str] = None
    target_value: Optional[str] = None
    description: str


class CompareRulesResponse(BaseModel):
    classification: List[Dict[str, Any]] = []
    ignore: List[Dict[str, Any]] = []


class CompareRulesUpdateRequest(BaseModel):
    classification: List[Dict[str, Any]] = []
    ignore: List[Dict[str, Any]] = []


class DiscoveryResponse(BaseModel):
    id: int
    run_id: int
    profile: str
    segment: str
    field: str
    source_value: Optional[str] = None
    target_value: Optional[str] = None
    suggested_severity: str
    applied: bool
    discovered_at: str
