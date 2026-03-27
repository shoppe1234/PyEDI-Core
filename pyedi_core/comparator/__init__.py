"""PyEDI Compare engine — public API.

Usage:
    from pyedi_core.comparator import compare, export_csv, load_profile, list_profiles
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone

import yaml

from pyedi_core.comparator.engine import compare_flat_pair, compare_pair
from pyedi_core.comparator.matcher import pair_transactions
from pyedi_core.comparator.models import (
    CompareProfile,
    DiscoveryRecord,
    FieldDiff,
    MatchKeyConfig,
    RunSummary,
)
from pyedi_core.comparator.rules import is_wildcard_match, load_crosswalk_overrides, load_rules
from pyedi_core.comparator.rules import get_field_rule
from pyedi_core.comparator.rules import load_tiered_rules, merge_rules
from pyedi_core.comparator.store import (
    clone_pairs_for_reclassify,
    clone_run_for_reclassify,
    get_all_diffs_for_run,
    get_diffs,
    get_pairs,
    get_run,
    init_db,
    insert_diffs,
    insert_discoveries,
    insert_pair,
    insert_run,
    update_run,
)


def compare(
    profile: CompareProfile,
    source_dir: str,
    target_dir: str,
    db_path: str,
) -> RunSummary:
    """Run a full comparison. Public API entry point.

    1. Load rules from profile.rules_file
    2. Pair transactions via matcher.pair_transactions()
    3. Insert run into SQLite via store
    4. For each pair: compare via engine, insert results into SQLite
    5. Update run summary
    6. Return RunSummary
    """
    init_db(db_path)

    rules_dir = os.path.dirname(profile.rules_file)
    tiered = load_tiered_rules(rules_dir, profile.transaction_type, profile.rules_file)
    rules = merge_rules(tiered)

    # Load crosswalk overrides (cached once per run)
    crosswalk = load_crosswalk_overrides(db_path, profile.name)

    if not crosswalk and profile.rules_file:
        from pyedi_core.scaffold import scaffold_crosswalk_from_rules
        scaffold_crosswalk_from_rules(profile.rules_file, profile.name, db_path)
        crosswalk = load_crosswalk_overrides(db_path, profile.name)

    pairs = pair_transactions(source_dir, target_dir, profile.match_key)

    # Build match_key string for storage
    if profile.match_key.json_path:
        mk_str = f"json_path:{profile.match_key.json_path}"
    else:
        mk_str = f"{profile.match_key.segment}:{profile.match_key.field}"

    run_id = insert_run(
        db_path, profile.name, source_dir, target_dir, mk_str,
        trading_partner=profile.trading_partner,
        transaction_type=profile.transaction_type,
    )

    matched = 0
    mismatched = 0
    unmatched = 0
    all_diffs: list[FieldDiff] = []

    is_flat = not profile.segment_qualifiers

    for pair in pairs:
        if is_flat:
            result = compare_flat_pair(pair, rules, crosswalk=crosswalk)
        else:
            result = compare_pair(pair, rules, profile.segment_qualifiers)

        pair_id = insert_pair(db_path, run_id, pair, result.status, len(result.diffs))

        if result.diffs:
            insert_diffs(db_path, pair_id, result.diffs)
            all_diffs.extend(result.diffs)

        if result.status == "MATCH":
            matched += 1
        elif result.status == "MISMATCH":
            mismatched += 1
        else:
            unmatched += 1

    # Collect wildcard-fallback discoveries, deduplicate by (segment, field)
    discovery_count = 0
    seen: set[tuple[str, str]] = set()
    discoveries: list[DiscoveryRecord] = []
    now = datetime.now(timezone.utc).isoformat()
    for diff in all_diffs:
        if diff.wildcard_fallback and (diff.segment, diff.field) not in seen:
            seen.add((diff.segment, diff.field))
            discoveries.append(DiscoveryRecord(
                profile=profile.name,
                segment=diff.segment,
                field=diff.field,
                source_value=diff.source_value,
                target_value=diff.target_value,
                suggested_severity=diff.severity,
                discovered_at=now,
            ))
    if discoveries:
        discovery_count = insert_discoveries(db_path, run_id, discoveries)

    finished_at = datetime.now(timezone.utc).isoformat()
    summary = RunSummary(
        run_id=run_id,
        profile=profile.name,
        total_pairs=len(pairs),
        matched=matched,
        mismatched=mismatched,
        unmatched=unmatched,
        started_at="",
        finished_at=finished_at,
    )
    update_run(db_path, run_id, summary)

    if discovery_count:
        print(f"Discovered {discovery_count} new field combinations not yet classified")

    return summary


def reclassify(run_id: int, db_path: str, config_path: str) -> RunSummary:
    """Create a new run by re-evaluating diffs from an existing run against current rules + crosswalk.

    1. Get original run profile via get_run()
    2. Load profile from config via load_profile()
    3. Load rules + crosswalk
    4. Clone run + pairs into new run
    5. Get all original diffs
    6. For each diff: re-resolve severity via get_field_rule()
    7. Insert diffs with updated severities into new pairs
    8. Calculate counts and update run summary
    """
    init_db(db_path)

    orig_run = get_run(db_path, run_id)
    if orig_run is None:
        raise ValueError(f"Run {run_id} not found")

    profile = load_profile(config_path, orig_run.profile)
    rules_dir = os.path.dirname(profile.rules_file)
    tiered = load_tiered_rules(rules_dir, profile.transaction_type, profile.rules_file)
    rules = merge_rules(tiered)
    crosswalk = load_crosswalk_overrides(db_path, profile.name)

    # Apply crosswalk to rules if present
    if crosswalk:
        from pyedi_core.comparator.engine import _apply_crosswalk
        effective_rules = _apply_crosswalk(rules, crosswalk)
    else:
        effective_rules = rules

    new_run_id = clone_run_for_reclassify(db_path, run_id)
    pair_mapping = clone_pairs_for_reclassify(db_path, run_id, new_run_id)

    orig_diffs = get_all_diffs_for_run(db_path, run_id)

    # Group diffs by original pair_id
    diffs_by_pair: dict[int, list[dict]] = {}
    for d in orig_diffs:
        diffs_by_pair.setdefault(d["pair_id"], []).append(d)

    matched = 0
    mismatched = 0
    unmatched = 0

    for old_pair_id, new_pair_id in pair_mapping.items():
        pair_diffs = diffs_by_pair.get(old_pair_id, [])
        new_diffs: list[FieldDiff] = []

        for d in pair_diffs:
            # Re-resolve severity with current rules
            new_rule = get_field_rule(effective_rules, d["segment"].split("*")[0] if "*" in d["segment"] else d["segment"], d["field"])
            if new_rule.severity == "ignore":
                continue
            new_diffs.append(FieldDiff(
                segment=d["segment"],
                field=d["field"],
                severity=new_rule.severity,
                source_value=d["source_value"],
                target_value=d["target_value"],
                description=d["description"],
            ))

        # Check if this pair is unmatched (missing source or target)
        from pyedi_core.comparator.store import _connect
        conn = _connect(db_path)
        try:
            pair_row = conn.execute(
                "SELECT source_file, target_file FROM compare_pairs WHERE id = ?",
                (new_pair_id,),
            ).fetchone()
            is_unmatched = pair_row and (pair_row[0] is None or pair_row[1] is None)
        finally:
            conn.close()

        if is_unmatched:
            unmatched += 1
            status = "UNMATCHED"
        elif new_diffs:
            insert_diffs(db_path, new_pair_id, new_diffs)
            mismatched += 1
            status = "MISMATCH"
        else:
            matched += 1
            status = "MATCH"

        # Update pair diff_count and status
        conn = _connect(db_path)
        try:
            conn.execute(
                "UPDATE compare_pairs SET diff_count = ?, status = ? WHERE id = ?",
                (len(new_diffs), status, new_pair_id),
            )
            conn.commit()
        finally:
            conn.close()

    finished_at = datetime.now(timezone.utc).isoformat()
    summary = RunSummary(
        run_id=new_run_id,
        profile=orig_run.profile,
        total_pairs=len(pair_mapping),
        matched=matched,
        mismatched=mismatched,
        unmatched=unmatched,
        started_at="",
        finished_at=finished_at,
        reclassified_from=run_id,
    )
    update_run(db_path, new_run_id, summary)

    return summary


def export_csv(db_path: str, run_id: int, output_dir: str) -> str:
    """Export a run's results to CSV. Returns the output file path.

    Format: 15 columns with metadata header and summary footer.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"compare_run_{run_id}.csv")

    run = get_run(db_path, run_id)
    pair_rows = get_pairs(db_path, run_id, limit=10000)

    severity_counts: dict[str, int] = {}

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Metadata header
        if run:
            f.write(f"# Profile: {run.profile}\n")
            f.write(f"# Trading Partner: {run.trading_partner}\n")
            f.write(f"# Transaction Type: {run.transaction_type}\n")
            f.write(f"# Run ID: {run_id}\n")
            f.write(f"# Started: {run.started_at}\n")
            f.write(f"# Total Pairs: {run.total_pairs} | Matched: {run.matched}"
                    f" | Mismatched: {run.mismatched} | Unmatched: {run.unmatched}\n")

        # 15-column header
        writer.writerow([
            "timestamp", "profile", "trading_partner", "run_id", "pair_id",
            "source_file", "target_file", "match_value", "status",
            "segment", "field", "severity", "source_value",
            "target_value", "description",
        ])

        timestamp = run.started_at if run else ""
        profile_name = run.profile if run else ""
        trading_partner = run.trading_partner if run else ""

        for pair in pair_rows:
            diffs = get_diffs(db_path, pair["id"])
            if diffs:
                for diff in diffs:
                    severity_counts[diff.severity] = severity_counts.get(diff.severity, 0) + 1
                    writer.writerow([
                        timestamp, profile_name, trading_partner,
                        run_id, pair["id"], pair["source_file"],
                        pair.get("target_file", ""), pair["match_value"],
                        pair["status"], diff.segment, diff.field,
                        diff.severity, diff.source_value or "",
                        diff.target_value or "", diff.description,
                    ])
            else:
                writer.writerow([
                    timestamp, profile_name, trading_partner,
                    run_id, pair["id"], pair["source_file"],
                    pair.get("target_file", ""), pair["match_value"],
                    pair["status"], "", "", "", "", "", "",
                ])

        # Summary footer
        parts = [f"{k}={v}" for k, v in sorted(severity_counts.items())]
        f.write(f"# Summary: {', '.join(parts) if parts else 'no diffs'}\n")

    return output_path


def load_profile(config_path: str, profile_name: str) -> CompareProfile:
    """Load a named profile from config.yaml compare.profiles section."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    profiles = config.get("compare", {}).get("profiles", {})
    if profile_name not in profiles:
        raise ValueError(f"Profile '{profile_name}' not found in {config_path}")

    return _parse_profile(profile_name, profiles[profile_name])


def list_profiles(config_path: str) -> list[CompareProfile]:
    """List all available profiles from config.yaml."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    profiles = config.get("compare", {}).get("profiles", {})
    return [_parse_profile(name, data) for name, data in profiles.items()]


def _parse_profile(name: str, data: dict) -> CompareProfile:
    """Parse a profile dict from config.yaml into a CompareProfile dataclass."""
    mk = data.get("match_key", {})
    return CompareProfile(
        name=name,
        description=data.get("description", ""),
        match_key=MatchKeyConfig(
            segment=mk.get("segment"),
            field=mk.get("field"),
            json_path=mk.get("json_path"),
        ),
        segment_qualifiers=data.get("segment_qualifiers", {}),
        rules_file=data.get("rules_file", ""),
        trading_partner=data.get("trading_partner", ""),
        transaction_type=data.get("transaction_type", ""),
    )
