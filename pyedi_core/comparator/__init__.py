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
    MatchKeyConfig,
    RunSummary,
)
from pyedi_core.comparator.rules import load_crosswalk_overrides, load_rules
from pyedi_core.comparator.store import (
    get_diffs,
    get_pairs,
    init_db,
    insert_diffs,
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

    rules = load_rules(profile.rules_file)

    # Load crosswalk overrides (cached once per run)
    crosswalk = load_crosswalk_overrides(db_path, profile.name)

    pairs = pair_transactions(source_dir, target_dir, profile.match_key)

    # Build match_key string for storage
    if profile.match_key.json_path:
        mk_str = f"json_path:{profile.match_key.json_path}"
    else:
        mk_str = f"{profile.match_key.segment}:{profile.match_key.field}"

    run_id = insert_run(db_path, profile.name, source_dir, target_dir, mk_str)

    matched = 0
    mismatched = 0
    unmatched = 0

    is_flat = not profile.segment_qualifiers

    for pair in pairs:
        if is_flat:
            result = compare_flat_pair(pair, rules, crosswalk=crosswalk)
        else:
            result = compare_pair(pair, rules, profile.segment_qualifiers)

        pair_id = insert_pair(db_path, run_id, pair, result.status, len(result.diffs))

        if result.diffs:
            insert_diffs(db_path, pair_id, result.diffs)

        if result.status == "MATCH":
            matched += 1
        elif result.status == "MISMATCH":
            mismatched += 1
        else:
            unmatched += 1

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

    return summary


def export_csv(db_path: str, run_id: int, output_dir: str) -> str:
    """Export a run's results to CSV. Returns the output file path.

    Format: run_id,pair_id,source_file,target_file,match_value,status,
            segment,field,severity,source_value,target_value,description
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"compare_run_{run_id}.csv")

    pair_rows = get_pairs(db_path, run_id, limit=10000)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id", "pair_id", "source_file", "target_file", "match_value",
            "status", "segment", "field", "severity", "source_value",
            "target_value", "description",
        ])
        for pair in pair_rows:
            diffs = get_diffs(db_path, pair["id"])
            if diffs:
                for diff in diffs:
                    writer.writerow([
                        run_id, pair["id"], pair["source_file"],
                        pair.get("target_file", ""), pair["match_value"],
                        pair["status"], diff.segment, diff.field,
                        diff.severity, diff.source_value or "",
                        diff.target_value or "", diff.description,
                    ])
            else:
                writer.writerow([
                    run_id, pair["id"], pair["source_file"],
                    pair.get("target_file", ""), pair["match_value"],
                    pair["status"], "", "", "", "", "", "",
                ])

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
    )
