"""
Unit tests for PyEDI-Core core modules.

Tests logger, manifest, error_handler, schema_compiler, and mapper modules.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest


# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestLogger:
    """Tests for the logger module."""
    
    def test_generate_correlation_id(self):
        """Test correlation ID generation."""
        from pyedi_core.core import logger
        
        corr_id = logger.generate_correlation_id()
        assert corr_id is not None
        assert len(corr_id) == 36  # UUID4 format
        
        # Test uniqueness
        corr_id2 = logger.generate_correlation_id()
        assert corr_id != corr_id2
    
    def test_configure(self):
        """Test logger configuration."""
        from pyedi_core.core import logger
        
        # Test with default config
        logger.configure({
            "log_level": "DEBUG",
            "output": "console",
            "format": "pretty"
        })
        
        log = logger.get_logger()
        assert log is not None
    
    def test_bind_logger(self):
        """Test binding context to logger."""
        from pyedi_core.core import logger
        
        bound = logger.bind_logger(
            correlation_id="test-123",
            file_name="test.csv",
            stage="DETECTION"
        )
        
        assert bound is not None


class TestManifest:
    """Tests for the manifest module."""
    
    @pytest.fixture
    def temp_manifest(self):
        """Create a temporary manifest file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.processed') as f:
            manifest_path = f.name
        yield manifest_path
        # Cleanup
        if os.path.exists(manifest_path):
            os.unlink(manifest_path)
    
    def test_compute_sha256(self, tmp_path):
        """Test SHA-256 computation."""
        from pyedi_core.core import manifest
        
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        
        hash1 = manifest.compute_sha256(str(test_file))
        assert hash1 is not None
        assert len(hash1) == 64  # SHA-256 hex length
        
        # Same content = same hash
        hash2 = manifest.compute_sha256(str(test_file))
        assert hash1 == hash2
    
    def test_is_duplicate_not_exists(self, temp_manifest):
        """Test duplicate check for new file."""
        from pyedi_core.core import manifest
        
        # Create a test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            test_file = f.name
            f.write("test,data")
        
        try:
            is_dup, status = manifest.is_duplicate(test_file, temp_manifest)
            assert is_dup is False
            assert status is None
        finally:
            os.unlink(test_file)
    
    def test_mark_processed(self, temp_manifest):
        """Test marking a file as processed."""
        from pyedi_core.core import manifest
        
        # Create a test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            test_file = f.name
            f.write("test,data")
        
        try:
            manifest.mark_processed(test_file, "SUCCESS", temp_manifest)
            
            # Check it's now a duplicate
            is_dup, status = manifest.is_duplicate(test_file, temp_manifest)
            assert is_dup is True
            assert status == "SUCCESS"
        finally:
            os.unlink(test_file)
    
    def test_filter_inbound_files(self, temp_manifest):
        """Test filtering inbound files against manifest."""
        from pyedi_core.core import manifest
        
        # Create test files
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f1:
            file1 = f1.name
            f1.write("test1,data")
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f2:
            file2 = f2.name
            f2.write("test2,data")
        
        try:
            # Mark file1 as processed
            manifest.mark_processed(file1, "SUCCESS", temp_manifest)
            
            # Filter
            new_files, dup_files = manifest.filter_inbound_files(
                [file1, file2], temp_manifest
            )
            
            assert file1 in dup_files
            assert file2 in new_files
        finally:
            os.unlink(file1)
            os.unlink(file2)


