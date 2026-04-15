"""Tests for the pyedi_core.comparator module."""

from __future__ import annotations

import json
import os
from dataclasses import asdict

import pytest
import yaml

from pyedi_core.comparator.engine import (
    compare_flat_pair,
    compare_pair,
    compare_segment_fields,
    group_segments_by_id,
    match_segments_by_qualifier,
    segment_to_dict,
)
from pyedi_core.comparator.matcher import extract_match_values, pair_transactions
from pyedi_core.comparator.models import (
    CompareProfile,
    CompareResult,
    CompareRules,
    FieldDiff,
    FieldRule,
    MatchEntry,
    MatchKeyConfig,
    MatchKeyPart,
    MatchPair,
    RunSummary,
)
from pyedi_core.comparator.rules import get_field_rule, load_rules
from pyedi_core.comparator.store import (
    get_diffs,
    get_pairs,
    get_run,
    get_runs,
    init_db,
    insert_diffs,
    insert_pair,
    insert_run,
    update_run,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def rules_path(tmp_path: "os.PathLike[str]") -> str:
    """Write a minimal rules YAML and return its path."""
    rules = {
        "classification": [
            {"segment": "N1", "field": "N102", "severity": "hard", "ignore_case": True},
            {"segment": "IT1", "field": "IT104", "severity": "hard", "numeric": True},
            {"segment": "IT1", "field": "IT109", "severity": "soft", "conditional_qualifier": "IT108"},
            {"segment": "*", "field": "*", "severity": "hard"},
        ],
        "ignore": [
            {"segment": "SE", "field": "SE01", "reason": "Segment count varies"},
            {"segment": "ISA", "field": "*", "reason": "Envelope-level"},
        ],
    }
    p = tmp_path / "rules.yaml"
    p.write_text(yaml.dump(rules), encoding="utf-8")
    return str(p)


@pytest.fixture()
def sample_rules(rules_path: str) -> CompareRules:
    """Load sample rules from the fixture file."""
    return load_rules(rules_path)


def _make_segment(seg_id: str, fields: dict[str, str]) -> dict:
    return {
        "segment": seg_id,
        "fields": [{"name": k, "content": v} for k, v in fields.items()],
    }


def _make_x12_json(transactions: list[list[dict]]) -> dict:
    """Build a document dict from a list of transaction segment lists."""
    segments: list[dict] = []
    for tx in transactions:
        segments.extend(tx)
    return {"document": {"segments": segments}}


def _make_transaction(seg_id: str, match_field: str, match_value: str, extra: list[dict] | None = None) -> list[dict]:
    """Build a minimal ST/SE transaction with a match segment."""
    segs = [
        _make_segment("ST", {"ST01": "810"}),
        _make_segment(seg_id, {match_field: match_value}),
    ]
    if extra:
        segs.extend(extra)
    segs.append(_make_segment("SE", {"SE01": str(len(segs) + 1)}))
    return segs


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSegmentToDict:
    def test_converts_segment(self) -> None:
        seg = _make_segment("N1", {"N101": "ST", "N102": "Ship To Corp"})
        assert segment_to_dict(seg) == {"N101": "ST", "N102": "Ship To Corp"}

    def test_empty_fields(self) -> None:
        seg = {"segment": "N1", "fields": []}
        assert segment_to_dict(seg) == {}


@pytest.mark.unit
class TestGroupSegmentsById:
    def test_groups_correctly(self) -> None:
        segs = [
            _make_segment("N1", {"N101": "ST"}),
            _make_segment("N1", {"N101": "BT"}),
            _make_segment("REF", {"REF01": "ZZ"}),
        ]
        grouped = group_segments_by_id(segs)
        assert len(grouped["N1"]) == 2
        assert len(grouped["REF"]) == 1


@pytest.mark.unit
class TestMatchSegmentsByQualifier:
    def test_qualifier_matching(self) -> None:
        src = [
            _make_segment("N1", {"N101": "ST", "N102": "Source ST"}),
            _make_segment("N1", {"N101": "BT", "N102": "Source BT"}),
        ]
        tgt = [
            _make_segment("N1", {"N101": "BT", "N102": "Target BT"}),
            _make_segment("N1", {"N101": "ST", "N102": "Target ST"}),
        ]
        matches = match_segments_by_qualifier(src, tgt, "N101")
        # Should have 2 matches, one for ST and one for BT
        assert len(matches) == 2
        for s, t, qual in matches:
            assert s is not None
            assert t is not None

    def test_positional_fallback(self) -> None:
        src = [_make_segment("N3", {"N301": "123 Main St"})]
        tgt = [_make_segment("N3", {"N301": "456 Oak Ave"})]
        matches = match_segments_by_qualifier(src, tgt, None)
        assert len(matches) == 1
        assert matches[0][2] == "position_0"

    def test_unmatched_source(self) -> None:
        src = [_make_segment("N1", {"N101": "ST"})]
        tgt: list[dict] = []
        matches = match_segments_by_qualifier(src, tgt, "N101")
        assert len(matches) == 1
        assert matches[0][0] is not None
        assert matches[0][1] is None


@pytest.mark.unit
class TestCompareSegmentFields:
    def test_exact_match(self, sample_rules: CompareRules) -> None:
        src = _make_segment("N1", {"N101": "ST", "N102": "Acme Corp"})
        tgt = _make_segment("N1", {"N101": "ST", "N102": "Acme Corp"})
        diffs = compare_segment_fields(src, tgt, "N1", "ST", sample_rules)
        assert len(diffs) == 0

    def test_mismatch(self, sample_rules: CompareRules) -> None:
        src = _make_segment("REF", {"REF01": "PO", "REF02": "ABC"})
        tgt = _make_segment("REF", {"REF01": "PO", "REF02": "XYZ"})
        diffs = compare_segment_fields(src, tgt, "REF", "PO", sample_rules)
        assert len(diffs) == 1
        assert diffs[0].field == "REF02"
        assert diffs[0].severity == "hard"

    def test_numeric_match(self, sample_rules: CompareRules) -> None:
        src = _make_segment("IT1", {"IT104": "70.03"})
        tgt = _make_segment("IT1", {"IT104": "70.0300"})
        diffs = compare_segment_fields(src, tgt, "IT1", None, sample_rules)
        assert len(diffs) == 0

    def test_case_insensitive(self, sample_rules: CompareRules) -> None:
        src = _make_segment("N1", {"N101": "ST", "N102": "GFS Canada"})
        tgt = _make_segment("N1", {"N101": "ST", "N102": "GFS CANADA"})
        diffs = compare_segment_fields(src, tgt, "N1", "ST", sample_rules)
        assert len(diffs) == 0

    def test_conditional_qualifier(self, sample_rules: CompareRules) -> None:
        # IT109 has conditional_qualifier="IT108". If IT108 exists in source
        # but IT109 is missing, the conditional logic should skip the diff.
        src = _make_segment("IT1", {"IT108": "VP"})
        tgt = _make_segment("IT1", {"IT108": "VP", "IT109": "WIDGET"})
        diffs = compare_segment_fields(src, tgt, "IT1", None, sample_rules)
        # IT109 missing in source, but IT108 exists → skip via conditional
        it109_diffs = [d for d in diffs if d.field == "IT109"]
        assert len(it109_diffs) == 0


@pytest.mark.unit
class TestRulesWildcard:
    def test_wildcard_fallback(self, sample_rules: CompareRules) -> None:
        rule = get_field_rule(sample_rules, "REF", "REF02")
        assert rule.severity == "hard"
        assert rule.ignore_case is False

    def test_exact_over_wildcard(self, sample_rules: CompareRules) -> None:
        rule = get_field_rule(sample_rules, "N1", "N102")
        assert rule.ignore_case is True


@pytest.mark.unit
class TestMatchKeyExtraction:
    def test_x12_match_key(self) -> None:
        tx = _make_transaction("BIG", "BIG02", "INV-001")
        data = _make_x12_json([tx])
        mk = MatchKeyConfig(segment="BIG", field="BIG02")
        entries = extract_match_values(data, mk)
        assert len(entries) == 1
        assert entries[0].match_value == "INV-001"

    def test_json_path_match_key(self) -> None:
        data = {"header": {"invoice_number": "INV-999"}, "lines": []}
        mk = MatchKeyConfig(json_path="header.invoice_number")
        entries = extract_match_values(data, mk)
        assert len(entries) == 1
        assert entries[0].match_value == "INV-999"

    def test_split_remainder_excluded(self) -> None:
        """Files flagged as split remainders should not produce match entries."""
        data = {
            "header": {"invoiceNumber": "unknown", "_is_split_remainder": True},
            "lines": [],
        }
        mk = MatchKeyConfig(json_path="header.invoiceNumber")
        entries = extract_match_values(data, mk)
        assert len(entries) == 0

    def test_split_remainder_flag_absent_allows_match(self) -> None:
        """Normal files without the remainder flag should match normally."""
        data = {"header": {"invoiceNumber": "INV-123"}, "lines": []}
        mk = MatchKeyConfig(json_path="header.invoiceNumber")
        entries = extract_match_values(data, mk)
        assert len(entries) == 1
        assert entries[0].match_value == "INV-123"


@pytest.mark.unit
class TestModelsSerializable:
    def test_all_dataclasses_serialize(self) -> None:
        mk = MatchKeyConfig(segment="BIG", field="BIG02")
        assert isinstance(asdict(mk), dict)

        entry = MatchEntry(file_path="a.json", match_value="X", transaction_index=0, transaction_data={})
        assert isinstance(asdict(entry), dict)

        pair = MatchPair(source=entry, target=None, match_value="X")
        assert isinstance(asdict(pair), dict)

        rule = FieldRule(segment="N1", field="N102")
        assert isinstance(asdict(rule), dict)

        rules = CompareRules()
        assert isinstance(asdict(rules), dict)

        diff = FieldDiff(segment="N1", field="N102", severity="hard", source_value="A", target_value="B", description="mismatch")
        assert isinstance(asdict(diff), dict)

        result = CompareResult(pair=pair, status="MATCH", diffs=[], timestamp="2026-01-01")
        assert isinstance(asdict(result), dict)

        summary = RunSummary(run_id=1, profile="test", total_pairs=0, matched=0, mismatched=0, unmatched=0, started_at="", finished_at="")
        assert isinstance(asdict(summary), dict)


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPairTransactions:
    def test_matched(self, tmp_path: "os.PathLike[str]") -> None:
        src_dir = tmp_path / "source"
        tgt_dir = tmp_path / "target"
        src_dir.mkdir()
        tgt_dir.mkdir()

        tx = _make_transaction("BIG", "BIG02", "INV-001")
        (src_dir / "s.json").write_text(json.dumps(_make_x12_json([tx])))
        (tgt_dir / "t.json").write_text(json.dumps(_make_x12_json([tx])))

        mk = MatchKeyConfig(segment="BIG", field="BIG02")
        pairs = pair_transactions(str(src_dir), str(tgt_dir), mk)
        assert len(pairs) == 1
        assert pairs[0].target is not None
        assert pairs[0].match_value == "INV-001"

    def test_unmatched(self, tmp_path: "os.PathLike[str]") -> None:
        src_dir = tmp_path / "source"
        tgt_dir = tmp_path / "target"
        src_dir.mkdir()
        tgt_dir.mkdir()

        tx = _make_transaction("BIG", "BIG02", "INV-ORPHAN")
        (src_dir / "s.json").write_text(json.dumps(_make_x12_json([tx])))
        # target dir is empty

        mk = MatchKeyConfig(segment="BIG", field="BIG02")
        pairs = pair_transactions(str(src_dir), str(tgt_dir), mk)
        assert len(pairs) == 1
        assert pairs[0].target is None


@pytest.mark.integration
class TestCompareFullPipeline:
    def test_end_to_end(self, tmp_path: "os.PathLike[str]", rules_path: str) -> None:
        from pyedi_core.comparator import compare

        # Build source and target with a mismatch
        src_dir = tmp_path / "source"
        tgt_dir = tmp_path / "target"
        src_dir.mkdir()
        tgt_dir.mkdir()

        src_tx = _make_transaction("BIG", "BIG02", "INV-100", extra=[
            _make_segment("N1", {"N101": "ST", "N102": "Source Name"}),
        ])
        tgt_tx = _make_transaction("BIG", "BIG02", "INV-100", extra=[
            _make_segment("N1", {"N101": "ST", "N102": "Target Name"}),
        ])
        (src_dir / "s.json").write_text(json.dumps(_make_x12_json([src_tx])))
        (tgt_dir / "t.json").write_text(json.dumps(_make_x12_json([tgt_tx])))

        profile = CompareProfile(
            name="test_810",
            description="test",
            match_key=MatchKeyConfig(segment="BIG", field="BIG02"),
            segment_qualifiers={"N1": "N101"},
            rules_file=rules_path,
        )
        db_path = str(tmp_path / "test.db")
        summary = compare(profile, str(src_dir), str(tgt_dir), db_path)

        assert summary.total_pairs == 1
        # N102 differs but ignore_case is true and values differ in more than case
        assert summary.mismatched == 1

    def test_export_csv(self, tmp_path: "os.PathLike[str]", rules_path: str) -> None:
        from pyedi_core.comparator import compare, export_csv

        src_dir = tmp_path / "source"
        tgt_dir = tmp_path / "target"
        src_dir.mkdir()
        tgt_dir.mkdir()

        tx = _make_transaction("BIG", "BIG02", "INV-200")
        (src_dir / "s.json").write_text(json.dumps(_make_x12_json([tx])))
        (tgt_dir / "t.json").write_text(json.dumps(_make_x12_json([tx])))

        profile = CompareProfile(
            name="test_810",
            description="test",
            match_key=MatchKeyConfig(segment="BIG", field="BIG02"),
            segment_qualifiers={},
            rules_file=rules_path,
        )
        db_path = str(tmp_path / "test.db")
        summary = compare(profile, str(src_dir), str(tgt_dir), db_path)

        csv_dir = str(tmp_path / "csv_out")
        csv_path = export_csv(db_path, summary.run_id, csv_dir)
        assert os.path.isfile(csv_path)
        with open(csv_path, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) >= 2  # header + at least one data row


@pytest.mark.integration
class TestStore:
    def test_init_idempotent(self, tmp_path: "os.PathLike[str]") -> None:
        db = str(tmp_path / "test.db")
        init_db(db)
        init_db(db)  # second call should not error

    def test_insert_and_query(self, tmp_path: "os.PathLike[str]") -> None:
        db = str(tmp_path / "test.db")
        init_db(db)

        run_id = insert_run(db, "810_invoice", "/src", "/tgt", "BIG:BIG02")
        assert run_id == 1

        entry = MatchEntry(file_path="a.json", match_value="INV-1", transaction_index=0, transaction_data={})
        pair = MatchPair(source=entry, target=entry, match_value="INV-1")
        pair_id = insert_pair(db, run_id, pair, "MISMATCH", 2)

        diffs = [
            FieldDiff(segment="N1*ST", field="N102", severity="hard", source_value="A", target_value="B", description="mismatch"),
            FieldDiff(segment="REF*PO", field="REF02", severity="soft", source_value="X", target_value="Y", description="mismatch"),
        ]
        insert_diffs(db, pair_id, diffs)

        summary = RunSummary(
            run_id=run_id, profile="810_invoice", total_pairs=1,
            matched=0, mismatched=1, unmatched=0,
            started_at="", finished_at="2026-01-01T00:00:00",
        )
        update_run(db, run_id, summary)

        runs = get_runs(db)
        assert len(runs) == 1
        assert runs[0].mismatched == 1

        run = get_run(db, run_id)
        assert run is not None
        assert run.finished_at == "2026-01-01T00:00:00"

        pairs_result = get_pairs(db, run_id)
        assert len(pairs_result) == 1
        assert pairs_result[0]["status"] == "MISMATCH"

        diffs_result = get_diffs(db, pair_id)
        assert len(diffs_result) == 2
        assert diffs_result[0].segment == "N1*ST"


# ---------------------------------------------------------------------------
# Multi-dimensional match keys
# ---------------------------------------------------------------------------

def _make_x12_tx_doc(segments: list[dict]) -> dict:
    """Wrap a segment list as a single ST/SE transaction document."""
    wrapped = [{"segment": "ST", "fields": [{"name": "ST01", "content": "855"}]}] \
        + segments \
        + [{"segment": "SE", "fields": []}]
    return {"document": {"segments": wrapped}}


def test_multi_key_tuple_pairs_all_match() -> None:
    doc = _make_x12_tx_doc([
        {"segment": "BIG", "fields": [
            {"name": "BIG01", "content": "20260101"},
            {"name": "BIG02", "content": "PO1"},
        ]},
        {"segment": "IT1", "fields": [
            {"name": "IT101", "content": "1"},
            {"name": "IT107", "content": "LINE1"},
        ]},
    ])
    mk = MatchKeyConfig(parts=[
        MatchKeyPart(segment="BIG", field="BIG02"),
        MatchKeyPart(segment="IT1", field="IT107"),
    ])
    entries = extract_match_values(doc, mk)
    assert len(entries) == 1
    assert entries[0].match_value == "PO1\x1fLINE1"


def test_multi_key_missing_part_drops_transaction() -> None:
    doc = _make_x12_tx_doc([
        {"segment": "BIG", "fields": [
            {"name": "BIG02", "content": "PO1"},
        ]},
        # IT1 omitted
    ])
    mk = MatchKeyConfig(parts=[
        MatchKeyPart(segment="BIG", field="BIG02"),
        MatchKeyPart(segment="IT1", field="IT107"),
    ])
    entries = extract_match_values(doc, mk)
    assert entries == []
