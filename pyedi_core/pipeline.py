"""
Pipeline - Orchestrator for PyEDI-Core processing.

Wires all drivers, manifest, logger together.
Callable from CLI, external programs, or REST API.
"""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field

from .core import error_handler
from .core import logger as core_logger
from .core import manifest
from .drivers.base import DriverRegistry, TransactionProcessor, get_driver


# Import drivers to register them
from .drivers.csv_handler import CSVHandler
from .drivers.x12_handler import X12Handler
from .drivers.xml_handler import XMLHandler


# PipelineResult model - the return contract
class PipelineResult(BaseModel):
    """Result of pipeline processing."""
    status: str = Field(..., description="SUCCESS, FAILED, or SKIPPED")
    correlation_id: str = Field(..., description="UUID per file processed")
    source_file: str = Field(..., description="Original source file name")
    transaction_type: str = Field(..., description="Transaction type (e.g., 810, 850)")
    output_path: Optional[str] = Field(None, description="Output JSON path (None in dry_run)")
    payload: Optional[dict] = Field(None, description="In-memory JSON when return_payload=True")
    errors: List[str] = Field(default_factory=list, description="Error messages if any")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class Pipeline:
    """
    Main pipeline orchestrator.
    
    Processes files through the complete ETL pipeline:
    1. Load configuration
    2. Detect file format
    3. Select appropriate driver
    4. Apply mapping rules
    5. Write output
    """
    
    def __init__(self, config_path: str = "./config/config.yaml"):
        """
        Initialize pipeline with configuration.
        
        Args:
            config_path: Path to YAML configuration file
        """
        self._config = self._load_config(config_path)
        self._transaction_registry = self._config.get("transaction_registry", {})
        
        # Configure logger
        observability = self._config.get("observability", {})
        core_logger.configure(observability)
        
        # Store directory paths
        self._directories = self._config.get("directories", {})
        self._inbound_dirs = self._directories.get("inbound", ["./inbound"])
        self._outbound_dir = self._directories.get("outbound", "./outbound")
        self._failed_dir = self._directories.get("failed", "./failed")
        self._manifest_path = self._directories.get("manifest", ".processed")
        
        # System config
        system = self._config.get("system", {})
        self._source_system_id = system.get("source_system_id", "unknown")
        self._max_workers = system.get("max_workers", 8)
        self._dry_run = system.get("dry_run", False)
        self._return_payload = system.get("return_payload", False)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        path = Path(config_path)
        if not path.exists():
            # Return default config
            return {
                "system": {"source_system_id": "unknown", "max_workers": 8},
                "observability": {"log_level": "INFO", "output": "console"},
                "directories": {
                    "inbound": ["./inbound"],
                    "outbound": "./outbound",
                    "failed": "./failed",
                    "manifest": ".processed"
                },
                "transaction_registry": {}
            }
        
        with open(path, "r") as f:
            return yaml.safe_load(f)
    
    def run(
        self,
        file: Optional[str] = None,
        files: Optional[List[str]] = None,
        return_payload: Optional[bool] = None,
        dry_run: Optional[bool] = None
    ) -> Union[PipelineResult, List[PipelineResult]]:
        """
        Run the pipeline on one or more files.
        
        Args:
            file: Single file path to process
            files: List of file paths to process
            return_payload: Override return_payload setting
            dry_run: Override dry_run setting
            
        Returns:
            PipelineResult for single file, or list for multiple files
        """
        # Determine files to process
        if file:
            file_list = [file]
        elif files:
            file_list = files
        else:
            # Scan inbound directories
            file_list = self._scan_inbound()
        
        if not file_list:
            return PipelineResult(
                status="SKIPPED",
                correlation_id=core_logger.generate_correlation_id(),
                source_file="",
                transaction_type="",
                output_path=None,
                payload=None,
                errors=["No files to process"],
                processing_time_ms=0
            )
        
        # Handle single file vs multiple
        if len(file_list) == 1:
            return self._process_single(
                file_list[0],
                return_payload=return_payload,
                dry_run=dry_run
            )
        
        # Handle multiple files
        return self._process_batch(
            file_list,
            return_payload=return_payload,
            dry_run=dry_run
        )
    
    def _scan_inbound(self) -> List[str]:
        """Scan inbound directories for files."""
        files = []
        for inbound_dir in self._inbound_dirs:
            path = Path(inbound_dir)
            if path.exists():
                # Find all processable files
                for ext in ("*.csv", "*.edi", "*.x12", "*.xml", "*.cxml"):
                    files.extend([str(f) for f in path.glob(ext)])
        return files
    
    def _process_single(
        self,
        file_path: str,
        return_payload: Optional[bool] = None,
        dry_run: Optional[bool] = None
    ) -> PipelineResult:
        """Process a single file."""
        start_time = time.time()
        
        # Determine settings
        do_dry_run = dry_run if dry_run is not None else self._dry_run
        do_return_payload = return_payload if return_payload is not None else self._return_payload
        
        # Generate correlation ID
        correlation_id = core_logger.generate_correlation_id()
        
        # Get filename
        filename = Path(file_path).name
        
        # Log start
        logger = core_logger.bind_logger(
            correlation_id=correlation_id,
            file_name=filename,
            stage="START"
        )
        logger.info(f"Processing file", file_path=file_path)
        
        # Check for duplicates (skip in dry-run mode)
        skip_hash = do_dry_run
        is_dup, existing_status = manifest.is_duplicate(
            file_path,
            manifest_path=self._manifest_path,
            skip_hash=skip_hash
        )
        
        if is_dup:
            logger.info(f"File already processed", status=existing_status)
            return PipelineResult(
                status="SKIPPED",
                correlation_id=correlation_id,
                source_file=filename,
                transaction_type="",
                output_path=None,
                payload=None,
                errors=[f"File already processed with status: {existing_status}"],
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
        
        errors = []
        
        try:
            # Detect format
            driver = self._detect_driver(file_path)
            if not driver:
                raise ValueError(f"No driver available for file: {file_path}")
            
            driver.set_correlation_id(correlation_id)
            
            # Get mapping rules
            map_yaml = self._get_mapping_rules(file_path, driver)
            if not map_yaml:
                raise ValueError(f"No mapping rules found for file: {file_path}")
            
            transaction_type = map_yaml.get("transaction_type", "unknown")
            
            # Execute pipeline stages
            logger = logger.bind(stage="DETECTION", transaction_type=transaction_type)
            
            # Stage 1: Read
            logger.info(f"Stage: READ")
            raw_data = driver.read(file_path)
            
            # Stage 2: Transform
            logger = logger.bind(stage="TRANSFORMATION")
            logger.info(f"Stage: TRANSFORMATION")
            transformed_data = driver.transform(raw_data, map_yaml)
            
            # Stage 3: Write (unless dry-run)
            output_path = None
            payload = None
            
            if not do_dry_run:
                logger = logger.bind(stage="WRITE")
                logger.info(f"Stage: WRITE")
                output_path = self._get_output_path(filename)
                driver.write(transformed_data, output_path)
            
            # Return payload if requested
            if do_return_payload:
                payload = transformed_data
            
            # Mark as processed in manifest
            if not do_dry_run:
                manifest.mark_processed(
                    file_path=file_path,
                    status="SUCCESS",
                    manifest_path=self._manifest_path,
                    skip_hash=skip_hash
                )
            
            processing_time = int((time.time() - start_time) * 1000)
            logger.info(f"Processing complete", status="SUCCESS", processing_time_ms=processing_time)
            
            return PipelineResult(
                status="SUCCESS",
                correlation_id=correlation_id,
                source_file=filename,
                transaction_type=transaction_type,
                output_path=output_path,
                payload=payload,
                errors=[],
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            errors.append(str(e))
            processing_time = int((time.time() - start_time) * 1000)
            
            logger.error(f"Processing failed", error=str(e), processing_time_ms=processing_time)
            
            # Handle failure (unless dry-run)
            if not do_dry_run:
                error_handler.handle_failure(
                    file_path=file_path,
                    stage=error_handler.Stage.TRANSFORMATION,
                    reason=str(e),
                    exception=e,
                    correlation_id=correlation_id,
                    failed_dir=self._failed_dir,
                    manifest_path=self._manifest_path,
                    skip_manifest=do_dry_run
                )
            
            return PipelineResult(
                status="FAILED",
                correlation_id=correlation_id,
                source_file=filename,
                transaction_type="",
                output_path=None,
                payload=None,
                errors=errors,
                processing_time_ms=processing_time
            )
    
    def _process_batch(
        self,
        file_list: List[str],
        return_payload: Optional[bool] = None,
        dry_run: Optional[bool] = None
    ) -> List[PipelineResult]:
        """Process multiple files in parallel."""
        # Filter against manifest
        skip_hash = dry_run if dry_run is not None else self._dry_run
        new_files, duplicate_files = manifest.filter_inbound_files(
            file_list,
            manifest_path=self._manifest_path,
            skip_hash=skip_hash
        )
        
        if not new_files:
            return [
                PipelineResult(
                    status="SKIPPED",
                    correlation_id=core_logger.generate_correlation_id(),
                    source_file=Path(f).name,
                    transaction_type="",
                    output_path=None,
                    payload=None,
                    errors=["Duplicate file"],
                    processing_time_ms=0
                )
                for f in file_list
            ]
        
        # Process in parallel
        results = []
        max_workers = self._max_workers
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(
                    self._process_single,
                    f,
                    return_payload,
                    dry_run
                ): f
                for f in new_files
            }
            
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(PipelineResult(
                        status="FAILED",
                        correlation_id=core_logger.generate_correlation_id(),
                        source_file=Path(file_path).name,
                        transaction_type="",
                        output_path=None,
                        payload=None,
                        errors=[str(e)],
                        processing_time_ms=0
                    ))
        
        # Add skipped results for duplicates
        for f in duplicate_files:
            results.append(PipelineResult(
                status="SKIPPED",
                correlation_id=core_logger.generate_correlation_id(),
                source_file=Path(f).name,
                transaction_type="",
                output_path=None,
                payload=None,
                errors=["Duplicate file"],
                processing_time_ms=0
            ))
        
        return results
    
    def _detect_driver(self, file_path: str) -> Optional[TransactionProcessor]:
        """Detect file format and return appropriate driver."""
        path = Path(file_path)
        extension = path.suffix.lower()
        
        # Map extension to format
        format_map = {
            ".csv": "csv",
            ".edi": "x12",
            ".x12": "x12",
            ".xml": "xml",
            ".cxml": "cxml"
        }
        
        format_name = format_map.get(extension)
        if not format_name:
            # Try to detect from content
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(500)
                    
                    if "ST*" in content:
                        format_name = "x12"
                    elif content.strip().startswith("<?xml") or "<" in content[:100]:
                        format_name = "xml"
            except Exception:
                pass
        
        if format_name:
            return get_driver(format_name, config=self._config)
        
        return None
    
    def _get_mapping_rules(self, file_path: str, driver: TransactionProcessor) -> Optional[Dict]:
        """Get mapping rules for a file."""
        from .core import mapper
        
        filename = Path(file_path).name
        
        # Try to match by transaction type in config
        # First, try to detect transaction type from filename
        import re
        match = re.search(r'(\d{3})', filename)
        
        if match:
            transaction_code = match.group(1)
            map_file = self._transaction_registry.get(transaction_code)
            
            if map_file:
                try:
                    return mapper.load_map(map_file)
                except Exception:
                    pass
        
        # Try by filename stem
        stem = Path(file_path).stem
        map_file = self._transaction_registry.get(stem)
        if map_file:
            try:
                return mapper.load_map(map_file)
            except Exception:
                pass
        
        # Try default X12 mapping
        default_map = self._transaction_registry.get("_default_x12")
        if default_map:
            try:
                return mapper.load_map(default_map)
            except Exception:
                pass
        
        # Try to find a map file in rules directory
        rules_dir = self._transaction_registry.get("_rules_dir", "./rules")
        for map_file in Path(rules_dir).glob("*.yaml"):
            try:
                map_yaml = mapper.load_map(str(map_file))
                # Check if this map applies to the file
                if self._matches_mapping(map_yaml, file_path):
                    return map_yaml
            except Exception:
                continue
        
        return None
    
    def _matches_mapping(self, map_yaml: Dict, file_path: str) -> bool:
        """Check if a mapping applies to a file."""
        # Simple matching - check transaction type
        # In production, this would be more sophisticated
        filename = Path(file_path).stem
        
        transaction_type = map_yaml.get("transaction_type", "")
        if transaction_type and transaction_type.lower() in filename.lower():
            return True
        
        return False
    
    def _get_output_path(self, filename: str) -> str:
        """Get output path for a processed file."""
        # Create output directory
        Path(self._outbound_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate output filename
        stem = Path(filename).stem
        output_filename = f"{stem}.json"
        
        return str(Path(self._outbound_dir) / output_filename)


def create_pipeline(config_path: str = "./config/config.yaml") -> Pipeline:
    """
    Factory function to create a Pipeline instance.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Pipeline instance
    """
    return Pipeline(config_path=config_path)