class TestErrorHandler:
    """Tests for the error_handler module."""
    
    @pytest.fixture
    def temp_failed_dir(self, tmp_path):
        """Create a temporary failed directory."""
        failed_dir = tmp_path / "failed"
        failed_dir.mkdir()
        return str(failed_dir)
    
    def test_handle_failure(self, tmp_path, temp_failed_dir):
        """Test error handling creates correct output."""
        from pyedi_core.core import error_handler
        
        # Create a test file
        test_file = tmp_path / "test.csv"
        test_file.write_text("test,data")
        
        # Handle failure
        error_file = error_handler.handle_failure(
            file_path=str(test_file),
            stage=error_handler.Stage.TRANSFORMATION,
            reason="Test error",
            exception=ValueError("Test exception"),
            correlation_id="test-123",
            failed_dir=temp_failed_dir
        )
        
        # Verify error file exists
        assert os.path.exists(error_file)
        
        # Verify error content
        with open(error_file, 'r') as f:
            error_details = json.load(f)
        
        assert error_details['stage'] == 'TRANSFORMATION'
        assert error_details['reason'] == 'Test error'
        assert error_details['correlation_id'] == 'test-123'
        assert 'Test exception' in error_details['exception']
    
    def test_validate_stage(self):
        """Test stage validation."""
        from pyedi_core.core import error_handler
        
        assert error_handler.validate_stage("DETECTION") is True
        assert error_handler.validate_stage("VALIDATION") is True
        assert error_handler.validate_stage("TRANSFORMATION") is True
        assert error_handler.validate_stage("WRITE") is True
        assert error_handler.validate_stage("INVALID") is False


class TestSchemaCompiler:
    """Tests for the schema_compiler module."""
    
    def test_parse_dsl_record(self):
        """Test DSL record parsing."""
        from pyedi_core.core import schema_compiler
        
        dsl_text = """
        def record Header {
            invoice_number String
            invoice_date Date
            amount Decimal = 0.0
        }
        """
        
        result = schema_compiler._parse_dsl_record(dsl_text)
        
        assert result['name'] == 'Header'
        assert result['type'] == 'header'
        assert len(result['fields']) >= 2
    
    def test_compile_to_yaml(self):
        """Test YAML compilation."""
        from pyedi_core.core import schema_compiler
        
        record_defs = [
            {
                "name": "Header",
                "type": "header",
                "fields": [
                    {"name": "invoice_number", "type": "string", "required": True},
                    {"name": "amount", "type": "float", "required": False, "default": 0.0}
                ]
            }
        ]
        
        result = schema_compiler._compile_to_yaml(record_defs, "test_810.txt")
        
        assert 'transaction_type' in result
        assert 'mapping' in result
        assert 'header' in result['mapping']


