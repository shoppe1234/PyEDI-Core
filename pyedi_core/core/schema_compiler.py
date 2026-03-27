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
        result["fieldIdentifier"] = identifier_match.group(1).strip()
        
    # Extract field definitions
    # Pattern: field_name Type
    valid_types = ["String", "string", "Integer", "int", "Decimal", "float", 
                   "double", "Boolean", "bool", "Date", "datetime"]
    type_or = '|'.join(valid_types)
    field_pattern = re.compile(
        rf'^\s*([A-Za-z0-9_]+)\s+({type_or})', re.MULTILINE
    )
    
    attr_kv_pattern = re.compile(r'(\w+)\s*=\s*(\w+|"[^"]*")')

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
            "dsl_type": field_type,
            "required": True
        }

        # Parse parenthesized field attributes: (length = 10, readEmptyAsNull = true, ...)
        after_match = match.end()
        remaining = record_text[after_match:]
        stripped = remaining.lstrip()
        if stripped.startswith("("):
            paren_start = after_match + (len(remaining) - len(stripped))
            paren_end = record_text.find(")", paren_start)
            if paren_end != -1:
                attr_text = record_text[paren_start + 1:paren_end]
                for kv in attr_kv_pattern.finditer(attr_text):
                    key, value = kv.group(1), kv.group(2).strip('"')
                    if key == "length":
                        field_def["length"] = int(value)
                    elif key == "readEmptyAsNull" and value == "true":
                        field_def["read_empty_as_null"] = True

        result["fields"].append(field_def)
    
    return result


def _parse_record_sequences(dsl_text: str, record_defs: List[Dict]) -> Dict[str, Any]:
    """
    Parse recordSequence blocks from DSL text and resolve member record IDs.

    Args:
        dsl_text: Raw DSL file content
        record_defs: Parsed record definitions (from _parse_dsl_record)

    Returns:
        Dict mapping group name to group metadata with resolved record IDs.
    """
    # Build DSL class name → fieldIdentifier mapping (e.g., TpmHdr → TPM_HDR)
    name_to_id: Dict[str, str] = {}
    for rec in record_defs:
        rec_name = rec.get("name", "")
        fid = rec.get("fieldIdentifier")
        if rec_name and fid:
            name_to_id[rec_name] = fid

    # Find all recordSequence blocks using brace counting
    seq_pattern = re.compile(r'def\s+recordSequence\s+(\w+)\s*\{')
    groups: Dict[str, Any] = {}

    search_pos = 0
    while True:
        match = seq_pattern.search(dsl_text, search_pos)
        if not match:
            break

        group_name = match.group(1)
        brace_count = 0
        end_idx = -1

        for i in range(match.end() - 1, len(dsl_text)):
            if dsl_text[i] == '{':
                brace_count += 1
            elif dsl_text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break

        if end_idx == -1:
            search_pos = match.end()
            continue

        block_text = dsl_text[match.start():end_idx]
        search_pos = end_idx

        group: Dict[str, Any] = {
            "group_on_record": False,
            "member_records": [],
            "nested_groups": [],
        }

        # Check for groupOnRecord = true
        if re.search(r'groupOnRecord\s*=\s*true', block_text):
            group["group_on_record"] = True

        # Check for groupType
        gt_match = re.search(r'groupType\s*=\s*(\w+)', block_text)
        if gt_match:
            group["group_type"] = gt_match.group(1)

        # Parse members: _varName TypeName [cardinality] or _varName TypeName []
        member_pattern = re.compile(r'_\w+\s+(\w+)\s+\[([^\]]*)\]')
        for mem in member_pattern.finditer(block_text):
            type_name = mem.group(1)
            # Check if this is a nested group (references another recordSequence)
            # or a record (has a fieldIdentifier mapping)
            if type_name in name_to_id:
                group["member_records"].append(name_to_id[type_name])
            else:
                # Could be a nested group reference (e.g., OinDtl1Group)
                group["nested_groups"].append(type_name)

        groups[group_name] = group

    # Flatten nested groups: collect all member_records transitively
    def _collect_all_records(group_name: str, visited: Optional[set] = None) -> List[str]:
        if visited is None:
            visited = set()
        if group_name in visited:
            return []
        visited.add(group_name)
        g = groups.get(group_name)
        if not g:
            return []
        records = list(g["member_records"])
        for nested in g.get("nested_groups", []):
            records.extend(_collect_all_records(nested, visited))
        return records

    # Add all_member_records (flattened) to each group
    for gname, gdata in groups.items():
        gdata["all_member_records"] = _collect_all_records(gname)

    # For the primary group (group_on_record=true), identify boundary_record and key_field
    for gdata in groups.values():
        if gdata.get("group_on_record"):
            # The boundary record is the first member that contains invoiceNumber
            # Look through record_defs to find which record has an invoiceNumber field
            for rec_id in gdata["member_records"]:
                rec_def = next((r for r in record_defs if r.get("fieldIdentifier") == rec_id), None)
                if rec_def:
                    field_names = [f["name"] for f in rec_def.get("fields", [])]
                    if "invoiceNumber" in field_names or "InvoiceID" in field_names:
                        key_field = "invoiceNumber" if "invoiceNumber" in field_names else "InvoiceID"
                        gdata["boundary_record"] = rec_id
                        gdata["key_field"] = key_field
                        break

    return groups


