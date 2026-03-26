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


@pytest.mark.unit
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


@pytest.mark.unit
class TestManifest:
    """Tests for the manifest module."""

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
    
    def test_read_manifest_missing_file_no_error(self, tmp_path):
        """C3 regression: reading a non-existent manifest returns (False, None) without raising."""
        from pyedi_core.core import manifest

        missing_path = str(tmp_path / "does_not_exist.processed")
        is_dup, status = manifest.is_duplicate("/some/file.csv", manifest_path=missing_path, skip_hash=True)
        assert is_dup is False
        assert status is None

    def test_read_manifest_race_condition(self, tmp_path):
        """C3 regression: FileNotFoundError during open (simulated TOCTOU) is handled gracefully."""
        from pyedi_core.core import manifest
        from pyedi_core.core.manifest import _read_manifest

        # Create a manifest so the path looks real, then mock open to raise
        manifest_file = tmp_path / "race.processed"
        manifest_file.write_text("abc123|test.csv|2025-01-01T00:00:00|SUCCESS\n")

        with patch("builtins.open", side_effect=FileNotFoundError("deleted between check and open")):
            result = _read_manifest(str(manifest_file))

        assert result == []

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


@pytest.mark.unit
class TestErrorHandler:
    """Tests for the error_handler module."""

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
    
    def test_handle_failure_missing_source_no_sidecar(self, tmp_path, temp_failed_dir):
        """C4 regression: missing source file produces no sidecar and no manifest entry."""
        from pyedi_core.core import error_handler

        manifest_path = str(tmp_path / "test.processed")
        nonexistent = str(tmp_path / "ghost.csv")

        error_handler.handle_failure(
            file_path=nonexistent,
            stage=error_handler.Stage.DETECTION,
            reason="File vanished",
            failed_dir=temp_failed_dir,
            manifest_path=manifest_path,
            skip_manifest=False
        )

        # No .error.json sidecar should exist
        error_files = list(Path(temp_failed_dir).glob("*.error.json"))
        assert error_files == []

        # Manifest should not exist (was never written)
        assert not Path(manifest_path).exists()

    def test_handle_failure_existing_file_creates_sidecar(self, tmp_path, temp_failed_dir):
        """C4 regression: existing source file is moved, sidecar created, manifest updated."""
        from pyedi_core.core import error_handler

        manifest_path = str(tmp_path / "test.processed")

        # Create a real source file
        test_file = tmp_path / "real.csv"
        test_file.write_text("col1,col2\nval1,val2\n")

        error_file = error_handler.handle_failure(
            file_path=str(test_file),
            stage=error_handler.Stage.TRANSFORMATION,
            reason="Bad data",
            failed_dir=temp_failed_dir,
            manifest_path=manifest_path,
            skip_manifest=False
        )

        # Source file should be moved
        assert not test_file.exists()
        assert (Path(temp_failed_dir) / "real.csv").exists()

        # Sidecar should exist
        assert Path(error_file).exists()
        assert error_file.endswith(".error.json")

    def test_validate_stage(self):
        """Test stage validation."""
        from pyedi_core.core import error_handler
        
        assert error_handler.validate_stage("DETECTION") is True
        assert error_handler.validate_stage("VALIDATION") is True
        assert error_handler.validate_stage("TRANSFORMATION") is True
        assert error_handler.validate_stage("WRITE") is True
        assert error_handler.validate_stage("INVALID") is False

    def test_exception_hierarchy(self):
        """W3 regression: all typed exceptions are subclasses of PyEDIError."""
        from pyedi_core.core import error_handler

        for cls in (error_handler.DetectionError, error_handler.SchemaLookupError,
                    error_handler.MappingError, error_handler.TransformationError):
            assert issubclass(cls, error_handler.PyEDIError), f"{cls.__name__} must subclass PyEDIError"

    def test_exception_stage_attributes(self):
        """W3 regression: each exception class carries the correct stage."""
        from pyedi_core.core import error_handler

        assert error_handler.DetectionError.stage == error_handler.Stage.DETECTION
        assert error_handler.SchemaLookupError.stage == error_handler.Stage.DETECTION
        assert error_handler.MappingError.stage == error_handler.Stage.TRANSFORMATION
        assert error_handler.TransformationError.stage == error_handler.Stage.TRANSFORMATION


