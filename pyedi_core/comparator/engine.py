"""Core comparison logic for the compare engine.

Ported from: json810Compare/comparator.py — compare_transactions(),
match_segments_by_qualifier(), compare_segment_fields(), segment_to_dict(),
group_segments_by_id(). Qualifiers are passed in (from profile config),
not hardcoded. Error dicts replaced by FieldDiff dataclasses.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pyedi_core.comparator.models import (
    CompareResult,
    CompareRules,
    FieldDiff,
    MatchPair,
)
from pyedi_core.comparator.rules import get_field_rule


def segment_to_dict(segment: dict) -> dict[str, str]:
    """Convert {"segment": "N1", "fields": [{"name":"N101","content":"ST"},...]} to {"N101":"ST",...}.

    Direct port from: comparator.py segment_to_dict()
    """
    return {f.get("name", ""): f.get("content", "") for f in segment.get("fields", [])}


def group_segments_by_id(segments: list[dict]) -> dict[str, list[dict]]:
    """Group segments by segment ID. {"N1": [seg1, seg2], "REF": [seg1, seg2, seg3]}.

    Direct port from: comparator.py group_segments_by_id()
    """
    groups: dict[str, list[dict]] = {}
    for seg in segments:
        seg_id = seg.get("segment", "")
        groups.setdefault(seg_id, []).append(seg)
    return groups


def _get_field_content(segment: dict, field_name: str) -> str:
    """Extract a field value from a segment dict."""
    for f in segment.get("fields", []):
        if f.get("name") == field_name:
            return f.get("content", "")
    return ""


def match_segments_by_qualifier(
    source_segments: list[dict],
    target_segments: list[dict],
    qualifier_field: str | None,
) -> list[tuple[dict | None, dict | None, str]]:
    """Match multi-instance segments by qualifier value, fallback to positional.

    Ported from: comparator.py match_segments_by_qualifier()
    - qualifier_field="N101": matches N1 segments where N101 values are equal
    - qualifier_field=None: matches by position (N3, N4)
    """
    matches: list[tuple[dict | None, dict | None, str]] = []

    if qualifier_field:
        # Group by qualifier value
        source_by_qual: dict[str, list[dict]] = {}
        for seg in source_segments:
            qual = _get_field_content(seg, qualifier_field)
            source_by_qual.setdefault(qual, []).append(seg)

        target_by_qual: dict[str, list[dict]] = {}
        for seg in target_segments:
            qual = _get_field_content(seg, qualifier_field)
            target_by_qual.setdefault(qual, []).append(seg)

        all_qualifiers = set(source_by_qual.keys()) | set(target_by_qual.keys())

        for qual in all_qualifiers:
            src_list = source_by_qual.get(qual, [])
            tgt_list = target_by_qual.get(qual, [])
            max_len = max(len(src_list), len(tgt_list))
            for i in range(max_len):
                src = src_list[i] if i < len(src_list) else None
                tgt = tgt_list[i] if i < len(tgt_list) else None
                matches.append((src, tgt, qual))
    else:
        # Positional matching
        max_len = max(len(source_segments), len(target_segments)) if source_segments or target_segments else 0
        for i in range(max_len):
            src = source_segments[i] if i < len(source_segments) else None
            tgt = target_segments[i] if i < len(target_segments) else None
            matches.append((src, tgt, f"position_{i}"))

    return matches


def _is_ignored(segment: str, field: str, rules: CompareRules) -> bool:
    """Check if a (segment, field) pair is in the ignore list."""
    for entry in rules.ignore:
        rule_seg = entry.get("segment", "")
        rule_field = entry.get("field", "")
        if rule_seg == segment and (rule_field == field or rule_field == "*"):
            return True
        if rule_seg == "*" and rule_field == field:
            return True
    return False


def compare_segment_fields(
    source_seg: dict | None,
    target_seg: dict | None,
    segment_id: str,
    qualifier_value: str | None,
    rules: CompareRules,
) -> list[FieldDiff]:
    """Compare all fields in a matched segment pair, applying rules.

    Ported from: comparator.py compare_segment_fields()
    Handles: ignore_case, numeric, conditional_qualifier, severity classification.
    """
    seg_label = f"{segment_id}*{qualifier_value}" if qualifier_value else segment_id

    if source_seg is None:
        tgt_fields = segment_to_dict(target_seg) if target_seg else {}
        return [FieldDiff(
            segment=seg_label, field="", severity="hard",
            source_value=None, target_value=str(tgt_fields),
            description=f"Extra segment in Target: {seg_label}",
        )]

    if target_seg is None:
        src_fields = segment_to_dict(source_seg)
        return [FieldDiff(
            segment=seg_label, field="", severity="hard",
            source_value=str(src_fields), target_value=None,
            description=f"Missing segment in Target: {seg_label}",
        )]

    diffs: list[FieldDiff] = []
    source_fields = segment_to_dict(source_seg)
    target_fields = segment_to_dict(target_seg)
    all_field_names = set(source_fields.keys()) | set(target_fields.keys())

    for field_name in all_field_names:
        if _is_ignored(segment_id, field_name, rules):
            continue

        src_value = source_fields.get(field_name, "")
        tgt_value = target_fields.get(field_name, "")

        rule = get_field_rule(rules, segment_id, field_name)

        # Numeric precision comparison
        if rule.numeric:
            try:
                if float(src_value) == float(tgt_value):
                    continue
            except (ValueError, TypeError):
                pass

        # Case-insensitive comparison
        if rule.ignore_case:
            values_match = src_value.lower() == tgt_value.lower()
        else:
            values_match = src_value == tgt_value

        if values_match:
            continue

        # Skip if severity is ignore
        if rule.severity == "ignore":
            continue

        # Conditional qualifier logic
        if rule.conditional_qualifier:
            if field_name not in source_fields and source_fields.get(rule.conditional_qualifier):
                continue
            if field_name not in target_fields and target_fields.get(rule.conditional_qualifier):
                continue

        # Build description
        if field_name not in source_fields:
            description = f"Missing field in Source: {field_name} (Target has: '{tgt_value}')"
        elif field_name not in target_fields:
            description = f"Missing field in Target: {field_name} (Source has: '{src_value}')"
        else:
            description = f"Content mismatch: Source='{src_value}' vs Target='{tgt_value}'"

        diffs.append(FieldDiff(
            segment=seg_label,
            field=field_name,
            severity=rule.severity,
            source_value=src_value if field_name in source_fields else None,
            target_value=tgt_value if field_name in target_fields else None,
            description=description,
        ))

    return diffs


def compare_pair(
    pair: MatchPair,
    rules: CompareRules,
    qualifiers: dict[str, str | None],
) -> CompareResult:
    """Compare a matched source/target pair.

    1. Group segments by ID for both source and target
    2. For each segment type, match by qualifier
    3. Compare fields using rules
    4. Return CompareResult with all diffs

    Ported from: comparator.py compare_transactions()
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    if pair.target is None:
        return CompareResult(
            pair=pair, status="UNMATCHED", diffs=[], timestamp=timestamp,
        )

    source_segments = pair.source.transaction_data.get("segments", [])
    target_segments = pair.target.transaction_data.get("segments", [])

    source_groups = group_segments_by_id(source_segments)
    target_groups = group_segments_by_id(target_segments)

    all_seg_ids = set(source_groups.keys()) | set(target_groups.keys())
    all_diffs: list[FieldDiff] = []

    for seg_id in all_seg_ids:
        src_segs = source_groups.get(seg_id, [])
        tgt_segs = target_groups.get(seg_id, [])
        qualifier_field = qualifiers.get(seg_id)

        matches = match_segments_by_qualifier(src_segs, tgt_segs, qualifier_field)

        for src_seg, tgt_seg, qual_value in matches:
            field_diffs = compare_segment_fields(
                src_seg, tgt_seg, seg_id, qual_value, rules,
            )
            all_diffs.extend(field_diffs)

    status = "MISMATCH" if all_diffs else "MATCH"
    return CompareResult(pair=pair, status=status, diffs=all_diffs, timestamp=timestamp)