def _compile_to_yaml(record_defs: List[Dict], source_filename: str, delimiter: str = ",", format_type: str = "CSV", dsl_content: str = "") -> Dict[str, Any]:
    """
    Compile record definitions to standard YAML map format.

    Args:
        record_defs: List of parsed record definitions
        source_filename: Original source filename (for context)
        delimiter: The delimited text file's delimiter (extracted from DSL)
        format_type: "FIXED_WIDTH" or "CSV"

    Returns:
        Standard PyEDI YAML map structure
    """
    # Determine transaction type from filename
    base_name = Path(source_filename).stem
    
    # Try to extract transaction type (e.g., 810, 850)
    transaction_type_match = re.search(r'(\d{3})', base_name)
    transaction_type = transaction_type_match.group(1) if transaction_type_match else base_name.upper()
    
    # Build the YAML map structure
    schema_section: Dict[str, Any] = {
        "columns": [],
        "records": {}
    }
    if format_type != "FIXED_WIDTH":
        schema_section["delimiter"] = delimiter
    if format_type == "FIXED_WIDTH":
        schema_section["record_layouts"] = {}

    yaml_map = {
        "transaction_type": f"{transaction_type}_INVOICE" if transaction_type.isdigit() else transaction_type,
        "input_format": format_type,
        "schema": schema_section,
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

        # Build record_layouts entry for fixed-width schemas
        if format_type == "FIXED_WIDTH" and "fieldIdentifier" in record_def:
            layout = []
            for field in record_def.get("fields", []):
                layout.append({"name": field["name"], "width": field.get("length", 0)})
            yaml_map["schema"]["record_layouts"][record_key] = layout

        for field in record_def.get("fields", []):
            field_name = field["name"]

            if "fieldIdentifier" in record_def:
                yaml_map["schema"]["records"][record_key].append(field_name)

            # Build column entry with optional width attributes
            col_entry: Dict[str, Any] = {
                "name": field_name,
                "type": field.get("type", "string"),
                "required": field.get("required", True),
            }
            if field.get("length") is not None:
                col_entry["width"] = field["length"]
            if field.get("read_empty_as_null"):
                col_entry["read_empty_as_null"] = True

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
                yaml_map["schema"]["columns"].append(col_entry)
            else:
                if record_type == "header":
                    yaml_map["mapping"]["header"][field_name] = {
                        "source": source_path
                    }
                    yaml_map["schema"]["columns"].append(col_entry)

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
                        yaml_map["schema"]["columns"].append(col_entry)

                elif record_type == "summary":
                    yaml_map["mapping"]["summary"][field_name] = {
                        "source": source_path
                    }
                    # Add to schema columns if not already there
                    if not any(c["name"] == field_name for c in yaml_map["schema"]["columns"]):
                        yaml_map["schema"]["columns"].append(col_entry)
    
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
            # Preserve width from whichever has it
            if col.get("width") and not seen[name].get("width"):
                seen[name]["width"] = col["width"]
            if col.get("read_empty_as_null") and not seen[name].get("read_empty_as_null"):
                seen[name]["read_empty_as_null"] = col["read_empty_as_null"]
    yaml_map["schema"]["columns"] = list(seen.values())

    # Build record_inventory summary
    records = yaml_map["schema"].get("records", {})
    if records:
        inventory = []
        for rec_key, fields in records.items():
            inventory.append({
                "fieldIdentifier": rec_key,
                "field_count": len(fields) if isinstance(fields, list) else 0,
            })
        yaml_map["schema"]["record_inventory"] = inventory

    # Parse and emit record_groups for fixed-width schemas with hierarchy
    if format_type == "FIXED_WIDTH" and dsl_content:
        record_groups = _parse_record_sequences(dsl_content, record_defs)
        if record_groups:
            yaml_map["record_groups"] = {}
            for gname, gdata in record_groups.items():
                entry: Dict[str, Any] = {
                    "member_records": gdata.get("all_member_records", []),
                }
                if gdata.get("group_on_record"):
                    entry["group_on_record"] = True
                if gdata.get("boundary_record"):
                    entry["boundary_record"] = gdata["boundary_record"]
                if gdata.get("key_field"):
                    entry["key_field"] = gdata["key_field"]
                if gdata.get("group_type"):
                    entry["group_type"] = gdata["group_type"]
                if gdata.get("nested_groups"):
                    entry["nested_groups"] = gdata["nested_groups"]
                yaml_map["record_groups"][gname] = entry

    return yaml_map


def parse_dsl_file(source_file: str) -> Tuple[List[Dict[str, Any]], str, str]:
    """
    Parse a DSL file into record definitions, delimiter, and format type.

    Args:
        source_file: Path to the source .txt DSL file

    Returns:
        Tuple of (record_defs, delimiter, format_type) where format_type
        is "FIXED_WIDTH" if any field has a length attribute, else "CSV".

    Raises:
        FileNotFoundError: If source file doesn't exist
        ValueError: If no valid record definitions found
    """
    source_path = Path(source_file)
    if not source_path.exists():
        raise FileNotFoundError(f"Source DSL file not found: {source_file}")

    with open(source_path, "r", encoding="utf-8") as f:
        dsl_content = f.read()

    # Extract delimiter if defined
    delimiter = ","
    delim_match = re.search(r'delimiter\s*=\s*[\'"]([^\'"]+)[\'"]', dsl_content)
    if delim_match:
        delimiter = delim_match.group(1)

    # Parse record definitions using brace counting
    record_matches: List[str] = []
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

    record_defs = [_parse_dsl_record(m) for m in record_matches]

    has_lengths = any(
        fld.get("length") is not None
        for rec in record_defs
        for fld in rec.get("fields", [])
    )
    format_type = "FIXED_WIDTH" if has_lengths else "CSV"

    return record_defs, delimiter, format_type, dsl_content


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

    record_defs, delimiter, format_type, dsl_content = parse_dsl_file(source_file)

    # Compile to YAML format
    yaml_map = _compile_to_yaml(record_defs, source_filename, delimiter, format_type, dsl_content)
    
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


def parse_xsd_file(source_file: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Parse an XSD file into record definitions and hierarchy metadata.

    Args:
        source_file: Path to the source XSD file

    Returns:
        Tuple of (record_defs, hierarchy_metadata)
        record_defs: list of {"name", "type", "fields": [{"name", "type"}]}
        hierarchy_metadata: {"root_element", "transaction_element", "header_path",
                             "line_container_path", "line_element", "transmission_header_path"}

    Raises:
        FileNotFoundError: If source file doesn't exist
        ValueError: If XSD structure cannot be parsed
    """
    import defusedxml.ElementTree as DET

    source_path = Path(source_file)
    if not source_path.exists():
        raise FileNotFoundError(f"Source XSD file not found: {source_file}")

    XS = "{http://www.w3.org/2001/XMLSchema}"
    XSD_TYPE_MAP: Dict[str, str] = {
        "xs:string": "string", "xs:float": "float", "xs:decimal": "float",
        "xs:integer": "integer", "xs:int": "integer", "xs:boolean": "boolean",
        "xs:date": "date", "xs:dateTime": "date",
    }

    def _get_sequence(elem: Any) -> Any:
        ct = elem.find(f"{XS}complexType")
        if ct is not None:
            return ct.find(f"{XS}sequence")
        return None

    def _extract_fields(elem: Any, prefix: str = "") -> List[Dict[str, Any]]:
        """Recursively extract fields with dot-notation paths."""
        fields: List[Dict[str, Any]] = []
        seq = _get_sequence(elem)
        if seq is None:
            return fields
        for child in seq:
            if child.tag != f"{XS}element":
                continue
            name = child.get("name")
            if not name:
                continue
            ftype = child.get("type")
            full_name = f"{prefix}.{name}" if prefix else name
            if ftype:
                mapped = XSD_TYPE_MAP.get(ftype, "string")
                fields.append({"name": full_name, "type": mapped})
            else:
                nested = _extract_fields(child, full_name)
                fields.extend(nested)
        return fields

    tree = DET.parse(source_file)
    root = tree.getroot()

    # Root xs:element
    root_elem = root.find(f"{XS}element")
    if root_elem is None:
        raise ValueError(f"No root element found in {source_file}")

    root_element_name: str = root_elem.get("name", "")
    root_seq = _get_sequence(root_elem)
    if root_seq is None:
        raise ValueError(f"No sequence under root element in {source_file}")

    record_defs: List[Dict[str, Any]] = []
    transmission_header_name: Optional[str] = None
    transaction_element_name: Optional[str] = None
    header_name: Optional[str] = None
    line_container_name: Optional[str] = None
    line_element_name: Optional[str] = None

    for child in root_seq:
        if child.tag != f"{XS}element":
            continue
        name: str = child.get("name", "")
        child_seq = _get_sequence(child)
        if child_seq is None:
            continue

        # Check whether any grandchild's sequence has an unbounded element
        has_transaction_structure = False
        for gc in child_seq:
            if gc.tag != f"{XS}element":
                continue
            gc_seq = _get_sequence(gc)
            if gc_seq is not None:
                for ggc in gc_seq:
                    if ggc.tag == f"{XS}element" and ggc.get("maxOccurs") == "unbounded":
                        has_transaction_structure = True
                        break
            if has_transaction_structure:
                break

        if has_transaction_structure:
            transaction_element_name = name
            for gc in child_seq:
                if gc.tag != f"{XS}element":
                    continue
                gc_name: str = gc.get("name", "")
                gc_seq = _get_sequence(gc)
                if gc_seq is None:
                    continue
                has_unbounded = any(
                    ggc.tag == f"{XS}element" and ggc.get("maxOccurs") == "unbounded"
                    for ggc in gc_seq
                )
                if has_unbounded:
                    line_container_name = gc_name
                    for ggc in gc_seq:
                        if ggc.tag == f"{XS}element" and ggc.get("maxOccurs") == "unbounded":
                            line_element_name = ggc.get("name", "")
                            line_fields = _extract_fields(ggc)
                            record_defs.append({
                                "name": line_element_name,
                                "type": "line",
                                "fields": line_fields,
                            })
                            break
                else:
                    header_name = gc_name
                    header_fields = _extract_fields(gc)
                    record_defs.insert(0, {
                        "name": gc_name,
                        "type": "header",
                        "fields": header_fields,
                    })
        else:
            transmission_header_name = name
            trans_fields = _extract_fields(child)
            record_defs.insert(0, {
                "name": name,
                "type": "transmission",
                "fields": trans_fields,
            })

    if not record_defs:
        raise ValueError(f"No record definitions found in {source_file}")

    hierarchy_metadata: Dict[str, Any] = {
        "root_element": root_element_name,
        "transaction_element": transaction_element_name,
        "header_path": (
            f"{transaction_element_name}/{header_name}"
            if transaction_element_name and header_name else None
        ),
        "line_container_path": (
            f"{transaction_element_name}/{line_container_name}"
            if transaction_element_name and line_container_name else None
        ),
        "line_element": line_element_name,
        "transmission_header_path": transmission_header_name,
    }

    return record_defs, hierarchy_metadata


def _compile_xsd_to_yaml(
    record_defs: List[Dict[str, Any]],
    hierarchy: Dict[str, Any],
    source_filename: str,
) -> Dict[str, Any]:
    """
    Compile XSD record definitions to standard YAML map format.

    Args:
        record_defs: Parsed record definitions from parse_xsd_file
        hierarchy: Hierarchy metadata from parse_xsd_file
        source_filename: Original XSD filename (for transaction_type derivation)

    Returns:
        Standard PyEDI YAML map structure for XML
    """
    base_name = Path(source_filename).stem
    transaction_type = re.sub(r"[^A-Z0-9]+", "_", base_name.upper()).strip("_")

    all_columns: List[Dict[str, Any]] = []
    seen_col_names: set = set()
    for rec in record_defs:
        for field in rec.get("fields", []):
            fname = field["name"]
            if fname not in seen_col_names:
                seen_col_names.add(fname)
                all_columns.append({"name": fname, "type": field["type"]})

    records_section: Dict[str, Any] = {}
    for rec in record_defs:
        records_section[rec["name"]] = [f["name"] for f in rec.get("fields", [])]

    # Header mapping: source uses "header.<field>" path so mapper.map_data resolves correctly
    header_mapping: Dict[str, Any] = {}
    for rec in record_defs:
        if rec["type"] in ("header", "transmission"):
            for field in rec.get("fields", []):
                fname = field["name"]
                header_mapping[fname] = {"source": f"header.{fname}"}

    # Lines mapping: list-of-dicts format expected by mapper
    lines_mapping: List[Dict[str, Any]] = []
    for rec in record_defs:
        if rec["type"] == "line":
            for field in rec.get("fields", []):
                fname = field["name"]
                lines_mapping.append({fname: {"source": fname}})

    return {
        "transaction_type": transaction_type,
        "input_format": "XML",
        "xml_config": {
            "namespace": None,
            "root_element": hierarchy.get("root_element"),
            "transaction_element": hierarchy.get("transaction_element"),
            "header_path": hierarchy.get("header_path"),
            "line_container_path": hierarchy.get("line_container_path"),
            "line_element": hierarchy.get("line_element"),
            "transmission_header_path": hierarchy.get("transmission_header_path"),
        },
        "schema": {
            "columns": all_columns,
            "records": records_section,
        },
        "mapping": {
            "header": header_mapping,
            "lines": lines_mapping,
            "summary": {},
        },
    }


def compile_xsd(
    source_file: str,
    compiled_dir: str = DEFAULT_SCHEMA_COMPILED_DIR,
    archive_dir: str = DEFAULT_SCHEMA_ARCHIVE_DIR,
    correlation_id: Optional[str] = None,
    target_yaml_path: Optional[str] = None,
    namespace: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compile an XSD file to YAML format with version awareness.

    Mirrors compile_dsl() — checks hash, archives on change, skips if unchanged.

    Args:
        source_file: Path to the source XSD file
        compiled_dir: Directory for compiled YAML maps
        archive_dir: Directory for archived previous versions
        correlation_id: Optional correlation ID for logging
        target_yaml_path: Explicit output path for compiled YAML
        namespace: XML namespace URI to record in xml_config

    Returns:
        Compiled YAML map as a dictionary

    Raises:
        FileNotFoundError: If source file doesn't exist
        ValueError: If XSD parsing fails
    """
    source_path = Path(source_file)
    if not source_path.exists():
        raise FileNotFoundError(f"Source XSD file not found: {source_file}")

    source_hash = compute_file_hash(str(source_path.absolute()))
    source_filename = source_path.name

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
        yaml_filename = source_path.stem + "_map.yaml"
        yaml_path = compiled_path / yaml_filename
        meta_filename = source_path.stem + "_map.meta.json"
        meta_path = compiled_path / meta_filename

    if yaml_path.exists() and meta_path.exists():
        with open(meta_path, "r") as f:
            meta = json.load(f)
        existing_hash = meta.get("source_hash", "")
        if existing_hash == source_hash:
            logger.info(
                "Schema unchanged, loading existing",
                source_file=source_filename,
                hash=source_hash[:16] + "...",
            )
            with open(yaml_path, "r") as f:
                return yaml.safe_load(f)

        logger.info(
            "Schema changed, archiving and recompiling",
            source_file=source_filename,
            old_hash=existing_hash[:16] + "...",
            new_hash=source_hash[:16] + "...",
        )
        archive_path = Path(archive_dir)
        archive_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if yaml_path.exists():
            yaml_path.rename(archive_path / f"{yaml_path.stem}_{timestamp}.yaml")
        if meta_path.exists():
            meta_path.rename(archive_path / f"{meta_path.stem}_{timestamp}.meta.json")

    logger.info("Compiling XSD schema", source_file=source_filename)

    record_defs, hierarchy = parse_xsd_file(source_file)
    yaml_map = _compile_xsd_to_yaml(record_defs, hierarchy, source_filename)

    if namespace:
        yaml_map["xml_config"]["namespace"] = namespace

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(yaml_map, f, default_flow_style=False, sort_keys=False)

    meta = {
        "source_file": source_filename,
        "source_hash": source_hash,
        "compiled_at": datetime.now().isoformat(),
        "compiled_yaml": yaml_filename,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    logger.info(f"Compiled XSD to {yaml_path}")
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
