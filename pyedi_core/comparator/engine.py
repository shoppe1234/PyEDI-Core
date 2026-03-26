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


def _compare_flat_dict(
    src_dict: dict,
    tgt_dict: dict,
    segment_label: str,
    rules: CompareRules,
) -> list[FieldDiff]:
    """Compare two flat dictionaries field-by-field using rules.

    Extracted from compare_flat_pair for reuse across header, line, and summary sections.
    """
    diffs: list[FieldDiff] = []
    all_keys = set(src_dict.keys()) | set(tgt_dict.keys())

    for key in all_keys:
        if _is_ignored("*", key, rules):
            continue

        src_val = str(src_dict.get(key, ""))
        tgt_val = str(tgt_dict.get(key, ""))

        rule = get_field_rule(rules, "*", key)

        if rule.numeric:
            try:
                src_f, tgt_f = float(src_val), float(tgt_val)
                variance = getattr(rule, "amount_variance", None)
                if variance is not None:
                    if abs(src_f - tgt_f) <= variance:
                        continue
                elif src_f == tgt_f:
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

        # Conditional qualifier logic (parity with compare_segment_fields)
        if rule.conditional_qualifier:
            if key not in src_dict and src_dict.get(rule.conditional_qualifier):
                continue
            if key not in tgt_dict and tgt_dict.get(rule.conditional_qualifier):
                continue

        if key not in src_dict:
            desc = f"Missing key in Source: {key} (Target has: '{tgt_val}')"
        elif key not in tgt_dict:
            desc = f"Missing key in Target: {key} (Source has: '{src_val}')"
        else:
            desc = f"Content mismatch: Source='{src_val}' vs Target='{tgt_val}'"

        diffs.append(FieldDiff(
            segment=segment_label,
            field=key,
            severity=rule.severity,
            source_value=src_val if key in src_dict else None,
            target_value=tgt_val if key in tgt_dict else None,
            description=desc,
        ))

    return diffs


def compare_flat_pair(
    pair: MatchPair,
    rules: CompareRules,
    crosswalk: dict[str, "FieldRule"] | None = None,
) -> CompareResult:
    """Compare flat JSON pairs (CSV/cXML output).

    Handles both truly flat JSON and structured {header, lines, summary} payloads.
    When crosswalk is provided, overrides YAML rules with crosswalk entries.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    if pair.target is None:
        return CompareResult(
            pair=pair, status="UNMATCHED", diffs=[], timestamp=timestamp,
        )

    source_data = pair.source.transaction_data
    target_data = pair.target.transaction_data

    # Apply crosswalk overrides to a copy of rules if provided
    effective_rules = _apply_crosswalk(rules, crosswalk) if crosswalk else rules

    # Detect structured JSON (has "lines" key)
    if "lines" in source_data or "lines" in target_data:
        diffs: list[FieldDiff] = []

        # Compare header
        src_header = source_data.get("header", {})
        tgt_header = target_data.get("header", {})
        diffs.extend(_compare_flat_dict(src_header, tgt_header, "header", effective_rules))

        # Compare lines positionally
        src_lines = source_data.get("lines", [])
        tgt_lines = target_data.get("lines", [])
        max_lines = max(len(src_lines), len(tgt_lines))
        for i in range(max_lines):
            src_line = src_lines[i] if i < len(src_lines) else None
            tgt_line = tgt_lines[i] if i < len(tgt_lines) else None
            if src_line is None:
                diffs.append(FieldDiff(
                    segment=f"line_{i}", field="", severity="hard",
                    source_value=None, target_value=str(tgt_line),
                    description=f"Extra line in Target at position {i}",
                ))
                continue
            if tgt_line is None:
                diffs.append(FieldDiff(
                    segment=f"line_{i}", field="", severity="hard",
                    source_value=str(src_line), target_value=None,
                    description=f"Missing line in Target at position {i}",
                ))
                continue
            diffs.extend(_compare_flat_dict(src_line, tgt_line, f"line_{i}", effective_rules))

        # Compare summary
        src_summary = source_data.get("summary", {})
        tgt_summary = target_data.get("summary", {})
        diffs.extend(_compare_flat_dict(src_summary, tgt_summary, "summary", effective_rules))

        status = "MISMATCH" if diffs else "MATCH"
        return CompareResult(pair=pair, status=status, diffs=diffs, timestamp=timestamp)

    # Backward compatible: truly flat JSON
    diffs = _compare_flat_dict(source_data, target_data, "flat", effective_rules)
    status = "MISMATCH" if diffs else "MATCH"
    return CompareResult(pair=pair, status=status, diffs=diffs, timestamp=timestamp)


def _apply_crosswalk(
    rules: CompareRules,
    crosswalk: dict[str, "FieldRule"],
) -> CompareRules:
    """Create a copy of rules with crosswalk overrides applied."""
    if not crosswalk:
        return rules

    new_classification = list(rules.classification)

    for field_name, xwalk_rule in crosswalk.items():
        # Replace or prepend the crosswalk rule (higher priority than wildcard)
        found = False
        for i, existing in enumerate(new_classification):
            if existing.segment == "*" and existing.field == field_name:
                new_classification[i] = xwalk_rule
                found = True
                break
        if not found:
            # Insert before the default wildcard
            new_classification.insert(len(new_classification) - 1, xwalk_rule)

    return CompareRules(classification=new_classification, ignore=rules.ignore)
