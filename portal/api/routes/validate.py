"""Validate API routes — DSL compilation and mapping verification."""

import dataclasses
import os
import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from pyedi_core.validator import validate as core_validate

from ..models import (
    ColumnInfoModel,
    CoverageReportModel,
    FieldTraceModel,
    TypeWarningModel,
    ValidateRequest,
    ValidateResponse,
)

router = APIRouter(prefix="/api/validate", tags=["validate"])


def _to_response(result: object) -> ValidateResponse:
    """Convert a ValidationResult dataclass to ValidateResponse Pydantic model."""
    r = result  # type: ignore[assignment]
    columns = [
        ColumnInfoModel(
            name=c.name,
            compiled_type=c.compiled_type,
            dsl_type=c.dsl_type,
            record_name=c.record_name,
            type_preserved=c.type_preserved,
            width=c.width,
        )
        for c in r.columns
    ]
    type_warnings = [
        TypeWarningModel(
            field_name=tw.field_name,
            record_name=tw.record_name,
            dsl_type=tw.dsl_type,
            compiled_type=tw.compiled_type,
        )
        for tw in r.type_warnings
    ]
    coverage = None
    if r.coverage is not None:
        coverage = CoverageReportModel(**dataclasses.asdict(r.coverage))

    field_traces = None
    if r.field_traces is not None:
        field_traces = [
            [FieldTraceModel(**dataclasses.asdict(ft)) for ft in row]
            for row in r.field_traces
        ]

    return ValidateResponse(
        dsl_path=r.dsl_path,
        compiled_yaml_path=r.compiled_yaml_path,
        transaction_type=r.compiled_yaml.get("transaction_type"),
        columns=columns,
        records=r.records,
        type_warnings=type_warnings,
        compilation_warnings=r.compilation_warnings,
        field_traces=field_traces,
        coverage=coverage,
        sample_row_count=r.sample_row_count,
        sample_errors=r.sample_errors,
    )


@router.post("", response_model=ValidateResponse)
def validate_path(req: ValidateRequest) -> ValidateResponse:
    """Validate a DSL file by path."""
    try:
        result = core_validate(
            dsl_path=req.dsl_path,
            sample_path=req.sample_path,
            compiled_dir=req.output_dir or "./schemas/compiled",
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _to_response(result)


@router.post("/upload", response_model=ValidateResponse)
async def validate_upload(
    dsl_file: UploadFile = File(...),
    sample_file: UploadFile | None = File(None),
) -> ValidateResponse:
    """Validate uploaded DSL file (+ optional sample)."""
    tmp_dir = tempfile.mkdtemp(prefix="pyedi_validate_")
    try:
        dsl_path = os.path.join(tmp_dir, dsl_file.filename or "upload.txt")
        with open(dsl_path, "wb") as f:
            f.write(await dsl_file.read())

        sample_path = None
        if sample_file is not None and sample_file.filename:
            sample_path = os.path.join(tmp_dir, sample_file.filename)
            with open(sample_path, "wb") as f:
                f.write(await sample_file.read())

        result = core_validate(
            dsl_path=dsl_path,
            sample_path=sample_path,
        )
        return _to_response(result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/history")
def validate_history() -> List[dict]:
    """List past validation reports (if any)."""
    reports_dir = Path("reports/validate")
    if not reports_dir.exists():
        return []
    entries = []
    for p in sorted(reports_dir.iterdir(), reverse=True):
        if p.suffix == ".json":
            entries.append({"filename": p.name, "path": str(p)})
    return entries
