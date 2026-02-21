"""
Manifest module for idempotency and deduplication.

Prevents reprocessing of duplicate files using SHA-256 content hash.
A renamed copy of the same file is still detected as a duplicate.

Format: {sha256_hash}|{filename}|{iso_timestamp}|{status}
Status values: SUCCESS | FAILED | SKIPPED
"""

import hashlib
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from . import logger

# Thread safety for manifest operations
_lock = threading.Lock()

# Default manifest file location
MANIFEST_FILE = ".processed"


def compute_sha256(file_path: str) -> str:
    """
    Compute SHA-256 hash of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Hexadecimal SHA-256 hash string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def _read_manifest(manifest_path: str = MANIFEST_FILE) -> List[Tuple[str, str, str, str]]:
    """
    Read the manifest file and return parsed entries.
    
    Args:
        manifest_path: Path to the manifest file
        
    Returns:
        List of tuples: (sha256_hash, filename, timestamp, status)
    """
    entries = []
    path = Path(manifest_path)
    
    if not path.exists():
        return entries
    
    with _lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("|")
                    if len(parts) == 4:
                        entries.append((parts[0], parts[1], parts[2], parts[3]))
        except (IOError, OSError) as e:
            logger.warning(f"Failed to read manifest: {e}")
    
    return entries


def _write_manifest_entry(
    sha256_hash: str,
    filename: str,
    status: str,
    manifest_path: str = MANIFEST_FILE
) -> None:
    """
    Append a new entry to the manifest file.
    
    Args:
        sha256_hash: SHA-256 hash of the file
        filename: Original filename
        status: Processing status (SUCCESS | FAILED | SKIPPED)
        manifest_path: Path to the manifest file
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    line = f"{sha256_hash}|{filename}|{timestamp}|{status}\n"
    
    with _lock:
        try:
            with open(manifest_path, "a", encoding="utf-8") as f:
                f.write(line)
        except (IOError, OSError) as e:
            logger.error(f"Failed to write manifest entry: {e}")
            raise


def is_duplicate(
    file_path: str,
    manifest_path: str = MANIFEST_FILE,
    skip_hash: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Check if a file has already been processed.
    
    Args:
        file_path: Path to the file to check
        manifest_path: Path to the manifest file
        skip_hash: If True, only check by filename (for dry-run mode)
        
    Returns:
        Tuple of (is_duplicate: bool, existing_status: Optional[str])
        If duplicate, returns (True, status) where status is the existing status
    """
    path = Path(file_path)
    if not path.exists():
        return False, None
    
    filename = path.name
    
    # Compute hash unless skipped
    sha256_hash = None
    if not skip_hash:
        try:
            sha256_hash = compute_sha256(str(path.absolute()))
        except (IOError, OSError) as e:
            logger.warning(f"Failed to compute hash for {filename}: {e}")
            return False, None
    
    # Read manifest entries
    entries = _read_manifest(manifest_path)
    
    for entry_hash, entry_filename, _, entry_status in entries:
        # Check hash match first (more accurate)
        if sha256_hash and entry_hash == sha256_hash:
            logger.info(
                f"Duplicate file detected by hash",
                filename=filename,
                hash=sha256_hash[:16] + "...",
                existing_status=entry_status
            )
            return True, entry_status
        
        # Fallback to filename match if hash not available
        if skip_hash and entry_filename == filename:
            logger.info(
                f"Duplicate file detected by name",
                filename=filename,
                existing_status=entry_status
            )
            return True, entry_status
    
    return False, None


def mark_processed(
    file_path: str,
    status: str,
    manifest_path: str = MANIFEST_FILE,
    skip_hash: bool = False
) -> None:
    """
    Mark a file as processed in the manifest.
    
    Args:
        file_path: Path to the processed file
        status: Processing status (SUCCESS | FAILED | SKIPPED)
        manifest_path: Path to the manifest file
        skip_hash: If True, skip computing hash (for dry-run mode)
    """
    if status not in ("SUCCESS", "FAILED", "SKIPPED"):
        raise ValueError(f"Invalid status: {status}. Must be SUCCESS, FAILED, or SKIPPED")
    
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"Cannot mark non-existent file: {file_path}")
        return
    
    filename = path.name
    
    # Compute hash unless skipped
    sha256_hash = None
    if not skip_hash:
        try:
            sha256_hash = compute_sha256(str(path.absolute()))
        except (IOError, OSError) as e:
            logger.warning(f"Failed to compute hash for {filename}: {e}")
            sha256_hash = "unknown"
    
    _write_manifest_entry(sha256_hash, filename, status, manifest_path)
    logger.info(
        f"File marked in manifest",
        filename=filename,
        status=status,
        hash=(sha256_hash[:16] + "...") if sha256_hash and len(sha256_hash) > 16 else sha256_hash
    )


def get_processed_files(manifest_path: str = MANIFEST_FILE) -> List[dict]:
    """
    Get list of all processed files from manifest.
    
    Args:
        manifest_path: Path to the manifest file
        
    Returns:
        List of dicts with keys: hash, filename, timestamp, status
    """
    entries = _read_manifest(manifest_path)
    return [
        {
            "hash": entry_hash,
            "filename": entry_filename,
            "timestamp": entry_timestamp,
            "status": entry_status
        }
        for entry_hash, entry_filename, entry_timestamp, entry_status in entries
    ]


def filter_inbound_files(
    file_paths: List[str],
    manifest_path: str = MANIFEST_FILE,
    skip_hash: bool = False
) -> Tuple[List[str], List[str]]:
    """
    Filter inbound files against manifest, returning (new_files, duplicate_files).
    
    Args:
        file_paths: List of file paths to filter
        manifest_path: Path to the manifest file
        skip_hash: If True, skip computing hash (for dry-run mode)
        
    Returns:
        Tuple of (new_files, duplicate_files) - both lists of file paths
    """
    new_files = []
    duplicate_files = []
    
    for file_path in file_paths:
        is_dup, _ = is_duplicate(file_path, manifest_path, skip_hash)
        if is_dup:
            duplicate_files.append(file_path)
        else:
            new_files.append(file_path)
    
    logger.info(
        f"Filtered inbound files",
        total=len(file_paths),
        new=len(new_files),
        duplicates=len(duplicate_files)
    )
    
    return new_files, duplicate_files


def clear_manifest(manifest_path: str = MANIFEST_FILE) -> None:
    """
    Clear the manifest file (for testing purposes).
    
    Args:
        manifest_path: Path to the manifest file
    """
    path = Path(manifest_path)
    if path.exists():
        with _lock:
            path.unlink()
        logger.info(f"Manifest cleared: {manifest_path}")
