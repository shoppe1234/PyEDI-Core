"""
Schema Compiler module - Version-Aware DSL Parser.

Parses proprietary .txt DSL files (def record { ... } blocks) into standard
PyEDI YAML map format. Designed to be idempotent and version-aware.

On every CSV file detection, checks if a compiled YAML exists in ./schemas/compiled/
If hash matches: load existing YAML and proceed
If hash differs: recompile, archive previous version, update meta.json
If no compiled YAML exists: compile and write fresh
"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from . import error_handler
from . import logger

# Default paths
DEFAULT_SCHEMA_SOURCE_DIR = "./schemas/source"
DEFAULT_SCHEMA_COMPILED_DIR = "./schemas/compiled"
DEFAULT_SCHEMA_ARCHIVE_DIR = "./schemas/compiled/archive"


def compute_file_hash(file_path: str) -> str:
    """
    Compute SHA-256 hash of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Hexadecimal SHA-256 hash string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def _parse_dsl_record(record_text: str) -> Dict[str, Any]:
    """
    Parse a single record definition from DSL text.
    
    Args:
        record_text: Text content of a 'def record { ... }' block
        
    Returns:
        Dict with record metadata and fields
    """
    result = {
        "name": "",
        "type": "detail",
        "fields": []
    }
    
    # Extract record name
    name_match = re.search(r'def\s+record\s+(\w+)\s*\{', record_text)
    if name_match:
        result["name"] = name_match.group(1)
    
    # Determine record type (header/detail/summary)
    if "header" in result["name"].lower():
        result["type"] = "header"
    elif "summary" in result["name"].lower():
        result["type"] = "summary"
    else:
        result["type"] = "detail"
        
    # Extract field identifier
    identifier_match = re.search(r'fieldIdentifier\s*\{\s*value\s*=\s*"([^"]+)"', record_text)
    if identifier_match:
        result["fieldIdentifier"] = identifier_match.group(1)
        
    # Extract field definitions
    # Pattern: field_name Type
    valid_types = ["String", "string", "Integer", "int", "Decimal", "float", 
                   "double", "Boolean", "bool", "Date", "datetime"]
    type_or = '|'.join(valid_types)
    field_pattern = re.compile(
        rf'^\s*([A-Za-z0-9_]+)\s+({type_or})', re.MULTILINE
    )
    
    for match in field_pattern.finditer(record_text):
        field_name = match.group(1)
        field_type = match.group(2)
        # Map DSL types to YAML types
        type_mapping = {
            "String": "string",
            "string": "string",
            "Integer": "integer",
            "int": "integer",
            "Decimal": "float",
            "float": "float",
            "double": "float",
            "Boolean": "boolean",
            "bool": "boolean",
            "Date": "date",
            "datetime": "date",
        }
        
        field_def = {
            "name": field_name,
            "type": type_mapping.get(field_type, "string"),
            "required": True
        }
        
        result["fields"].append(field_def)
    
    return result


