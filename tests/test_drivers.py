"""
Integration tests for driver modules - improving driver coverage.
"""

import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.mark.integration
class TestCSVHandlerIntegration:
    """Integration tests for CSV driver."""
    
    def test_csv_read_basic(self, tmp_path):
        """Test basic CSV reading."""
        from pyedi_core.drivers import CSVHandler
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name,value\ntest,123\n")
        
        handler = CSVHandler()
        result = handler.read(str(csv_file))
        
        assert result is not None
        assert "header" in result
        assert result["header"] == {}
        assert result["lines"][0]["name"] == "test"
    
    def test_csv_transform(self):
        """Test CSV transform method."""
        from pyedi_core.drivers import CSVHandler
        
        handler = CSVHandler()
        
        raw_data = {"col1": "value1", "col2": "value2"}
        
        map_config = {
            "mapping": {
                "header": {
                    "field1": {"source": "col1"},
                    "field2": {"source": "col2", "transform": "upper"}
                }
            }
        }
        
        result = handler.transform(raw_data, map_config)
        
        assert result["header"]["field1"] == "value1"
        assert result["header"]["field2"] == "VALUE2"
    
    def test_csv_write(self, tmp_path):
        """Test CSV write method."""
        from pyedi_core.drivers import CSVHandler
        
        handler = CSVHandler()
        
        output_file = tmp_path / "output.csv"
        
        payload = {
            "header": {"name": "test", "value": "123"},
            "lines": [{"item": "A"}]
        }
        
        handler.write(payload, str(output_file))
        
        assert output_file.exists()
        content = output_file.read_text()
        assert "name" in content
    
    def test_csv_supported_formats(self):
        """Test CSV supported formats."""
        from pyedi_core.drivers import CSVHandler
        
        handler = CSVHandler()
        
        assert handler.detect_format("test.csv") == "csv"
        assert handler.detect_format("test.txt") == "unknown"


@pytest.mark.integration
class TestX12HandlerIntegration:
    """Integration tests for X12 driver."""
    
    def test_x12_handler_init(self):
        """Test X12 handler initialization."""
        from pyedi_core.drivers import X12Handler
        
        handler = X12Handler(correlation_id="test-123")
        
        assert handler.correlation_id == "test-123"
    
    def test_x12_detect_format(self):
        """Test X12 format detection."""
        from pyedi_core.drivers import X12Handler
        
        handler = X12Handler()
        
        # By extension
        assert handler.detect_format("test.x12") == "x12"
        assert handler.detect_format("test.edi") == "x12"
    
    def test_x12_transform(self):
        """Test X12 transform."""
        from pyedi_core.drivers import X12Handler
        
        handler = X12Handler()
        
        raw_data = {"BEG": {"order_num": "123"}}
        
        map_config = {
            "mapping": {
                "header": {
                    "po_number": {"source": "BEG.order_num"}
                }
            }
        }
        
        result = handler.transform(raw_data, map_config)
        
        assert result is not None
    
    def test_x12_empty_fields_no_crash(self, tmp_path):
        """C9 regression: body segment with empty fields list doesn't raise IndexError."""
        from pyedi_core.drivers import X12Handler

        handler = X12Handler(correlation_id="test-empty-fields")

        # Minimal X12 file (content doesn't matter — we mock the parser)
        x12_file = tmp_path / "test.x12"
        x12_file.write_text("ISA*00*" + " " * 94 + "~")

        # Build a fake parsed document with one empty-fields body segment
        fake_doc_dict = {
            "document": {
                "config": {},
                "interchange": {
                    "header": {"fields": [{"content": "00"}]},
                    "groups": [{
                        "header": {"fields": [{"content": "IN"}]},
                        "transaction_sets": [{
                            "header": {"fields": [{"content": "810"}, {"content": "0001"}]},
                            "body": [
                                {"fields": []},  # <-- the empty-fields case
                                {"fields": [{"content": "BIG"}, {"content": "20250101"}]},
                            ],
                            "trailer": {"fields": [{"content": "2"}, {"content": "0001"}]}
                        }],
                        "trailer": {"fields": [{"content": "1"}, {"content": "1234"}]}
                    }],
                    "trailer": {"fields": [{"content": "1"}, {"content": "000000001"}]}
                }
            }
        }

        mock_document = MagicMock()
        mock_document.to_dict.return_value = fake_doc_dict

        with patch("pyedi_core.drivers.x12_handler.Parser") as MockParser:
            MockParser.return_value.parse_document.return_value = mock_document
            result = handler.read(str(x12_file))

        # The empty-fields segment should be skipped; BIG segment should be present
        seg_names = [s["segment"] for s in result["document"]["segments"]]
        assert "BIG" in seg_names
        # No segment with name from the empty-fields entry
        assert "UNKNOWN" not in seg_names

    def test_x12_write(self, tmp_path):
        """Test X12 write."""
        from pyedi_core.drivers import X12Handler
        
        handler = X12Handler()
        
        output_file = tmp_path / "output.x12"
        
        payload = {"header": {"isa": "test"}}
        
        handler.write(payload, str(output_file))
        
        assert output_file.exists()


