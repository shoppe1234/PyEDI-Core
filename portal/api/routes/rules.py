"""Rules tier management API routes — CRUD for universal, transaction-type, and effective views."""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, HTTPException, Query
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


# ---------------------------------------------------------------------------
# GET /api/rules/field-options
# ---------------------------------------------------------------------------


class SegmentOption(BaseModel):
    name: str
    label: str
    fields: List[str]


class FieldOptionsResponse(BaseModel):
    format: str  # "edi" | "csv" | "xml" | "unknown"
    segments: List[SegmentOption]


def _detect_profile_format(profile_name: str) -> str:
    """Determine format (edi/csv/xml) for a compare profile."""
    try:
        profile = load_profile(_CONFIG_PATH, profile_name)
    except ValueError:
        return "unknown"

    if profile.match_key.segment:
        return "edi"
    # Check csv_schema_registry for a compiled YAML
    compiled = _find_compiled_yaml_for_profile(profile)
    if compiled:
        return "csv"
    if "xml" in profile.name or "cxml" in profile.name:
        return "xml"
    return "csv"  # default for json_path-based profiles


def _load_config() -> dict:
    """Load config.yaml once."""
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _find_compiled_yaml_for_profile(profile: Any) -> Optional[str]:
    """Find the compiled YAML path for a compare profile via csv_schema_registry."""
    config = _load_config()
    registry = config.get("csv_schema_registry", {})

    # Try exact name match first
    if profile.name in registry:
        path = registry[profile.name].get("compiled_output", "")
        if path:
            return str(_PROJECT_ROOT / path)

    # Match by trading_partner + transaction_type
    for _key, entry in registry.items():
        tp = profile.trading_partner.lower() if profile.trading_partner else ""
        entry_name = _key.lower()
        txn_match = entry.get("transaction_type", "") == profile.transaction_type
        partner_match = tp and tp in entry_name
        if txn_match and partner_match:
            path = entry.get("compiled_output", "")
            if path:
                return str(_PROJECT_ROOT / path)

    # Fallback: match by transaction_type alone (pick first)
    for _key, entry in registry.items():
        if entry.get("transaction_type", "") == profile.transaction_type:
            path = entry.get("compiled_output", "")
            if path:
                return str(_PROJECT_ROOT / path)

    return None


