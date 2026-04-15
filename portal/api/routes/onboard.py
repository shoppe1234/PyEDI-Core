"""Onboard API routes — trading partner registration and rules template generation."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from fastapi import APIRouter, HTTPException, Query, UploadFile, File as FastAPIFile
from pydantic import BaseModel

from pyedi_core.standards_parser import (
    get_catalog,
    get_message_segments,
    MessageSchema,
    parse_edi_schema,
    scan_standards_dir,
)

router = APIRouter(prefix="/api/onboard", tags=["onboard"])

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "config.yaml"


def _get_standards_dir() -> Path:
    """Resolve standards directory from config or default."""
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        rel = config.get("standards_dir", "./standards")
    else:
        rel = "./standards"
    return _PROJECT_ROOT / rel


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
    match_key: Union[Dict[str, str], List[Dict[str, str]]]
    segment_qualifiers: Dict[str, Optional[str]] = {}
    split_config: Optional[Dict[str, str]] = None


class RegisterPartnerResponse(BaseModel):
    profile_name: str
    rules_file: str
    config_updated: bool
    rules_created: bool


class RulesTemplateResponse(BaseModel):
    classification: List[Dict[str, Any]]
    ignore: List[Any]


# ---------------------------------------------------------------------------
# X12 onboard models
# ---------------------------------------------------------------------------

class X12TypeEntry(BaseModel):
    code: str
    label: str
    map_file: str
    version: str = '5010'
    available_versions: List[str] = ['5010']
    category: str = 'Other'
    description: str = ''
    has_mapping: bool = True


class X12TypesResponse(BaseModel):
    types: List[X12TypeEntry]


class X12Field(BaseModel):
    name: str
    source: str
    section: str


class X12SchemaResponse(BaseModel):
    transaction_type: str
    input_format: str
    segments: List[str]
    fields: List[X12Field]
    match_key_default: Dict[str, str]


class X12ValidateRequest(BaseModel):
    type: str
    sample_path: str


class X12ValidateSegment(BaseModel):
    segment: str
    fields: List[Dict[str, str]]


class X12ValidateResponse(BaseModel):
    transaction_type: str
    segment_count: int
    segments: List[X12ValidateSegment]


class X12UploadMapResponse(BaseModel):
    code: str
    map_file: str
    x12_schema: X12SchemaResponse


# ---------------------------------------------------------------------------
# Standards discovery models
# ---------------------------------------------------------------------------

class StandardVersion(BaseModel):
    version: str
    transaction_count: int


class StandardType(BaseModel):
    standard: str
    versions: List[StandardVersion]


class StandardsCatalogResponse(BaseModel):
    standards: List[StandardType]


class StandardTransaction(BaseModel):
    code: str
    name: str
    file: str
    has_mapping: bool


class TransactionsResponse(BaseModel):
    standard: str
    version: str
    transactions: List[StandardTransaction]


class StandardSegmentRef(BaseModel):
    name: str
    ref_type: str
    min_occurs: int
    max_occurs: int
    children: List['StandardSegmentRef'] = []


class StandardElementDef(BaseModel):
    position: int
    name: str
    data_type: str
    min_occurs: int
    max_occurs: int


class StandardSegmentDef(BaseModel):
    code: str
    name: str
    elements: List[StandardElementDef]


class StandardSchemaResponse(BaseModel):
    code: str
    name: str
    version: str
    standard: str
    functional_group: str
    areas: List[List[StandardSegmentRef]]
    segment_defs: Dict[str, StandardSegmentDef]
    has_mapping: bool
    match_key_default: Dict[str, str]


# ---------------------------------------------------------------------------
# GET /api/onboard/standards
# ---------------------------------------------------------------------------

@router.get("/standards", response_model=StandardsCatalogResponse)
def standards_catalog() -> StandardsCatalogResponse:
    """Return available EDI standards and their versions from the standards directory."""
    standards_dir = _get_standards_dir()
    if not standards_dir.exists():
        raise HTTPException(status_code=404, detail="Standards directory not found")
    catalog = get_catalog(standards_dir)
    result: List[StandardType] = []
    for std_name, versions in sorted(catalog.items()):
        sv_list = [
            StandardVersion(version=v, transaction_count=len(txns))
            for v, txns in sorted(versions.items())
        ]
        result.append(StandardType(standard=std_name, versions=sv_list))
    return StandardsCatalogResponse(standards=result)


# ---------------------------------------------------------------------------
# GET /api/onboard/standards/{standard}/{version}/transactions
# ---------------------------------------------------------------------------

@router.get("/standards/{standard}/{version}/transactions", response_model=TransactionsResponse)
def standards_transactions(standard: str, version: str) -> TransactionsResponse:
    """Return all transaction types for a given standard and version."""
    standards_dir = _get_standards_dir()
    catalog = get_catalog(standards_dir)
    std_data = catalog.get(standard)
    if not std_data:
        raise HTTPException(status_code=404, detail=f"Standard '{standard}' not found")
    txns = std_data.get(version)
    if txns is None:
        raise HTTPException(status_code=404, detail=f"Version '{version}' not found for '{standard}'")

    # Check which have custom mappings in transaction_registry
    registry_codes: set = set()
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        registry = config.get("transaction_registry", {})
        default_map = registry.get("_default_x12", "")
        for code, map_file in registry.items():
            if not code.startswith("_") and map_file != default_map:
                base = code.split("_")[0] if code[0].isdigit() else code
                registry_codes.add(base)

    # Sort by code (numeric)
    sorted_txns = sorted(txns, key=lambda t: t["code"].zfill(6))
    transactions = [
        StandardTransaction(
            code=t["code"],
            name=t["name"],
            file=t["file"],
            has_mapping=t["code"] in registry_codes,
        )
        for t in sorted_txns
    ]
    return TransactionsResponse(standard=standard, version=version, transactions=transactions)


# ---------------------------------------------------------------------------
# GET /api/onboard/standards/{standard}/{version}/{code}/schema
# ---------------------------------------------------------------------------

def _seg_ref_to_model(ref: Any) -> StandardSegmentRef:
    """Convert a SegmentRef dataclass to the Pydantic model."""
    return StandardSegmentRef(
        name=ref.name,
        ref_type=ref.ref_type,
        min_occurs=ref.min_occurs,
        max_occurs=ref.max_occurs,
        children=[_seg_ref_to_model(c) for c in ref.children],
    )


@router.get("/standards/{standard}/{version}/{code}/schema", response_model=StandardSchemaResponse)
def standards_schema(standard: str, version: str, code: str) -> StandardSchemaResponse:
    """Parse and return the full schema for a specific transaction type."""
    standards_dir = _get_standards_dir()
    # Pad version: "4010" -> "v004010"
    padded = version.zfill(6)
    schema_file = standards_dir / standard / f"v{padded}" / "schemas" / f"Message{code}.ediSchema"
    if not schema_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Schema file not found: {standard}/{version}/{code}",
        )

    msg = parse_edi_schema(schema_file)

    # Convert areas
    areas_out: List[List[StandardSegmentRef]] = []
    for area in msg.areas:
        areas_out.append([_seg_ref_to_model(ref) for ref in area])

    # Convert segment defs
    seg_defs_out: Dict[str, StandardSegmentDef] = {}
    for seg_code, seg_def in msg.segment_defs.items():
        seg_defs_out[seg_code] = StandardSegmentDef(
            code=seg_def.code,
            name=seg_def.name,
            elements=[
                StandardElementDef(
                    position=e.position,
                    name=e.name,
                    data_type=e.data_type,
                    min_occurs=e.min_occurs,
                    max_occurs=e.max_occurs,
                )
                for e in seg_def.elements
            ],
        )

    # Check has_mapping
    has_mapping = False
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        registry = config.get("transaction_registry", {})
        default_map = registry.get("_default_x12", "")
        map_file = registry.get(code, "")
        has_mapping = bool(map_file) and map_file != default_map

    match_key = _X12_MATCH_KEY_DEFAULTS.get(code, {})

    return StandardSchemaResponse(
        code=msg.code,
        name=msg.name,
        version=msg.version,
        standard=standard,
        functional_group=msg.functional_group,
        areas=areas_out,
        segment_defs=seg_defs_out,
        has_mapping=has_mapping,
        match_key_default=match_key,
    )


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
    registry_entry: Dict[str, Any] = {
        "source_dsl": req.source_dsl,
        "compiled_output": req.compiled_output,
        "inbound_dir": req.inbound_dir,
        "transaction_type": req.transaction_type,
    }

    # Detect split_key for the registry (pipeline uses this for auto-splitting)
    split_cfg = req.split_config
    if not split_cfg:
        split_cfg = _detect_split_config(req.compiled_output)
    if split_cfg:
        registry_entry["split_key"] = split_cfg["split_key"]

    registry[req.profile_name] = registry_entry

    # Normalize match_key: validate, collapse N=1 list → singleton dict
    mk_in = req.match_key
    if isinstance(mk_in, list):
        if not mk_in:
            raise HTTPException(status_code=400, detail="match_key list is empty")
        has_x12 = any(p.get("segment") and p.get("field") for p in mk_in)
        has_json = any(p.get("json_path") for p in mk_in)
        if has_x12 and has_json:
            raise HTTPException(
                status_code=400,
                detail="match_key parts must all be X12 segment/field or all json_path",
            )
        for p in mk_in:
            if not ((p.get("segment") and p.get("field")) or p.get("json_path")):
                raise HTTPException(
                    status_code=400,
                    detail="each match_key part needs segment+field or json_path",
                )
        match_key_out: Union[Dict[str, str], List[Dict[str, str]]] = (
            dict(mk_in[0]) if len(mk_in) == 1 else [dict(p) for p in mk_in]
        )
    else:
        if not ((mk_in.get("segment") and mk_in.get("field")) or mk_in.get("json_path")):
            raise HTTPException(
                status_code=400,
                detail="match_key needs segment+field or json_path",
            )
        match_key_out = dict(mk_in)

    # Add compare profile entry
    rules_file = f"config/compare_rules/{req.profile_name}.yaml"
    compare = config.setdefault("compare", {})
    compare_profiles = compare.setdefault("profiles", {})
    profile_entry: Dict[str, Any] = {
        "description": req.description,
        "trading_partner": req.trading_partner,
        "transaction_type": req.transaction_type,
        "match_key": match_key_out,
        "segment_qualifiers": {k: v for k, v in req.segment_qualifiers.items()},
        "rules_file": rules_file,
    }

    # Add split_config if provided by wizard or auto-detected from compiled schema
    split_cfg = req.split_config
    if not split_cfg:
        split_cfg = _detect_split_config(req.compiled_output)
    if split_cfg:
        profile_entry["split_config"] = dict(split_cfg)

    compare_profiles[req.profile_name] = profile_entry

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
# Helpers
# ---------------------------------------------------------------------------

def _detect_split_config(compiled_output: str) -> Optional[Dict[str, str]]:
    """Read compiled YAML and extract split_key from record_groups if present."""
    schema_path = _PROJECT_ROOT / compiled_output
    if not schema_path.exists():
        return None
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return None

    record_groups = schema_data.get("record_groups", {})
    for group_data in record_groups.values():
        if group_data.get("group_on_record"):
            key_field = group_data.get("key_field")
            boundary_record = group_data.get("boundary_record")
            if key_field and boundary_record:
                return {
                    "split_key": key_field,
                    "boundary_record": boundary_record,
                }
    return None


class SplitSuggestionResponse(BaseModel):
    split_key: Optional[str] = None
    boundary_record: Optional[str] = None
    source: Optional[str] = None


# ---------------------------------------------------------------------------
# X12 helpers
# ---------------------------------------------------------------------------

# Match-key defaults per X12 transaction type.  Used by x12-schema to
# auto-populate the match key in the wizard.  Keys that appear in the
# compare.profiles section of config.yaml for the built-in types.
_X12_MATCH_KEY_DEFAULTS: Dict[str, Dict[str, str]] = {
    "810": {"segment": "BIG", "field": "BIG02"},
    "850": {"segment": "BEG", "field": "BEG03"},
    "856": {"segment": "BSN", "field": "BSN02"},
    "820": {"segment": "BPR", "field": "BPR16"},
    "855": {"segment": "BAK", "field": "BAK03"},
    "860": {"segment": "BCH", "field": "BCH03"},
}


def _resolve_map_path(rel_path: str) -> Path:
    """Resolve a mapping YAML path, checking both project root and pyedi_core/.

    Config paths like ``./rules/gfs_810_map.yaml`` are relative to pyedi_core/
    (the pipeline CWD), but the portal runs from the project root.
    """
    candidate = _PROJECT_ROOT / rel_path
    if candidate.exists():
        return candidate
    alt = _PROJECT_ROOT / "pyedi_core" / rel_path
    if alt.exists():
        return alt
    return candidate  # will fail downstream with a clear 404


def _parse_mapping_yaml(map_path: Path) -> Dict[str, Any]:
    """Read and return a mapping YAML, raising 404 if missing."""
    if not map_path.exists():
        raise HTTPException(status_code=404, detail=f"Mapping file not found: {map_path}")
    with open(map_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _extract_x12_schema(map_data: Dict[str, Any], code: str) -> X12SchemaResponse:
    """Build an X12SchemaResponse from a parsed mapping YAML."""
    mapping = map_data.get("mapping", {})
    segments_list: List[str] = [
        s["name"] for s in map_data.get("schema", {}).get("segments", [])
    ]

    fields: List[X12Field] = []
    for section in ("header", "lines", "summary"):
        section_data = mapping.get(section)
        if section_data is None:
            continue
        if isinstance(section_data, dict):
            for field_name, field_def in section_data.items():
                source = field_def.get("source", "") if isinstance(field_def, dict) else str(field_def)
                fields.append(X12Field(name=field_name, source=source, section=section))
        elif isinstance(section_data, list):
            # lines are a list of dicts
            for item in section_data:
                if isinstance(item, dict):
                    for field_name, field_def in item.items():
                        source = field_def.get("source", "") if isinstance(field_def, dict) else str(field_def)
                        fields.append(X12Field(name=field_name, source=source, section="lines"))

    # Derive match_key_default from the known defaults or first header field
    match_key = _X12_MATCH_KEY_DEFAULTS.get(code, {})
    if not match_key and fields:
        first_header = next((f for f in fields if f.section == "header"), None)
        if first_header:
            seg = first_header.source.split(".")[0] if "." in first_header.source else ""
            match_key = {"segment": seg, "field": f"{seg}{first_header.source.split('.')[-1].zfill(2)}" if seg else ""}

    return X12SchemaResponse(
        transaction_type=map_data.get("transaction_type", code),
        input_format=map_data.get("input_format", "X12"),
        segments=segments_list,
        fields=fields,
        match_key_default=match_key,
    )


# ---------------------------------------------------------------------------
# GET /api/onboard/x12-types
# ---------------------------------------------------------------------------

_X12_META: Dict[str, tuple] = {
    '810': ('Purchasing', 'Invoice'),
    '820': ('Financial', 'Payment Order/Remittance Advice'),
    '834': ('Insurance', 'Benefit Enrollment and Maintenance'),
    '835': ('Insurance', 'Health Care Claim Payment/Advice'),
    '837': ('Insurance', 'Health Care Claim'),
    '850': ('Purchasing', 'Purchase Order'),
    '855': ('Purchasing', 'Purchase Order Acknowledgment'),
    '856': ('Shipping', 'Ship Notice/Manifest'),
    '860': ('Purchasing', 'Purchase Order Change Request'),
    '997': ('Acknowledgment', 'Functional Acknowledgment'),
}


@router.get("/x12-types", response_model=X12TypesResponse)
def x12_types() -> X12TypesResponse:
    """Return X12 transaction types — standards as base, overlaid with registry mappings."""
    standards_dir = _get_standards_dir()
    catalog = get_catalog(standards_dir)
    x12_catalog = catalog.get("x12", {})

    # Build set of codes with custom (non-default) mappings
    registry_codes: set = set()
    registry_map_files: Dict[str, str] = {}
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        registry = config.get("transaction_registry", {})
        default_map = registry.get("_default_x12", "")
        for code, map_file in registry.items():
            if not code.startswith("_") and map_file != default_map:
                base = code.split("_")[0] if code[0].isdigit() else code
                registry_codes.add(base)
                registry_map_files[base] = map_file

    # Use highest version (5010) as the default catalog source
    highest_version = sorted(x12_catalog.keys(), reverse=True)[0] if x12_catalog else "5010"
    txns = x12_catalog.get(highest_version, [])

    # Collect all versions per code
    code_versions: Dict[str, List[str]] = {}
    for v, v_txns in x12_catalog.items():
        for t in v_txns:
            code_versions.setdefault(t["code"], []).append(v)

    entries: List[X12TypeEntry] = []
    for t in sorted(txns, key=lambda x: x["code"].zfill(6)):
        code = t["code"]
        meta = _X12_META.get(code, ('Other', ''))
        has_mapping = code in registry_codes
        map_file = registry_map_files.get(code, f"./rules/default_x12_map.yaml")
        entries.append(X12TypeEntry(
            code=code,
            label=t["name"],
            map_file=map_file,
            version=highest_version,
            available_versions=sorted(code_versions.get(code, [highest_version])),
            category=meta[0],
            description=t["name"],
            has_mapping=has_mapping,
        ))

    return X12TypesResponse(types=entries)


# ---------------------------------------------------------------------------
# GET /api/onboard/x12-types/{code}/versions
# ---------------------------------------------------------------------------

@router.get("/x12-types/{code}/versions")
def get_x12_versions(code: str) -> Dict[str, List[str]]:
    """Return available X12 versions for a transaction type from standards."""
    standards_dir = _get_standards_dir()
    catalog = get_catalog(standards_dir)
    x12 = catalog.get("x12", {})
    versions = [v for v, txns in x12.items() if any(t["code"] == code for t in txns)]
    if not versions:
        raise HTTPException(status_code=404, detail=f"No versions found for '{code}'")
    return {"versions": sorted(versions)}


# ---------------------------------------------------------------------------
# GET /api/onboard/x12-schema
# ---------------------------------------------------------------------------

def _schema_from_standard(msg: MessageSchema, code: str) -> X12SchemaResponse:
    """Convert a MessageSchema from standards parser to X12SchemaResponse."""
    segments: List[str] = []
    seen: set = set()
    for area in msg.areas:
        for ref in area:
            if ref.ref_type == 'segment' and ref.name not in seen:
                seen.add(ref.name)
                segments.append(ref.name)
            for child in ref.children:
                if child.ref_type == 'segment' and child.name not in seen:
                    seen.add(child.name)
                    segments.append(child.name)

    fields: List[X12Field] = []
    for area_idx, area in enumerate(msg.areas):
        section = 'header' if area_idx == 0 else 'lines' if area_idx == 1 else 'summary'
        for ref in area:
            seg_code = ref.name if ref.ref_type == 'segment' else None
            if seg_code and seg_code in msg.segment_defs:
                for elem in msg.segment_defs[seg_code].elements:
                    fields.append(X12Field(
                        name=f"{seg_code}{str(elem.position).zfill(2)}",
                        source=f"{seg_code}.{elem.position}",
                        section=section,
                    ))

    match_key = _X12_MATCH_KEY_DEFAULTS.get(code, {})
    return X12SchemaResponse(
        transaction_type=code,
        input_format='X12',
        segments=segments,
        fields=fields,
        match_key_default=match_key,
    )


@router.get("/x12-schema", response_model=X12SchemaResponse)
def x12_schema(
    type: str = Query(..., description="X12 transaction type code (e.g. 810)"),
    version: Optional[str] = Query(None, description="X12 version (e.g. 5010)"),
) -> X12SchemaResponse:
    """Parse a mapping YAML and return its fields for wizard review.

    Falls back to standards .ediSchema if no mapping YAML matches.
    """
    # Try mapping YAML first
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        registry = config.get("transaction_registry", {})
        map_rel = registry.get(type)

        if map_rel:
            # If version specified, try version-specific map
            if version:
                for reg_code, reg_map in registry.items():
                    if reg_code.startswith("_"):
                        continue
                    base = reg_code.split("_")[0] if reg_code[0].isdigit() else reg_code
                    if base != type:
                        continue
                    candidate_path = _resolve_map_path(reg_map)
                    if not candidate_path.exists():
                        continue
                    try:
                        with open(candidate_path, "r", encoding="utf-8") as f:
                            candidate_data = yaml.safe_load(f)
                    except (yaml.YAMLError, OSError):
                        continue
                    if candidate_data.get("x12_version") == version:
                        map_rel = reg_map
                        break

            map_path = _resolve_map_path(map_rel)
            # Only use mapping YAML if it's not the default stub
            if map_path.exists() and map_path.name != "default_x12_map.yaml":
                map_data = _parse_mapping_yaml(map_path)
                return _extract_x12_schema(map_data, type)

    # Fall back to standards directory
    if version:
        standards_dir = _get_standards_dir()
        padded = version.zfill(6)
        schema_file = standards_dir / "x12" / f"v{padded}" / "schemas" / f"Message{type}.ediSchema"
        if schema_file.exists():
            msg = parse_edi_schema(schema_file)
            return _schema_from_standard(msg, type)

    raise HTTPException(status_code=404, detail=f"No schema found for type '{type}'")


# ---------------------------------------------------------------------------
# POST /api/onboard/x12-validate
# ---------------------------------------------------------------------------

@router.post("/x12-validate", response_model=X12ValidateResponse)
def x12_validate(req: X12ValidateRequest) -> X12ValidateResponse:
    """Parse a sample EDI file and return the extracted segments as preview."""
    import collections
    import collections.abc
    collections.Iterable = collections.abc.Iterable  # type: ignore[attr-defined]
    from badx12 import Parser

    sample_path = _PROJECT_ROOT / req.sample_path
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail=f"Sample file not found: {req.sample_path}")

    try:
        with open(sample_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Input sanitization (same as x12_handler)
        if content and len(content) > 106:
            potential_terminator = content[105]
            if potential_terminator not in ("\r", "\n"):
                content = content.replace("\n", "").replace("\r", "")

        parser = Parser()
        document = parser.parse_document(content)
        full_data = document.to_dict()

        interchange = full_data.get("document", {}).get("interchange", {})
        segments: List[X12ValidateSegment] = []

        def _add_seg(name: str, fields_list: List[Dict[str, Any]]) -> None:
            formatted = [
                {"name": f"{name}{str(i).zfill(2)}", "content": fld.get("content", "")}
                for i, fld in enumerate(fields_list, 1)
            ]
            segments.append(X12ValidateSegment(segment=name, fields=formatted))

        if "header" in interchange:
            _add_seg("ISA", interchange["header"].get("fields", []))

        for group in interchange.get("groups", []):
            if "header" in group:
                _add_seg("GS", group["header"].get("fields", []))
            for txn in group.get("transaction_sets", []):
                if "header" in txn:
                    _add_seg("ST", txn["header"].get("fields", []))
                for body_seg in txn.get("body", []):
                    fields = body_seg.get("fields", [])
                    if not fields:
                        continue
                    seg_name = fields[0].get("content", "UNKNOWN")
                    _add_seg(seg_name, fields[1:])
                if "trailer" in txn:
                    _add_seg("SE", txn["trailer"].get("fields", []))
            if "trailer" in group:
                _add_seg("GE", group["trailer"].get("fields", []))

        if "trailer" in interchange:
            _add_seg("IEA", interchange["trailer"].get("fields", []))

        # Detect transaction type from ST01
        txn_type = req.type
        for seg in segments:
            if seg.segment == "ST":
                for fld in seg.fields:
                    if fld.get("name") == "ST01":
                        txn_type = fld.get("content", txn_type)
                        break
                break

        return X12ValidateResponse(
            transaction_type=txn_type,
            segment_count=len(segments),
            segments=segments,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse sample EDI: {e}")


# ---------------------------------------------------------------------------
# POST /api/onboard/x12-upload-map
# ---------------------------------------------------------------------------

@router.post("/x12-upload-map", response_model=X12UploadMapResponse)
async def x12_upload_map(
    map_file: UploadFile = FastAPIFile(..., description="Mapping YAML file"),
) -> X12UploadMapResponse:
    """Upload a new mapping YAML, validate it, add to transaction_registry."""
    content = await map_file.read()
    try:
        map_data = yaml.safe_load(content.decode("utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {e}")

    # Validate required structure
    if not isinstance(map_data, dict):
        raise HTTPException(status_code=422, detail="Mapping YAML must be a dict")
    if "transaction_type" not in map_data:
        raise HTTPException(status_code=422, detail="Missing 'transaction_type' key")
    if "mapping" not in map_data:
        raise HTTPException(status_code=422, detail="Missing 'mapping' key")

    # Derive a registry code from the transaction_type
    txn_type: str = map_data["transaction_type"]
    # Strip suffix like _INVOICE, _PURCHASE_ORDER to get the numeric code
    code = txn_type.split("_")[0] if "_" in txn_type else txn_type

    # Save file to rules directory
    rules_dir = _PROJECT_ROOT / "pyedi_core" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    dest_filename = f"{code.lower()}_map.yaml"
    dest_path = rules_dir / dest_filename
    if dest_path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Mapping file already exists: {dest_filename}. Remove it first or use a different transaction_type.",
        )

    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(content.decode("utf-8"))

    # Add to transaction_registry in config.yaml
    rel_map_path = f"./rules/{dest_filename}"
    if not _CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="config.yaml not found")

    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    registry = config.setdefault("transaction_registry", {})
    registry[code] = rel_map_path

    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    x12_schema = _extract_x12_schema(map_data, code)
    return X12UploadMapResponse(code=code, map_file=rel_map_path, x12_schema=x12_schema)


# ---------------------------------------------------------------------------
# GET /api/onboard/split-suggestion
# ---------------------------------------------------------------------------

@router.get("/split-suggestion", response_model=SplitSuggestionResponse)
def split_suggestion(
    compiled_yaml: str = Query(..., description="Path to compiled YAML schema"),
) -> SplitSuggestionResponse:
    """Detect split key from compiled schema record_groups metadata."""
    result = _detect_split_config(compiled_yaml)
    if result:
        return SplitSuggestionResponse(
            split_key=result["split_key"],
            boundary_record=result["boundary_record"],
            source="record_groups",
        )
    return SplitSuggestionResponse()


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


# ---------------------------------------------------------------------------
# DELETE /api/onboard/profile/{name}
# ---------------------------------------------------------------------------

@router.delete("/profile/{name}")
def delete_profile(name: str) -> Dict[str, str]:
    """Delete a trading partner profile from config.yaml and remove its rules file."""
    if not _CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="config.yaml not found")

    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Remove from compare.profiles
    profiles = config.get("compare", {}).get("profiles", {})
    if name not in profiles:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    del profiles[name]

    # Remove from csv_schema_registry if present
    csv_registry = config.get("csv_schema_registry", {})
    if name in csv_registry:
        del csv_registry[name]

    # Write updated config
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Delete rules file if it exists
    import os
    rules_path = _PROJECT_ROOT / "config" / "compare_rules" / f"{name}.yaml"
    if rules_path.exists():
        os.remove(rules_path)

    return {"status": "deleted", "profile": name}
