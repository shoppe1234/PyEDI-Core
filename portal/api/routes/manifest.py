"""Manifest API routes — processing history and stats."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from ..models import ManifestEntry, ManifestStatsResponse

router = APIRouter(prefix="/api/manifest", tags=["manifest"])

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MANIFEST_PATH = str(_PROJECT_ROOT / ".processed")


def _parse_manifest() -> List[ManifestEntry]:
    """Parse the .processed manifest file into entries."""
    path = Path(MANIFEST_PATH)
    if not path.exists():
        return []

    entries: List[ManifestEntry] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                entries.append(ManifestEntry(
                    hash=parts[0],
                    filename=parts[1],
                    timestamp=parts[2],
                    status=parts[3],
                ))
    return entries


@router.get("", response_model=List[ManifestEntry])
def get_manifest(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> List[ManifestEntry]:
    """List manifest entries with optional filtering and pagination."""
    entries = _parse_manifest()

    # Filter by status
    if status:
        entries = [e for e in entries if e.status.upper() == status.upper()]

    # Filter by search (filename)
    if search:
        entries = [e for e in entries if search.lower() in e.filename.lower()]

    # Reverse for most-recent-first
    entries.reverse()

    return entries[offset : offset + limit]


@router.get("/stats", response_model=ManifestStatsResponse)
def get_manifest_stats() -> ManifestStatsResponse:
    """Aggregate manifest entry counts by status."""
    entries = _parse_manifest()
    return ManifestStatsResponse(
        total=len(entries),
        success=sum(1 for e in entries if e.status == "SUCCESS"),
        failed=sum(1 for e in entries if e.status == "FAILED"),
        skipped=sum(1 for e in entries if e.status == "SKIPPED"),
    )
