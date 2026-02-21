"""
X12 Handler - badx12-based driver for X12 EDI files.

Handles X12 EDI parsing using the badx12 library.
Open-ended transaction support: looks up Transaction ID in transaction_registry.
Falls back to default_x12_map.yaml for unknown transactions.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core import error_handler
from ..core import logger as core_logger
from ..core import mapper
from .base import TransactionProcessor

# Try to import badx12, if not available, use fallback
try:
    import badx12
    BADX12_AVAILABLE = True
except ImportError:
    BADX12_AVAILABLE = False


class X12Handler(TransactionProcessor):
    """
    Transaction processor for X12 EDI files.
    
    Uses badx12 library for parsing with fallback for unknown transaction types.
    """
    
    def __init__(
        self,
        correlation_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        rules_dir: Optional[str] = None,
        default_map: Optional[str] = None
    ):
        """
        Initialize X12 handler.
        
        Args:
            correlation_id: Optional correlation ID
            config: Configuration dictionary
            rules_dir: Directory for mapping rules
            default_map: Path to default X12 map for unknown transactions
        """
        super().__init__(correlation_id, config)
        self._rules_dir = rules_dir or "./rules"
        self._default_map = default_map or "./rules/default_x12_map.yaml"
    
    def read(self, file_path: str) -> Dict[str, Any]:
        """
        Read and parse an X12 EDI file.
        
        Args:
            file_path: Path to X12 EDI file
            
        Returns:
            Raw parsed data as dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If EDI cannot be parsed
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"X12 file not found: {file_path}")
        
        self.logger.info(f"Reading X12 file", file_path=file_path)
        
        # Read the file content
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        
        # Extract transaction type from ST segment
        transaction_type = self._extract_transaction_type(content)
        
        if not transaction_type:
            raise ValueError("Could not extract transaction type from X12 file")
        
        self.logger.info(f"Detected transaction type", transaction_type=transaction_type)
        
        # Parse using badx12 or fallback
        if BADX12_AVAILABLE:
            try:
                parsed = self._parse_with_badx12(content, transaction_type)
            except Exception as e:
                self.logger.warning(f"badx12 parsing failed, using fallback: {e}")
                parsed = self._parse_fallback(content, transaction_type)
        else:
            parsed = self._parse_fallback(content, transaction_type)
        
        # Add transaction type to parsed data
        parsed["_transaction_type"] = transaction_type
        parsed["_source_file"] = path.name
        
        return parsed
    
    def _extract_transaction_type(self, content: str) -> Optional[str]:
        """
        Extract transaction type from ST segment.
        
        Args:
            content: EDI file content
            
        Returns:
            Transaction type (e.g., '810', '850') or None
        """
        # Find ST segment
        st_match = re.search(r'ST\*(\d{3})', content)
        if st_match:
            return st_match.group(1)
        return None
    
    def _parse_with_badx12(self, content: str, transaction_type: str) -> Dict[str, Any]:
        """
        Parse X12 using badx12 library.
        
        Args:
            content: EDI file content
            transaction_type: Transaction type code
            
        Returns:
            Parsed data dictionary
        """
        # Use badx12 to parse
        parser = badx12.X12Parser()
        parsed = parser.parse(content)
        
        # Extract segments into a structured dict
        result = {
            "header": {},
            "lines": [],
            "summary": {}
        }
        
        # Extract ISA segment (interchange control)
        isa_segments = parsed.find_segments("ISA")
        if isa_segments:
            isa = isa_segments[0]
            result["header"]["interchange_control_number"] = isa.get_element(13)
            result["header"]["sender_id"] = isa.get_element(6)
            result["header"]["receiver_id"] = isa.get_element(8)
        
        # Extract GS segment (functional group)
        gs_segments = parsed.find_segments("GS")
        if gs_segments:
            gs = gs_segments[0]
            result["header"]["application_sender_code"] = gs.get_element(2)
            result["header"]["application_receiver_code"] = gs.get_element(3)
        
        # Extract ST segment
        st_segments = parsed.find_segments("ST")
        if st_segments:
            st = st_segments[0]
            result["header"]["transaction_set_control_number"] = st.get_element(2)
        
        # Extract transaction-specific segments based on type
        if transaction_type == "810":  # Invoice
            self._parse_810(parsed, result)
        elif transaction_type == "850":  # Purchase Order
            self._parse_850(parsed, result)
        elif transaction_type == "856":  # Ship Notice
            self._parse_856(parsed, result)
        else:
            # Generic parsing for unknown types
            self._parse_generic(parsed, result)
        
        return result
    
    def _parse_810(self, parsed, result: Dict[str, Any]) -> None:
        """Parse 810 Invoice transaction."""
        # Extract BEG segment (Beginning Segment for Invoice)
        beg_segments = parsed.find_segments("BEG")
        if beg_segments:
            beg = beg_segments[0]
            result["header"]["invoice_number"] = beg.get_element(2)
            result["header"]["purchase_order_number"] = beg.get_element(3)
        
        # Extract REF segments for references
        for ref in parsed.find_segments("REF"):
            ref_id = ref.get_element(1)
            if ref_id == "IV":
                result["header"]["invoice_date"] = ref.get_element(2)
            elif ref_id == "PO":
                result["header"]["po_number"] = ref.get_element(2)
        
        # Extract IT1 segments (Line Items)
        for it1 in parsed.find_segments("IT1"):
            line = {
                "line_number": it1.get_element(1),
                "quantity_ordered": it1.get_element(2),
                "unit_price": it1.get_element(3),
                "product_id": it1.get_element(6)
            }
            result["lines"].append(line)
        
        # Extract TDS segment (Total Monetary Value Summary)
        tds_segments = parsed.find_segments("TDS")
        if tds_segments:
            tds = tds_segments[0]
            result["summary"]["invoice_amount"] = tds.get_element(1)
    
    def _parse_850(self, parsed, result: Dict[str, Any]) -> None:
        """Parse 850 Purchase Order transaction."""
        # Extract BEG segment
        beg_segments = parsed.find_segments("BEG")
        if beg_segments:
            beg = beg_segments[0]
            result["header"]["po_number"] = beg.get_element(3)
            result["header"]["po_date"] = beg.get_element(5)
        
        # Extract PO1 segments (Line Items)
        for po1 in parsed.find_segments("PO1"):
            line = {
                "line_number": po1.get_element(1),
                "quantity_ordered": po1.get_element(2),
                "unit_price": po1.get_element(4),
                "product_id": po1.get_element(7)
            }
            result["lines"].append(line)
    
    def _parse_856(self, parsed, result: Dict[str, Any]) -> None:
        """Parse 856 Ship Notice/Manifest."""
        # Extract BSN segment
        bsn_segments = parsed.find_segments("BSN")
        if bsn_segments:
            bsn = bsn_segments[0]
            result["header"]["shipment_id"] = bsn.get_element(2)
            result["header"]["ship_date"] = bsn.get_element(5)
        
        # Extract SN1 segment (Ship Notice)
        for sn1 in parsed.find_segments("SN1"):
            line = {
                "ship_quantity": sn1.get_element(2),
                "unit": sn1.get_element(3)
            }
            result["lines"].append(line)
    
    def _parse_generic(self, parsed, result: Dict[str, Any]) -> None:
        """Generic parsing - extract all segments."""
        # Just extract all segments as raw data
        for segment in parsed:
            seg_type = segment.id if hasattr(segment, 'id') else str(segment)
            result["header"][seg_type] = str(segment)
    
    def _parse_fallback(self, content: str, transaction_type: str) -> Dict[str, Any]:
        """
        Fallback parser when badx12 is not available.
        
        Parses X12 as simple line-separated segments.
        
        Args:
            content: EDI file content
            transaction_type: Transaction type code
            
        Returns:
            Parsed data dictionary
        """
        result = {
            "header": {},
            "lines": [],
            "summary": {}
        }
        
        # Split into segments (~ is segment terminator)
        segments = content.replace('\n', '~').split('~')
        
        current_loop = []
        
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            
            # Parse segment elements (* is element separator)
            elements = segment.split('*')
            seg_type = elements[0] if elements else ""
            
            # Map common segments
            if seg_type == "ISA":
                result["header"]["sender_id"] = elements[6].strip() if len(elements) > 6 else ""
                result["header"]["receiver_id"] = elements[8].strip() if len(elements) > 8 else ""
            
            elif seg_type == "ST":
                result["header"]["transaction_set_control_number"] = elements[2].strip() if len(elements) > 2 else ""
            
            elif seg_type == "BEG":
                if transaction_type == "810":
                    result["header"]["invoice_number"] = elements[2].strip() if len(elements) > 2 else ""
                    result["header"]["purchase_order_number"] = elements[3].strip() if len(elements) > 3 else ""
                elif transaction_type == "850":
                    result["header"]["po_number"] = elements[3].strip() if len(elements) > 3 else ""
            
            elif seg_type in ("IT1", "PO1", "SN1", "REF"):
                # Line item segments
                line = {"segment": segment}
                result["lines"].append(line)
            
            elif seg_type == "TDS":
                result["summary"]["invoice_amount"] = elements[1].strip() if len(elements) > 1 else ""
        
        return result
    
    def transform(self, raw_data: Dict[str, Any], map_yaml: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw X12 data using mapping rules.
        
        Args:
            raw_data: Raw parsed X12 data
            map_yaml: Mapping configuration
            
        Returns:
            Transformed data dictionary
        """
        self.logger.info("Transforming X12 data")
        
        # Use mapper to apply mapping rules
        transformed = mapper.map_data(raw_data, map_yaml)
        
        self.logger.info(
            "X12 transformation complete",
            header_fields=len(transformed.get("header", {})),
            line_count=len(transformed.get("lines", []))
        )
        
        return transformed
    
    def write(self, payload: Dict[str, Any], output_path: str) -> None:
        """
        Write transformed data to JSON file.
        
        Args:
            payload: Transformed data
            output_path: Output file path
            
        Raises:
            IOError: If writing fails
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            
            self.logger.info(f"Output written", output_path=output_path)
            
        except Exception as e:
            self.logger.error(f"Failed to write output: {e}")
            error_handler.handle_failure(
                file_path=output_path,
                stage=error_handler.Stage.WRITE,
                reason=f"Failed to write output: {str(e)}",
                exception=e,
                correlation_id=self.correlation_id
            )
            raise


# Register this driver
from .base import DriverRegistry
DriverRegistry.register("x12", X12Handler)
