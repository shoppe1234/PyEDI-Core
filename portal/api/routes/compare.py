"""Compare API routes — run comparisons, query results, manage rules."""

from typing import List, Optional

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from pyedi_core.comparator import compare as core_compare
from pyedi_core.comparator import export_csv, list_profiles, load_profile
from pyedi_core.comparator.models import MatchKeyConfig
from pyedi_core.comparator.rules import load_rules
from pyedi_core.comparator.store import get_diffs, get_pairs, get_run, get_runs, init_db

from ..models import (
    CompareFieldDiffResponse,
    CompareMatchKeyModel,
    ComparePairResponse,
    CompareProfileResponse,
    CompareRunRequest,
    CompareRunResponse,
    CompareRulesResponse,
    CompareRulesUpdateRequest,
)

router = APIRouter(prefix="/api/compare", tags=["compare"])

_CONFIG_PATH = "./config/config.yaml"


def _get_db_path() -> str:
    """Resolve the SQLite DB path from config."""
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("compare", {}).get("sqlite_db", "data/compare.db")


@router.get("/profiles", response_model=List[CompareProfileResponse])
def get_profiles() -> List[CompareProfileResponse]:
    """List all available compare profiles."""
    try:
        profiles = list_profiles(_CONFIG_PATH)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return [
        CompareProfileResponse(
            name=p.name,
            description=p.description,
            match_key=CompareMatchKeyModel(
                segment=p.match_key.segment,
                field=p.match_key.field,
                json_path=p.match_key.json_path,
            ),
            segment_qualifiers=p.segment_qualifiers,
            rules_file=p.rules_file,
        )
        for p in profiles
    ]


@router.post("/run", response_model=CompareRunResponse)
def run_comparison(req: CompareRunRequest) -> CompareRunResponse:
    """Run a full comparison for a profile."""
    try:
        profile = load_profile(_CONFIG_PATH, req.profile)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if req.match_json_path:
        profile.match_key = MatchKeyConfig(json_path=req.match_json_path)

    db_path = _get_db_path()
    try:
        summary = core_compare(profile, req.source_dir, req.target_dir, db_path)
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return CompareRunResponse(
        run_id=summary.run_id,
        profile=summary.profile,
        total_pairs=summary.total_pairs,
        matched=summary.matched,
        mismatched=summary.mismatched,
        unmatched=summary.unmatched,
        started_at=summary.started_at,
        finished_at=summary.finished_at,
    )


@router.get("/runs", response_model=List[CompareRunResponse])
def list_runs(profile: Optional[str] = None, limit: int = 20) -> List[CompareRunResponse]:
    """List recent comparison runs."""
    db_path = _get_db_path()
    init_db(db_path)
    runs = get_runs(db_path, profile=profile, limit=limit)
    return [
        CompareRunResponse(
            run_id=r.run_id,
            profile=r.profile,
            total_pairs=r.total_pairs,
            matched=r.matched,
            mismatched=r.mismatched,
            unmatched=r.unmatched,
            started_at=r.started_at,
            finished_at=r.finished_at,
        )
        for r in runs
    ]


@router.get("/runs/{run_id}", response_model=CompareRunResponse)
def get_run_detail(run_id: int) -> CompareRunResponse:
    """Get a single run by ID."""
    db_path = _get_db_path()
    run = get_run(db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return CompareRunResponse(
        run_id=run.run_id,
        profile=run.profile,
        total_pairs=run.total_pairs,
        matched=run.matched,
        mismatched=run.mismatched,
        unmatched=run.unmatched,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get("/runs/{run_id}/pairs", response_model=List[ComparePairResponse])
def list_pairs(run_id: int, status: Optional[str] = None, limit: int = 50) -> List[ComparePairResponse]:
    """List pairs for a run, optionally filtered by status."""
    db_path = _get_db_path()
    pairs = get_pairs(db_path, run_id, status=status, limit=limit)
    return [ComparePairResponse(**p) for p in pairs]


@router.get("/runs/{run_id}/pairs/{pair_id}/diffs", response_model=List[CompareFieldDiffResponse])
def list_diffs(run_id: int, pair_id: int) -> List[CompareFieldDiffResponse]:
    """List field diffs for a pair."""
    db_path = _get_db_path()
    diffs = get_diffs(db_path, pair_id)
    return [
        CompareFieldDiffResponse(
            segment=d.segment,
            field=d.field,
            severity=d.severity,
            source_value=d.source_value,
            target_value=d.target_value,
            description=d.description,
        )
        for d in diffs
    ]


@router.get("/runs/{run_id}/export")
def export_run(run_id: int) -> FileResponse:
    """Export a run's results to CSV and return the file."""
    db_path = _get_db_path()
    run = get_run(db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    csv_dir = config.get("compare", {}).get("csv_dir", "reports/compare")

    csv_path = export_csv(db_path, run_id, csv_dir)
    return FileResponse(csv_path, media_type="text/csv", filename=f"compare_run_{run_id}.csv")


@router.get("/profiles/{name}/rules", response_model=CompareRulesResponse)
def get_rules(name: str) -> CompareRulesResponse:
    """Get rules for a profile as JSON."""
    try:
        profile = load_profile(_CONFIG_PATH, name)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    try:
        rules = load_rules(profile.rules_file)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    classification = [
        {
            "segment": r.segment,
            "field": r.field,
            "severity": r.severity,
            "ignore_case": r.ignore_case,
            "numeric": r.numeric,
            "conditional_qualifier": r.conditional_qualifier,
        }
        for r in rules.classification
    ]
    return CompareRulesResponse(classification=classification, ignore=rules.ignore)


@router.put("/profiles/{name}/rules", response_model=CompareRulesResponse)
def update_rules(name: str, req: CompareRulesUpdateRequest) -> CompareRulesResponse:
    """Update rules for a profile (writes to the profile's YAML file)."""
    try:
        profile = load_profile(_CONFIG_PATH, name)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    data = {
        "classification": req.classification,
        "ignore": req.ignore,
    }
    try:
        with open(profile.rules_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return CompareRulesResponse(classification=req.classification, ignore=req.ignore)
