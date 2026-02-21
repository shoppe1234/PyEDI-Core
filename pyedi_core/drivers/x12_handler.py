"""
X12 Handler - badx12-based driver for X12 EDI files.

Handles X12 EDI parsing using the badx12 library.
Open-ended transaction support: looks up Transaction ID in transaction_registry.
Falls back to _default_x12 for unknown transactions.
"""

import collections
import collections.abc
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# Python 2/3 compatibility shim for collections.Iterable
# This must be at the top of the file - do not modify
collections.Iterable = collections.abc.Iterable

from badx12 import Parser

from ..core import error_handler
from ..core import logger as core_logger
from ..core import mapper
from .base import TransactionProcessor


class X12Handler(TransactionProcessor):
    """
    Transaction processor for X12 EDI files.
    
    Uses badx12 library for parsing with fallback for unknown transaction types.
    Implements Section 4.2 of PyEDI_Core_Specification.docx.
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
            config: Configuration dictionary (should contain transaction_registry)
            rules_dir: Directory for mapping rules
            default_map: Path to default X12 map for unknown transactions
        """
        super().__init__(correlation_id, config)
        self._rules_dir = rules_dir or "./rules"
        self._default_map = default_map or "./rules/default_x12_map.yaml"
        self._config = config or {}
        self._transaction_registry = self._config.get("transaction_registry", {})
    
    def read(self, file_path: str) -> Dict[str, Any]:
        """
        Read and parse an X12 EDI file.
        
        Implements Section 4.2:
        1. Input Sanitization (pre-parse)
        2. Parsing via badx12
        3. Normalized Segment Output
        4. Transaction Routing
        
        Args:
            file_path: Path to X12 EDI file
            
        Returns:
            Dictionary with segments list in document order
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If EDI cannot be parsed
        """
        path = Path(file_path)
        if not path.exists():
            error_handler.handle_failure(
                file_path=file_path,
                stage=error_handler.Stage.DETECTION,
                reason=f"X12 file not found: {file_path}",
                exception=FileNotFoundError(f"X12 file not found: {file_path}"),
                correlation_id=self.correlation_id
            )
            raise FileNotFoundError(f"X12 file not found: {file_path}")
        
        self.logger.info(
            f"Reading X12 file",
            file_path=file_path,
            stage="DETECTION"
        )
        
        try:
            # Read the file content
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                edi_content = f.read()
            
            # --- STEP 1: INPUT SANITIZATION (Pre-Parse) ---
            # Port directly from edi_processor.py
            # Handle wrapped vs unwrapped format
            if edi_content and len(edi_content) > 106:
                # ISA segment is exactly 106 characters
                # Position 105 (0-indexed) is the segment terminator
                potential_terminator = edi_content[105]
                
                # If terminator is NOT newline, newlines are cosmetic - strip them
                if potential_terminator not in ['\r', '\n']:
                    edi_content = edi_content.replace('\n', '').replace('\r', '')
            
            self.logger.debug(
                f"Input sanitization complete",
                content_length=len(edi_content)
            )
            
            # --- STEP 2: PARSING VIA BADX12 ---
            # Port the three-line parse call directly from edi_processor.py
            parser = Parser()
            document = parser.parse_document(edi_content)
            full_data = document.to_dict()
            
            # Extract document structure
            doc_structure = full_data.get('document', {})
            config = doc_structure.get('config', {})
            interchange = doc_structure.get('interchange', {})
            
            self.logger.debug(
                f"badx12 parsing complete",
                has_interchange=bool(interchange)
            )
            
            # --- STEP 3: NORMALIZED SEGMENT OUTPUT ---
            # Port format_segment() helper and full hierarchy traversal
            # Output must be flat ordered list: ISA → GS → ST → body → SE → GE → IEA
            # Each segment: { "segment": "BIG", "fields": [{ "name": "BIG01", "content": "..." }] }
            
            sequential_segments = []
            
            def format_segment(seg_name: str, fields_list: List[Dict]) -> Dict[str, Any]:
                """
                Helper to format fields as objects: {"name": "TAG01", "content": "VAL"}
                
                Args:
                    seg_name: Segment tag (e.g., "BIG", "ISA")
                    fields_list: List of field dicts from badx12
                    
                Returns:
                    Formatted segment dict
                """
                formatted = []
                for i, field in enumerate(fields_list, 1):
                    formatted.append({
                        "name": f"{seg_name}{str(i).zfill(2)}",
                        "content": field.get('content', '')
                    })
                return {"segment": seg_name, "fields": formatted}
            
            # Traverse hierarchy in document order
            # Add Interchange Header (ISA)
            if 'header' in interchange:
                sequential_segments.append(
                    format_segment('ISA', interchange['header'].get('fields', []))
                )
            
            # Process groups
            for group in interchange.get('groups', []):
                # Add Group Header (GS)
                if 'header' in group:
                    sequential_segments.append(
                        format_segment('GS', group['header'].get('fields', []))
                    )
                
                for txn in group.get('transaction_sets', []):
                    # Add Transaction Header (ST)
                    if 'header' in txn:
                        sequential_segments.append(
                            format_segment('ST', txn['header'].get('fields', []))
                        )
                    
                    # Add Transaction Body Segments in order
                    for body_seg in txn.get('body', []):
                        seg_name = body_seg.get('fields', [{}])[0].get('content', 'UNKNOWN')
                        # Skip the segment name itself from fields list
                        fields = body_seg.get('fields', [])[1:]
                        sequential_segments.append(format_segment(seg_name, fields))
                    
                    # Add Transaction Trailer (SE)
                    if 'trailer' in txn:
                        sequential_segments.append(
                            format_segment('SE', txn['trailer'].get('fields', []))
                        )
                
                # Add Group Trailer (GE)
                if 'trailer' in group:
                    sequential_segments.append(
                        format_segment('GE', group['trailer'].get('fields', []))
                    )
            
            # Add Interchange Trailer (IEA)
            if 'trailer' in interchange:
                sequential_segments.append(
                    format_segment('IEA', interchange['trailer'].get('fields', []))
                )
            
            self.logger.debug(
                f"Segment reconstruction complete",
                segment_count=len(sequential_segments)
            )
            
            # --- STEP 4: TRANSACTION ROUTING ---
            # Extract ST Transaction Set ID from ST segment header fields
            # Look up in transaction_registry from config
            
            # Find ST segment in the sequential list
            st_segment = None
            for seg in sequential_segments:
                if seg.get("segment") == "ST":
                    st_segment = seg
                    break
            
            txn_id = None
            if st_segment:
                # ST01 is the transaction set identifier (e.g., '810', '850')
                for field in st_segment.get("fields", []):
                    if field.get("name") == "ST01":
                        txn_id = field.get("content", "").strip()
                        break
            
            if not txn_id:
                error_handler.handle_failure(
                    file_path=file_path,
                    stage=error_handler.Stage.VALIDATION,
                    reason="Could not extract transaction type from ST segment",
                    exception=ValueError("ST segment not found or ST01 empty"),
                    correlation_id=self.correlation_id
                )
                raise ValueError("Could not extract transaction type from ST segment")
            
            self.logger.info(
                f"Transaction type detected",
                transaction_type=txn_id,
                stage="VALIDATION"
            )
            
            # Look up in transaction_registry
            map_file = self._transaction_registry.get(txn_id)
            
            # Store for transform() - either map path or None (will use default)
            result = {
                "segments": sequential_segments,
                "_transaction_type": txn_id,
                "_source_file": path.name,
                "_map_file": map_file,
                "_is_unmapped": map_file is None
            }
            
            # If no match found, use default and log WARNING
            if map_file is None:
                # Get default map path
                default_map_path = self._transaction_registry.get("_default_x12")
                if default_map_path:
                    result["_map_file"] = default_map_path
                
                # Log UNMAPPED_TRANSACTION at WARNING level
                self.logger.warning(
                    f"UNMAPPED_TRANSACTION",
                    transaction_type=txn_id,
                    fallback_map=result["_map_file"],
                    stage="VALIDATION"
                )
            
            return result
            
        except FileNotFoundError:
            raise
        except Exception as e:
            error_handler.handle_failure(
                file_path=file_path,
                stage=error_handler.Stage.DETECTION,
                reason=f"Failed to read/parse X12 file: {str(e)}",
                exception=e,
                correlation_id=self.correlation_id
            )
            raise ValueError(f"Failed to read/parse X12 file: {str(e)}")
    
    def transform(self, raw_data: Dict[str, Any], map_yaml: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw X12 data using mapping rules.
        
        Args:
            raw_data: Raw parsed X12 data from read()
            map_yaml: Mapping configuration from YAML file
            
        Returns:
            Transformed data dictionary
        """
        self.logger.info(
            f"Transforming X12 data",
            transaction_type=raw_data.get("_transaction_type"),
            stage="TRANSFORMATION"
        )
        
        try:
            # Use mapper to apply mapping rules
            # The raw_data contains 'segments' key with normalized segment list
            transformed = mapper.map_data(raw_data, map_yaml)
            
            # Add envelope information
            if "envelope" not in transformed:
                transformed["envelope"] = {}
            
            transformed["envelope"]["transaction_type"] = raw_data.get("_transaction_type", "unknown")
            transformed["envelope"]["source_file"] = raw_data.get("_source_file", "unknown")
            
            self.logger.info(
                f"X12 transformation complete",
                transaction_type=raw_data.get("_transaction_type"),
                header_fields=len(transformed.get("header", {})),
                line_count=len(transformed.get("lines", [])),
                stage="TRANSFORMATION"
            )
            
            return transformed
            
        except Exception as e:
            error_handler.handle_failure(
                file_path=raw_data.get("_source_file", "unknown"),
                stage=error_handler.Stage.TRANSFORMATION,
                reason=f"Failed to transform X12 data: {str(e)}",
                exception=e,
                correlation_id=self.correlation_id
            )
            raise
    
    def write(self, payload: Dict[str, Any], output_path: str) -> None:
        """
        Write transformed data to JSON file.
        
        Args:
            payload: Transformed data
            output_path: Output file path
            
        Raises:
            IOError: If writing fails
        """
        self.logger.info(
            f"Writing output",
            output_path=output_path,
            stage="WRITE"
        )
        
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            
            self.logger.info(
                f"Output written successfully",
                output_path=output_path,
                stage="WRITE"
            )
            
        except Exception as e:
            error_handler.handle_failure(
                file_path=output_path,
                stage=error_handler.Stage.WRITE,
                reason=f"Failed to write output: {str(e)}",
                exception=e,
                correlation_id=self.correlation_id
            )
            raise IOError(f"Failed to write output: {str(e)}")


# Register this driver
from .base import DriverRegistry
DriverRegistry.register("x12", X12Handler)