def _compile_to_yaml(record_defs: List[Dict], source_filename: str, delimiter: str = ",") -> Dict[str, Any]:
    """
    Compile record definitions to standard YAML map format.
    
    Args:
        record_defs: List of parsed record definitions
        source_filename: Original source filename (for context)
        delimiter: The delimited text file's delimiter (extracted from DSL)
        
    Returns:
        Standard PyEDI YAML map structure
    """
    # Determine transaction type from filename
    base_name = Path(source_filename).stem
    
    # Try to extract transaction type (e.g., 810, 850)
    transaction_type_match = re.search(r'(\d{3})', base_name)
    transaction_type = transaction_type_match.group(1) if transaction_type_match else base_name.upper()
    
    # Build the YAML map structure
    yaml_map = {
        "transaction_type": f"{transaction_type}_INVOICE" if transaction_type.isdigit() else transaction_type,
        "input_format": "CSV",
        "schema": {
            "delimiter": delimiter,
            "columns": [],
            "records": {}
        },
        "mapping": {
            "header": {},
            "lines": [],
            "summary": {}
        }
    }
    
    has_records = any("fieldIdentifier" in r for r in record_defs)
    
    # Process each record definition
    for record_def in record_defs:
        record_type = record_def.get("type", "detail")
        
        if "fieldIdentifier" in record_def:
            record_key = record_def["fieldIdentifier"]
            if record_key in yaml_map["schema"]["records"]:
                record_key = record_def.get("name", record_key)
            yaml_map["schema"]["records"][record_key] = []

        for field in record_def.get("fields", []):
            field_name = field["name"]

            if "fieldIdentifier" in record_def:
                yaml_map["schema"]["records"][record_key].append(field_name)
            
            # Determine source_path based on record type
            source_path = field_name
            if not has_records:
                if record_type == "header":
                    source_path = f"header.{field_name}"
                elif record_type == "summary":
                    source_path = f"summary.{field_name}"
            # For detail (or when we have records), source_path remains field_name
            
            if has_records:
                if not any(field_name in l for l in yaml_map["mapping"]["lines"]):
                    yaml_map["mapping"]["lines"].append({
                        field_name: {
                            "source": source_path
                        }
                    })
                # Add to schema columns logically
                yaml_map["schema"]["columns"].append({
                    "name": field_name,
                    "type": field.get("type", "string"),
                    "required": field.get("required", True)
                })
            else:
                if record_type == "header":
                    yaml_map["mapping"]["header"][field_name] = {
                        "source": source_path
                    }
                    # Add to schema columns
                    yaml_map["schema"]["columns"].append({
                        "name": field_name,
                        "type": field.get("type", "string"),
                        "required": field.get("required", True)
                    })
                    
                elif record_type == "detail":
                    # Only add if not already present 
                    if not any(field_name in l for l in yaml_map["mapping"]["lines"]):
                        yaml_map["mapping"]["lines"].append({
                            field_name: {
                                "source": source_path
                            }
                        })
                    
                    # Add to schema columns if not already there
                    if not any(c["name"] == field_name for c in yaml_map["schema"]["columns"]):
                        yaml_map["schema"]["columns"].append({
                            "name": field_name,
                            "type": field.get("type", "string"),
                            "required": field.get("required", True)
                        })
                        
                elif record_type == "summary":
                    yaml_map["mapping"]["summary"][field_name] = {
                        "source": source_path
                    }
                    # Add to schema columns if not already there
                    if not any(c["name"] == field_name for c in yaml_map["schema"]["columns"]):
                        yaml_map["schema"]["columns"].append({
                            "name": field_name,
                            "type": field.get("type", "string"),
                            "required": field.get("required", True)
                        })
    
    # Deduplicate columns by name, preferring the most specific type
    type_specificity = {"float": 5, "integer": 4, "date": 3, "boolean": 2, "string": 1}
    seen: Dict[str, Dict[str, Any]] = {}
    for col in yaml_map["schema"]["columns"]:
        name = col["name"]
        if name not in seen:
            seen[name] = col
        else:
            existing_rank = type_specificity.get(seen[name]["type"], 0)
            new_rank = type_specificity.get(col["type"], 0)
            if new_rank > existing_rank:
                seen[name] = col
    yaml_map["schema"]["columns"] = list(seen.values())

    return yaml_map


