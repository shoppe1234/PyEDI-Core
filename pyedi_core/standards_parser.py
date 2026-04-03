"""Parser for .ediSchema DSL files from certPortal standards.

Extracts message metadata, area/segment structure, segment definitions,
and element definitions from the proprietary .ediSchema format.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SegmentRef:
    """A segment or segment group reference within an area."""
    name: str
    ref_type: str  # "segment" or "segmentGroup"
    min_occurs: int
    max_occurs: int  # -1 for unbounded
    children: List['SegmentRef'] = field(default_factory=list)


@dataclass
class ElementDef:
    """An element within a segment definition."""
    position: int  # 1-based position (01, 02, ...)
    element_id: str  # e.g., "373", "C040"
    element_type: str  # "simpleElement" or "compositeElement"
    min_occurs: int
    max_occurs: int
    name: str = ''
    data_type: str = ''


@dataclass
class SegmentDef:
    """A segment definition with its elements."""
    code: str  # e.g., "BIG", "ST"
    name: str  # e.g., "Beginning Segment for Invoice"
    elements: List[ElementDef] = field(default_factory=list)


@dataclass
class MessageSchema:
    """Parsed representation of a single .ediSchema message."""
    code: str  # e.g., "810", "850"
    name: str  # e.g., "Invoice", "Purchase Order"
    version: str  # e.g., "004010", "005010"
    functional_group: str  # e.g., "IN", "PO"
    standard_type: str  # "x12" or "edifact"
    areas: List[List[SegmentRef]] = field(default_factory=list)
    segment_defs: Dict[str, SegmentDef] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class _State(Enum):
    TOP = auto()
    MESSAGE = auto()
    AREA = auto()
    SEGMENT_GROUP = auto()
    SEGMENT_DEF = auto()
    ELEMENT_DEF = auto()
    COMPOSITE_DEF = auto()
    SKIP_BLOCK = auto()


# Regex patterns
_RE_DEF_MESSAGE = re.compile(r'def\s+message\s+(\w+)\s*\{')
_RE_DEF_AREA = re.compile(r'def\s+area\s+(\d+)\s*\{')
_RE_DEF_SEG_GROUP = re.compile(r'def\s+segmentGroup\s+(\w+)\s*\{')
_RE_DEF_SEGMENT = re.compile(r'def\s+segment\s+(\w+)\s*\{')
_RE_DEF_SIMPLE_ELEM = re.compile(r'def\s+simpleElement\s+(\w+)\s*\{')
_RE_DEF_COMPOSITE_ELEM = re.compile(r'def\s+compositeElement\s+(\w+)\s*\{')
_RE_SEG_REF = re.compile(
    r'(\d+)\s+(segment|segmentGroup)\s+(\w+)\s+\[(\d*)\.?\.?(\d*|\*)\]'
)
_RE_SEG_REF_EMPTY = re.compile(
    r'(\d+)\s+(segment|segmentGroup)\s+(\w+)\s+\[\]'
)
_RE_ELEM_REF = re.compile(
    r'(\d+)\s+(simpleElement|compositeElement)\s+(\w+)\s+\[(\d*)\.?\.?(\d*|\*)\]'
)
_RE_NAME = re.compile(r'name\s*=\s*"([^"]*)"')
_RE_VERSION = re.compile(r'version\s*=\s*"([^"]*)"')
_RE_FUNC_GROUP = re.compile(r'functionalGroup\s*=\s*functionalGroups\.(\w+)')
_RE_TYPE = re.compile(r'type\s*=\s*types\.(\w+)')
_RE_MIN_LEN = re.compile(r'minLength\s*=\s*(\d+)')
_RE_MAX_LEN = re.compile(r'maxLength\s*=\s*(\d+)')


def _parse_cardinality(min_s: str, max_s: str) -> Tuple[int, int]:
    """Parse min/max cardinality strings into ints (-1 for unbounded)."""
    min_val = int(min_s) if min_s else 0
    if max_s == '*' or max_s == '':
        max_val = -1
    else:
        max_val = int(max_s)
    return min_val, max_val


# ---------------------------------------------------------------------------
# Full parser
# ---------------------------------------------------------------------------

def parse_edi_schema(file_path: Path) -> MessageSchema:
    """Parse a .ediSchema file and return a MessageSchema."""
    lines = file_path.read_text(encoding='utf-8', errors='replace').splitlines()

    # Detect standard type from path
    path_str = str(file_path).replace('\\', '/')
    if '/x12/' in path_str:
        standard_type = 'x12'
    elif '/edifact/' in path_str:
        standard_type = 'edifact'
    else:
        standard_type = 'unknown'

    schema = MessageSchema(
        code='', name='', version='', functional_group='',
        standard_type=standard_type,
    )

    state = _State.TOP
    # Stack for tracking nested segment groups: list of (state, container)
    # where container is the list that segment refs are appended to
    state_stack: List[Tuple[_State, List[SegmentRef]]] = []
    current_area_refs: List[SegmentRef] = []
    current_seg_def: Optional[SegmentDef] = None
    current_elem_id: Optional[str] = None
    current_elem_name: str = ''
    current_elem_data_type: str = ''
    skip_depth: int = 0
    depth: int = 0  # brace depth within current block

    # Element definitions: id -> (name, data_type)
    elem_defs: Dict[str, Tuple[str, str]] = {}

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('//'):
            continue

        # --- SKIP_BLOCK: skip composite internals, identifierValues, etc. ---
        if state == _State.SKIP_BLOCK:
            skip_depth += stripped.count('{') - stripped.count('}')
            if skip_depth <= 0:
                state = state_stack.pop()[0] if state_stack else _State.TOP
                skip_depth = 0
            continue

        # --- ELEMENT_DEF ---
        if state == _State.ELEMENT_DEF:
            if '}' in stripped:
                if current_elem_id:
                    elem_defs[current_elem_id] = (current_elem_name, current_elem_data_type)
                current_elem_id = None
                current_elem_name = ''
                current_elem_data_type = ''
                state = state_stack.pop()[0] if state_stack else _State.TOP
                continue
            m = _RE_NAME.search(stripped)
            if m:
                current_elem_name = m.group(1)
                continue
            m = _RE_TYPE.search(stripped)
            if m:
                current_elem_data_type = m.group(1)
                continue
            # identifierValues block — skip it
            if 'identifierValues' in stripped and '{' in stripped:
                state_stack.append((state, []))
                state = _State.SKIP_BLOCK
                skip_depth = 1
            continue

        # --- COMPOSITE_DEF: skip internals ---
        if state == _State.COMPOSITE_DEF:
            if '}' in stripped:
                state = state_stack.pop()[0] if state_stack else _State.TOP
                continue
            # identifierValues block — skip
            if 'identifierValues' in stripped and '{' in stripped:
                state_stack.append((state, []))
                state = _State.SKIP_BLOCK
                skip_depth = 1
            continue

        # --- SEGMENT_DEF ---
        if state == _State.SEGMENT_DEF:
            if stripped == '}':
                if current_seg_def:
                    # Resolve element names from elem_defs
                    for elem in current_seg_def.elements:
                        if elem.element_id in elem_defs:
                            info = elem_defs[elem.element_id]
                            if not elem.name:
                                elem.name = info[0]
                            if not elem.data_type:
                                elem.data_type = info[1]
                    schema.segment_defs[current_seg_def.code] = current_seg_def
                current_seg_def = None
                state = state_stack.pop()[0] if state_stack else _State.TOP
                continue
            m = _RE_NAME.search(stripped)
            if m and current_seg_def:
                current_seg_def.name = m.group(1)
                continue
            m = _RE_ELEM_REF.search(stripped)
            if m and current_seg_def:
                pos = int(m.group(1))
                min_v, max_v = _parse_cardinality(m.group(4), m.group(5))
                current_seg_def.elements.append(ElementDef(
                    position=pos,
                    element_id=m.group(3),
                    element_type=m.group(2),
                    min_occurs=min_v,
                    max_occurs=max_v,
                ))
                continue
            continue

        # --- AREA / SEGMENT_GROUP: parse segment refs ---
        if state in (_State.AREA, _State.SEGMENT_GROUP):
            # Check for nested segmentGroup definition
            m = _RE_DEF_SEG_GROUP.search(stripped)
            if m:
                group_name = m.group(1)
                # Find the matching SegmentRef to attach children
                parent_refs = current_area_refs
                target_ref = None
                for ref in parent_refs:
                    if ref.name == group_name and ref.ref_type == 'segmentGroup':
                        target_ref = ref
                        break
                if target_ref is None:
                    # Create a placeholder
                    target_ref = SegmentRef(
                        name=group_name, ref_type='segmentGroup',
                        min_occurs=0, max_occurs=-1,
                    )
                state_stack.append((state, current_area_refs))
                current_area_refs = target_ref.children
                state = _State.SEGMENT_GROUP
                continue

            if stripped == '}':
                if state == _State.SEGMENT_GROUP:
                    prev = state_stack.pop() if state_stack else (_State.TOP, [])
                    state = prev[0]
                    current_area_refs = prev[1]
                elif state == _State.AREA:
                    schema.areas.append(current_area_refs)
                    current_area_refs = []
                    state = _State.MESSAGE
                continue

            # Segment/segmentGroup reference with empty cardinality []
            m = _RE_SEG_REF_EMPTY.search(stripped)
            if m:
                current_area_refs.append(SegmentRef(
                    name=m.group(3), ref_type=m.group(2),
                    min_occurs=0, max_occurs=-1,
                ))
                continue

            # Segment/segmentGroup reference with cardinality [n..m]
            m = _RE_SEG_REF.search(stripped)
            if m:
                min_v, max_v = _parse_cardinality(m.group(4), m.group(5))
                current_area_refs.append(SegmentRef(
                    name=m.group(3), ref_type=m.group(2),
                    min_occurs=min_v, max_occurs=max_v,
                ))
                continue

            # name = "..." inside segmentGroup def (skip)
            if _RE_NAME.search(stripped):
                continue

            continue

        # --- MESSAGE ---
        if state == _State.MESSAGE:
            m = _RE_DEF_AREA.search(stripped)
            if m:
                current_area_refs = []
                state = _State.AREA
                continue
            m = _RE_DEF_SEGMENT.search(stripped)
            if m:
                state_stack.append((_State.MESSAGE, []))
                current_seg_def = SegmentDef(code=m.group(1), name='')
                state = _State.SEGMENT_DEF
                continue
            m = _RE_DEF_SIMPLE_ELEM.search(stripped)
            if m:
                state_stack.append((_State.MESSAGE, []))
                current_elem_id = m.group(1)
                current_elem_name = ''
                current_elem_data_type = ''
                state = _State.ELEMENT_DEF
                continue
            m = _RE_DEF_COMPOSITE_ELEM.search(stripped)
            if m:
                state_stack.append((_State.MESSAGE, []))
                state = _State.COMPOSITE_DEF
                continue
            if stripped == '}':
                state = _State.TOP
                continue
            # Message metadata
            m = _RE_NAME.search(stripped)
            if m:
                schema.name = m.group(1)
                continue
            m = _RE_VERSION.search(stripped)
            if m:
                schema.version = m.group(1)
                continue
            m = _RE_FUNC_GROUP.search(stripped)
            if m:
                schema.functional_group = m.group(1)
                continue
            continue

        # --- TOP ---
        if state == _State.TOP:
            m = _RE_DEF_MESSAGE.search(stripped)
            if m:
                schema.code = m.group(1)
                state = _State.MESSAGE
                continue
            # 'def standard {' — stay at TOP level (message defs are inside)
            if stripped.startswith('def standard'):
                continue
            # Top-level segment/element defs (outside message, still in standard block)
            m = _RE_DEF_SEGMENT.search(stripped)
            if m:
                state_stack.append((_State.TOP, []))
                current_seg_def = SegmentDef(code=m.group(1), name='')
                state = _State.SEGMENT_DEF
                continue
            m = _RE_DEF_SIMPLE_ELEM.search(stripped)
            if m:
                state_stack.append((_State.TOP, []))
                current_elem_id = m.group(1)
                current_elem_name = ''
                current_elem_data_type = ''
                state = _State.ELEMENT_DEF
                continue
            m = _RE_DEF_COMPOSITE_ELEM.search(stripped)
            if m:
                state_stack.append((_State.TOP, []))
                state = _State.COMPOSITE_DEF
                continue
            # version = "005010" at standard level (v005010 format)
            m = _RE_VERSION.search(stripped)
            if m and not schema.version:
                schema.version = m.group(1)
                continue
            continue

    # Resolve element names in segment defs (second pass for late-defined elements)
    for seg_def in schema.segment_defs.values():
        for elem in seg_def.elements:
            if elem.element_id in elem_defs:
                info = elem_defs[elem.element_id]
                if not elem.name:
                    elem.name = info[0]
                if not elem.data_type:
                    elem.data_type = info[1]

    return schema


# ---------------------------------------------------------------------------
# Catalog scanner (lightweight — reads first ~20 lines per file)
# ---------------------------------------------------------------------------

def _quick_parse_header(file_path: Path) -> Optional[Dict[str, str]]:
    """Read first ~30 lines of an .ediSchema file to extract code and name."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            code: Optional[str] = None
            name: Optional[str] = None
            for i, line in enumerate(f):
                if i > 30:
                    break
                stripped = line.strip()
                if code is None:
                    m = _RE_DEF_MESSAGE.search(stripped)
                    if m:
                        code = m.group(1)
                if name is None:
                    m = _RE_NAME.search(stripped)
                    if m:
                        name = m.group(1)
                if code and name:
                    break
            if code:
                return {
                    'code': code,
                    'name': name or code,
                    'file': file_path.name,
                }
    except OSError:
        pass
    return None


