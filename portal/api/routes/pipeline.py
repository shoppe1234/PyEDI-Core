"""Pipeline API routes — run pipeline, upload files, list results."""

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from ..models import PipelineResponse, PipelineRunRequest

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


def _result_to_response(r: Any) -> PipelineResponse:
    return PipelineResponse(
        status=r.status,
        correlation_id=r.correlation_id,
        source_file=r.source_file,
        transaction_type=r.transaction_type,
        output_path=r.output_path,
        errors=r.errors,
        processing_time_ms=r.processing_time_ms,
    )


@router.post("/run", response_model=List[PipelineResponse])
def pipeline_run(req: PipelineRunRequest) -> List[PipelineResponse]:
    """Run the pipeline on file(s) by path."""
    from pyedi_core.pipeline import Pipeline

    try:
        pipeline = Pipeline()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline init error: {exc}")

    try:
        result = pipeline.run(
            file=req.file,
            files=req.files,
            dry_run=req.dry_run,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}")

    results = result if isinstance(result, list) else [result]
    return [_result_to_response(r) for r in results]


@router.post("/upload", response_model=List[PipelineResponse])
async def pipeline_upload(
    files: List[UploadFile] = File(...),
    dry_run: bool = False,
) -> List[PipelineResponse]:
    """Upload files and run them through the pipeline."""
    from pyedi_core.pipeline import Pipeline

    tmp_dir = tempfile.mkdtemp(prefix="pyedi_pipeline_")
    try:
        file_paths = []
        for upload in files:
            dest = os.path.join(tmp_dir, upload.filename or "upload")
            with open(dest, "wb") as f:
                f.write(await upload.read())
            file_paths.append(dest)

        pipeline = Pipeline()
        result = pipeline.run(files=file_paths, dry_run=dry_run)
        results = result if isinstance(result, list) else [result]
        return [_result_to_response(r) for r in results]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/results")
def pipeline_results(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> List[Dict[str, Any]]:
    """List pipeline results from outbound and failed directories."""
    entries: List[Dict[str, Any]] = []

    for directory, dir_status in [("outbound", "SUCCESS"), ("failed", "FAILED")]:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue
        for p in sorted(dir_path.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.suffix == ".json" and not p.name.endswith(".error.json"):
                entry: Dict[str, Any] = {
                    "filename": p.name,
                    "path": str(p),
                    "status": dir_status,
                    "modified": p.stat().st_mtime,
                }
                entries.append(entry)

    if status:
        entries = [e for e in entries if e["status"] == status.upper()]

    return entries[:limit]


@router.get("/results/{correlation_id}")
def pipeline_result_detail(correlation_id: str) -> Dict[str, Any]:
    """Get detail for a specific pipeline result by correlation ID."""
    for directory in ["outbound", "failed"]:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue
        for p in dir_path.iterdir():
            if correlation_id in p.name and p.suffix == ".json":
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Check for error sidecar
                error_path = p.with_suffix("").with_suffix(".error.json")
                error_data = None
                if error_path.exists():
                    with open(error_path, "r", encoding="utf-8") as f:
                        error_data = json.load(f)
                return {"result": data, "error": error_data}

    raise HTTPException(status_code=404, detail=f"Result not found: {correlation_id}")