def _extract_csv_options(compiled_yaml_path: str) -> List[SegmentOption]:
    """Extract segment/field options from a compiled YAML schema."""
    if not os.path.isfile(compiled_yaml_path):
        return []

    with open(compiled_yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    schema = data.get("schema", {})
    columns = schema.get("columns", [])
    records = schema.get("records", {})

    all_field_names = [c.get("name", "") for c in columns if c.get("name")]

    segments: list[SegmentOption] = []

    if records and isinstance(records, dict) and any(records.values()):
        # Multi-record flat file: each record is a segment
        for record_name, record_fields in records.items():
            if not record_fields:
                continue
            segments.append(SegmentOption(
                name=record_name,
                label=record_name,
                fields=list(record_fields),
            ))
    else:
        # Single-record: all columns under wildcard
        segments.append(SegmentOption(
            name="*",
            label="* (all records)",
            fields=all_field_names,
        ))

    # Always add wildcard segment with all fields
    if records and isinstance(records, dict) and any(records.values()):
        segments.append(SegmentOption(
            name="*",
            label="* (all records)",
            fields=all_field_names,
        ))

    return segments


# Standard X12 envelope/common segments and typical element counts
_X12_SEGMENT_ELEMENTS: Dict[str, int] = {
    "ISA": 16, "GS": 8, "ST": 3, "SE": 2, "GE": 2, "IEA": 2,
    "BIG": 10, "BEG": 12, "BSN": 8, "BPR": 21, "BAK": 9, "BCH": 12,
    "N1": 6, "N2": 2, "N3": 2, "N4": 7,
    "REF": 4, "DTM": 6, "PER": 9,
    "IT1": 25, "PO1": 25, "PID": 9,
    "TDS": 4, "CTT": 7, "SAC": 16,
    "HL": 4, "LIN": 31, "SN1": 10,
    "CUR": 21, "FOB": 13, "TD5": 17,
    "ISS": 8, "AMT": 3, "QTY": 4,
    "TXI": 10, "ENT": 5, "POC": 25,
}


def _extract_edi_options(segment_qualifiers: Dict[str, Optional[str]]) -> List[SegmentOption]:
    """Generate segment/field options for EDI X12 from segment_qualifiers."""
    segments: list[SegmentOption] = []

    # Profile-specific segments from qualifiers
    for seg_name in sorted(segment_qualifiers.keys()):
        elem_count = _X12_SEGMENT_ELEMENTS.get(seg_name, 15)
        fields = [f"{seg_name}{str(i).zfill(2)}" for i in range(1, elem_count + 1)]
        segments.append(SegmentOption(name=seg_name, label=seg_name, fields=fields))

    # Add common envelope/structural segments not already in qualifiers
    for seg_name in ["ISA", "GS", "ST", "SE", "GE", "IEA"]:
        if seg_name not in segment_qualifiers:
            elem_count = _X12_SEGMENT_ELEMENTS[seg_name]
            fields = [f"{seg_name}{str(i).zfill(2)}" for i in range(1, elem_count + 1)]
            segments.append(SegmentOption(name=seg_name, label=f"{seg_name} (envelope)", fields=fields))

    # Add common body segments not already present
    common_body = ["BIG", "BEG", "BSN", "BPR", "BAK", "BCH",
                   "N1", "N2", "N3", "N4", "REF", "DTM", "PER",
                   "IT1", "PO1", "PID", "TDS", "CTT", "SAC",
                   "HL", "LIN", "SN1", "CUR", "FOB", "TD5",
                   "ISS", "AMT", "QTY", "TXI", "ENT", "POC"]
    existing = set(segment_qualifiers.keys()) | {"ISA", "GS", "ST", "SE", "GE", "IEA"}
    for seg_name in common_body:
        if seg_name not in existing:
            elem_count = _X12_SEGMENT_ELEMENTS[seg_name]
            fields = [f"{seg_name}{str(i).zfill(2)}" for i in range(1, elem_count + 1)]
            segments.append(SegmentOption(name=seg_name, label=seg_name, fields=fields))

    # Wildcard
    all_fields: list[str] = []
    for s in segments:
        all_fields.extend(s.fields)
    segments.append(SegmentOption(name="*", label="* (all segments)", fields=sorted(set(all_fields))))

    return segments


def _get_all_compiled_yamls() -> List[str]:
    """Return paths to all compiled YAML schemas."""
    config = _load_config()
    registry = config.get("csv_schema_registry", {})
    paths: set[str] = set()
    for entry in registry.values():
        p = entry.get("compiled_output", "")
        if p:
            full = str(_PROJECT_ROOT / p)
            if os.path.isfile(full):
                paths.add(full)
    return list(paths)


@router.get("/field-options", response_model=FieldOptionsResponse)
def get_field_options(
    profile: Optional[str] = Query(None, description="Compare profile name (for partner tier)"),
    format: Optional[str] = Query(None, description="Format filter: edi, csv, xml (for universal tier)"),
    transaction_type: Optional[str] = Query(None, description="Transaction type (for transaction tier)"),
) -> FieldOptionsResponse:
    """Return segment/field dropdown options based on context.

    - If ``profile`` is given, detect format from that profile and return its fields.
    - If ``format`` is given (universal tier), aggregate across all profiles/schemas of that format.
    - If ``transaction_type`` is given, aggregate from profiles of that type.
    """

    # --- Profile-specific (partner tier) ---
    if profile:
        try:
            prof = load_profile(_CONFIG_PATH, profile)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        fmt = _detect_profile_format(profile)

        if fmt == "edi":
            return FieldOptionsResponse(
                format="edi",
                segments=_extract_edi_options(prof.segment_qualifiers),
            )
        elif fmt == "csv":
            compiled = _find_compiled_yaml_for_profile(prof)
            if compiled:
                return FieldOptionsResponse(format="csv", segments=_extract_csv_options(compiled))
            return FieldOptionsResponse(format="csv", segments=[])
        else:
            return FieldOptionsResponse(format=fmt, segments=[])

    # --- Transaction-type tier ---
    if transaction_type:
        profiles_list = list_profiles(_CONFIG_PATH)
        matching = [p for p in profiles_list if p.transaction_type == transaction_type]

        if not matching:
            return FieldOptionsResponse(format="unknown", segments=[])

        # Use first matching profile to determine format + options
        first = matching[0]
        fmt = _detect_profile_format(first.name)

        if fmt == "edi":
            # Merge segment_qualifiers across all matching profiles
            merged_quals: Dict[str, Optional[str]] = {}
            for p in matching:
                merged_quals.update(p.segment_qualifiers)
            return FieldOptionsResponse(format="edi", segments=_extract_edi_options(merged_quals))
        elif fmt == "csv":
            compiled = _find_compiled_yaml_for_profile(first)
            if compiled:
                return FieldOptionsResponse(format="csv", segments=_extract_csv_options(compiled))
            return FieldOptionsResponse(format="csv", segments=[])
        else:
            return FieldOptionsResponse(format=fmt, segments=[])

    # --- Format-based (universal tier with format toggle) ---
    if format:
        fmt = format.lower()

        if fmt == "edi":
            # Aggregate segment_qualifiers from all EDI profiles
            profiles_list = list_profiles(_CONFIG_PATH)
            merged_quals: Dict[str, Optional[str]] = {}
            for p in profiles_list:
                if p.match_key.segment:
                    merged_quals.update(p.segment_qualifiers)
            return FieldOptionsResponse(format="edi", segments=_extract_edi_options(merged_quals))

        elif fmt == "csv":
            # Aggregate from all compiled YAMLs
            all_yamls = _get_all_compiled_yamls()
            merged_segments: Dict[str, set[str]] = {}
            for yp in all_yamls:
                for seg in _extract_csv_options(yp):
                    if seg.name not in merged_segments:
                        merged_segments[seg.name] = set()
                    merged_segments[seg.name].update(seg.fields)

            segments = [
                SegmentOption(name=name, label=name if name != "*" else "* (all records)", fields=sorted(fields))
                for name, fields in sorted(merged_segments.items())
            ]
            return FieldOptionsResponse(format="csv", segments=segments)

        else:
            # XML — no pre-compiled schema available
            return FieldOptionsResponse(format="xml", segments=[])

    # No params — return empty
    return FieldOptionsResponse(format="unknown", segments=[])