@pytest.mark.integration
class TestXMLHandlerIntegration:
    """Integration tests for XML driver."""
    
    def test_xml_handler_init(self):
        """Test XML handler initialization."""
        from pyedi_core.drivers import XMLHandler
        
        handler = XMLHandler(correlation_id="test-xml")
        
        assert handler.correlation_id == "test-xml"
    
    def test_xml_detect_format(self):
        """Test XML format detection."""
        from pyedi_core.drivers import XMLHandler
        
        handler = XMLHandler()
        
        # By extension
        assert handler.detect_format("test.xml") == "xml"
        
        # .cxml returns xml (need content to detect cxml)
        assert handler.detect_format("test.cxml") == "xml"
    
    def test_xml_read_simple(self, tmp_path):
        """Test XML reading."""
        from pyedi_core.drivers import XMLHandler
        
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<?xml version="1.0"?>
<root>
    <item>value1</item>
</root>
""")
        
        handler = XMLHandler()
        result = handler.read(str(xml_file))
        
        assert result is not None
        # Should have header with item
        assert "header" in result
    
    def test_xml_transform(self):
        """Test XML transform."""
        from pyedi_core.drivers import XMLHandler
        
        handler = XMLHandler()
        
        raw_data = {"Invoice": {"id": "INV-001", "amount": "100"}}
        
        map_config = {
            "mapping": {
                "header": {
                    "invoice_id": {"source": "Invoice.id"},
                    "amount": {"source": "Invoice.amount", "transform": "to_float"}
                }
            }
        }
        
        result = handler.transform(raw_data, map_config)
        
        assert result is not None
        assert "header" in result
    
    def test_xml_write_json(self, tmp_path):
        """Test XML write outputs JSON (current behavior)."""
        from pyedi_core.drivers import XMLHandler
        
        handler = XMLHandler()
        
        output_file = tmp_path / "output.xml"
        
        payload = {"root": {"item": "value"}}
        
        handler.write(payload, str(output_file))
        
        assert output_file.exists()
        # Currently writes JSON format
        content = output_file.read_text()
        assert "root" in content

    def test_xml_xxe_rejected(self, tmp_path):
        """Regression: XXE entity declarations must be rejected by defusedxml."""
        import defusedxml.common
        from pyedi_core.drivers import XMLHandler

        xxe_xml = tmp_path / "xxe.xml"
        xxe_xml.write_text(
            '<?xml version="1.0"?>\n'
            '<!DOCTYPE foo [\n'
            '  <!ENTITY xxe SYSTEM "file:///etc/passwd">\n'
            ']>\n'
            '<root>&xxe;</root>\n'
        )

        handler = XMLHandler()
        with pytest.raises((defusedxml.common.DefusedXmlException, ValueError)):
            handler.read(str(xxe_xml))

    def test_xml_bomb_rejected(self, tmp_path):
        """Regression: billion-laughs XML bomb must be rejected by defusedxml."""
        import defusedxml.common
        from pyedi_core.drivers import XMLHandler

        bomb_xml = tmp_path / "bomb.xml"
        bomb_xml.write_text(
            '<?xml version="1.0"?>\n'
            '<!DOCTYPE lolz [\n'
            '  <!ENTITY lol "lol">\n'
            '  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">\n'
            '  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">\n'
            '  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">\n'
            ']>\n'
            '<root>&lol4;</root>\n'
        )

        handler = XMLHandler()
        with pytest.raises((defusedxml.common.DefusedXmlException, ValueError)):
            handler.read(str(bomb_xml))


@pytest.mark.integration
class TestDriverRegistryIntegration:
    """Integration tests for driver registry."""
    
    def test_list_all_drivers(self):
        """Test listing all drivers."""
        from pyedi_core.drivers.base import DriverRegistry
        
        drivers = DriverRegistry.list_drivers()
        
        assert "csv" in drivers
        assert "x12" in drivers
        assert "xml" in drivers
    
    def test_driver_caching(self):
        """Test driver instance caching."""
        from pyedi_core.drivers import CSVHandler
        
        handler1 = CSVHandler()
        handler2 = CSVHandler()
        
        # Should be different instances by default
        assert handler1 is not handler2
    
    def test_get_driver_unknown(self):
        """Test getting unknown driver."""
        from pyedi_core.drivers.base import get_driver
        
        result = get_driver("totally_fake_format")
        
        assert result is None


@pytest.mark.integration
class TestPipelineIntegration:
    """Integration tests for full pipeline."""
    
    def test_pipeline_result_creation(self):
        """Test creating pipeline result."""
        from pyedi_core.pipeline import PipelineResult
        
        result = PipelineResult(
            status="SUCCESS",
            correlation_id="test-123",
            source_file="test.csv",
            transaction_type="810",
            output_path="/output/test.json",
            payload={"header": {"id": "123"}},
            errors=[],
            processing_time_ms=100
        )
        
        assert result.status == "SUCCESS"
        assert result.correlation_id == "test-123"
        assert result.processing_time_ms == 100
    
    def test_pipeline_error_handling(self):
        """Test pipeline error handling."""
        from pyedi_core.pipeline import Pipeline
        
        # Create pipeline with invalid config
        pipeline = Pipeline("/nonexistent/config.yaml")
        
        # Should use defaults
        assert pipeline._source_system_id == "unknown"
    
    def test_pipeline_get_output_path(self):
        """Test output path generation."""
        from pyedi_core.pipeline import Pipeline
        
        pipeline = Pipeline("/nonexistent/config.yaml")
        pipeline._outbound_dir = "./outbound"
        
        output_path = pipeline._get_output_path("test_file.csv")
        
        assert "test_file.json" in output_path


@pytest.mark.integration
class TestCsvSchemaRegistry:
    """Tests for CSV Schema Registry functionality."""
    
    def test_csv_schema_entry_validation(self):
        """Test CsvSchemaEntry Pydantic model validates correctly."""
        from pyedi_core.config import CsvSchemaEntry
        
        entry = CsvSchemaEntry(
            source_dsl="./schemas/source/test.txt",
            compiled_output="./schemas/compiled/test.yaml",
            inbound_dir="./inbound/csv/test",
            transaction_type="810"
        )
        
        assert entry.source_dsl == "./schemas/source/test.txt"
        assert entry.compiled_output == "./schemas/compiled/test.yaml"
        assert entry.inbound_dir == "./inbound/csv/test"
        assert entry.transaction_type == "810"
    
    def test_csv_schema_entry_missing_field(self):
        """Test CsvSchemaEntry raises error for missing required field."""
        from pyedi_core.config import CsvSchemaEntry
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            CsvSchemaEntry(
                source_dsl="./schemas/source/test.txt",
                # missing compiled_output
                inbound_dir="./inbound/csv/test",
                transaction_type="810"
            )
        
        # Check error message is human-readable
        error = exc_info.value
        assert "compiled_output" in str(error)
    
    def test_app_config_csv_schema_registry(self):
        """Test AppConfig includes csv_schema_registry field."""
        from pyedi_core.config import AppConfig
        
        # Create a config with csv_schema_registry
        config_data = {
            "system": {"max_workers": 4},
            "transaction_registry": {"810": "./rules/test.yaml"},
            "csv_schema_registry": {
                "test_entry": {
                    "source_dsl": "./schemas/source/test.txt",
                    "compiled_output": "./schemas/compiled/test.yaml",
                    "inbound_dir": "./inbound/csv/test",
                    "transaction_type": "810"
                }
            },
            "directories": {
                "inbound": "./inbound",
                "outbound": "./outbound",
                "failed": "./failed",
                "processed": ".processed"
            }
        }
        
        config = AppConfig(**config_data)
        
        assert "test_entry" in config.csv_schema_registry
        assert config.csv_schema_registry["test_entry"].transaction_type == "810"
    
    def test_app_config_missing_csv_registry_field(self):
        """Test AppConfig handles missing csv_schema_registry gracefully."""
        from pyedi_core.config import AppConfig
        
        # Config without csv_schema_registry
        config_data = {
            "system": {"max_workers": 4},
            "transaction_registry": {},
            "directories": {
                "inbound": "./inbound",
                "outbound": "./outbound",
                "failed": "./failed",
                "processed": ".processed"
            }
        }
        
        config = AppConfig(**config_data)
        
        # Should default to empty dict
        assert config.csv_schema_registry == {}


@pytest.mark.integration
class TestPipelineCsvSchemaResolution:
    """Tests for Pipeline CSV schema resolution."""
    
    def test_resolve_csv_schema_known_directory(self, tmp_path):
        """Test _resolve_csv_schema returns correct entry for known inbound_dir."""
        from pyedi_core.config import AppConfig, CsvSchemaEntry
        
        # Create test directories
        inbound_dir = tmp_path / "inbound" / "gfs_ca"
        inbound_dir.mkdir(parents=True)
        
        # Create config with csv_schema_registry
        config_data = {
            "system": {"max_workers": 4},
            "transaction_registry": {},
            "csv_schema_registry": {
                "gfs_ca_810": {
                    "source_dsl": "./schemas/source/gfsGenericOut810FF.txt",
                    "compiled_output": "./schemas/compiled/gfs_ca_810_map.yaml",
                    "inbound_dir": str(inbound_dir),
                    "transaction_type": "810"
                }
            },
            "directories": {
                "inbound": "./inbound",
                "outbound": "./outbound",
                "failed": "./failed",
                "processed": ".processed"
            }
        }
        
        config = AppConfig(**config_data)
        
        # Create pipeline with test config
        from pyedi_core.pipeline import Pipeline
        
        class TestPipeline(Pipeline):
            def __init__(self, config):
                self._config = config
                self._csv_schema_registry = config.csv_schema_registry
        
        pipeline = TestPipeline(config)
        
        # Create a test CSV file in the registered directory
        test_file = inbound_dir / "test.csv"
        test_file.write_text("col1,col2\nval1,val2\n")
        
        # Resolve the schema
        result = pipeline._resolve_csv_schema(test_file)
        
        assert result is not None
        assert result.transaction_type == "810"
        assert result.source_dsl == "./schemas/source/gfsGenericOut810FF.txt"
    
    def test_resolve_csv_schema_unknown_directory(self, tmp_path):
        """Test _resolve_csv_schema raises error for unknown directory."""
        from pyedi_core.config import AppConfig
        from pyedi_core.pipeline import Pipeline
        
        # Create config with empty csv_schema_registry
        config_data = {
            "system": {"max_workers": 4},
            "transaction_registry": {},
            "csv_schema_registry": {},
            "directories": {
                "inbound": "./inbound",
                "outbound": "./outbound",
                "failed": "./failed",
                "processed": ".processed"
            }
        }
        
        config = AppConfig(**config_data)
        
        class TestPipeline(Pipeline):
            def __init__(self, config):
                self._config = config
                self._csv_schema_registry = config.csv_schema_registry
        
        pipeline = TestPipeline(config)
        
        # Create a test CSV file in an unregistered directory
        unknown_dir = tmp_path / "unknown_dir"
        unknown_dir.mkdir(parents=True)
        test_file = unknown_dir / "test.csv"
        test_file.write_text("col1,col2\nval1,val2\n")
        
        # Should raise ValueError
        from pyedi_core.core import error_handler
        with pytest.raises(error_handler.SchemaLookupError) as exc_info:
            pipeline._resolve_csv_schema(test_file)

        assert "csv_schema_registry" in str(exc_info.value)
        assert "No csv_schema_registry entry found" in str(exc_info.value)


@pytest.mark.integration
class TestCsvHandlerCompiledYamlPath:
    """Tests for CSV Handler compiled_yaml_path functionality."""
    
    def test_csv_handler_accepts_compiled_yaml_path(self):
        """Test CSVHandler accepts compiled_yaml_path in constructor."""
        from pyedi_core.drivers import CSVHandler
        
        handler = CSVHandler(
            compiled_yaml_path="./schemas/compiled/gfs_ca_810_map.yaml"
        )

        assert handler._compiled_yaml_path == "./schemas/compiled/gfs_ca_810_map.yaml"
    
    def test_csv_handler_set_compiled_yaml_path(self):
        """Test CSVHandler set_compiled_yaml_path method."""
        from pyedi_core.drivers import CSVHandler
        
        handler = CSVHandler()
        handler.set_compiled_yaml_path("./schemas/compiled/another_map.yaml")
        
        assert handler._compiled_yaml_path == "./schemas/compiled/another_map.yaml"
    
    def test_csv_handler_missing_compiled_yaml_path_triggers_error(self, tmp_path):
        """Test CSVHandler triggers error_handler when compiled_yaml_path doesn't exist."""
        from pyedi_core.drivers import CSVHandler
        from pyedi_core.core import error_handler
        from unittest.mock import patch, MagicMock
        
        # Create a CSV file
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("col1,col2\nval1,val2\n")
        
        # Set up handler with non-existent compiled_yaml_path
        handler = CSVHandler(compiled_yaml_path="/nonexistent/path/map.yaml")
        
        # Mock error_handler.handle_failure to prevent file operations
        with patch.object(error_handler, 'handle_failure') as mock_handle_failure:
            # Attempt to read - should trigger validation error
            try:
                handler.read(str(csv_file))
            except ValueError:
                pass  # Expected to raise
            
            # Verify handle_failure was called at VALIDATION stage
            mock_handle_failure.assert_called()
            call_kwargs = mock_handle_failure.call_args[1]
            assert call_kwargs['stage'] == error_handler.Stage.VALIDATION
            assert "does not exist" in call_kwargs['reason']


