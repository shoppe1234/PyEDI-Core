"""File pairing and transaction extraction for the compare engine.

Ported from: json810Compare/comparator.py — find_invoice_in_json(),
find_target_file_for_invoice(), load_target_files_cache().
Generalized from BIG02-only to any match key via MatchKeyConfig.
"""

from __future__ import annotations

import json
import logging
import os

from pyedi_core.comparator.models import MatchEntry, MatchKeyConfig, MatchPair

logger = logging.getLogger(__name__)


def _get_field_content(segment: dict, field_name: str) -> str:
    """Extract a field value from a segment dict."""
    for f in segment.get("fields", []):
        if f.get("name") == field_name:
            return f.get("content", "")
    return ""


def _split_transactions(segments: list[dict]) -> list[list[dict]]:
    """Split a flat segment list into ST/SE transaction loops."""
    transactions: list[list[dict]] = []
    current: list[dict] = []
    in_tx = False

    for seg in segments:
        seg_id = seg.get("segment")
        if seg_id == "ST":
            in_tx = True
            current = [seg]
        elif in_tx:
            current.append(seg)
            if seg_id == "SE":
                transactions.append(current)
                in_tx = False
                current = []

    return transactions


def _resolve_json_path(data: dict, path: str) -> str | None:
    """Walk dot-notation path into a flat dict. Returns None if not found."""
    parts = path.split(".")
    current: object = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return str(current) if current is not None else None


def extract_match_values(json_data: dict, match_key: MatchKeyConfig) -> list[MatchEntry]:
    """Extract ALL matching values from a JSON file.

    For X12: walks every ST/SE transaction, finds segment, extracts field.
    For flat JSON (CSV/cXML): resolves dot-notation json_path.
    Returns list of MatchEntry(match_value, transaction_index, transaction_data).

    Ported from: comparator.py find_invoice_in_json() — generalized from BIG02.
    """
    results: list[MatchEntry] = []

    # Flat JSON path mode (CSV/cXML)
    if match_key.json_path:
        value = _resolve_json_path(json_data, match_key.json_path)
        if value:
            results.append(MatchEntry(
                file_path="",
                match_value=value,
                transaction_index=0,
                transaction_data=json_data,
            ))
        return results

    # X12 segment/field mode
    if not match_key.segment or not match_key.field:
        return results

    segments = json_data.get("document", {}).get("segments", [])
    transactions = _split_transactions(segments)

    for tx_index, tx_segments in enumerate(transactions):
        for seg in tx_segments:
            if seg.get("segment") == match_key.segment:
                value = _get_field_content(seg, match_key.field)
                if value:
                    results.append(MatchEntry(
                        file_path="",
                        match_value=value,
                        transaction_index=tx_index,
                        transaction_data={"segments": tx_segments},
                    ))
                    break  # one match per transaction

    return results


def build_match_index(directory: str, match_key: MatchKeyConfig) -> dict[str, list[MatchEntry]]:
    """Scan all JSON files in a directory, return {match_value: [MatchEntry, ...]}.

    Ported from: comparator.py load_target_files_cache() — generalized to index by any match key.
    """
    index: dict[str, list[MatchEntry]] = {}

    for filename in os.listdir(directory):
        if not filename.lower().endswith(".json"):
            continue
        filepath = os.path.join(directory, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping %s: %s", filepath, exc)
            continue

        entries = extract_match_values(data, match_key)
        for entry in entries:
            entry.file_path = filepath
            index.setdefault(entry.match_value, []).append(entry)

    return index


def pair_transactions(
    source_dir: str,
    target_dir: str,
    match_key: MatchKeyConfig,
) -> list[MatchPair]:
    """Pair source and target transactions by match key value.

    Ported from: comparator.py find_target_file_for_invoice() — direct dir scan
    instead of Sheet lookup.
    """
    source_index = build_match_index(source_dir, match_key)
    target_index = build_match_index(target_dir, match_key)

    pairs: list[MatchPair] = []

    for match_value, source_entries in source_index.items():
        target_entries = target_index.get(match_value, [])
        for i, src in enumerate(source_entries):
            tgt = target_entries[i] if i < len(target_entries) else None
            pairs.append(MatchPair(source=src, target=tgt, match_value=match_value))

    return pairs
