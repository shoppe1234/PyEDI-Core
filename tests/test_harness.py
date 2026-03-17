"""
Tests for the pyedi test harness module.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pyedi_core.test_harness import compare_outputs, run_tests, generate_expected, verify


@pytest.mark.unit
class TestCompareOutputs:
    """Tests for the recursive compare_outputs function."""

    def test_matching_dicts(self):
        actual = {"a": 1, "b": "hello"}
        expected = {"a": 1, "b": "hello"}
        discrepancies = []
        compare_outputs(actual, expected, set(), discrepancies)
        assert discrepancies == []

    def test_value_mismatch(self):
        actual = {"a": 1}
        expected = {"a": 2}
        discrepancies = []
        compare_outputs(actual, expected, set(), discrepancies)
        assert len(discrepancies) == 1
        assert "Value mismatch" in discrepancies[0]

    def test_missing_key(self):
        actual = {"a": 1}
        expected = {"a": 1, "b": 2}
        discrepancies = []
        compare_outputs(actual, expected, set(), discrepancies)
        assert len(discrepancies) == 1
        assert "Missing key" in discrepancies[0]

    def test_unexpected_key(self):
        actual = {"a": 1, "extra": 99}
        expected = {"a": 1}
        discrepancies = []
        compare_outputs(actual, expected, set(), discrepancies)
        assert len(discrepancies) == 1
        assert "Unexpected key" in discrepancies[0]

    def test_skip_fields(self):
        actual = {"a": 1, "id": "xxx"}
        expected = {"a": 1, "id": "yyy"}
        discrepancies = []
        compare_outputs(actual, expected, {"id"}, discrepancies)
        assert discrepancies == []

    def test_list_length_mismatch(self):
        actual = [1, 2, 3]
        expected = [1, 2]
        discrepancies = []
        compare_outputs(actual, expected, set(), discrepancies)
        assert len(discrepancies) == 1
        assert "List length mismatch" in discrepancies[0]

    def test_nested_comparison(self):
        actual = {"header": {"amount": 100.0}}
        expected = {"header": {"amount": 200.0}}
        discrepancies = []
        compare_outputs(actual, expected, set(), discrepancies)
        assert len(discrepancies) == 1
        assert "header.amount" in discrepancies[0]

    def test_float_tolerance(self):
        actual = {"val": 1.005}
        expected = {"val": 1.001}
        discrepancies = []
        compare_outputs(actual, expected, set(), discrepancies)
        assert discrepancies == []  # diff < 0.01

    def test_float_nan_equal(self):
        actual = {"val": float("nan")}
        expected = {"val": float("nan")}
        discrepancies = []
        compare_outputs(actual, expected, set(), discrepancies)
        assert discrepancies == []


@pytest.mark.unit
class TestRunTests:
    """Tests for the run_tests function."""

    def test_missing_metadata(self, tmp_path):
        result = run_tests(
            config_path="./config/config.yaml",
            metadata_path=str(tmp_path / "nonexistent.yaml"),
        )
        assert result == 1

    def test_empty_test_cases(self, tmp_path):
        meta = tmp_path / "metadata.yaml"
        meta.write_text("test_cases: []\n")
        result = run_tests(
            config_path="./config/config.yaml",
            metadata_path=str(meta),
        )
        assert result == 0


@pytest.mark.integration
class TestRunTestsIntegration:
    """Integration test for run_tests with real metadata."""

    def test_run_real_tests(self):
        result = run_tests(
            config_path="./config/config.yaml",
            metadata_path="tests/user_supplied/metadata.yaml",
        )
        assert result == 0


@pytest.mark.unit
class TestVerify:
    """Tests for the verify function."""

    def test_verify_passes_in_project(self):
        result = verify()
        assert result == 0


@pytest.mark.unit
class TestGenerateExpected:
    """Tests for the generate_expected function."""

    def test_missing_metadata(self, tmp_path):
        result = generate_expected(
            config_path="./config/config.yaml",
            metadata_path=str(tmp_path / "nonexistent.yaml"),
        )
        assert result == 1

    def test_empty_test_cases(self, tmp_path):
        meta = tmp_path / "metadata.yaml"
        meta.write_text("test_cases: []\n")
        result = generate_expected(
            config_path="./config/config.yaml",
            metadata_path=str(meta),
        )
        assert result == 0


@pytest.mark.unit
class TestMainTestSubcommand:
    """Tests for the `pyedi test` CLI subcommand wiring."""

    def test_test_verify_subcommand(self):
        from pyedi_core.main import main
        result = main(["test", "--verify"])
        assert result == 0

    def test_test_subcommand_runs(self):
        from pyedi_core.main import main
        result = main(["test", "--metadata", "tests/user_supplied/metadata.yaml"])
        assert result == 0

    def test_backward_compat_no_subcommand(self):
        """Calling main with --dry-run and no subcommand should still work."""
        from pyedi_core.main import main
        # No file provided → pipeline scans inbound (may find nothing)
        result = main(["--dry-run"])
        # Should not crash — returns 0 or 1 depending on inbound state
        assert result in (0, 1)