@pytest.mark.integration
class TestCxmlParsing:
    """Integration tests for cXML detection and parsing."""

    def test_cxml_detection(self, tmp_path):
        """cXML root element triggers _is_cxml=True."""
        from pyedi_core.drivers import XMLHandler

        cxml_file = tmp_path / "test.cxml"
        cxml_file.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<cXML payloadID="1" timestamp="2025-01-15T10:00:00">\n'
            '  <Request/>\n'
            '</cXML>\n'
        )

        handler = XMLHandler()
        result = handler.read(str(cxml_file))

        assert result["_is_cxml"] is True

    def test_cxml_order_request_parsing(self, tmp_path):
        """OrderRequestHeader attributes are extracted into header dict."""
        from pyedi_core.drivers import XMLHandler

        cxml_file = tmp_path / "order.cxml"
        cxml_file.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<cXML payloadID="123" timestamp="2025-01-15T10:00:00">\n'
            '  <Header>\n'
            '    <From><Credential domain="DUNS"><Identity>sender123</Identity></Credential></From>\n'
            '    <To><Credential domain="DUNS"><Identity>receiver456</Identity></Credential></To>\n'
            '  </Header>\n'
            '  <Request>\n'
            '    <OrderRequest>\n'
            '      <OrderRequestHeader orderID="PO-001" orderDate="2025-01-15">\n'
            '        <Total><Money currency="USD">1500.00</Money></Total>\n'
            '      </OrderRequestHeader>\n'
            '    </OrderRequest>\n'
            '  </Request>\n'
            '</cXML>\n'
        )

        handler = XMLHandler()
        result = handler.read(str(cxml_file))

        assert result["_is_cxml"] is True
        assert result["header"]["@orderID"] == "PO-001"

    def test_cxml_with_line_items(self, tmp_path):
        """OrderRequestLine elements are collected into result['lines']."""
        from pyedi_core.drivers import XMLHandler

        cxml_file = tmp_path / "lines.cxml"
        cxml_file.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<cXML payloadID="456" timestamp="2025-01-15T10:00:00">\n'
            '  <Request>\n'
            '    <OrderRequest>\n'
            '      <OrderRequestHeader orderID="PO-002" orderDate="2025-01-15"/>\n'
            '      <OrderRequestDetail>\n'
            '        <OrderRequestLine lineNumber="1">\n'
            '          <ItemID><SupplierPartID>PART-001</SupplierPartID></ItemID>\n'
            '        </OrderRequestLine>\n'
            '        <OrderRequestLine lineNumber="2">\n'
            '          <ItemID><SupplierPartID>PART-002</SupplierPartID></ItemID>\n'
            '        </OrderRequestLine>\n'
            '      </OrderRequestDetail>\n'
            '    </OrderRequest>\n'
            '  </Request>\n'
            '</cXML>\n'
        )

        handler = XMLHandler()
        result = handler.read(str(cxml_file))

        assert len(result["lines"]) == 2

    def test_generic_xml_not_cxml(self, tmp_path):
        """A plain XML file without cXML element has _is_cxml=False."""
        from pyedi_core.drivers import XMLHandler

        xml_file = tmp_path / "plain.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<Invoice id="INV-001">\n'
            '  <Amount>100.00</Amount>\n'
            '</Invoice>\n'
        )

        handler = XMLHandler()
        result = handler.read(str(xml_file))

        assert result["_is_cxml"] is False

    def test_cxml_empty_order(self, tmp_path):
        """cXML with OrderRequest but no line items produces empty lines list."""
        from pyedi_core.drivers import XMLHandler

        cxml_file = tmp_path / "empty_order.cxml"
        cxml_file.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<cXML payloadID="789" timestamp="2025-01-15T10:00:00">\n'
            '  <Request>\n'
            '    <OrderRequest>\n'
            '      <OrderRequestHeader orderID="PO-003" orderDate="2025-01-15"/>\n'
            '    </OrderRequest>\n'
            '  </Request>\n'
            '</cXML>\n'
        )

        handler = XMLHandler()
        result = handler.read(str(cxml_file))

        assert result["_is_cxml"] is True
        assert result["lines"] == []


