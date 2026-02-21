"""
Extended unit tests for PyEDI-Core core modules - higher coverage.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest


class TestLoggerExtended:
    """Extended tests for logger module."""
    
    def test_logger_mixin(self):
        """Test LoggerMixin class."""
        from pyedi_core.core.logger import LoggerMixin
        
        class TestClass(LoggerMixin):
            pass
        
        obj = TestClass()
        # Should have correlation_id
        assert obj.correlation_id is not None
        # Should have logger property
        assert obj.logger is not None
        
        # Test setting correlation_id
        obj.set_correlation_id("custom-id")
        assert obj.correlation_id == "custom-id"
    
    def test_module_level_log_functions(self):
        """Test module-level logging functions."""
        from pyedi_core.core import logger
        
        # These should not raise errors
        logger.debug("debug test")
        logger.info("info test")
        logger.warning("warning test")
        logger.error("error test")


class TestManifestExtended:
    """Extended tests for manifest module."""
    
    def test_get_processed_files(self, tmp_path):
        """Test getting processed files list."""
        from pyedi_core.core import manifest
        
        manifest_file = tmp_path / ".processed"
        
        # Write some test entries
        with open(manifest_file, 'w') as f:
            f.write("abc123|test1.csv|2025-01-15T10:00:00Z|SUCCESS\n")
            f.write("def456|test2.csv|2025-01-15T11:00:00Z|FAILED\n")
        
        files = manifest.get_processed_files(str(manifest_file))
        
        assert len(files) == 2
        assert files[0]['filename'] == 'test1.csv'
        assert files[0]['status'] == 'SUCCESS'
        assert files[1]['status'] == 'FAILED'
    
    def test_clear_manifest(self, tmp_path):
        """Test clearing manifest."""
        from pyedi_core.core import manifest
        
        manifest_file = tmp_path / ".processed"
        manifest_file.write_text("abc123|test.csv|2025-01-15T10:00:00Z|SUCCESS\n")
        
        manifest.clear_manifest(str(manifest_file))
        
        assert not manifest_file.exists()


class TestErrorHandlerExtended:
    """Extended tests for error_handler module."""
    
    def test_get_failed_files(self, tmp_path):
        """Test getting failed files list."""
        from pyedi_core.core import error_handler
        
        failed_dir = tmp_path / "failed"
        failed_dir.mkdir()
        
        # Create some failed files
        (failed_dir / "file1.csv").write_text("data1")
        (failed_dir / "file2.csv").write_text("data2")
        
        files = error_handler.get_failed_files(str(failed_dir))
        
        assert len(files) == 2
    
    def test_read_error_details(self, tmp_path):
        """Test reading error details from JSON."""
        from pyedi_core.core import error_handler
        
        error_file = tmp_path / "test.error.json"
        error_data = {
            "stage": "TRANSFORMATION",
            "reason": "Test error",
            "exception": "ValueError",
            "correlation_id": "test-123",
            "timestamp": "2025-01-15T10:00:00Z",
            "source_file": "test.csv"
        }
        
        with open(error_file, 'w') as f:
            json.dump(error_data, f)
        
        result = error_handler.read_error_details(str(error_file))
        
        assert result is not None
        assert result['stage'] == 'TRANSFORMATION'
        assert result['reason'] == 'Test error'
    
    def test_retry_failed_file(self, tmp_path):
        """Test retry failed file functionality."""
        from pyedi_core.core import error_handler
        
        # Setup directories
        failed_dir = tmp_path / "failed"
        failed_dir.mkdir()
        retry_dir = tmp_path / "retry"
        retry_dir.mkdir()
        
        # Create failed file with error JSON
        failed_file = failed_dir / "test.csv"
        failed_file.write_text("test data")
        error_file = failed_dir / "test.error.json"
        error_file.write_text('{"stage": "WRITE"}')
        
        # Retry
        result = error_handler.retry_failed_file(
            str(failed_file),
            str(retry_dir),
            remove_error_json=True
        )
        
        assert result is True
        assert (retry_dir / "test.csv").exists()
        assert not error_file.exists()


class TestSchemaCompilerExtended:
    """Extended tests for schema_compiler module."""
    
    def test_list_compiled_schemas(self, tmp_path):
        """Test listing compiled schemas."""
        from pyedi_core.core import schema_compiler
        
        compiled_dir = tmp_path / "compiled"
        compiled_dir.mkdir()
        
        # Create a meta file
        meta_file = compiled_dir / "test.meta.json"
        meta_file.write_text(json.dumps({
            "source_file": "test.txt",
            "source_hash": "abc123"
        }))
        
        schemas = schema_compiler.list_compiled_schemas(str(compiled_dir))
        
        assert len(schemas) == 1
        assert schemas[0]['source_hash'] == 'abc123'
    
    def test_get_schema_hash(self, tmp_path):
        """Test getting schema hash."""
        from pyedi_core.core import schema_compiler
        
        schema_file = tmp_path / "test.yaml"
        schema_file.write_text("key: value")
        
        # Create meta file
        meta_file = tmp_path / "test.meta.json"
        meta_file.write_text(json.dumps({
            "source_hash": "abc123"
        }))
        
        hash_val = schema_compiler.get_schema_hash(str(schema_file))
        
        assert hash_val == 'abc123'


class TestMapperExtended:
    """Extended tests for mapper module."""
    
    def test_load_map(self, tmp_path):
        """Test loading map file."""
        from pyedi_core.core import mapper
        
        map_file = tmp_path / "test_map.yaml"
        map_file.write_text("""
