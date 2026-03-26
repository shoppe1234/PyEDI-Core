"""
CSV Handler - pandas-based driver for CSV files.

Handles CSV file processing with schema enforcement from compiled YAML.
The handler receives the compiled_yaml_path from pipeline.py via csv_schema_registry.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

from ..core import error_handler
from ..core import logger as core_logger
from ..core import mapper
from ..core import schema_compiler
from .base import TransactionProcessor


class CSVHandler(TransactionProcessor):
    """
    Transaction processor for CSV files.
    
    Uses pandas for CSV reading with schema enforcement from compiled YAML.
    The compiled_yaml_path is set explicitly by pipeline.py via csv_schema_registry.
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
        Initialize CSV handler.
        
        Args:
            correlation_id: Optional correlation ID
            config: Configuration dictionary
            schema_dir: Directory for source DSL schemas
            compiled_schema_dir: Directory for compiled YAML schemas
            compiled_yaml_path: Explicit path to compiled YAML map (from pipeline.py)
        """
        super().__init__(correlation_id, config)
        self._schema_dir = schema_dir or "./schemas/source"
        self._compiled_schema_dir = compiled_schema_dir or "./schemas/compiled"
        self._compiled_yaml_path = compiled_yaml_path
    
    def set_compiled_yaml_path(self, compiled_yaml_path: str) -> None:
        """
        Set the compiled YAML path from pipeline.py.
        
        Args:
            compiled_yaml_path: Path to the compiled YAML map file
        """
        self._compiled_yaml_path = compiled_yaml_path
    
    def _detect_delimiter(self, file_path: str, schema_delimiter: str) -> str:
        """Auto-detect delimiter by counting occurrences in the first line.

        Args:
            file_path: Path to data file
            schema_delimiter: Delimiter declared in the compiled schema

        Returns:
            Detected delimiter (or schema_delimiter if detection is inconclusive)
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().rstrip('\n\r')

        candidates = {'|': first_line.count('|'), ',': first_line.count(','), '\t': first_line.count('\t')}
        detected = max(candidates, key=candidates.get)

        if detected != schema_delimiter and candidates[detected] > candidates.get(schema_delimiter, 0):
            self.logger.info(
                "Auto-detected delimiter differs from schema",
                detected=detected,
                schema_delimiter=schema_delimiter,
            )
            return detected
        return schema_delimiter

    def read(self, file_path: str) -> Dict[str, Any]:
        """
        Read and parse a CSV file.

        Args:
            file_path: Path to CSV file

        Returns:
            Raw parsed data as dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If CSV cannot be parsed
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        self.logger.info(f"Reading CSV file", file_path=file_path)

        # Get schema - prefer explicit path from pipeline, fall back to discovery
        schema = self._get_schema_for_file(file_path)
        
        try:
            records_schema = schema.get("schema", {}).get("records", {}) if schema else {}
            
            if records_schema:
                # Manual parsing for heterogeneous multi-record file
                delimiter = schema.get("schema", {}).get("delimiter", ",")
                delimiter = self._detect_delimiter(file_path, delimiter)
                
                result = {
                    "header": {},
                    "lines": [],
                    "summary": {}
                }
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.rstrip('\n\r')
                        if not line:
                            continue
                            
                        parts = line.split(delimiter)
                        if not parts:
                            continue
                            
                        record_id = parts[0]
                        if record_id in records_schema:
                            record_cols = records_schema[record_id]
                            
                            row_dict = {}
                            for i, col_name in enumerate(record_cols):
                                if i < len(parts):
                                    row_dict[col_name] = parts[i]
                                else:
                                    row_dict[col_name] = None
                            
                            result["lines"].append(row_dict)
                                
                self.logger.info(
                    f"Flat file parsed manually",
                    lines=len(result["lines"])
                )
                return result
                
            # Fallback: Read CSV with pandas (Homogeneous tabular data)
            if schema and "schema" in schema:
                # Use schema for type enforcement
                dtype = {}
                parse_dates = []
                column_config = schema.get("schema", {}).get("columns", [])
                
                for col in column_config:
                    col_type = col.get("type", "string")
                    if col_type == "integer":
                        dtype[col["name"]] = "Int64"  # Nullable integer
                    elif col_type == "float":
                        dtype[col["name"]] = "float64"
                    elif col_type == "date":
                        parse_dates.append(col["name"])
                
                delimiter = schema.get("schema", {}).get("delimiter", ",")
                delimiter = self._detect_delimiter(file_path, delimiter)

                # Detect headerless files: read first line, check if it matches schema column names
                schema_col_names = [c["name"] for c in column_config]
                header_mode: Any = 0  # default: first row is header
                col_names: Optional[List[str]] = None
                with open(file_path, 'r', encoding='utf-8') as _f:
                    first_line = _f.readline().rstrip('\n\r')
                first_fields = first_line.split(delimiter)
                # If none of the first-row fields match schema column names, treat as headerless
                if schema_col_names and not any(f.strip() in schema_col_names for f in first_fields):
                    header_mode = None
                    col_names = schema_col_names

                df = pd.read_csv(
                    file_path,
                    sep=delimiter,
                    header=header_mode,
                    names=col_names,
                    dtype=dtype if dtype else None,
                    parse_dates=parse_dates if parse_dates else False,
                    keep_default_na=True
                )
            else:
                # Read without schema
                df = pd.read_csv(file_path)
            
            # Sanitize Dataframe columns to match schema definitions (remove spaces/special chars)
            if schema and "schema" in schema and "columns" in schema["schema"]:
                import re
                schema_cols = [c["name"] for c in schema["schema"]["columns"]]
                unique_schema_cols = []
                for c in schema_cols:
                    if c not in unique_schema_cols:
                        unique_schema_cols.append(c)
                
                new_cols = []
                for df_col in df.columns:
                    matched = False
                    norm_df = re.sub(r'[^a-zA-Z0-9]', '', str(df_col)).lower()
                    for s_col in unique_schema_cols:
                        norm_s = re.sub(r'[^a-zA-Z0-9]', '', str(s_col)).lower()
                        if norm_df == norm_s:
                            new_cols.append(s_col)
                            matched = True
                            break
                    if not matched:
                        new_cols.append(df_col)
                df.columns = new_cols

            
            # Convert to dict with records
            # Handle both flat (header-only) and detailed (with line items) formats
            data = df.to_dict(orient="records")
            
            result = {
                "header": {},
                "lines": data,
                "summary": {}
            }
            
            self.logger.info(
                f"CSV parsed successfully",
                rows=len(data),
                columns=len(df.columns)
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to parse CSV: {e}")
            error_handler.handle_failure(
                file_path=file_path,
                stage=error_handler.Stage.DETECTION,
                reason=f"CSV parsing failed: {str(e)}",
                exception=e,
                correlation_id=self.correlation_id
            )
            raise ValueError(f"Failed to parse CSV: {e}")
    
    def _get_schema_for_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get compiled schema for a CSV file.
        
        First checks for explicit compiled_yaml_path from pipeline.py,
        then falls back to discovery by filename.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Compiled schema dict or None
            
        Raises:
            ValueError: If compiled_yaml_path is explicitly set but doesn't exist
        """
        # First priority: explicit path from pipeline.py via csv_schema_registry
        if self._compiled_yaml_path:
            schema_path = Path(self._compiled_yaml_path)
            if schema_path.exists():
                try:
                    with open(schema_path, "r") as f:
                        return yaml.safe_load(f)
                except Exception as e:
                    self.logger.warning(f"Failed to load compiled schema from {schema_path}: {e}")
                    # If explicit path fails, this is a validation error
                    error_handler.handle_failure(
                        file_path=file_path,
                        stage=error_handler.Stage.VALIDATION,
                        reason=f"Failed to load compiled YAML map from {self._compiled_yaml_path}: {str(e)}",
                        exception=e,
                        correlation_id=self.correlation_id
                    )
                    raise ValueError(f"Compiled YAML map not accessible: {self._compiled_yaml_path}")
            else:
                # Explicit path was provided but doesn't exist - this is a validation error
                error_handler.handle_failure(
                    file_path=file_path,
                    stage=error_handler.Stage.VALIDATION,
                    reason=f"Compiled YAML map does not exist: {self._compiled_yaml_path}",
                    exception=None,
                    correlation_id=self.correlation_id
                )
                raise ValueError(f"Compiled YAML map does not exist: {self._compiled_yaml_path}")
        
        # Fallback: discover schema by filename (legacy behavior)
        path = Path(file_path)
        base_name = path.stem
        
        # Look for compiled schema
        schema_file = Path(self._compiled_schema_dir) / f"{base_name}.yaml"
        
        if schema_file.exists():
            try:
                with open(schema_file, "r") as f:
                    return yaml.safe_load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load compiled schema: {e}")
        
        # Try to find source DSL and compile
        source_schema = Path(self._schema_dir) / f"{base_name}.txt"
        if source_schema.exists():
            try:
                return schema_compiler.compile_dsl(
                    str(source_schema),
                    compiled_dir=self._compiled_schema_dir,
                    correlation_id=self.correlation_id
                )
            except Exception as e:
                self.logger.warning(f"Failed to compile schema: {e}")
        
        return None
    
    def transform(self, raw_data: Dict[str, Any], map_yaml: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw CSV data using mapping rules.
        
        Args:
            raw_data: Raw parsed CSV data
            map_yaml: Mapping configuration
            
        Returns:
            Transformed data dictionary
        """
        self.logger.info("Transforming CSV data")
        
        # Use mapper to apply mapping rules
        transformed = mapper.map_data(raw_data, map_yaml)
        
        # Add expected envelope
        if "envelope" not in transformed:
            transformed["envelope"] = {}
        
        transformed["envelope"]["schema_version"] = map_yaml.get("schema_version", "1.0")
        transformed["envelope"]["transaction_type"] = map_yaml.get("transaction_type", "unknown")
        transformed["envelope"]["input_format"] = map_yaml.get("input_format", "CSV")
        
        self.logger.info(
            "CSV transformation complete",
            header_fields=len(transformed.get("header", {})),
            line_count=len(transformed.get("lines", []))
        )
        
        return transformed
    
    def write_split(
        self,
        payload: Dict[str, Any],
        output_dir: str,
        split_key: str,
    ) -> List[str]:
        """Write transformed data split by a key field — one JSON per unique value.

        Groups lines by split_key, promotes split_key into header for each group,
        writes each group as a separate JSON file.

        Args:
            payload: Transformed data with {header, lines, summary}
            output_dir: Output directory
            split_key: Field name to group by (e.g., "InvoiceID")

        Returns:
            List of output file paths written
        """
        from collections import defaultdict

        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for line in payload.get("lines", []):
            key_val = str(line.get(split_key, "unknown"))
            groups[key_val].append(line)

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_paths: List[str] = []

        for key_val, lines in groups.items():
            split_payload = {
                "header": {**payload.get("header", {}), split_key: key_val},
                "lines": lines,
                "summary": payload.get("summary", {}),
            }
            out_path = str(out_dir / f"{split_key}_{key_val}.json")
            self.write(split_payload, out_path)
            output_paths.append(out_path)

        self.logger.info(
            "Split output by key",
            split_key=split_key,
            total_lines=len(payload.get("lines", [])),
            groups=len(groups),
        )
        return output_paths

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
DriverRegistry.register("csv", CSVHandler)
