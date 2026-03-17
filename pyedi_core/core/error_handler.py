"""
Error Handler module - Dead Letter Queue.

A shared injectable utility called at every stage boundary across all drivers.
It is never duplicated - every driver imports the same module.

Stage values: DETECTION | VALIDATION | TRANSFORMATION | WRITE
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import logger
from . import manifest


# Stage constants
class Stage:
    DETECTION = "DETECTION"
    VALIDATION = "VALIDATION"
    TRANSFORMATION = "TRANSFORMATION"
    WRITE = "WRITE"

class PyEDIError(Exception):
    """Base exception for PyEDI core errors."""
    stage = Stage.DETECTION  # default

class DetectionError(PyEDIError):
    """File format detection failure (no driver, unknown format)."""
    stage = Stage.DETECTION

class SchemaLookupError(PyEDIError):
    """CSV schema registry lookup or compiled map loading failure."""
    stage = Stage.DETECTION

class MappingError(PyEDIError):
    """No mapping rules found for file."""
    stage = Stage.TRANSFORMATION

class TransformationError(PyEDIError):
    """Data transformation stage failure."""
    stage = Stage.TRANSFORMATION


# Default directories
DEFAULT_FAILED_DIR = "./failed"


def handle_failure(
    file_path: str,
    stage: str,
    reason: str,
    exception: Optional[Exception] = None,
    correlation_id: Optional[str] = None,
    failed_dir: str = DEFAULT_FAILED_DIR,
    manifest_path: str = ".processed",
    skip_manifest: bool = False
) -> str:
    """
    Handle a processing failure - move file to failed directory and write error details.
    
    Args:
        file_path: Path to the failed file
        stage: Stage where failure occurred (DETECTION | VALIDATION | TRANSFORMATION | WRITE)
        reason: Human-readable reason for failure
        exception: Optional exception that caused the failure
        correlation_id: Optional correlation ID for tracking
        failed_dir: Directory to move failed files to
        manifest_path: Path to the manifest file
        skip_manifest: If True, skip updating manifest (for dry-run mode)
        
    Returns:
        Path to the error JSON file created
    """
    # Validate stage
    valid_stages = (Stage.DETECTION, Stage.VALIDATION, Stage.TRANSFORMATION, Stage.WRITE)
    if stage not in valid_stages:
        logger.warning(f"Invalid stage '{stage}', defaulting to TRANSFORMATION")
        stage = Stage.TRANSFORMATION
    
    # Get exception message if provided
    exception_message = str(exception) if exception else ""
    if exception and hasattr(exception, '__class__'):
        exception_type = exception.__class__.__name__
        if exception_message:
            exception_message = f"{exception_type}: {exception_message}"
        else:
            exception_message = exception_type
    
    # Prepare error details
    error_details = {
        "stage": stage,
        "reason": reason,
        "exception": exception_message,
        "correlation_id": correlation_id or "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_file": Path(file_path).name if file_path else "unknown"
    }
    
    # Log the error
    logger.error(
        f"Processing failed: {reason}",
        stage=stage,
        reason=reason,
        file=Path(file_path).name if file_path else "unknown",
        correlation_id=correlation_id,
        exception=exception_message
    )
    
    # Create failed directory if it doesn't exist
    failed_path = Path(failed_dir)
    failed_path.mkdir(parents=True, exist_ok=True)
    
    # Move file to failed directory
    source_file = Path(file_path)
    destination_file = failed_path / source_file.name
    
    if source_file.exists():

        # Handle duplicate filenames in failed directory
        counter = 1
        while destination_file.exists():
            stem = source_file.stem
            suffix = source_file.suffix
            destination_file = failed_path / f"{stem}_{counter}{suffix}"
            counter += 1

        try:
            shutil.move(str(source_file), str(destination_file))
            logger.info(f"File moved to failed directory: {destination_file}")
        except (IOError, OSError) as e:
            logger.error(f"Failed to move file to failed directory: {e}")

        # Write error JSON sidecar (ONLY if source file existed and was moved)
        error_file = failed_path / f"{destination_file.stem}.error.json"
        try:
            with open(error_file, "w", encoding="utf-8") as f:
                json.dump(error_details, f, indent=2)
            logger.info(f"Error details written: {error_file}")
        except (IOError, OSError) as e:
            logger.error(f"Failed to write error JSON: {e}")

        # Update manifest (ONLY if source file existed)
        if not skip_manifest and file_path:
            try:
                manifest.mark_processed(
                    file_path=file_path,
                    status="FAILED",
                    manifest_path=manifest_path,
                    skip_hash=skip_manifest
                )
            except Exception as e:
                logger.error(f"Failed to update manifest: {e}")

        return str(error_file)
    else:
        logger.warning(
            f"Source file not found, skipping move/sidecar/manifest",
            file_path=file_path,
            stage=stage
        )
        return ""


def validate_stage(stage: str) -> bool:
    """
    Validate if a stage string is valid.
    
    Args:
        stage: The stage string to validate
        
    Returns:
        True if valid, False otherwise
    """
    return stage in (
        Stage.DETECTION,
        Stage.VALIDATION,
        Stage.TRANSFORMATION,
        Stage.WRITE
    )


def get_failed_files(failed_dir: str = DEFAULT_FAILED_DIR) -> list:
    """
    Get list of failed files in the failed directory.
    
    Args:
        failed_dir: Directory to scan for failed files
        
    Returns:
        List of file paths in the failed directory
    """
    failed_path = Path(failed_dir)
    if not failed_path.exists():
        return []
    
    return [str(f) for f in failed_path.glob("*") if f.is_file()]


def read_error_details(error_file: str) -> Optional[dict]:
    """
    Read error details from an error JSON file.
    
    Args:
        error_file: Path to the error JSON file
        
    Returns:
        Error details dict or None if file doesn't exist
    """
    path = Path(error_file)
    if not path.exists():
        return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to read error file: {e}")
        return None


def retry_failed_file(
    failed_file: str,
    destination_dir: str,
    remove_error_json: bool = True
) -> bool:
    """
    Move a failed file back to the inbound directory for retry.
    
    Args:
        failed_file: Path to the failed file
        destination_dir: Directory to move the file to
        remove_error_json: Whether to remove the error JSON sidecar
        
    Returns:
        True if successful, False otherwise
    """
    source = Path(failed_file)
    if not source.exists():
        logger.warning(f"Failed file does not exist: {failed_file}")
        return False
    
    dest_dir = Path(destination_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / source.name
    
    # Handle duplicate filenames
    counter = 1
    while dest.exists():
        stem = source.stem
        suffix = source.suffix
        dest = dest_dir / f"{stem}_retry_{counter}{suffix}"
        counter += 1
    
    try:
        shutil.move(str(source), str(dest))
        
        # Remove error JSON sidecar if requested
        if remove_error_json:
            error_json = source.parent / f"{source.stem}.error.json"
            if error_json.exists():
                error_json.unlink()
        
        logger.info(f"Failed file moved for retry: {dest}")
        return True
    except (IOError, OSError) as e:
        logger.error(f"Failed to move file for retry: {e}")
        return False
