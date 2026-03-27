"""Onboard API routes — trading partner registration and rules template generation."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/onboard", tags=["onboard"])

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "config.yaml"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RegisterPartnerRequest(BaseModel):
    profile_name: str
    trading_partner: str
    transaction_type: str
    description: str
    source_dsl: str
    compiled_output: str
    inbound_dir: str
    match_key: Dict[str, str]
    segment_qualifiers: Dict[str, Optional[str]] = {}


class RegisterPartnerResponse(BaseModel):
    profile_name: str
    rules_file: str
    config_updated: bool
    rules_created: bool


class RulesTemplateResponse(BaseModel):
    classification: List[Dict[str, Any]]
    ignore: List[Any]


# ---------------------------------------------------------------------------
# POST /api/onboard/register
# ---------------------------------------------------------------------------

@router.post("/register", response_model=RegisterPartnerResponse)
def register_partner(req: RegisterPartnerRequest) -> RegisterPartnerResponse:
    """Register a new trading partner in config.yaml and create skeleton rules."""
    if not _CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="config.yaml not found")

    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    profiles = config.get("compare", {}).get("profiles", {})
    if req.profile_name in profiles:
        raise HTTPException(
            status_code=409,
            detail=f"Profile '{req.profile_name}' already exists",
        )

    # Add csv_schema_registry entry
    registry = config.setdefault("csv_schema_registry", {})
    registry[req.profile_name] = {
        "source_dsl": req.source_dsl,
        "compiled_output": req.compiled_output,
        "inbound_dir": req.inbound_dir,
        "transaction_type": req.transaction_type,
    }

    # Add compare profile entry
    rules_file = f"config/compare_rules/{req.profile_name}.yaml"
    compare = config.setdefault("compare", {})
    compare_profiles = compare.setdefault("profiles", {})
    compare_profiles[req.profile_name] = {
        "description": req.description,
        "trading_partner": req.trading_partner,
        "transaction_type": req.transaction_type,
        "match_key": dict(req.match_key),
        "segment_qualifiers": {k: v for k, v in req.segment_qualifiers.items()},
        "rules_file": rules_file,
    }

    # Write updated config
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Create skeleton rules file
    rules_path = _PROJECT_ROOT / rules_file
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    skeleton = {
        "classification": [
            {
                "segment": "*",
                "field": "*",
                "severity": "hard",
                "ignore_case": False,
                "numeric": False,
            }
        ],
        "ignore": [],
    }
    with open(rules_path, "w", encoding="utf-8") as f:
        yaml.dump(skeleton, f, default_flow_style=False, sort_keys=False)

    return RegisterPartnerResponse(
        profile_name=req.profile_name,
        rules_file=rules_file,
        config_updated=True,
        rules_created=True,
    )


# ---------------------------------------------------------------------------
# GET /api/onboard/rules-template
# ---------------------------------------------------------------------------

@router.get("/rules-template", response_model=RulesTemplateResponse)
def rules_template(
    compiled_yaml: str = Query(..., description="Path to compiled YAML schema"),
) -> RulesTemplateResponse:
    """Generate compare rules template from a compiled schema YAML."""
    schema_path = _PROJECT_ROOT / compiled_yaml
    if not schema_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Compiled schema not found: {compiled_yaml}",
        )

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_data = yaml.safe_load(f)

    columns = schema_data.get("schema", {}).get("columns", [])
    if not columns:
        raise HTTPException(
            status_code=422,
            detail="No columns found in compiled schema",
        )

    # Build reverse map: field_name -> record_name from schema.records
    records: Dict[str, List[str]] = schema_data.get("schema", {}).get("records", {})
    field_to_record: Dict[str, str] = {}
    for record_key, field_list in records.items():
        if isinstance(field_list, list):
            for fname in field_list:
                if fname not in field_to_record:
                    field_to_record[fname] = record_key

    classification: List[Dict[str, Any]] = []
    for col in columns:
        col_name: str = col.get("name", "")
        col_type: str = col.get("type", "string")

        is_numeric = col_type in ("float", "integer")
        is_description = "Description" in col_name

        if is_description:
            severity = "soft"
            ignore_case = True
        else:
            severity = "hard"
            ignore_case = False

        classification.append({
            "segment": "*",
            "field": col_name,
            "severity": severity,
            "ignore_case": ignore_case,
            "numeric": is_numeric,
            "record_name": field_to_record.get(col_name, ""),
        })

    # Catch-all rule
    classification.append({
        "segment": "*",
        "field": "*",
        "severity": "hard",
        "ignore_case": False,
        "numeric": False,
        "record_name": "",
    })

    return RulesTemplateResponse(classification=classification, ignore=[])
