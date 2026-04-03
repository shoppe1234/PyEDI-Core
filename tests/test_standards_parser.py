"""Tests for the .ediSchema standards parser."""
import pytest
from pathlib import Path
from pyedi_core.standards_parser import (
    parse_edi_schema,
    scan_standards_dir,
    get_message_segments,
    MessageSchema,
)

_STANDARDS_DIR = Path(__file__).resolve().parent.parent / "standards"
_SKIP_NO_STANDARDS = pytest.mark.skipif(
    not (_STANDARDS_DIR / "x12").exists(),
    reason="standards directory not present"
)


@_SKIP_NO_STANDARDS
class TestParseEdiSchema:
    """Tests for parse_edi_schema()."""

    def test_810_v004010_metadata(self) -> None:
        """Parse 810 Invoice from 4010 and verify metadata."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message810.ediSchema"
        result = parse_edi_schema(path)
        assert result.code == "810"
        assert result.name == "Invoice"
        assert result.version == "004010"
        assert result.functional_group == "IN"
        assert result.standard_type == "x12"

    def test_850_v004010_metadata(self) -> None:
        """Parse 850 Purchase Order from 4010."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message850.ediSchema"
        result = parse_edi_schema(path)
        assert result.code == "850"
        assert result.name == "Purchase Order"
        assert result.version == "004010"

    def test_997_v004010_small_file(self) -> None:
        """Parse 997 Functional Ack -- a small file as smoke test."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message997.ediSchema"
        result = parse_edi_schema(path)
        assert result.code == "997"
        assert result.name == "Functional Acknowledgment"

    def test_810_has_areas(self) -> None:
        """Verify the 810 schema contains multiple areas with segments."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message810.ediSchema"
        result = parse_edi_schema(path)
        assert len(result.areas) >= 2
        area1_names = [ref.name for ref in result.areas[0]]
        assert "ST" in area1_names
        assert "BIG" in area1_names

    def test_810_has_segment_defs(self) -> None:
        """Verify segment definitions are parsed."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message810.ediSchema"
        result = parse_edi_schema(path)
        assert "BIG" in result.segment_defs
        big = result.segment_defs["BIG"]
        assert big.name == "Beginning Segment for Invoice"
        assert len(big.elements) > 0

    def test_810_segment_group_children(self) -> None:
        """Verify segment groups contain child segment refs."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message810.ediSchema"
        result = parse_edi_schema(path)
        n1_group = None
        for ref in result.areas[0]:
            if ref.name == "N1" and ref.ref_type == "segmentGroup":
                n1_group = ref
                break
        assert n1_group is not None, "N1 segment group not found in area 1"
        child_names = [c.name for c in n1_group.children]
        assert "N1" in child_names
        assert "N2" in child_names

    def test_810_v005010_different_version(self) -> None:
        """Parse the same transaction from a different version."""
        path = _STANDARDS_DIR / "x12" / "v005010" / "schemas" / "Message810.ediSchema"
        result = parse_edi_schema(path)
        assert result.code == "810"
        assert result.version == "005010"

    def test_cardinality_parsing(self) -> None:
        """Verify min/max cardinality is parsed correctly."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message810.ediSchema"
        result = parse_edi_schema(path)
        st = next(r for r in result.areas[0] if r.name == "ST")
        assert st.min_occurs == 1
        assert st.max_occurs == 1
        nte = next(r for r in result.areas[0] if r.name == "NTE")
        assert nte.min_occurs == 0
        assert nte.max_occurs == 100


@_SKIP_NO_STANDARDS
class TestScanStandardsDir:
    """Tests for scan_standards_dir()."""

    def test_returns_x12(self) -> None:
        """Catalog should contain x12 standard."""
        result = scan_standards_dir(_STANDARDS_DIR)
        assert "x12" in result

    def test_x12_has_five_versions(self) -> None:
        """X12 should have 5 versions."""
        result = scan_standards_dir(_STANDARDS_DIR)
        assert len(result["x12"]) == 5

    def test_v004010_has_294_transactions(self) -> None:
        """v004010 should have 294 transactions."""
        result = scan_standards_dir(_STANDARDS_DIR)
        assert len(result["x12"]["4010"]) == 294

    def test_v005010_has_318_transactions(self) -> None:
        """v005010 should have 318 transactions."""
        result = scan_standards_dir(_STANDARDS_DIR)
        assert len(result["x12"]["5010"]) == 318

    def test_transaction_entry_has_required_fields(self) -> None:
        """Each transaction entry should have code, name, file."""
        result = scan_standards_dir(_STANDARDS_DIR)
        entry = result["x12"]["4010"][0]
        assert "code" in entry
        assert "name" in entry
        assert "file" in entry

    def test_810_exists_in_all_versions(self) -> None:
        """810 should be available in all 5 X12 versions."""
        result = scan_standards_dir(_STANDARDS_DIR)
        for version, txns in result["x12"].items():
            codes = [t["code"] for t in txns]
            assert "810" in codes, f"810 not found in version {version}"


@_SKIP_NO_STANDARDS
class TestGetMessageSegments:
    """Tests for get_message_segments()."""

    def test_810_segments(self) -> None:
        """810 should include common invoice segments."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message810.ediSchema"
        segments = get_message_segments(path)
        assert "ST" in segments
        assert "BIG" in segments
        assert "SE" in segments

    def test_850_segments(self) -> None:
        """850 should include BEG segment."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message850.ediSchema"
        segments = get_message_segments(path)
        assert "BEG" in segments
