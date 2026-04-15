"""File pairing and transaction extraction for the compare engine.

Ported from: json810Compare/comparator.py — find_invoice_in_json(),
find_target_file_for_invoice(), load_target_files_cache().
Generalized from BIG02-only to any match key via MatchKeyConfig.
"""

from __future__ import annotations

import json
import logging
import os
import re

from pyedi_core.comparator.models import MatchEntry, MatchKeyConfig, MatchKeyPart, MatchPair

_COMPOSITE_SEP = "\x1f"

logger = logging.getLogger(__name__)


def _normalize_value(value: str, normalize: str | None) -> str:
    """Apply optional regex normalization to a match value.

    Format: "pattern|replacement" — applies re.sub(pattern, replacement, value).
    """
    if not normalize:
        return value
    parts = normalize.split("|", 1)
    if len(parts) != 2:
        logger.warning("Invalid normalize format (expected 'pattern|replacement'): %s", normalize)
        return value
    pattern, replacement = parts
    try:
        return re.sub(pattern, replacement, value)
    except re.error as exc:
        logger.warning("Normalize regex error: %s", exc)
        return value


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


def _part_value_from_tx(tx_segments: list[dict], part: MatchKeyPart) -> str | None:
    """Extract one part's value from an X12 transaction segment list."""
    for seg in tx_segments:
        if seg.get("segment") == part.segment:
            value = _get_field_content(seg, part.field or "")
            if value:
                return _normalize_value(value, part.normalize)
    return None


def extract_match_values(json_data: dict, match_key: MatchKeyConfig) -> list[MatchEntry]:
    """Extract ALL matching values from a JSON file.

    Composite keys: all configured parts must resolve (strict AND) or the
    transaction is dropped. Parts are joined by unit separator \\x1f.

    Ported from: comparator.py find_invoice_in_json() — generalized from BIG02.
    """
    results: list[MatchEntry] = []

    parts = match_key.parts
    if not parts:
        raise ValueError("match_key has no parts configured")

    is_json_mode = all(p.json_path for p in parts)
    is_x12_mode = all(p.segment and p.field for p in parts)
    if not (is_json_mode or is_x12_mode):
        raise ValueError(
            "match_key parts must all be X12 segment/field or all json_path — not mixed"
        )

    # Flat JSON path mode (CSV/cXML)
    if is_json_mode:
        if json_data.get("header", {}).get("_is_split_remainder"):
            return results
        values: list[str] = []
        for p in parts:
            v = _resolve_json_path(json_data, p.json_path or "")
            if not v:
                return results
            values.append(_normalize_value(v, p.normalize))
        results.append(MatchEntry(
            file_path="",
            match_value=_COMPOSITE_SEP.join(values),
            transaction_index=0,
            transaction_data=json_data,
        ))
        return results

    # X12 segment/field mode
    segments = json_data.get("document", {}).get("segments", [])
    transactions = _split_transactions(segments)

    for tx_index, tx_segments in enumerate(transactions):
        values = []
        missing = False
        for p in parts:
            v = _part_value_from_tx(tx_segments, p)
            if v is None:
                missing = True
                break
            values.append(v)
        if missing:
            continue
        results.append(MatchEntry(
            file_path="",
            match_value=_COMPOSITE_SEP.join(values),
            transaction_index=tx_index,
            transaction_data={"segments": tx_segments},
        ))

    return results


_X12_EXTENSIONS = (".txt", ".edi", ".x12")
_SUPPORTED_EXTENSIONS = (".json",) + _X12_EXTENSIONS


def _parse_x12_to_doc(file_path: str) -> dict:
    """Parse a raw X12 file into pipeline-equivalent document form.

    Detects element separator from ISA segment char[3] and segment terminator
    from char[105]. Names fields positionally as `{segment_id}{NN:02d}`.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if len(content) < 106 or not content.startswith("ISA"):
        raise ValueError(f"Not a valid X12 file (missing ISA header): {file_path}")

    element_sep = content[3]
    segment_term = content[105]

    raw_segments = [s for s in content.split(segment_term) if s.strip()]

    segments: list[dict] = []
    transaction_type = ""
    for raw in raw_segments:
        raw = raw.strip("\r\n")
        if not raw:
            continue
        elements = raw.split(element_sep)
        seg_id = elements[0]
        fields = [
            {"name": f"{seg_id}{idx:02d}", "content": elements[idx]}
            for idx in range(1, len(elements))
        ]
        segments.append({"segment": seg_id, "fields": fields})
        if seg_id == "ST" and not transaction_type and len(elements) > 1:
            transaction_type = elements[1]

    return {
        "document": {"segments": segments},
        "_transaction_type": transaction_type,
        "_is_unmapped": True,
    }


def build_match_index(directory: str, match_key: MatchKeyConfig) -> dict[str, list[MatchEntry]]:
    """Scan all supported files in a directory, return {match_value: [MatchEntry, ...]}.

    Ported from: comparator.py load_target_files_cache() — generalized to index by any match key.
    Accepts .json (pipeline output) and raw X12 (.txt/.edi/.x12).
    """
    index: dict[str, list[MatchEntry]] = {}

    for filename in os.listdir(directory):
        lower = filename.lower()
        if not lower.endswith(_SUPPORTED_EXTENSIONS):
            continue
        filepath = os.path.join(directory, filename)
        try:
            if lower.endswith(".json"):
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = _parse_x12_to_doc(filepath)
        except (json.JSONDecodeError, OSError, IndexError, ValueError) as exc:
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

    # Target-only pairs (match values present in target but not in source)
    for match_value, target_entries in target_index.items():
        if match_value not in source_index:
            for tgt in target_entries:
                pairs.append(MatchPair(source=None, target=tgt, match_value=match_value))

    return pairs
