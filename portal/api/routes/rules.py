"""Rules tier management API routes — CRUD for universal, transaction-type, and effective views."""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pyedi_core.comparator import list_profiles, load_profile
from pyedi_core.comparator.models import FieldRule
from pyedi_core.comparator.rules import (
    get_resolved_field_rule,
    load_rules,
    load_tiered_rules,
    merge_rules,
)

router = APIRouter(prefix="/api/rules", tags=["rules"])

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_CONFIG_PATH = str(_PROJECT_ROOT / "config" / "config.yaml")
_RULES_DIR = str(_PROJECT_ROOT / "config" / "compare_rules")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TierInfoResponse(BaseModel):
    tier: str
    name: str
    file: str
    rule_count: int
    ignore_count: int


class TierListResponse(BaseModel):
    tiers: List[TierInfoResponse]


class RulesBody(BaseModel):
    classification: List[Dict[str, Any]] = []
    ignore: List[Dict[str, Any]] = []


class EffectiveRuleResponse(BaseModel):
    segment: str
    field: str
    severity: str
    ignore_case: bool
    numeric: bool
    conditional_qualifier: Optional[str] = None
    amount_variance: Optional[float] = None
    tier: str


class EffectiveRulesResponse(BaseModel):
    rules: List[EffectiveRuleResponse]
    ignore: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_rules(path: str) -> tuple[int, int]:
    """Return (classification_count, ignore_count) for a rules YAML file."""
    try:
        rules = load_rules(path)
        return len(rules.classification), len(rules.ignore)
    except Exception:
        return 0, 0


# ---------------------------------------------------------------------------
# GET /api/rules/tiers
# ---------------------------------------------------------------------------


@router.get("/tiers", response_model=TierListResponse)
def get_tiers() -> TierListResponse:
    """List all tier files with rule counts."""
    tiers: list[TierInfoResponse] = []

    # Universal
    universal_path = os.path.join(_RULES_DIR, "_universal.yaml")
    if os.path.isfile(universal_path):
        rc, ic = _count_rules(universal_path)
        tiers.append(TierInfoResponse(
            tier="universal", name="Universal", file="_universal.yaml",
            rule_count=rc, ignore_count=ic,
        ))

    # Transaction-type files (_global_*.yaml)
    for path in sorted(glob.glob(os.path.join(_RULES_DIR, "_global_*.yaml"))):
        fname = os.path.basename(path)
        txn_type = fname.replace("_global_", "").replace(".yaml", "")
        rc, ic = _count_rules(path)
        tiers.append(TierInfoResponse(
            tier="transaction", name=f"Transaction {txn_type}", file=fname,
            rule_count=rc, ignore_count=ic,
        ))

    # Partner files from config profiles
    profiles = list_profiles(_CONFIG_PATH)
    for profile in profiles:
        if profile.rules_file and os.path.isfile(profile.rules_file):
            rc, ic = _count_rules(profile.rules_file)
            tiers.append(TierInfoResponse(
                tier="partner", name=profile.name, file=os.path.basename(profile.rules_file),
                rule_count=rc, ignore_count=ic,
            ))

    return TierListResponse(tiers=tiers)


# ---------------------------------------------------------------------------
# GET/PUT /api/rules/universal
# ---------------------------------------------------------------------------


@router.get("/universal", response_model=RulesBody)
def get_universal() -> RulesBody:
    """Read universal rules."""
    path = os.path.join(_RULES_DIR, "_universal.yaml")
    if not os.path.isfile(path):
        return RulesBody()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return RulesBody(
        classification=data.get("classification", []) or [],
        ignore=data.get("ignore", []) or [],
    )


@router.put("/universal", response_model=RulesBody)
def update_universal(body: RulesBody) -> RulesBody:
    """Update universal rules."""
    path = os.path.join(_RULES_DIR, "_universal.yaml")
    data = {
        "classification": body.classification,
        "ignore": body.ignore,
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return body


# ---------------------------------------------------------------------------
# GET/PUT/DELETE /api/rules/transaction/{txn_type}
# ---------------------------------------------------------------------------


@router.get("/transaction/{txn_type}", response_model=RulesBody)
def get_transaction(txn_type: str) -> RulesBody:
    """Read transaction-type rules."""
    path = os.path.join(_RULES_DIR, f"_global_{txn_type}.yaml")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"No transaction rules for type '{txn_type}'")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return RulesBody(
        classification=data.get("classification", []) or [],
        ignore=data.get("ignore", []) or [],
    )


@router.put("/transaction/{txn_type}", response_model=RulesBody)
def update_transaction(txn_type: str, body: RulesBody) -> RulesBody:
    """Update transaction-type rules (creates file if needed)."""
    path = os.path.join(_RULES_DIR, f"_global_{txn_type}.yaml")
    data = {
        "classification": body.classification,
        "ignore": body.ignore,
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return body


@router.delete("/transaction/{txn_type}")
def delete_transaction(txn_type: str) -> dict[str, str]:
    """Delete transaction-type rules file."""
    path = os.path.join(_RULES_DIR, f"_global_{txn_type}.yaml")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"No transaction rules for type '{txn_type}'")
    os.remove(path)
    return {"status": "deleted", "txn_type": txn_type}


# ---------------------------------------------------------------------------
# GET /api/rules/effective/{profile_name}
# ---------------------------------------------------------------------------


@router.get("/effective/{profile_name}", response_model=EffectiveRulesResponse)
def get_effective(profile_name: str) -> EffectiveRulesResponse:
    """Get merged effective rules for a profile with tier provenance."""
    try:
        profile = load_profile(_CONFIG_PATH, profile_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    rules_dir = os.path.dirname(profile.rules_file) if profile.rules_file else _RULES_DIR
    tiered = load_tiered_rules(rules_dir, profile.transaction_type, profile.rules_file)

    # Collect all unique (segment, field) keys across all 3 tiers
    all_keys: set[tuple[str, str]] = set()
    for tier_rules in [tiered.universal, tiered.transaction, tiered.partner]:
        for rule in tier_rules.classification:
            all_keys.add((rule.segment, rule.field))

    # Resolve each key with provenance
    effective: list[EffectiveRuleResponse] = []
    for segment, field in sorted(all_keys):
        resolved = get_resolved_field_rule(tiered, segment, field)
        effective.append(EffectiveRuleResponse(
            segment=segment,
            field=field,
            severity=resolved.rule.severity,
            ignore_case=resolved.rule.ignore_case,
            numeric=resolved.rule.numeric,
            conditional_qualifier=resolved.rule.conditional_qualifier,
            amount_variance=resolved.rule.amount_variance,
            tier=resolved.tier,
        ))

    # Merge ignore lists across tiers
    seen_ignores: set[tuple[str, str]] = set()
    merged_ignores: list[dict[str, Any]] = []
    for tier_rules in [tiered.universal, tiered.transaction, tiered.partner]:
        for entry in tier_rules.ignore:
            key = (entry.get("segment", ""), entry.get("field", ""))
            if key not in seen_ignores:
                seen_ignores.add(key)
                merged_ignores.append(entry)

    return EffectiveRulesResponse(rules=effective, ignore=merged_ignores)