@pytest.mark.integration
class TestPipelineFailurePaths:
    """Failure-path tests: verify the pipeline returns FAILED results for bad inputs."""

    def test_pipeline_no_driver_available(self, tmp_path):
        """Unrecognised extension produces FAILED with 'No driver' message."""
        from pyedi_core.pipeline import Pipeline

        unknown_file = tmp_path / "data.xyz"
        unknown_file.write_text("some content")

        pipeline = Pipeline(config_path="./config/config.yaml")
        result = pipeline.run(file=str(unknown_file), dry_run=True)

        assert result.status == "FAILED"
        assert any("No driver" in e or "driver" in e.lower() for e in result.errors)

    def test_pipeline_csv_no_schema_registry_match(self, tmp_path):
        """CSV in unregistered directory produces FAILED mentioning csv_schema_registry."""
        from pyedi_core.pipeline import Pipeline

        csv_file = tmp_path / "orphan.csv"
        csv_file.write_text("col1,col2\nval1,val2\n")

        pipeline = Pipeline(config_path="./config/config.yaml")
        result = pipeline.run(file=str(csv_file), dry_run=True)

        assert result.status == "FAILED"
        assert any("csv_schema_registry" in e for e in result.errors)

    def test_pipeline_nonexistent_file(self, tmp_path):
        """Non-existent file path produces FAILED."""
        from pyedi_core.pipeline import Pipeline

        pipeline = Pipeline(config_path="./config/config.yaml")
        result = pipeline.run(file=str(tmp_path / "ghost.csv"), dry_run=True)

        assert result.status == "FAILED"

    def test_pipeline_malformed_xml(self, tmp_path):
        """Malformed XML produces FAILED."""
        from pyedi_core.pipeline import Pipeline

        xml_file = tmp_path / "bad.xml"
        xml_file.write_text("<root><unclosed>")

        pipeline = Pipeline(config_path="./config/config.yaml")
        result = pipeline.run(file=str(xml_file), dry_run=True)

        assert result.status == "FAILED"

    def test_pipeline_failed_result_has_correlation_id(self, tmp_path):
        """Failed result carries a valid UUID correlation_id (36 chars)."""
        from pyedi_core.pipeline import Pipeline

        unknown_file = tmp_path / "data.xyz"
        unknown_file.write_text("some content")

        pipeline = Pipeline(config_path="./config/config.yaml")
        result = pipeline.run(file=str(unknown_file), dry_run=True)

        assert result.status == "FAILED"
        assert len(result.correlation_id) == 36
        # Validate it is a well-formed UUID
        uuid.UUID(result.correlation_id)

    def test_pipeline_failed_result_has_processing_time(self, tmp_path):
        """Failed result carries a non-negative processing_time_ms."""
        from pyedi_core.pipeline import Pipeline

        unknown_file = tmp_path / "data.xyz"
        unknown_file.write_text("some content")

        pipeline = Pipeline(config_path="./config/config.yaml")
        result = pipeline.run(file=str(unknown_file), dry_run=True)

        assert result.status == "FAILED"
        assert result.processing_time_ms >= 0


