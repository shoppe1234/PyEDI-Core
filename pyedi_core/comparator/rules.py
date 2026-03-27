"""Rule loading and resolution for the compare engine.

Ported from: json810Compare/comparator.py — load_error_classification(),
load_ignore_rules(), get_rule_property(). Reads from YAML instead of Google Sheets.
"""

from __future__ import annotations

import os

import yaml

from pyedi_core.comparator.models import CompareRules, FieldRule, ResolvedFieldRule, TieredRules


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
            amount_variance=entry.get("amount_variance"),
        ))

    ignore: list[dict[str, str]] = data.get("ignore", [])

    return CompareRules(classification=classification, ignore=ignore)


def load_tiered_rules(
    rules_dir: str,
    transaction_type: str,
    partner_rules_path: str,
) -> TieredRules:
    """Load up to 3 tiers of rules from the rules directory.

    Tier 1: {rules_dir}/_universal.yaml
    Tier 2: {rules_dir}/_global_{transaction_type}.yaml
    Tier 3: partner_rules_path (the profile's existing rules file)

    Missing tier files produce empty CompareRules (no error).
    """
    universal = CompareRules()
    transaction = CompareRules()
    partner = CompareRules()

    universal_path = os.path.join(rules_dir, "_universal.yaml")
    if os.path.isfile(universal_path):
        universal = load_rules(universal_path)

    if transaction_type:
        txn_path = os.path.join(rules_dir, f"_global_{transaction_type}.yaml")
        if os.path.isfile(txn_path):
            transaction = load_rules(txn_path)

    if partner_rules_path and os.path.isfile(partner_rules_path):
        partner = load_rules(partner_rules_path)

    return TieredRules(universal=universal, transaction=transaction, partner=partner)


def merge_rules(tiered: TieredRules) -> CompareRules:
    """Flatten 3-tier rules into a single CompareRules.

    Resolution: partner overrides transaction overrides universal.
    For each (segment, field) key, the most specific tier wins.
    Ignore lists are unioned across all tiers (deduplicated by segment+field).
    """
    # Build merged classification dict: universal → overlay txn → overlay partner
    merged: dict[tuple[str, str], FieldRule] = {}

    for rule in tiered.universal.classification:
        merged[(rule.segment, rule.field)] = rule
    for rule in tiered.transaction.classification:
        merged[(rule.segment, rule.field)] = rule
    for rule in tiered.partner.classification:
        merged[(rule.segment, rule.field)] = rule

    # Union ignore lists, deduplicate by (segment, field)
    seen_ignores: set[tuple[str, str]] = set()
    merged_ignores: list[dict[str, str]] = []
    for ignore_list in [
        tiered.universal.ignore,
        tiered.transaction.ignore,
        tiered.partner.ignore,
    ]:
        for entry in ignore_list:
            key = (entry.get("segment", ""), entry.get("field", ""))
            if key not in seen_ignores:
                seen_ignores.add(key)
                merged_ignores.append(entry)

    return CompareRules(classification=list(merged.values()), ignore=merged_ignores)


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


def get_resolved_field_rule(
    tiered: TieredRules, segment: str, field: str
) -> ResolvedFieldRule:
    """Resolve rule for (segment, field) across tiers, annotating which tier it came from.

    Resolution order: partner → transaction → universal → default.
    Within each tier, uses the same wildcard chain as get_field_rule().
    """
    for tier_name, tier_rules in [
        ("partner", tiered.partner),
        ("transaction", tiered.transaction),
        ("universal", tiered.universal),
    ]:
        if not tier_rules.classification:
            continue
        lookup = {(r.segment, r.field): r for r in tier_rules.classification}

        # Same priority chain as get_field_rule()
        for key in [
            (segment, field),
            (segment, "*"),
            ("*", field),
            ("*", "*"),
        ]:
            if key in lookup:
                return ResolvedFieldRule(rule=lookup[key], tier=tier_name)

    # No rule in any tier — hardcoded default
    return ResolvedFieldRule(
        rule=FieldRule(segment=segment, field=field, severity="hard"),
        tier="default",
    )


def is_wildcard_match(rules: CompareRules, segment: str, field: str) -> bool:
    """Return True if (segment, field) resolves only to (*,*) or the hardcoded default."""
    lookup = {(r.segment, r.field) for r in rules.classification}
    has_exact = (segment, field) in lookup
    # Exclude the (*,*) catch-all when checking for segment/field wildcards
    has_segment_wildcard = (segment, "*") in lookup and segment != "*"
    has_field_wildcard = ("*", field) in lookup and field != "*"
    return not has_exact and not has_segment_wildcard and not has_field_wildcard


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
            segment=entry.get("segment", "*"),
            field=entry["field_name"],
            severity=entry["severity"],
            ignore_case=bool(entry["ignore_case"]),
            numeric=bool(entry["numeric"]),
            amount_variance=entry.get("amount_variance"),
        )
    return overrides