@pytest.mark.unit
class TestSchemaCompiler:
    """Tests for the schema_compiler module."""
    
    def test_parse_dsl_record(self):
        """Test DSL record parsing."""
        from pyedi_core.core import schema_compiler
        
        dsl_text = """
        def record Header {
            invoice_number String
            invoice_date Date
            amount Decimal
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

    def test_compile_dsl_round_trip(self, tmp_path):
        """Round-trip: compile real DSL source, verify output structure and files."""
        from pyedi_core.core import schema_compiler

        source = "schemas/source/gfsGenericOut810FF.txt"
        compiled_dir = str(tmp_path / "compiled")

        result = schema_compiler.compile_dsl(
            source_file=source,
            compiled_dir=compiled_dir
        )

        assert "transaction_type" in result
        assert "schema" in result
        assert "mapping" in result

        # Check deduplication worked
        col_names = [c["name"] for c in result["schema"]["columns"]]
        assert len(col_names) == len(set(col_names)), "Columns should be unique"
        assert len(col_names) == 42

        # Mapping should have content
        assert result["mapping"]["header"] or result["mapping"]["lines"]

        # Verify files were written
        compiled_files = list((tmp_path / "compiled").glob("*.yaml"))
        meta_files = list((tmp_path / "compiled").glob("*.meta.json"))
        assert len(compiled_files) == 1
        assert len(meta_files) == 1

    def test_compile_dsl_idempotent(self, tmp_path):
        """Compile same DSL twice; second call should return cached result."""
        from pyedi_core.core import schema_compiler

        source = "schemas/source/gfsGenericOut810FF.txt"
        compiled_dir = str(tmp_path / "compiled")

        result1 = schema_compiler.compile_dsl(source, compiled_dir=compiled_dir)

        # Get the meta.json timestamp
        meta_files = list((tmp_path / "compiled").glob("*.meta.json"))
        with open(meta_files[0]) as f:
            meta1 = json.load(f)

        result2 = schema_compiler.compile_dsl(source, compiled_dir=compiled_dir)

        # Results should be identical
        assert result1["transaction_type"] == result2["transaction_type"]
        assert len(result1["schema"]["columns"]) == len(result2["schema"]["columns"])

        # Meta should not have changed (hash matched, no recompile)
        with open(meta_files[0]) as f:
            meta2 = json.load(f)
        assert meta1["compiled_at"] == meta2["compiled_at"]

    def test_compile_dsl_missing_source_raises(self):
        """Compiling a nonexistent source file raises FileNotFoundError."""
        from pyedi_core.core import schema_compiler

        with pytest.raises(FileNotFoundError):
            schema_compiler.compile_dsl("schemas/source/does_not_exist.txt")

    def test_compile_dsl_invalid_content_raises(self, tmp_path):
        """DSL file with no valid record definitions raises ValueError."""
        from pyedi_core.core import schema_compiler

        bad_source = tmp_path / "bad.txt"
        bad_source.write_text("this is not a valid DSL file")

        with pytest.raises(ValueError, match="No valid record definitions"):
            schema_compiler.compile_dsl(str(bad_source), compiled_dir=str(tmp_path / "out"))


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
class TestFixedWidth:
    """Tests for fixed-width DSL compilation and parsing."""

    def test_compile_fixed_width_schema(self):
        """Compile .ffSchema and verify width metadata, record_layouts, no delimiter."""
        from pyedi_core.core.schema_compiler import compile_dsl
        import os

        # Remove cached compiled files to force fresh compilation
        for f in [
            "schemas/compiled/RetalixPIPOAckFF.yaml",
            "schemas/compiled/RetalixPIPOAckFF.meta.json",
        ]:
            if os.path.exists(f):
                os.remove(f)

        result = compile_dsl("artifacts/RetalixPIPOAckFF.ffSchema")

        assert result["input_format"] == "FIXED_WIDTH"
        assert "delimiter" not in result["schema"]
        assert "record_layouts" in result["schema"]
        assert len(result["schema"]["record_layouts"]) > 0

        # All columns should have width
        for col in result["schema"]["columns"]:
            assert "width" in col, f"Column {col['name']} missing width"

        # Record keys should be stripped (no trailing whitespace)
        for key in result["schema"]["records"]:
            assert key == key.strip(), f"Record key '{key}' has padding"

    def test_compile_delimited_backward_compat(self):
        """Compile delimited DSL and verify no width/record_layouts appear."""
        from pyedi_core.core.schema_compiler import parse_dsl_file, _compile_to_yaml

        record_defs, delimiter, format_type = parse_dsl_file(
            "schemas/source/gfsGenericOut810FF.txt"
        )
        result = _compile_to_yaml(record_defs, "gfsGenericOut810FF.txt", delimiter, format_type)

        assert result["input_format"] == "CSV"
        assert "delimiter" in result["schema"]
        assert "record_layouts" not in result["schema"]
        for col in result["schema"]["columns"]:
            assert "width" not in col, f"Column {col['name']} should not have width"

    def test_field_attribute_parsing(self):
        """Verify _parse_dsl_record extracts length and readEmptyAsNull."""
        from pyedi_core.core.schema_compiler import _parse_dsl_record

        record_text = '''def record TestRec {
            fieldIdentifier {
                value = "TEST"
                field = recordType
            }

            recordType String (
                length = 10
                readEmptyAsNull = true
            )
            amount Decimal (
                length = 8
            )
            label String
        }'''

        result = _parse_dsl_record(record_text)
        assert result["name"] == "TestRec"
        assert result["fieldIdentifier"] == "TEST"

        rt = result["fields"][0]
        assert rt["name"] == "recordType"
        assert rt["length"] == 10
        assert rt["read_empty_as_null"] is True

        amt = result["fields"][1]
        assert amt["name"] == "amount"
        assert amt["length"] == 8
        assert "read_empty_as_null" not in amt

        lbl = result["fields"][2]
        assert lbl["name"] == "label"
        assert "length" not in lbl

    def test_read_fixed_width_file(self):
        """CSVHandler._read_fixed_width slices fields by byte position."""
        import yaml
        from pyedi_core.drivers.csv_handler import CSVHandler

        # recordType(10) + value1(5) + value2(3) = 18 chars
        data_lines = [
            "HDR       Hello 42",
            "DTL       World 99",
        ]
        data_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        data_file.write("\n".join(data_lines))
        data_file.close()

        schema = {
            "transaction_type": "TEST",
            "input_format": "FIXED_WIDTH",
            "schema": {
                "columns": [
                    {"name": "recordType", "type": "string", "required": True, "width": 10},
                    {"name": "value1", "type": "string", "required": True, "width": 5},
                    {"name": "value2", "type": "integer", "required": True, "width": 3},
                ],
                "records": {
                    "HDR": ["recordType", "value1", "value2"],
                    "DTL": ["recordType", "value1", "value2"],
                },
                "record_layouts": {
                    "HDR": [
                        {"name": "recordType", "width": 10},
                        {"name": "value1", "width": 5},
                        {"name": "value2", "width": 3},
                    ],
                    "DTL": [
                        {"name": "recordType", "width": 10},
                        {"name": "value1", "width": 5},
                        {"name": "value2", "width": 3},
                    ],
                },
            },
            "mapping": {"header": {}, "lines": [], "summary": {}},
        }
        schema_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        yaml.dump(schema, schema_file, default_flow_style=False)
        schema_file.close()

        try:
            handler = CSVHandler()
            handler.set_compiled_yaml_path(schema_file.name)
            result = handler.read(data_file.name)

            assert len(result["lines"]) == 2
            assert result["lines"][0]["recordType"] == "HDR"
            assert result["lines"][0]["value1"] == "Hello"
            assert result["lines"][0]["value2"] == "42"
            assert result["lines"][1]["value1"] == "World"
        finally:
            os.unlink(data_file.name)
            os.unlink(schema_file.name)

    def test_read_empty_as_null(self):
        """Empty fields with read_empty_as_null should become None."""
        import yaml
        from pyedi_core.drivers.csv_handler import CSVHandler

        # recordType(5) + val(5) = 10 chars; val is all spaces
        data_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        data_file.write("REC       ")  # 5 + 5 spaces
        data_file.close()

        schema = {
            "transaction_type": "TEST",
            "input_format": "FIXED_WIDTH",
            "schema": {
                "columns": [
                    {"name": "recordType", "type": "string", "required": True, "width": 5},
                    {"name": "val", "type": "string", "required": True, "width": 5, "read_empty_as_null": True},
                ],
                "records": {"REC": ["recordType", "val"]},
                "record_layouts": {
                    "REC": [
                        {"name": "recordType", "width": 5},
                        {"name": "val", "width": 5},
                    ],
                },
            },
            "mapping": {"header": {}, "lines": [], "summary": {}},
        }
        schema_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        yaml.dump(schema, schema_file, default_flow_style=False)
        schema_file.close()

        try:
            handler = CSVHandler()
            handler.set_compiled_yaml_path(schema_file.name)
            result = handler.read(data_file.name)

            assert len(result["lines"]) == 1
            assert result["lines"][0]["recordType"] == "REC"
            assert result["lines"][0]["val"] is None
        finally:
            os.unlink(data_file.name)
            os.unlink(schema_file.name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