@pytest.mark.integration
class TestPipelineBatchProcessing:
    """Tests for Pipeline concurrent batch processing via _process_batch()."""

    def test_batch_multiple_files_returns_list(self, tmp_path):
        """Batch of multiple unrecognised files returns a list of FAILED results."""
        from pyedi_core.pipeline import Pipeline

        files = []
        for i in range(3):
            f = tmp_path / f"file{i}.xyz"
            f.write_text(f"content {i}")
            files.append(str(f))

        pipeline = Pipeline(config_path="./config/config.yaml")
        results = pipeline.run(files=files, dry_run=True)

        assert isinstance(results, list)
        assert len(results) == 3
        for r in results:
            assert r.status in ("FAILED", "SKIPPED")
            assert r.correlation_id  # Each gets a unique ID
            assert r.processing_time_ms >= 0

    def test_batch_mixed_results(self, tmp_path):
        """Batch with a mix of file types each gets its own result."""
        from pyedi_core.pipeline import Pipeline

        # .xyz will fail (no driver), .csv will fail (no schema registry match)
        xyz_file = tmp_path / "unknown.xyz"
        xyz_file.write_text("random data")

        csv_file = tmp_path / "orphan.csv"
        csv_file.write_text("col1,col2\nval1,val2\n")

        abc_file = tmp_path / "data.abc"
        abc_file.write_text("abc data")

        files = [str(xyz_file), str(csv_file), str(abc_file)]

        pipeline = Pipeline(config_path="./config/config.yaml")
        results = pipeline.run(files=files, dry_run=True)

        assert isinstance(results, list)
        assert len(results) == 3
        source_files = {r.source_file for r in results}
        assert "unknown.xyz" in source_files
        assert "orphan.csv" in source_files
        assert "data.abc" in source_files
        for r in results:
            assert r.status in ("FAILED", "SKIPPED")

    def test_batch_deduplication(self, tmp_path):
        """Duplicate file paths in a batch are handled gracefully."""
        from pyedi_core.pipeline import Pipeline

        f = tmp_path / "dup.xyz"
        f.write_text("content")

        pipeline = Pipeline(config_path="./config/config.yaml")
        pipeline._manifest_path = str(tmp_path / ".processed")

        # Pass the same file twice
        result = pipeline.run(files=[str(f), str(f)], dry_run=True)

        assert isinstance(result, list)
        # Should get results for both entries (processed + duplicate, or both processed)
        assert len(result) >= 1

    def test_batch_empty_file_list(self):
        """Empty file list returns a single SKIPPED PipelineResult."""
        from pyedi_core.pipeline import Pipeline, PipelineResult

        pipeline = Pipeline(config_path="./config/config.yaml")
        result = pipeline.run(files=[], dry_run=True)

        # Empty file list returns single SKIPPED result (not a list)
        assert isinstance(result, PipelineResult)
        assert result.status == "SKIPPED"
        assert "No files to process" in result.errors

    def test_batch_single_file_returns_single_result(self, tmp_path):
        """A single-element files list returns a PipelineResult, not a list."""
        from pyedi_core.pipeline import Pipeline, PipelineResult

        f = tmp_path / "single.xyz"
        f.write_text("content")

        pipeline = Pipeline(config_path="./config/config.yaml")
        result = pipeline.run(files=[str(f)], dry_run=True)

        assert isinstance(result, PipelineResult)  # Not a list

    def test_batch_unique_correlation_ids(self, tmp_path):
        """Each result in a batch has a unique correlation_id."""
        from pyedi_core.pipeline import Pipeline

        files = []
        for i in range(5):
            f = tmp_path / f"batch{i}.xyz"
            f.write_text(f"data {i}")
            files.append(str(f))

        pipeline = Pipeline(config_path="./config/config.yaml")
        results = pipeline.run(files=files, dry_run=True)

        assert isinstance(results, list)
        ids = [r.correlation_id for r in results]
        assert len(set(ids)) == len(ids), "Each result should have a unique correlation_id"
        # Verify each is a valid UUID
        for cid in ids:
            uuid.UUID(cid)


