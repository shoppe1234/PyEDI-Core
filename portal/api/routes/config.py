"""Config API routes — read and update configuration."""

from pathlib import Path
from typing import Any, Dict

import yaml
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/config", tags=["config"])

CONFIG_PATH = "config/config.yaml"


@router.get("")
def get_config() -> Dict[str, Any]:
    """Read the full config.yaml and return as JSON."""
    path = Path(CONFIG_PATH)
    if not path.exists():
        raise HTTPException(status_code=404, detail="config.yaml not found")

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@router.get("/registry")
def get_registry() -> Dict[str, Any]:
    """Return transaction_registry + csv_schema_registry."""
    path = Path(CONFIG_PATH)
    if not path.exists():
        raise HTTPException(status_code=404, detail="config.yaml not found")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return {
        "transaction_registry": config.get("transaction_registry", {}),
        "csv_schema_registry": config.get("csv_schema_registry", {}),
    }


@router.put("/registry/{entry_name}")
def update_registry_entry(entry_name: str, body: Dict[str, Any]) -> Dict[str, str]:
    """Update a csv_schema_registry entry."""
    path = Path(CONFIG_PATH)
    if not path.exists():
        raise HTTPException(status_code=404, detail="config.yaml not found")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    registry = config.get("csv_schema_registry", {})
    if entry_name not in registry:
        raise HTTPException(status_code=404, detail=f"Entry not found: {entry_name}")

    registry[entry_name].update(body)

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return {"status": "updated", "entry": entry_name}