class TestMapper:
    """Tests for the mapper module."""
    
    def test_transform_to_float(self):
        """Test to_float transform."""
        from pyedi_core.core import mapper
        
        assert mapper.transform_to_float("123.45") == 123.45
        assert mapper.transform_to_float("1,234.56") == 1234.56
        assert mapper.transform_to_float(None) is None
        assert mapper.transform_to_float("") is None
    
    def test_transform_to_int(self):
        """Test to_int transform."""
        from pyedi_core.core import mapper
        
        assert mapper.transform_to_int("123") == 123
        assert mapper.transform_to_int("123.99") == 123
        assert mapper.transform_to_int(None) is None
    
    def test_transform_to_date(self):
        """Test to_date transform."""
        from pyedi_core.core import mapper
        
        assert mapper.transform_to_date("01/15/2025") == "2025-01-15"
        assert mapper.transform_to_date("12/31/2024") == "2024-12-31"
        assert mapper.transform_to_date(None) is None
    
    def test_transform_strip(self):
        """Test strip transform."""
        from pyedi_core.core import mapper
        
        assert mapper.transform_strip("  hello  ") == "hello"
        assert mapper.transform_strip(None) == ""
    
    def test_transform_upper(self):
        """Test upper transform."""
        from pyedi_core.core import mapper
        
        assert mapper.transform_upper("hello") == "HELLO"
        assert mapper.transform_upper(None) == ""
    
    def test_transform_replace(self):
        """Test replace transform."""
        from pyedi_core.core import mapper
        
        assert mapper.transform_replace("hello world", "world", "there") == "hello there"
        assert mapper.transform_replace(None, "a", "b") == ""
    
    def test_get_nested_value(self):
        """Test nested value extraction."""
        from pyedi_core.core import mapper
        
        data = {
            "header": {
                "invoice_id": "INV-001"
            },
            "lines": [
                {"item_id": "ITEM-001"}
            ]
        }
        
        assert mapper._get_nested_value(data, "header.invoice_id") == "INV-001"
        assert mapper._get_nested_value(data, "lines.0.item_id") == "ITEM-001"
        assert mapper._get_nested_value(data, "nonexistent") is None
    
    def test_map_data(self):
        """Test full data mapping."""
        from pyedi_core.core import mapper
        
        raw_data = {
            "Invoice Number": "INV-001",
            "Invoice Date": "01/15/2025",
            "Net Case Price": "100.50",
            "lines": [
                {"Item Number": "ITEM-001", "Quantity": "5"}
            ]
        }
        
        map_yaml = {
            "transaction_type": "810_INVOICE",
            "input_format": "CSV",
            "mapping": {
                "header": {
                    "invoice_id": {
                        "source": "Invoice Number",
                        "transform": "strip"
                    },
                    "date": {
                        "source": "Invoice Date",
                        "transform": {"name": "to_date", "format": "%m/%d/%Y"}
                    }
                },
                "lines": [
                    {
                        "item_id": {"source": "Item Number"},
                        "quantity": {"source": "Quantity", "transform": "to_int"}
                    }
                ],
                "summary": {}
            }
        }
        
        result = mapper.map_data(raw_data, map_yaml)
        
        assert result['header']['invoice_id'] == "INV-001"
        assert result['header']['date'] == "2025-01-15"
        assert len(result['lines']) == 1
        assert result['lines'][0]['item_id'] == "ITEM-001"
    
    def test_list_available_transforms(self):
        """Test listing available transforms."""
        from pyedi_core.core import mapper
        
        transforms = mapper.list_available_transforms()
        
        assert 'to_float' in transforms
        assert 'to_int' in transforms
        assert 'to_date' in transforms
        assert 'strip' in transforms
        assert 'upper' in transforms


class TestDrivers:
    """Tests for driver modules."""
    
    def test_csv_handler_import(self):
        """Test CSV handler can be imported."""
        from pyedi_core.drivers import CSVHandler
        
        handler = CSVHandler(correlation_id="test-123")
        assert handler.correlation_id == "test-123"
    
    def test_x12_handler_import(self):
        """Test X12 handler can be imported."""
        from pyedi_core.drivers import X12Handler
        
        handler = X12Handler(correlation_id="test-456")
        assert handler.correlation_id == "test-456"
    
    def test_xml_handler_import(self):
        """Test XML handler can be imported."""
        from pyedi_core.drivers import XMLHandler
        
        handler = XMLHandler(correlation_id="test-789")
        assert handler.correlation_id == "test-789"
    
    def test_driver_registry(self):
        """Test driver registry."""
        from pyedi_core.drivers import DriverRegistry, get_driver
        
        # Check default drivers registered
        drivers = DriverRegistry.list_drivers()
        
        assert 'csv' in drivers
        assert 'x12' in drivers
        assert 'xml' in drivers
        assert 'cxml' in drivers


class TestPipeline:
    """Tests for Pipeline class."""
    
    def test_pipeline_result_model(self):
        """Test PipelineResult model."""
        from pyedi_core.pipeline import PipelineResult
        
        result = PipelineResult(
            status="SUCCESS",
            correlation_id="test-123",
            source_file="test.csv",
            transaction_type="810",
            output_path="/output/test.json",
            payload={"header": {}},
            errors=[],
            processing_time_ms=100
        )
        
        assert result.status == "SUCCESS"
        assert result.correlation_id == "test-123"
        assert result.processing_time_ms == 100
    
    def test_pipeline_init(self):
        """Test pipeline initialization."""
        from pyedi_core.pipeline import Pipeline
        
        # Create with non-existent config (should use defaults)
        pipeline = Pipeline(config_path="/nonexistent/config.yaml")
        
        assert pipeline._source_system_id == "unknown"
        assert pipeline._max_workers == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
