"""
XML Handler - Generic and cXML driver for XML files.

Handles XML file processing with auto-detection of cXML format.
Generic XML uses Python's built-in xml.etree.ElementTree.
cXML adds XPath-style source path awareness.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import defusedxml.ElementTree as ET
from xml.etree.ElementTree import Element

from ..core import error_handler
from ..core import logger as core_logger
from ..core import mapper
from .base import TransactionProcessor


class XMLHandler(TransactionProcessor):
    """
    Transaction processor for XML and cXML files.
    
    Auto-detects cXML format and uses appropriate parsing strategy.
    """
    
    def __init__(
        self,
        correlation_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        rules_dir: Optional[str] = None
    ):
        """
        Initialize XML handler.
        
        Args:
            correlation_id: Optional correlation ID
            config: Configuration dictionary
            rules_dir: Directory for mapping rules
        """
        super().__init__(correlation_id, config)
        self._rules_dir = rules_dir or "./rules"
    
    def set_compiled_yaml_path(self, compiled_yaml_path: str) -> None:
        """
        Store compiled YAML path for schema-aware parsing.

        Args:
            compiled_yaml_path: Path to the compiled YAML map file
        """
        self._compiled_yaml_path = compiled_yaml_path

    def _strip_namespace(self, element: Element) -> None:
        """
        Recursively strip XML namespace from all element tags.

        Handles both Clark notation {uri}Tag and prefix:Tag patterns.

        Args:
            element: Root element to strip namespaces from
        """
        import re as _re
        # Clark notation: {http://...}TagName -> TagName
        if element.tag and element.tag.startswith("{"):
            element.tag = element.tag.split("}", 1)[1]
        elif ":" in element.tag:
            # prefix:TagName -> TagName
            element.tag = element.tag.split(":", 1)[1]
        for child in element:
            self._strip_namespace(child)

    def _elem_to_dict(self, element: Element) -> Any:
        """
        Convert an XML element to a dict (nested) or string (leaf).

        Args:
            element: XML element

        Returns:
            String for leaf elements, dict for complex elements
        """
        children = list(element)
        if not children:
            text = element.text or ""
            return text.strip()
        result: Dict[str, Any] = {}
        for child in children:
            value = self._elem_to_dict(child)
            if child.tag in result:
                existing = result[child.tag]
                if not isinstance(existing, list):
                    result[child.tag] = [existing]
                result[child.tag].append(value)
            else:
                result[child.tag] = value
        return result

    def _parse_schema_aware_xml(
        self, content: bytes, xml_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse XML using compiled XSD xml_config for structured extraction.

        Args:
            content: Raw XML bytes
            xml_config: xml_config section from compiled YAML

        Returns:
            {"header": {...}, "lines": [...], "summary": {}}
        """
        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise ValueError(f"Failed to parse XML: {exc}") from exc

        self._strip_namespace(root)

        result: Dict[str, Any] = {"header": {}, "lines": [], "summary": {}}

        # Extract transmission header fields (prefixed with transmission_)
        trans_path = xml_config.get("transmission_header_path")
        if trans_path:
            trans_elem = root.find(trans_path)
            if trans_elem is not None:
                for child in trans_elem:
                    result["header"][child.tag] = (child.text or "").strip()

        # Navigate to header element
        header_path = xml_config.get("header_path")
        transaction_element = xml_config.get("transaction_element")
        if header_path and transaction_element:
            # header_path is relative to root, e.g. "ASBN/ASBNHeader"
            # strip the transaction_element prefix to get path under it
            txn_elems = root.findall(transaction_element)
            for txn_elem in txn_elems:
                # Extract the sub-path after transaction_element
                sub_path = header_path[len(transaction_element):].lstrip("/")
                header_elem = txn_elem.find(sub_path) if sub_path else txn_elem
                if header_elem is not None:
                    for child in header_elem:
                        value = self._elem_to_dict(child)
                        result["header"][child.tag] = value

                # Extract line items
                line_container_path = xml_config.get("line_container_path")
                line_element = xml_config.get("line_element")
                if line_container_path and line_element:
                    lc_sub = line_container_path[len(transaction_element):].lstrip("/")
                    container_elem = txn_elem.find(lc_sub) if lc_sub else txn_elem
                    if container_elem is not None:
                        for item_elem in container_elem.findall(line_element):
                            line: Dict[str, Any] = {}
                            for child in item_elem:
                                line[child.tag] = self._elem_to_dict(child)
                            if line:
                                result["lines"].append(line)

        return result

    def read(self, file_path: str) -> Dict[str, Any]:
        """
        Read and parse an XML file.
        
        Args:
            file_path: Path to XML file
            
        Returns:
            Raw parsed data as dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If XML cannot be parsed
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"XML file not found: {file_path}")
        
        self.logger.info(f"Reading XML file", file_path=file_path)
        
        # Read file content as bytes (let ET handle encoding declarations)
        with open(file_path, "rb") as f:
            content = f.read()

        # Schema-aware parsing (when compiled YAML is available)
        if getattr(self, "_compiled_yaml_path", None):
            import yaml as _yaml
            with open(self._compiled_yaml_path, "r", encoding="utf-8") as f:
                compiled = _yaml.safe_load(f)
            xml_config = compiled.get("xml_config")
            if xml_config:
                parsed = self._parse_schema_aware_xml(content, xml_config)
                parsed["_source_file"] = path.name
                return parsed

        # Detect cXML (decode first 500 bytes for detection)
        is_cxml = self._detect_cxml(content[:500].decode("utf-8", errors="replace"))

        if is_cxml:
            self.logger.info("Detected cXML format")
            parsed = self._parse_cxml(content)
        else:
            self.logger.info("Detected generic XML format")
            parsed = self._parse_generic_xml(content)

        # Add metadata
        parsed["_is_cxml"] = is_cxml
        parsed["_source_file"] = path.name

        return parsed
    
    def _detect_cxml(self, content: str) -> bool:
        """
        Detect if content is cXML.
        
        Args:
            content: XML file content
            
        Returns:
            True if cXML, False otherwise
        """
        # Check for cXML root element or DOCTYPE
        if "cXML" in content[:500] or "DOCTYPE cXML" in content:
            return True
        return False
    
    def _parse_generic_xml(self, content: str) -> Dict[str, Any]:
        """
        Parse generic XML using ElementTree.
        
        Args:
            content: XML file content
            
        Returns:
            Parsed data dictionary
        """
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse XML: {e}")
        
        result = {
            "header": {},
            "lines": [],
            "summary": {}
        }
        
        # Convert XML to dict recursively
        self._xml_to_dict(root, result["header"])
        
        # Try to identify line items (common patterns)
        self._extract_line_items(root, result["lines"])
        
        return result
    
    def _parse_cxml(self, content: str) -> Dict[str, Any]:
        """
        Parse cXML with XPath awareness.
        
        Args:
            content: cXML file content
            
        Returns:
            Parsed data dictionary
        """
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse cXML: {e}")
        
        result = {
            "header": {},
            "lines": [],
            "summary": {}
        }
        
        # cXML specific parsing
        # Extract Header (from Message/PunchOutOrderMessage)
        header_path = ".//PunchOutOrderMessage/Header"
        header_elem = root.find(header_path)
        if header_elem is not None:
            self._xml_element_to_dict(header_elem, result["header"])
        
        # Extract OrderRequest/OrderRequestHeader
        order_header_path = ".//OrderRequest/OrderRequestHeader"
        order_header_elem = root.find(order_header_path)
        if order_header_elem is not None:
            self._xml_element_to_dict(order_header_elem, result["header"])
        
        # Extract line items (OrderRequest/OrderRequestDetail/OrderRequestLine)
        line_path = ".//OrderRequest/OrderRequestDetail/OrderRequestLine"
        for line_elem in root.findall(line_path):
            line = {}
            self._xml_element_to_dict(line_elem, line)
            if line:
                result["lines"].append(line)
        
        # If no lines found, try other patterns
        if not result["lines"]:
            self._extract_line_items(root, result["lines"])
        
        return result
    
    def _xml_to_dict(self, element: Element, result: Dict[str, Any], prefix: str = "") -> None:
        """
        Recursively convert XML element to dictionary.
        
        Args:
            element: XML element
            result: Dictionary to populate
            prefix: Key prefix for nested elements
        """
        # Add attributes
        if element.attrib:
            for key, value in element.attrib.items():
                result[f"@{key}"] = value
        
        # Add text content if no children
        if len(element) == 0 and element.text and element.text.strip():
            result[element.tag] = element.text.strip()
        else:
            # Process children
            for child in element:
                child_key = child.tag
                
                if prefix:
                    child_key = f"{prefix}.{child.tag}"
                
                # Handle repeated elements (list)
                if child_key in result:
                    if not isinstance(result[child_key], list):
                        result[child_key] = [result[child_key]]
                    
                    child_dict = {}
                    self._xml_to_dict(child, child_dict)
                    result[child_key].append(child_dict)
                else:
                    child_dict = {}
                    self._xml_to_dict(child, child_dict)
                    
                    # If single child with text, simplify
                    if len(child_dict) == 1 and list(child_dict.values())[0] and isinstance(list(child_dict.values())[0], str):
                        result[child_key] = list(child_dict.values())[0]
                    else:
                        result[child_key] = child_dict
    
    def _xml_element_to_dict(self, element: Element, result: Dict[str, Any]) -> None:
        """
        Convert XML element to flat dictionary with XPath-like keys.
        
        Args:
            element: XML element
            result: Dictionary to populate
        """
        # Add attributes with @ prefix
        for key, value in element.attrib.items():
            result[f"@{key}"] = value
        
        # Process all children
        for child in element:
            child_dict = {}
            self._xml_element_to_dict(child, child_dict)
            
            # Merge child dict into result
            for key, value in child_dict.items():
                result[key] = value
    
    def _extract_line_items(self, root: Element, lines: List[Dict[str, Any]]) -> None:
        """
        Extract potential line items from XML.
        
        Looks for common patterns like Item, Line, Detail, etc.
        
        Args:
            root: XML root element
            lines: List to populate with line items
        """
        # Common line item tag names
        line_tags = ["Item", "Line", "Detail", "LineItem", "OrderLine", "ItemIn"]
        
        # Try to find elements that might be line items
        for tag in line_tags:
            found = root.findall(f".//{tag}")
            
            if found:
                for elem in found:
                    line = {}
                    self._xml_element_to_dict(elem, line)
                    if line:
                        lines.append(line)
                
                if lines:
                    return
        
        # Fallback: look for any repeated element at second level
        child_counts = {}
        for child in root:
            tag = child.tag
            child_counts[tag] = child_counts.get(tag, 0) + 1
        
        # Find elements that appear multiple times
        for tag, count in child_counts.items():
            if count > 1:
                for elem in root.findall(f".//{tag}"):
                    line = {}
                    self._xml_element_to_dict(elem, line)
                    if line:
                        lines.append(line)
                return
    
    def transform(self, raw_data: Dict[str, Any], map_yaml: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw XML data using mapping rules.
        
        Args:
            raw_data: Raw parsed XML data
            map_yaml: Mapping configuration
            
        Returns:
            Transformed data dictionary
        """
        self.logger.info("Transforming XML data")
        
        # Use mapper to apply mapping rules
        transformed = mapper.map_data(raw_data, map_yaml)
        
        self.logger.info(
            "XML transformation complete",
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
        """
        Write XML payload as a single JSON file named by the split_key value.

        For XML, each file is typically a single transaction, so write_split
        reads the split_key from header and names the output file accordingly.

        Args:
            payload: Transformed data with {header, lines, summary}
            output_dir: Output directory
            split_key: Field name in header to use for filename (e.g., "InvoiceNumber")

        Returns:
            List of output file paths written
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        key_val = str(payload.get("header", {}).get(split_key, "unknown"))
        out_path = str(out_dir / f"{split_key}_{key_val}.json")
        self.write(payload, out_path)
        return [out_path]

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
DriverRegistry.register("xml", XMLHandler)
DriverRegistry.register("cxml", XMLHandler)