def compile_dsl(
    source_file: str,
    compiled_dir: str = DEFAULT_SCHEMA_COMPILED_DIR,
    archive_dir: str = DEFAULT_SCHEMA_ARCHIVE_DIR,
    correlation_id: Optional[str] = None,
    target_yaml_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compile a DSL file to YAML format with version awareness.
    
    Args:
        source_file: Path to the source .txt DSL file
        compiled_dir: Directory for compiled YAML maps
        archive_dir: Directory for archived previous versions
        correlation_id: Optional correlation ID for logging
        
    Returns:
        Compiled YAML map as a dictionary
        
    Raises:
        FileNotFoundError: If source file doesn't exist
        ValueError: If DSL parsing fails
    """
    source_path = Path(source_file)
    if not source_path.exists():
        raise FileNotFoundError(f"Source DSL file not found: {source_file}")
    
    # Compute hash of source file
    source_hash = compute_file_hash(str(source_path.absolute()))
    source_filename = source_path.name
    
    # Determine compiled YAML path
    if target_yaml_path:
        yaml_path = Path(target_yaml_path)
        compiled_path = yaml_path.parent
        compiled_path.mkdir(parents=True, exist_ok=True)
        yaml_filename = yaml_path.name
        meta_filename = yaml_path.stem + ".meta.json"
        meta_path = compiled_path / meta_filename
    else:
        compiled_path = Path(compiled_dir)
        compiled_path.mkdir(parents=True, exist_ok=True)
        yaml_filename = source_path.stem + ".yaml"
        yaml_path = compiled_path / yaml_filename
        meta_filename = source_path.stem + ".meta.json"
        meta_path = compiled_path / meta_filename
    
    # Check if compiled YAML already exists
    if yaml_path.exists() and meta_path.exists():
        # Load existing meta
        with open(meta_path, "r") as f:
            meta = json.load(f)
        
        existing_hash = meta.get("source_hash", "")
        
        if existing_hash == source_hash:
            # Hash matches - load existing YAML
            logger.info(
                f"Schema hash matches, loading existing compiled YAML",
                source_file=source_filename,
                hash=source_hash[:16] + "..."
            )
            
            with open(yaml_path, "r") as f:
                return yaml.safe_load(f)
        
        # Hash differs - archive and recompile
        logger.info(
            f"Schema hash differs, archiving and recompiling",
            source_file=source_filename,
            old_hash=existing_hash[:16] + "...",
            new_hash=source_hash[:16] + "..."
        )
        
        # Archive existing YAML
        archive_path = Path(archive_dir)
        archive_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_yaml = archive_path / f"{source_path.stem}_{timestamp}.yaml"
        archived_meta = archive_path / f"{source_path.stem}_{timestamp}.meta.json"
        
        if yaml_path.exists():
            yaml_path.rename(archived_yaml)
        if meta_path.exists():
            meta_path.rename(archived_meta)
        
        logger.info(f"Archived previous schema version: {archived_yaml}")
    
    # Compile the DSL file
    logger.info(f"Compiling DSL schema", source_file=source_filename)
    
    with open(source_path, "r", encoding="utf-8") as f:
        dsl_content = f.read()

    # Extract delimiter if defined
    delimiter = ","
    delim_match = re.search(r'delimiter\s*=\s*[\'"]([^\'"]+)[\'"]', dsl_content)
    if delim_match:
        delimiter = delim_match.group(1)
    
    # Parse record definitions using brace counting
    record_matches = []
    start_pattern = re.compile(r'def\s+record\s+\w+\s*\{')
    
    search_pos = 0
    while True:
        match = start_pattern.search(dsl_content, search_pos)
        if not match:
            break
            
        start_idx = match.start()
        brace_count = 0
        end_idx = -1
        
        for i in range(match.end() - 1, len(dsl_content)):
            if dsl_content[i] == '{':
                brace_count += 1
            elif dsl_content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
                    
        if end_idx != -1:
            record_matches.append(dsl_content[start_idx:end_idx])
            search_pos = end_idx
        else:
            break
    
    if not record_matches:
        raise ValueError(f"No valid record definitions found in {source_file}")
    
    record_defs = [_parse_dsl_record(match) for match in record_matches]
    
    # Compile to YAML format
    yaml_map = _compile_to_yaml(record_defs, source_filename, delimiter)
    
    # Write compiled YAML
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(yaml_map, f, default_flow_style=False, sort_keys=False)
    
    # Write meta.json
    meta = {
        "source_file": source_filename,
        "source_hash": source_hash,
        "compiled_at": datetime.now().isoformat(),
        "compiled_yaml": yaml_filename
    }
    
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    
    logger.info(f"Compiled schema to {yaml_path}")
    
    return yaml_map


def get_compiled_schema(
    source_file: str,
    compiled_dir: str = DEFAULT_SCHEMA_COMPILED_DIR,
    archive_dir: str = DEFAULT_SCHEMA_ARCHIVE_DIR,
    correlation_id: Optional[str] = None,
    target_yaml_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get compiled schema for a source file, compiling if necessary.
    
    Args:
        source_file: Path to the source .txt DSL file
        compiled_dir: Directory for compiled YAML maps
        archive_dir: Directory for archived previous versions
        correlation_id: Optional correlation ID for logging
        
    Returns:
        Compiled YAML map as a dictionary, or None if compilation fails
    """
    try:
        return compile_dsl(
            source_file=source_file,
            compiled_dir=compiled_dir,
            archive_dir=archive_dir,
            correlation_id=correlation_id,
            target_yaml_path=target_yaml_path
        )
    except Exception as e:
        logger.error(f"Failed to compile schema: {e}", source_file=source_file)
        return None


def list_compiled_schemas(compiled_dir: str = DEFAULT_SCHEMA_COMPILED_DIR) -> List[Dict[str, Any]]:
    """
    List all compiled schemas in the compiled directory.
    
    Args:
        compiled_dir: Directory to scan for compiled schemas
        
    Returns:
        List of schema info dicts
    """
    compiled_path = Path(compiled_dir)
    if not compiled_path.exists():
        return []
    
    schemas = []
    for meta_file in compiled_path.glob("*.meta.json"):
        try:
            with open(meta_file, "r") as f:
                meta = json.load(f)
                schemas.append(meta)
        except (IOError, json.JSONDecodeError):
            continue
    
    return schemas


def get_schema_hash(schema_file: str) -> Optional[str]:
    """
    Get the source hash for a compiled schema.
    
    Args:
        schema_file: Path to the schema file
        
    Returns:
        Source hash string or None
    """
    meta_file = Path(schema_file).with_suffix(".meta.json")
    if not meta_file.exists():
        return None
    
    try:
        with open(meta_file, "r") as f:
            meta = json.load(f)
            return meta.get("source_hash")
    except (IOError, json.JSONDecodeError):
        return None
