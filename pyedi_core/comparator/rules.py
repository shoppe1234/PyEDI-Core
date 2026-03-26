"""Rule loading and resolution for the compare engine.

Ported from: json810Compare/comparator.py — load_error_classification(),
load_ignore_rules(), get_rule_property(). Reads from YAML instead of Google Sheets.
"""

from __future__ import annotations

import yaml

from pyedi_core.comparator.models import CompareRules, FieldRule


def load_rules(rules_path: str) -> CompareRules:
    """Load per-profile rules YAML, return CompareRules with classification + ignore lists.

    YAML format:
      classification:
        - segment: "N1"
          field: "N102"
          severity: "hard"
          ignore_case: true
      ignore:
        - segment: "SE"
          field: "SE01"
          reason: "..."
    """
    with open(rules_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    classification: list[FieldRule] = []
    for entry in data.get("classification", []):
        classification.append(FieldRule(
            segment=entry["segment"],
            field=entry["field"],
            severity=entry.get("severity", "hard"),
            ignore_case=entry.get("ignore_case", False),
            numeric=entry.get("numeric", False),
            conditional_qualifier=entry.get("conditional_qualifier"),
        ))

    ignore: list[dict[str, str]] = data.get("ignore", [])

    return CompareRules(classification=classification, ignore=ignore)


def get_field_rule(rules: CompareRules, segment: str, field: str) -> FieldRule:
    """Resolve rule for (segment, field) with wildcard fallback.

    Priority: exact (segment, field) > (segment, *) > (*, field) > (*, *)
    Default: hard severity, exact match, no special flags.

    Ported from: comparator.py get_rule_property()
    """
    # Build lookup dict keyed by (segment, field)
    lookup: dict[tuple[str, str], FieldRule] = {
        (r.segment, r.field): r for r in rules.classification
    }

    # Exact match
    if (segment, field) in lookup:
        return lookup[(segment, field)]
    # Segment wildcard field
    if (segment, "*") in lookup:
        return lookup[(segment, "*")]
    # Wildcard segment, specific field
    if ("*", field) in lookup:
        return lookup[("*", field)]
    # Both wildcard
    if ("*", "*") in lookup:
        return lookup[("*", "*")]

    # Default: hard severity, exact match
    return FieldRule(segment=segment, field=field, severity="hard")


def load_crosswalk_overrides(db_path: str, profile: str) -> dict[str, FieldRule]:
    """Load crosswalk entries as a {field_name: FieldRule} dict for fast lookup.

    Returns empty dict if table doesn't exist or has no entries.
    """
    from pyedi_core.comparator.store import get_crosswalk

    try:
        entries = get_crosswalk(db_path, profile)
    except Exception:
        return {}

    overrides: dict[str, FieldRule] = {}
    for entry in entries:
        overrides[entry["field_name"]] = FieldRule(
            segment="*",
            field=entry["field_name"],
            severity=entry["severity"],
            ignore_case=bool(entry["ignore_case"]),
            numeric=bool(entry["numeric"]),
            amount_variance=entry.get("amount_variance"),
        )
    return overrides
