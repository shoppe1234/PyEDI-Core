"""
Integration tests for driver modules - improving driver coverage.
"""

import json
import tempfile
from pathlib import Path

import pytest


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
        assert result["header"]["name"] == "test"
    
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
    
    def test_x12_write(self, tmp_path):
        """Test X12 write."""
        from pyedi_core.drivers import X12Handler
        
        handler = X12Handler()
        
        output_file = tmp_path / "output.x12"
        
        payload = {"header": {"isa": "test"}}
        
        handler.write(payload, str(output_file))
        
        assert output_file.exists()


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
