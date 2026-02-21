"""
PyEDI-Core - Configuration-driven EDI, CSV, and XML processing engine.

A deterministic, rule-based processing engine that normalizes X12 EDI, CSV flat files,
and XML (generic + cXML) into a standard JSON intermediate format.

Core Philosophy:
- Configuration over Convention: All business logic in YAML configuration
- Strategy Pattern: Dynamically loaded drivers per file type
- Deterministic Processing: Identical input always produces identical output
- Observable: Structured logging with correlation IDs

Usage:
    from pyedi_core import Pipeline
    
    result = Pipeline(config_path='./config/config.yaml').run(
        file='input.csv',
        return_payload=True
    )
    
    if result.status == 'SUCCESS':
        print(result.payload)
"""

from .pipeline import Pipeline, PipelineResult, create_pipeline
from .core import logger, manifest, error_handler, schema_compiler, mapper
from .drivers import (
    TransactionProcessor,
    DriverRegistry,
    get_driver,
    CSVHandler,
    X12Handler,
    XMLHandler
)

__version__ = "1.0.0"

__all__ = [
    # Pipeline
    "Pipeline",
    "PipelineResult",
    "create_pipeline",
    # Core
    "logger",
    "manifest",
    "error_handler",
    "schema_compiler",
    "mapper",
    # Drivers
    "TransactionProcessor",
    "DriverRegistry",
    "get_driver",
    "CSVHandler",
    "X12Handler",
    "XMLHandler",
]