def scan_standards_dir(standards_dir: Path) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
    """Scan standards directory and return catalog of available types and versions.

    Returns:
        {
            "x12": {
                "4010": [
                    {"code": "810", "name": "Invoice", "file": "Message810.ediSchema"},
                    ...
                ],
                ...
            }
        }
    """
    catalog: Dict[str, Dict[str, List[Dict[str, str]]]] = {}

    for std_type_dir in sorted(standards_dir.iterdir()):
        if not std_type_dir.is_dir():
            continue
        std_type = std_type_dir.name  # "x12" or "edifact"
        versions: Dict[str, List[Dict[str, str]]] = {}

        for version_dir in sorted(std_type_dir.iterdir()):
            if not version_dir.is_dir():
                continue
            # Extract version: "v004010" -> "4010"
            ver_name = version_dir.name  # e.g., "v004010"
            version = ver_name.lstrip('v').lstrip('0') or '0'
            # Keep trailing digits: "004010" -> "4010", "003040" -> "3040"
            raw = ver_name.lstrip('v')
            version = raw.lstrip('0') or '0'

            schemas_dir = version_dir / 'schemas'
            if not schemas_dir.is_dir():
                continue

            txns: List[Dict[str, str]] = []
            for schema_file in sorted(schemas_dir.glob('Message*.ediSchema')):
                entry = _quick_parse_header(schema_file)
                if entry:
                    txns.append(entry)

            if txns:
                versions[version] = txns

        if versions:
            catalog[std_type] = versions

    return catalog


