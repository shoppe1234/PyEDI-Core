"""
Mapper module - YAML-driven transformation engine.

Applies mapping rules from YAML configuration files to transform
raw data (X12, CSV, XML) into standardized JSON intermediate format.

All business logic is expressed in YAML - no hardcoded transformation logic.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import yaml

from . import logger

# Registry of transform functions
_TRANSFORM_REGISTRY: Dict[str, Callable] = {}


def register_transform(name: str) -> Callable:
    """
    Decorator to register a transform function.
    
    Usage:
        @register_transform('to_float')
        def to_float(value):
            return float(value)
    """
    def decorator(func: Callable) -> Callable:
        _TRANSFORM_REGISTRY[name] = func
        return func
    return decorator


# Built-in transform functions

@register_transform('to_float')
def transform_to_float(value: Any) -> Optional[float]:
    """Convert value to float."""
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(',', ''))
    except (ValueError, TypeError):
        return None


@register_transform('to_int')
def transform_to_int(value: Any) -> Optional[int]:
    """Convert value to integer."""
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(',', '')))
    except (ValueError, TypeError):
        return None


@register_transform('to_string')
def transform_to_string(value: Any) -> str:
    """Convert value to string."""
    if value is None:
        return ""
    return str(value).strip()


@register_transform('to_date')
def transform_to_date(value: Any, format: str = '%m/%d/%Y') -> Optional[str]:
    """Convert value to ISO date string."""
    if value is None or value == "":
        return None
    try:
        dt = datetime.strptime(str(value), format)
        return dt.date().isoformat()
    except ValueError:
        return None


@register_transform('to_datetime')
def transform_to_datetime(value: Any, format: str = '%m/%d/%Y %H:%M:%S') -> Optional[str]:
    """Convert value to ISO datetime string."""
    if value is None or value == "":
        return None
    try:
        dt = datetime.strptime(str(value), format)
        return dt.isoformat()
    except ValueError:
        return None


@register_transform('strip')
def transform_strip(value: Any) -> str:
    """Strip whitespace from value."""
    if value is None:
        return ""
    return str(value).strip()


@register_transform('upper')
def transform_upper(value: Any) -> str:
    """Convert value to uppercase."""
    if value is None:
        return ""
    return str(value).upper()


@register_transform('lower')
def transform_lower(value: Any) -> str:
    """Convert value to lowercase."""
    if value is None:
        return ""
    return str(value).lower()


@register_transform('default')
def transform_default(value: Any, default_value: Any = "") -> Any:
    """Return default value if value is empty, otherwise return value."""
    if value is None or value == "":
        return default_value
    return value


@register_transform('substring')
def transform_substring(value: Any, start: int = 0, end: Optional[int] = None) -> str:
    """Extract substring from value."""
    if value is None:
        return ""
    s = str(value)
    return s[start:end] if end else s[start:]


@register_transform('replace')
def transform_replace(value: Any, pattern: str = '', replacement: str = '') -> str:
    """Replace pattern in value."""
    if value is None:
        return ""
    return str(value).replace(pattern, replacement)


def load_map(map_file: str) -> Dict[str, Any]:
    """
    Load a YAML mapping file.
    
    Args:
        map_file: Path to the YAML map file
        
    Returns:
        Mapping configuration dictionary
        
    Raises:
        FileNotFoundError: If map file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    path = Path(map_file)
    if not path.exists():
        raise FileNotFoundError(f"Map file not found: {map_file}")
    
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_nested_value(data: Dict, path: str, delimiter: str = '.') -> Any:
    """
    Get a nested value from a dictionary using dot notation.
    
    Args:
        data: Dictionary to search
        path: Dot-separated path (e.g., "header.invoice_id")
        delimiter: Path delimiter
        
    Returns:
        Value at the path, or None if not found
    """
    if not path:
        return None
    
    parts = path.split(delimiter)
    current = data
    
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            current = current[idx] if idx < len(current) else None
        else:
            return None
        
        if current is None:
            return None
    
    return current