def compare_flat_pair(
    pair: MatchPair,
    rules: CompareRules,
) -> CompareResult:
    """Compare flat JSON pairs (CSV/cXML output).

    No segment structure — walks JSON keys, applies rules by key name.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    if pair.target is None:
        return CompareResult(
            pair=pair, status="UNMATCHED", diffs=[], timestamp=timestamp,
        )

    source_data = pair.source.transaction_data
    target_data = pair.target.transaction_data

    diffs: list[FieldDiff] = []
    all_keys = set(source_data.keys()) | set(target_data.keys())

    for key in all_keys:
        if _is_ignored("*", key, rules):
            continue

        src_val = str(source_data.get(key, ""))
        tgt_val = str(target_data.get(key, ""))

        rule = get_field_rule(rules, "*", key)

        if rule.numeric:
            try:
                if float(src_val) == float(tgt_val):
                    continue
            except (ValueError, TypeError):
                pass

        if rule.ignore_case:
            values_match = src_val.lower() == tgt_val.lower()
        else:
            values_match = src_val == tgt_val

        if values_match:
            continue

        if rule.severity == "ignore":
            continue

        if key not in source_data:
            desc = f"Missing key in Source: {key} (Target has: '{tgt_val}')"
        elif key not in target_data:
            desc = f"Missing key in Target: {key} (Source has: '{src_val}')"
        else:
            desc = f"Content mismatch: Source='{src_val}' vs Target='{tgt_val}'"

        diffs.append(FieldDiff(
            segment="flat",
            field=key,
            severity=rule.severity,
            source_value=src_val if key in source_data else None,
            target_value=tgt_val if key in target_data else None,
            description=desc,
        ))

    status = "MISMATCH" if diffs else "MATCH"
    return CompareResult(pair=pair, status=status, diffs=diffs, timestamp=timestamp)
