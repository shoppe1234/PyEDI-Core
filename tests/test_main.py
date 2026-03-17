"""
Unit tests for pyedi_core/main.py — CLI entry point.
"""

import pytest
from unittest.mock import patch, MagicMock

from pyedi_core.main import main, _print_result
from pyedi_core.pipeline import PipelineResult


def make_result(status="SUCCESS", errors=None, source_file="test.csv"):
    """Helper to create a PipelineResult for testing."""
    return PipelineResult(
        status=status,
        correlation_id="test-123",
        source_file=source_file,
        transaction_type="810",
        output_path=None,
        payload=None,
        errors=errors or [],
        processing_time_ms=100,
    )


@pytest.mark.unit
class TestMain:
    """Tests for the main() CLI entry point."""

    @patch("pyedi_core.main.Pipeline")
    def test_main_default_args(self, MockPipeline):
        """Call main([]) with mocked Pipeline returning SUCCESS. Expect exit 0."""
        mock_pipeline = MockPipeline.return_value
        mock_pipeline.run.return_value = make_result("SUCCESS")
        assert main([]) == 0

    @patch("pyedi_core.main.Pipeline")
    def test_main_single_file_success(self, MockPipeline):
        """Single file with --dry-run, SUCCESS result. Expect exit 0."""
        mock_pipeline = MockPipeline.return_value
        mock_pipeline.run.return_value = make_result("SUCCESS")
        assert main(["--file", "test.csv", "--dry-run"]) == 0

    @patch("pyedi_core.main.Pipeline")
    def test_main_single_file_failure(self, MockPipeline):
        """Single file, FAILED result. Expect exit 1."""
        mock_pipeline = MockPipeline.return_value
        mock_pipeline.run.return_value = make_result("FAILED", errors=["bad data"])
        assert main(["--file", "test.csv", "--dry-run"]) == 1

    @patch("pyedi_core.main.Pipeline")
    def test_main_batch_results(self, MockPipeline):
        """Batch with one SUCCESS and one FAILED. Expect exit 1."""
        mock_pipeline = MockPipeline.return_value
        mock_pipeline.run.return_value = [
            make_result("SUCCESS", source_file="a.csv"),
            make_result("FAILED", errors=["parse error"], source_file="b.csv"),
        ]
        assert main(["--files", "a.csv", "b.csv"]) == 1

    @patch("pyedi_core.main.Pipeline")
    def test_main_batch_all_success(self, MockPipeline):
        """Batch with all SUCCESS results. Expect exit 0."""
        mock_pipeline = MockPipeline.return_value
        mock_pipeline.run.return_value = [
            make_result("SUCCESS", source_file="a.csv"),
            make_result("SUCCESS", source_file="b.csv"),
        ]
        assert main(["--files", "a.csv", "b.csv"]) == 0

    @patch("pyedi_core.main.Pipeline")
    def test_main_pipeline_init_error(self, MockPipeline):
        """Pipeline constructor raises Exception. Expect exit 1."""
        MockPipeline.side_effect = Exception("config not found")
        assert main([]) == 1

    @patch("pyedi_core.main.Pipeline")
    def test_main_pipeline_runtime_error(self, MockPipeline):
        """Pipeline.run raises Exception. Expect exit 1."""
        mock_pipeline = MockPipeline.return_value
        mock_pipeline.run.side_effect = Exception("runtime boom")
        assert main([]) == 1

    @patch("pyedi_core.main.Pipeline")
    def test_main_verbose_flag(self, MockPipeline):
        """Passing --verbose should not crash."""
        mock_pipeline = MockPipeline.return_value
        mock_pipeline.run.return_value = make_result("SUCCESS")
        assert main(["--verbose"]) == 0


@pytest.mark.unit
class TestPrintResult:
    """Tests for the _print_result() helper."""

    def test_print_result(self, capsys):
        """Print a SUCCESS result and verify output contains key fields."""
        result = make_result("SUCCESS")
        _print_result(result)
        captured = capsys.readouterr()
        assert "SUCCESS" in captured.out
        assert "test.csv" in captured.out
        assert "810" in captured.out

    def test_print_result_with_errors(self, capsys):
        """Print a FAILED result with errors and verify errors appear in output."""
        result = make_result("FAILED", errors=["missing field X", "invalid date"])
        _print_result(result)
        captured = capsys.readouterr()
        assert "FAILED" in captured.out
        assert "missing field X" in captured.out
        assert "invalid date" in captured.out