def _apply_transform(value: Any, transform_config: Union[str, Dict]) -> Any:
    """
    Apply a transform function to a value.
    
    Args:
        value: Input value
        transform_config: Transform name (string) or config dict
        
    Returns:
        Transformed value
    """
    if transform_config is None:
        return value
    
    # Handle simple transform name
    if isinstance(transform_config, str):
        transform_name = transform_config
        transform_params = {}
    else:
        transform_name = transform_config.get('name')
        transform_params = {k: v for k, v in transform_config.items() if k != 'name'}
    
    if not transform_name:
        return value
    
    # Look up transform function
    transform_func = _TRANSFORM_REGISTRY.get(transform_name)
    if not transform_func:
        logger.warning(f"Unknown transform: {transform_name}")
        return value
    
    # Apply transform with parameters
    try:
        # Include value as first argument
        if transform_params:
            return transform_func(value, **transform_params)
        else:
            return transform_func(value)
    except Exception as e:
        logger.warning(f"Transform '{transform_name}' failed: {e}")
        return value


def _map_field(value: Any, mapping_rule: Dict[str, Any]) -> Any:
    """
    Apply a single mapping rule to a value.
    
    Args:
        value: Source value
        mapping_rule: Mapping rule configuration
        
    Returns:
        Mapped value
    """
    if value is None:
        # Check for default value in rule
        if 'default' in mapping_rule:
            return mapping_rule['default']
        return None
    
    # Apply transform if specified
    if 'transform' in mapping_rule:
        value = _apply_transform(value, mapping_rule['transform'])
    
    return value


def map_data(data: Dict[str, Any], map_yaml: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply mapping rules to transform raw data to intermediate format.
    
    Args:
        data: Raw input data dictionary
        map_yaml: Mapping configuration from YAML
        
    Returns:
        Transformed data dictionary with header, lines, summary
    """
    mapping_config = map_yaml.get("mapping", {})
    result = {
        "header": {},
        "lines": [],
        "summary": {}
    }
    
    # Map header fields
    header_mapping = mapping_config.get("header", {})
    for target_field, rule in header_mapping.items():
        if isinstance(rule, dict):
            source_path = rule.get("source", target_field)
            value = _get_nested_value(data, source_path)
            result["header"][target_field] = _map_field(value, rule)
        else:
            # Simple mapping - source = target
            value = _get_nested_value(data, rule)
            result["header"][target_field] = value
    
    # Map line items
    lines_mapping = mapping_config.get("lines", [])
    raw_lines = data.get("lines", [])
    
    if not raw_lines:
        # Try to find lines in data directly
        for key, value in data.items():
            if isinstance(value, list) and len(value) > 0:
                # Use first list found as lines
                raw_lines = value
                break
    
    for raw_line in raw_lines:
        mapped_line = {}
        
        # Handle different line mapping formats
        if isinstance(lines_mapping, list):
            for line_rule in lines_mapping:
                if isinstance(line_rule, dict):
                    for target_field, rule in line_rule.items():
                        if isinstance(rule, dict):
                            source_path = rule.get("source", target_field)
                            value = _get_nested_value(raw_line, source_path)
                            mapped_line[target_field] = _map_field(value, rule)
                        else:
                            value = _get_nested_value(raw_line, rule)
                            mapped_line[target_field] = value
                elif isinstance(line_rule, str):
                    # Simple field passthrough
                    mapped_line[line_rule] = raw_line.get(line_rule)
        
        if mapped_line:
            result["lines"].append(mapped_line)
    
    # Map summary fields
    summary_mapping = mapping_config.get("summary", {})
    for target_field, rule in summary_mapping.items():
        if isinstance(rule, dict):
            source_path = rule.get("source", target_field)
            value = _get_nested_value(data, source_path)
            result["summary"][target_field] = _map_field(value, rule)
        else:
            value = _get_nested_value(data, rule)
            result["summary"][target_field] = value
    
    return result


def validate_mapping_config(map_yaml: Dict[str, Any]) -> List[str]:
    """
    Validate a mapping configuration.
    
    Args:
        map_yaml: Mapping configuration dictionary
        
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    # Check required top-level keys
    required_keys = ["transaction_type", "input_format"]
    map_keys = map_yaml.keys() if isinstance(map_yaml, dict) else []
    for key in required_keys:
        if key not in map_keys:
            errors.append(f"Missing required key: {key}")
    
    # Validate mapping structure
    if "mapping" in map_yaml:
        mapping = map_yaml["mapping"]
        if not isinstance(mapping, dict):
            errors.append("mapping must be a dictionary")
        
        # Validate header, lines, summary
        for section in ["header", "lines", "summary"]:
            if section in mapping and not isinstance(mapping[section], (dict, list)):
                errors.append(f"mapping.{section} must be a dict or list")
    
    return errors


def list_available_transforms() -> List[str]:
    """
    Get list of available transform function names.
    
    Returns:
        List of transform names
    """
    return list(_TRANSFORM_REGISTRY.keys())
