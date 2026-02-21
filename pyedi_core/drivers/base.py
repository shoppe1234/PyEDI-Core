"""
Base Transaction Processor - Abstract base class for all drivers.

All drivers (X12, CSV, XML) implement this interface with:
- read(): Parse input file to raw dict
- transform(): Apply YAML mapping rules to raw dict
- write(): Write transformed data to output file
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from ..core import logger as core_logger


class TransactionProcessor(ABC):
    """
    Abstract base class for transaction processors.
    
    All drivers must implement read(), transform(), and write() methods.
    """
    
    def __init__(
        self,
        correlation_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the transaction processor.
        
        Args:
            correlation_id: Optional correlation ID for tracking
            config: Optional configuration dictionary
        """
        self._correlation_id = correlation_id or core_logger.generate_correlation_id()
        self._config = config or {}
        self._logger = None
    
    @property
    def correlation_id(self) -> str:
        """Get the correlation ID for this processor."""
        return self._correlation_id
    
    @property
    def logger(self) -> core_logger.bind_logger:
        """Get a bound logger with correlation_id."""
        if self._logger is None:
            self._logger = core_logger.bind_logger(
                correlation_id=self._correlation_id
            )
        return self._logger
    
    def set_correlation_id(self, correlation_id: str) -> None:
        """Set a specific correlation ID."""
        self._correlation_id = correlation_id
    
    @abstractmethod
    def read(self, file_path: str) -> Dict[str, Any]:
        """
        Read and parse an input file.
        
        Args:
            file_path: Path to the input file
            
        Returns:
            Raw parsed data as dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file cannot be parsed
        """
        pass
    
    @abstractmethod
    def transform(self, raw_data: Dict[str, Any], map_yaml: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw data using mapping rules.
        
        Args:
            raw_data: Raw parsed data from read()
            map_yaml: Mapping configuration from YAML file
            
        Returns:
            Transformed data dictionary with header, lines, summary
        """
        pass
    
    @abstractmethod
    def write(self, payload: Dict[str, Any], output_path: str) -> None:
        """
        Write transformed data to output file.
        
        Args:
            payload: Transformed data dictionary
            output_path: Path to write output JSON
            
        Raises:
            IOError: If writing fails
        """
        pass
    
    def process(
        self,
        file_path: str,
        map_yaml: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Full pipeline: read -> transform -> write.
        
        Args:
            file_path: Path to input file
            map_yaml: Mapping configuration
            output_path: Optional output path (if None, returns payload in memory)
            
        Returns:
            Dict with 'payload' key containing transformed data
        """
        # Read
        self.logger.info(f"Reading file", file_path=file_path)
        raw_data = self.read(file_path)
        
        # Transform
        self.logger.info(f"Transforming data")
        transformed_data = self.transform(raw_data, map_yaml)
        
        # Write (if output path provided)
        if output_path:
            self.logger.info(f"Writing output", output_path=output_path)
            self.write(transformed_data, output_path)
        
        return {"payload": transformed_data}
    
    def detect_format(self, file_path: str) -> str:
        """
        Detect the format of a file based on extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Format string: 'x12', 'csv', 'xml', 'cxml', or 'unknown'
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension in ('.edi', '.x12'):
            return 'x12'
        elif extension == '.csv':
            return 'csv'
        elif extension in ('.xml', '.cxml'):
            # Check for cXML
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read(500)
                    if 'cXML' in content or 'DOCTYPE cXML' in content:
                        return 'cxml'
            except Exception:
                pass
            return 'xml'
        else:
            return 'unknown'


class DriverRegistry:
    """
    Registry for transaction processors.
    
    Allows dynamic registration and lookup of drivers by format.
    """
    
    _drivers: Dict[str, type] = {}
    
    @classmethod
    def register(cls, format_name: str, driver_class: type) -> None:
        """
        Register a driver class for a format.
        
        Args:
            format_name: Format identifier (e.g., 'x12', 'csv', 'xml')
            driver_class: Driver class to register
        """
        cls._drivers[format_name] = driver_class
    
    @classmethod
    def get_driver(cls, format_name: str) -> Optional[type]:
        """
        Get a driver class by format name.
        
        Args:
            format_name: Format identifier
            
        Returns:
            Driver class or None if not found
        """
        return cls._drivers.get(format_name)
    
    @classmethod
    def list_drivers(cls) -> list:
        """
        List all registered driver formats.
        
        Returns:
            List of format names
        """
        return list(cls._drivers.keys())


def get_driver(format_name: str, **kwargs) -> Optional[TransactionProcessor]:
    """
    Factory function to get a driver instance.
    
    Args:
        format_name: Format identifier
        **kwargs: Additional arguments to pass to driver constructor
        
    Returns:
        TransactionProcessor instance or None
    """
    driver_class = DriverRegistry.get_driver(format_name)
    if driver_class:
        return driver_class(**kwargs)
    return None
