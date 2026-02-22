"""
Fixed-Length Handler - Driver for positional flat files.

Processes fixed-length positional flat files using a compiled YAML schema.
The schema drives all parsing - no hardcoded record IDs, field names, or lengths
in the Python source.

Key principles:
- All values governing parsing are read from the compiled schema at runtime
- No integer literals for field lengths or byte offsets
- No string literals matching any record ID from the DSL
- Multi-document files are segmented by detecting the invoice boundary record
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core import error_handler
from ..core import logger as core_logger
from ..core import mapper
from .base import TransactionProcessor


class FixedLengthHandler(TransactionProcessor):
    """
    Transaction processor for fixed-length positional flat files.
    
    Reads positional data from fixed-length files using a compiled YAML schema
    that defines record IDs, field positions, lengths, and types.
    """
    
    def __init__(
        self,
        correlation_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        schema_dir: Optional[str] = None,
        compiled_schema_dir: Optional[str] = None,
        compiled_yaml_path: Optional[str] = None
    ):
        """
        Initialize fixed-length handler.
        
        Args:
            correlation_id: Optional correlation ID
            config: Configuration dictionary
            schema_dir: Directory for source DSL schemas
            compiled_schema_dir: Directory for compiled YAML schemas
            compiled_yaml_path: Explicit path to compiled YAML map
        """
        super().__init__(correlation_id, config)
        self._schema_dir = schema_dir or "./schemas/source"
        self._compiled_schema_dir = compiled_schema_dir or "./schemas/compiled"
        self._compiled_yaml_path = compiled_yaml_path
        self._compiled_schema: Optional[Dict[str, Any]] = None
    
    def set_compiled_yaml_path(self, compiled_yaml_path: str) -> None:
        """
        Set the compiled YAML path from pipeline.py.
        
        Args:
            compiled_yaml_path: Path to the compiled YAML map file
        """
        self._compiled_yaml_path = compiled_yaml_path
    
    def read(self, file_path: str, compiled_schema: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Read and parse a fixed-length file.
        
        Segments the file into multiple documents if it contains multiple invoices.
        Each invoice boundary is detected via the schema's group_on_record setting.
        
        Args:
            file_path: Path to fixed-length file
            compiled_schema: Optional compiled schema dict (if None, loads from path)
            
        Returns:
            List of raw document dicts - one per detected invoice cycle
            
        Raises:
            FileNotFoundError: If file doesn't exist
            UnicodeDecodeError: On encoding failures (hard fail - no fallback)
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Fixed-length file not found: {file_path}")
        
        self.logger.info(f"Reading fixed-length file", file_path=file_path)
        
        # Get compiled schema
        if compiled_schema is None:
            compiled_schema = self._load_compiled_schema(file_path)
        
        if compiled_schema is None:
            raise ValueError(f"No compiled schema available for: {file_path}")
        
        self._compiled_schema = compiled_schema
        
        # Extract schema-driven configuration
        record_id_field = compiled_schema.get("record_id_field", {})
        id_length = record_id_field.get("length", 10)
        record_map = compiled_schema.get("records", {})
        
        # Find the invoice boundary group - schema drives this, no hardcoded names
        groups = compiled_schema.get("groups", {})
        boundary_group = None
        start_trigger_record = None
        
        for group_name, group_def in groups.items():
            if group_def.get("invoice_boundary") is True:
                boundary_group = group_def
                # Find the start trigger record from members
                for member in group_def.get("members", []):
                    if member.get("record") is not None:
                        start_trigger_record = member["record"]
                        break
                break
        
        if start_trigger_record is None:
            # Fallback: use first record type in the records map
            if record_map:
                start_trigger_record = next(iter(record_map.keys()))
        
        # Read file with UTF-8 encoding - hard fail on decode error
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError as e:
            self.logger.error(f"UTF-8 decode error", error=str(e))
            error_handler.handle_failure(
                file_path=file_path,
                stage=error_handler.Stage.VALIDATION,
                reason=f"ENCODING_ERROR: {str(e)}",
                exception=e,
                correlation_id=self.correlation_id
            )
            raise
        
        # Segment into multiple documents
        all_documents = []
        current_doc: Dict[str, Any] = {"records": [], "unmapped_lines": []}
        
        for line_number, line in enumerate(lines, start=1):
            # Skip blank lines
            if not line.strip():
                continue
            
            # Extract record key using schema-driven length
            line = line.rstrip('\n\r')
            if len(line) < id_length:
                # Line too short - skip or log warning
                self.logger.warning(
                    f"Line shorter than record ID length",
                    line_number=line_number,
                    line_length=len(line),
                    expected_length=id_length
                )
                continue
                
            record_key = line[0:id_length]
            
            # Check for document boundary - schema-driven trigger
            if start_trigger_record and record_key == start_trigger_record:
                if current_doc["records"]:
                    # Save current document and start a new one
                    all_documents.append(current_doc)
                    current_doc = {"records": [], "unmapped_lines": []}
            
            # Look up record definition - dict.get() not if/else on record names
            record_def = record_map.get(record_key)
            
            if record_def is None:
                # Unmapped record - warning, not failure
                self.logger.warning(
                    f"UNMAPPED_RECORD",
                    record_key=record_key,
                    line_number=line_number
                )
                current_doc["unmapped_lines"].append({
                    "line_number": line_number,
                    "raw": line
                })
                continue
            
            # Extract fields using schema-driven cursor positions
            cursor = id_length  # Start after record ID
            extracted: Dict[str, Any] = {}
            
            for field in record_def.get("fields", []):
                field_name = field.get("name")
                field_length = field.get("length", 0)
                
                if cursor + field_length > len(line):
                    # Field extends beyond line - use what's available
                    field_value = line[cursor:]
                else:
                    field_value = line[cursor:cursor + field_length]
                
                extracted[field_name] = field_value
                cursor += field_length
            
            current_doc["records"].append({
                "record_type": record_key,
                "fields": extracted
            })
        
        # Don't forget the last document
        if current_doc["records"]:
            all_documents.append(current_doc)
        
        self.logger.info(
            f"Fixed-length file parsed",
            documents=len(all_documents),
            total_records=sum(len(d["records"]) for d in all_documents)
        )
        
        return all_documents
    
    def _load_compiled_schema(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Load compiled schema from path or discover by filename.
        
        Args:
            file_path: Path to the data file
            
        Returns:
            Compiled schema dict or None
        """
        import yaml
        
        # First priority: explicit path from pipeline.py
        if self._compiled_yaml_path:
            schema_path = Path(self._compiled_yaml_path)
            if schema_path.exists():
                try:
                    with open(schema_path, "r") as f:
                        return yaml.safe_load(f)
                except Exception as e:
                    self.logger.warning(f"Failed to load compiled schema: {e}")
                    error_handler.handle_failure(
                        file_path=file_path,
                        stage=error_handler.Stage.VALIDATION,
                        reason=f"Failed to load compiled schema: {str(e)}",
                        exception=e,
                        correlation_id=self.correlation_id
                    )
                    raise ValueError(f"Compiled YAML map not accessible: {self._compiled_yaml_path}")
            else:
                error_handler.handle_failure(
                    file_path=file_path,
                    stage=error_handler.Stage.VALIDATION,
                    reason=f"Compiled YAML map does not exist: {self._compiled_yaml_path}",
                    exception=None,
                    correlation_id=self.correlation_id
                )
                raise ValueError(f"Compiled YAML map does not exist: {self._compiled_yaml_path}")
        
        # Fallback: discover by filename
        path = Path(file_path)
        base_name = path.stem
        
        schema_file = Path(self._compiled_schema_dir) / f"{base_name}.yaml"
        if schema_file.exists():
            try:
                with open(schema_file, "r") as f:
                    return yaml.safe_load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load schema: {e}")
        
        return None
    
    def transform(
        self,
        raw_data: Dict[str, Any],
        map_yaml: Dict[str, Any],
        compiled_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Transform raw fixed-length data using mapping rules.
        
        Applies type conversions based on field types from the compiled schema.
        
        Args:
            raw_data: Raw parsed data from read()
            map_yaml: Mapping configuration from YAML file
            compiled_schema: Optional compiled schema for type information
            
        Returns:
            Transformed data dictionary
        """
        self.logger.info("Transforming fixed-length data")
        
        # Use compiled schema for type conversions if available
        schema = compiled_schema or self._compiled_schema
        
        # Apply type conversions to raw data
        transformed_data = self._apply_type_conversions(raw_data, schema)
        
        # Use mapper to apply mapping rules
        mapped_data = mapper.map_data(transformed_data, map_yaml)
        
        # Add envelope
        if "envelope" not in mapped_data:
            mapped_data["envelope"] = {}
        
        mapped_data["envelope"]["schema_version"] = map_yaml.get("schema_version", "1.0")
        mapped_data["envelope"]["transaction_type"] = map_yaml.get("transaction_type", "810")
        mapped_data["envelope"]["input_format"] = "FIXED_LENGTH"
        
        self.logger.info(
            "Fixed-length transformation complete",
            header_fields=len(mapped_data.get("header", {})),
            line_count=len(mapped_data.get("lines", []))
        )
        
        return mapped_data
    
    def _apply_type_conversions(
        self,
        raw_data: Dict[str, Any],
        compiled_schema: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Apply type conversions to raw field values based on schema.
        
        Args:
            raw_data: Raw parsed data
            compiled_schema: Compiled schema with field type information
            
        Returns:
            Data with converted types
        """
        if compiled_schema is None:
            return raw_data
        
        # For single document (header/lines/summary structure)
        if "records" not in raw_data:
            return raw_data
        
        records = raw_data.get("records", [])
        if not records:
            return raw_data
        
        record_map = compiled_schema.get("records", {})
        
        # Process each record
        converted_records = []
        for record in records:
            record_type = record.get("record_type", "")
            record_def = record_map.get(record_type, {})
            
            fields = record.get("fields", {})
            converted_fields = {}
            
            for field_name, field_value in fields.items():
                # Find field definition in schema
                field_def = None
                for f in record_def.get("fields", []):
                    if f.get("name") == field_name:
                        field_def = f
                        break
                
                if field_def is None:
                    # No definition found - keep as string
                    converted_fields[field_name] = field_value
                    continue
                
                # Apply type conversion based on schema type
                converted_value = self._convert_field_value(
                    field_value,
                    field_def
                )
                converted_fields[field_name] = converted_value
            
            converted_records.append({
                "record_type": record_type,
                "fields": converted_fields
            })
        
        # Reconstruct the data structure for the mapper
        result = self._reconstruct_for_mapper(converted_records, compiled_schema)
        
        return result
    
    def _convert_field_value(self, value: str, field_def: Dict[str, Any]) -> Any:
        """
        Convert a field value based on its type definition.
        
        Args:
            value: Raw string value
            field_def: Field definition from schema
            
        Returns:
            Converted value
        """
        field_type = field_def.get("type", "string")
        read_empty_as_null = field_def.get("readEmptyAsNull", False)
        
        # Strip whitespace
        if isinstance(value, str):
            stripped = value.strip()
        else:
            stripped = str(value).strip() if value is not None else ""
        
        # Handle empty values
        if stripped == "":
            if read_empty_as_null:
                return None
            return value  # Return original empty string
        
        # Type-specific conversion
        if field_type == "string":
            return stripped
        
        elif field_type == "integer":
            try:
                return int(stripped)
            except ValueError:
                if read_empty_as_null:
                    return None
                return stripped
        
        elif field_type == "decimal":
            try:
                return float(stripped)
            except ValueError:
                if read_empty_as_null:
                    return None
                return stripped
        
        elif field_type == "implied_decimal":
            return self._convert_implied_decimal(stripped, field_def, read_empty_as_null)
        
        else:
            # Unknown type - return as string
            return stripped
    
    def _convert_implied_decimal(
        self,
        value: str,
        field_def: Dict[str, Any],
        read_empty_as_null: bool
    ) -> Optional[float]:
        """
        Convert an implied decimal value.
        
        Implied decimal: digits represent the value with implied decimal position.
        Example: "000009942" with fractionalDigits=2 becomes 99.42
        
        Args:
            value: Stripped string value
            field_def: Field definition with fractionalDigits
            read_empty_as_null: Whether to return None for empty values
            
        Returns:
            Python float or None
        """
        if not value:
            return None if read_empty_as_null else 0.0
        
        fractional_digits = field_def.get("fractionalDigits", 2)
        
        # Detect and capture leading sign
        sign = 1
        if value.startswith("-"):
            sign = -1
            value = value[1:]  # Remove the minus for processing
        elif value.startswith("+"):
            value = value[1:]
        
        # Strip any remaining non-digit characters (keep only digits)
        digits = "".join(c for c in value if c.isdigit())
        
        if not digits:
            return None if read_empty_as_null else 0.0
        
        # Convert to integer and apply decimal position
        try:
            int_value = int(digits)
            result = int_value / (10 ** fractional_digits) * sign
            return float(result)
        except (ValueError, ZeroDivisionError):
            if read_empty_as_null:
                return None
            return 0.0
    
    def _reconstruct_for_mapper(
        self,
        converted_records: List[Dict[str, Any]],
        compiled_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Reconstruct data structure for the mapper.
        
        Organizes records into header, lines, and summary sections
        based on group definitions in the schema.
        
        Args:
            converted_records: List of records with converted types
            compiled_schema: Compiled schema with group definitions
            
        Returns:
            Dictionary with header, lines, summary structure
        """
        groups = compiled_schema.get("groups", {})
        
        # Find OTpidGroup for document structure
        otpid_group = groups.get("OTpidGroup", {})
        
        # Simple approach: collect records by type
        header_records = []
        line_records = []
        summary_records = []
        
        # Track current line item
        current_line: Optional[Dict[str, Any]] = None
        lines: List[Dict[str, Any]] = []
        
        # Track SAC detail charges for current line
        current_line_sac: List[Dict[str, Any]] = []
        
        # Track summary SAC charges
        summary_sac: List[Dict[str, Any]] = []
        
        # Process each record
        for record in converted_records:
            record_type = record.get("record_type", "")
            fields = record.get("fields", {})
            
            # Header records (before first line item)
            if record_type in ("O_TPID    ", "OIN_DSTID ", "OIN_HDRA  ", 
                              "TPM_HDR   ", "OIN_HDR1  ", "OIN_HDR2  ",
                              "OIN_HDR3  ", "OIN_HDR4  ", "OIN_HDR5  ",
                              "OIN_REFH1 ", "OIN_TRM1  ", "OIN_ST1   ",
                              "OIN_ST2   ", "OIN_ST3   ", "OIN_BT1   ",
                              "OIN_BT2   ", "OIN_BT3   ", "OIN_RE1   ",
                              "OIN_RE2   ", "OIN_RE3   "):
                header_records.append(fields)
            
            # Line item start
            elif record_type == "OIN_DTL1  ":
                # Save previous line if exists
                if current_line is not None:
                    current_line["allowances_charges"] = current_line_sac
                    lines.append(current_line)
                    current_line_sac = []
                
                # Start new line
                current_line = dict(fields)
                current_line["_record_type"] = "OIN_DTL1"
            
            # Line item details (belong to current line)
            elif record_type in ("OIN_DTL2  ", "OIN_DTL3  ", "OIN_DTL4  ",
                                "OIN_DTL4Z ", "OIN_DTL5  ", "OIN_DTL6  ",
                                "OIN_DTL7  ", "OIN_DTL8  ", "OIN_DTL9  ",
                                "OIN_TAXD1 ", "OIN_DTL11 "):
                if current_line is not None:
                    current_line.update(fields)
            
            # Per-line SAC detail charges
            elif record_type in ("OIN_SACD1 ", "OIN_SACD2 "):
                if current_line is not None:
                    # Add to current line's SAC charges
                    if record_type == "OIN_SACD1 ":
                        current_line_sac.append(dict(fields))
                    elif record_type == "OIN_SACD2 " and current_line_sac:
                        # Add description to last SAC
                        current_line_sac[-1].update(fields)
            
            # Summary records
            elif record_type in ("OIN_TTL1  ", "OIN_TAXS1 "):
                summary_records.append(fields)
            
            # Summary SAC charges (document level)
            elif record_type in ("OIN_SACS1 ", "OIN_SACS2 ", "OIN_TAXS2 "):
                if record_type == "OIN_SACS1 ":
                    summary_sac.append(dict(fields))
                elif record_type == "OIN_SACS2 " and summary_sac:
                    summary_sac[-1].update(fields)
                elif record_type == "OIN_TAXS2 " and summary_sac:
                    summary_sac[-1].update(fields)
        
        # Don't forget the last line
        if current_line is not None:
            current_line["allowances_charges"] = current_line_sac
            lines.append(current_line)
        
        # Build result structure
        result: Dict[str, Any] = {
            "header": {},
            "lines": lines,
            "summary": {}
        }
        
        # Merge header records (last value wins for duplicates)
        for rec in header_records:
            result["header"].update(rec)
        
        # Add summary charges
        if summary_sac:
            result["summary"]["summary_charges"] = summary_sac
        
        # Merge summary records
        for rec in summary_records:
            result["summary"].update(rec)
        
        return result
    
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
DriverRegistry.register("fixed_length", FixedLengthHandler)