def get_message_segments(file_path: Path) -> List[str]:
    """Quick extraction of top-level segment codes from a message schema.

    Returns a flat list like ["ST", "BIG", "NTE", "N1", "N2", ...].
    """
    segments: List[str] = []
    seen: set = set()
    in_message = False
    depth = 0

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue

            if not in_message:
                if _RE_DEF_MESSAGE.search(stripped):
                    in_message = True
                    depth = 1
                continue

            depth += stripped.count('{') - stripped.count('}')
            if depth <= 0:
                break

            # Match segment references (not segmentGroup)
            m = _RE_SEG_REF.search(stripped)
            if not m:
                m = _RE_SEG_REF_EMPTY.search(stripped)
            if m:
                ref_type = m.group(2)
                seg_name = m.group(3)
                if ref_type == 'segment' and seg_name not in seen:
                    seen.add(seg_name)
                    segments.append(seg_name)

    return segments


# ---------------------------------------------------------------------------
# Catalog cache
# ---------------------------------------------------------------------------

_CATALOG_CACHE: Optional[Dict[str, Dict[str, List[Dict[str, str]]]]] = None
_CATALOG_CACHE_TIME: float = 0


def get_catalog(standards_dir: Path, max_age: float = 300.0) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
    """Return cached catalog, refreshing if older than max_age seconds."""
    global _CATALOG_CACHE, _CATALOG_CACHE_TIME
    now = time.time()
    if _CATALOG_CACHE is not None and (now - _CATALOG_CACHE_TIME) < max_age:
        return _CATALOG_CACHE
    _CATALOG_CACHE = scan_standards_dir(standards_dir)
    _CATALOG_CACHE_TIME = now
    return _CATALOG_CACHE