transaction_type: '810_INVOICE'
input_format: 'CSV'
mapping:
  header:
    invoice_id:
      source: 'Invoice Number'
""")
        
        result = mapper.load_map(str(map_file))
        
        assert result['transaction_type'] == '810_INVOICE'
        assert 'mapping' in result
    
    def test_load_map_not_found(self):
        """Test loading non-existent map file."""
        from pyedi_core.core import mapper
        
        with pytest.raises(FileNotFoundError):
            mapper.load_map("/nonexistent/map.yaml")
    
    def test_validate_mapping_config(self):
        """Test mapping config validation."""
        from pyedi_core.core import mapper
        
        # Valid config
        valid_map = {
            "transaction_type": "810",
            "input_format": "CSV",
            "mapping": {
                "header": {}
            }
        }
        errors = mapper.validate_mapping_config(valid_map)
        assert len(errors) == 0
        
        # Invalid - missing required keys
        invalid_map = {"mapping": {}}
        errors = mapper.validate_mapping_config(invalid_map)
        assert len(errors) > 0
    
    def test_apply_transform_with_params(self):
        """Test transform with parameters."""
        from pyedi_core.core import mapper
        
        # Test to_date with format param
        result = mapper.transform_to_date("2025-01-15", format="%Y-%m-%d")
        assert result == "2025-01-15"
        
        # Test substring
        result = mapper.transform_substring("Hello World", start=0, end=5)
        assert result == "Hello"
        
        # Test default
        result = mapper.transform_default("", default_value="N/A")
        assert result == "N/A"
        
        result = mapper.transform_default("value", default_value="N/A")
        assert result == "value"
    
    def test_map_field(self):
        """Test _map_field function."""
        from pyedi_core.core import mapper
        
        # Test with default
        rule = {"default": "fallback"}
        result = mapper._map_field(None, rule)
        assert result == "fallback"
        
        # Test with transform
        rule = {"transform": "upper"}
        result = mapper._map_field("hello", rule)
        assert result == "HELLO"
    
    def test_apply_transform_dict_config(self):
        """Test apply_transform with dict config."""
        from pyedi_core.core import mapper
        
        # Test with dict config (name + params)
        config = {"name": "to_date", "format": "%Y-%m-%d"}
        result = mapper._apply_transform("2025-01-15", config)
        assert result == "2025-01-15"


class TestDriversExtended:
    """Extended tests for driver modules."""
    
    def test_transaction_processor_base(self):
        """Test base TransactionProcessor."""
        from pyedi_core.drivers.base import TransactionProcessor
        
        # Can't instantiate abstract class directly
        with pytest.raises(TypeError):
            TransactionProcessor()
    
    def test_driver_registry_register(self):
        """Test driver registry registration."""
        from pyedi_core.drivers.base import DriverRegistry, TransactionProcessor
        
        class TestDriver(TransactionProcessor):
            def read(self, file_path):
                pass
            def transform(self, raw_data, map_yaml):
                pass
            def write(self, payload, output_path):
                pass
        
        # Register
        DriverRegistry.register("test", TestDriver)
        
        # Retrieve
        driver_class = DriverRegistry.get_driver("test")
        assert driver_class == TestDriver
    
    def test_get_driver(self):
        """Test get_driver factory function."""
        from pyedi_core.drivers.base import get_driver
        
        driver = get_driver("csv")
        assert driver is not None
        
        driver = get_driver("x12")
        assert driver is not None
        
        driver = get_driver("xml")
        assert driver is not None
        
        driver = get_driver("nonexistent")
        assert driver is None
    
    def test_detect_format(self):
        """Test detect_format method."""
        from pyedi_core.drivers import CSVHandler, XMLHandler
        
        csv_handler = CSVHandler()
        xml_handler = XMLHandler()
        
        assert csv_handler.detect_format("test.csv") == "csv"
        assert csv_handler.detect_format("test.edi") == "x12"
        assert csv_handler.detect_format("test.x12") == "x12"
        assert xml_handler.detect_format("test.xml") == "xml"
        # Note: .cxml detection requires reading file content
        assert csv_handler.detect_format("test.txt") == "unknown"


class TestPipelineExtended:
    """Extended tests for Pipeline class."""
    
    def test_create_pipeline_function(self):
        """Test create_pipeline factory function."""
        from pyedi_core.pipeline import create_pipeline
        
        pipeline = create_pipeline("/nonexistent/config.yaml")
        assert pipeline is not None
        assert pipeline._source_system_id == "unknown"
    
    def test_pipeline_with_real_config(self, tmp_path):
        """Test pipeline with config file."""
        from pyedi_core.pipeline import Pipeline
        
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
system:
  source_system_id: test_system
  max_workers: 4
observability:
  log_level: DEBUG
directories:
  inbound:
    - ./inbound
  outbound: ./outbound
  failed: ./failed
  manifest: .processed
transaction_registry: {}
""")
        
        pipeline = Pipeline(str(config_file))
        
        assert pipeline._source_system_id == "test_system"
        assert pipeline._max_workers == 4
    
    def test_pipeline_scan_inbound(self, tmp_path):
        """Test inbound directory scanning."""
        from pyedi_core.pipeline import Pipeline
        
        # Create inbound directories
        inbound1 = tmp_path / "inbound1"
        inbound1.mkdir()
        inbound2 = tmp_path / "inbound2"
        inbound2.mkdir()
        
        # Create test files
        (inbound1 / "file1.csv").write_text("test")
        (inbound2 / "file2.csv").write_text("test")
        
        config_file = tmp_path / "config.yaml"
        config_file.write_text(f"""
system:
  source_system_id: test
directories:
  inbound:
    - {inbound1}
    - {inbound2}
  outbound: ./outbound
  failed: ./failed
  manifest: .processed
transaction_registry: {{}}
""")
        
        pipeline = Pipeline(str(config_file))
        files = pipeline._scan_inbound()
        
        assert len(files) == 2
    
    def test_pipeline_get_output_path(self):
        """Test output path generation."""
        from pyedi_core.pipeline import Pipeline
        
        pipeline = Pipeline("/nonexistent/config.yaml")
        pipeline._outbound_dir = "./outbound"
        
        output_path = pipeline._get_output_path("test_file.csv")
        
        assert "test_file.json" in output_path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