@pytest.mark.integration
class TestX12RealParsing:
    """Integration tests that parse real X12 EDI content through the actual badx12 parser."""

    MINIMAL_X12_810 = (
        "ISA*00*          *00*          *ZZ*SENDER         "
        "*ZZ*RECEIVER       *230101*1200*U*00401*000000001*0*P*>~"
        "GS*IN*SENDER*RECEIVER*20230101*1200*1*X*004010~"
        "ST*810*0001~"
        "BIG*20230101*INV001*20221215*PO001~"
        "TDS*10000~"
        "SE*4*0001~"
        "GE*1*1~"
        "IEA*1*000000001~"
    )

    def test_x12_parse_minimal_document(self, tmp_path):
        """Parse a minimal valid X12 810 document and verify structure."""
        from pyedi_core.drivers import X12Handler

        x12_file = tmp_path / "minimal.edi"
        x12_file.write_text(self.MINIMAL_X12_810)

        handler = X12Handler()
        result = handler.read(str(x12_file))

        assert isinstance(result, dict)
        assert "document" in result
        assert "segments" in result["document"]
        assert len(result["document"]["segments"]) > 0

    def test_x12_parse_extracts_segments(self, tmp_path):
        """Parse minimal X12 and verify BIG and TDS segments are present."""
        from pyedi_core.drivers import X12Handler

        x12_file = tmp_path / "segments.edi"
        x12_file.write_text(self.MINIMAL_X12_810)

        handler = X12Handler()
        result = handler.read(str(x12_file))

        seg_names = [s["segment"] for s in result["document"]["segments"]]
        assert "BIG" in seg_names, f"BIG not found in segments: {seg_names}"
        assert "TDS" in seg_names, f"TDS not found in segments: {seg_names}"

    def test_x12_parse_real_file(self):
        """Parse the existing real X12 fixture file and verify output structure."""
        from pyedi_core.drivers import X12Handler

        real_file = str(
            Path(__file__).parent / "user_supplied" / "inputs" / "200220261215033.dat"
        )

        handler = X12Handler()
        result = handler.read(real_file)

        assert isinstance(result, dict)
        assert "document" in result
        segments = result["document"]["segments"]
        assert len(segments) >= 1, "Expected at least one segment from the real file"

    def test_x12_handler_set_correlation_id(self, tmp_path):
        """Set correlation_id, parse a file, and verify it persists."""
        from pyedi_core.drivers import X12Handler

        x12_file = tmp_path / "corr.edi"
        x12_file.write_text(self.MINIMAL_X12_810)

        handler = X12Handler(correlation_id="corr-abc-123")
        assert handler.correlation_id == "corr-abc-123"

        result = handler.read(str(x12_file))

        assert handler.correlation_id == "corr-abc-123"
        assert "document" in result

    def test_x12_parse_unknown_extension(self, tmp_path):
        """Valid X12 file with .txt extension: detect_format is 'unknown' but read() works."""
        from pyedi_core.drivers import X12Handler

        txt_file = tmp_path / "invoice.txt"
        txt_file.write_text(self.MINIMAL_X12_810)

        handler = X12Handler()

        assert handler.detect_format(str(txt_file)) == "unknown"

        result = handler.read(str(txt_file))
        assert isinstance(result, dict)
        assert "document" in result
        seg_names = [s["segment"] for s in result["document"]["segments"]]
        assert "BIG" in seg_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
