"""
PyEDI-Core Configuration Models

Pydantic models for type-safe configuration loading.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field


class CsvSchemaEntry(BaseModel):
    """Configuration entry for CSV schema registry."""
    source_dsl: str = Field(..., description="Path to source DSL schema file")
    compiled_output: str = Field(..., description="Path to compiled YAML map")
    inbound_dir: str = Field(..., description="Inbound directory for CSV files")
    transaction_type: str = Field(..., description="Transaction type (e.g., 810)")


class FixedLengthSchemaEntry(BaseModel):
    """Configuration entry for fixed-length schema registry."""
    source_dsl: str = Field(..., description="Path to source DSL schema file")
    compiled_output: str = Field(..., description="Path to compiled YAML map")
    inbound_dir: str = Field(..., description="Inbound directory for fixed-length files")
    transaction_type: str = Field(..., description="Transaction type (e.g., 810)")
    rules_map: str = Field(..., description="Path to mapping rules YAML")


class SystemConfig(BaseModel):
    """System configuration."""
    max_workers: int = Field(8, description="ThreadPoolExecutor max workers")
    dry_run: bool = Field(False, description="Dry run mode - no file writes")
    return_payload: bool = Field(False, description="Return payload in memory")
    source_system_id: str = Field("unknown", description="Source system identifier")


class ObservabilityConfig(BaseModel):
    """Observability/logging configuration."""
    log_level: str = Field("INFO", description="Log level")
    output: str = Field("console", description="Log output (console or file)")


class DirectoriesConfig(BaseModel):
    """Directory paths configuration."""
    inbound: Union[str, List[str]] = Field("./inbound", description="Inbound directory(ies)")
    outbound: str = Field("./outbound", description="Outbound directory")
    failed: str = Field("./failed", description="Failed files directory")
    processed: str = Field(".processed", description="Processed manifest file")
    rules: Optional[str] = Field(None, description="Rules directory")


class AppConfig(BaseModel):
    """Root application configuration."""
    system: SystemConfig = Field(default_factory=SystemConfig)
    transaction_registry: Dict[str, str] = Field(
        default_factory=dict,
        description="X12 transaction type to map file mapping"
    )
    csv_schema_registry: Dict[str, CsvSchemaEntry] = Field(
        default_factory=dict,
        description="CSV schema registry entries"
    )
    fixed_length_schema_registry: Dict[str, FixedLengthSchemaEntry] = Field(
        default_factory=dict,
        description="Fixed-length schema registry entries"
    )
    directories: DirectoriesConfig = Field(default_factory=DirectoriesConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

    @classmethod
    def load_from_yaml(cls, config_path: str) -> "AppConfig":
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            AppConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        path = Path(config_path)
        if not path.exists():
            # Return default config
            return cls()

        with open(path, "r") as f:
            config_data = yaml.safe_load(f)

        if config_data is None:
            return cls()

        return cls(**config_data)


# Singleton instance
_config: Optional[AppConfig] = None


def get_config(config_path: str = "./config/config.yaml") -> AppConfig:
    """
    Get or create the global configuration singleton.

    Args:
        config_path: Path to configuration file

    Returns:
        AppConfig instance
    """
    global _config
    if _config is None:
        _config = AppConfig.load_from_yaml(config_path)
    return _config


def reload_config(config_path: str = "./config/config.yaml") -> AppConfig:
    """
    Reload configuration from file.

    Args:
        config_path: Path to configuration file

    Returns:
        New AppConfig instance
    """
    global _config
    _config = AppConfig.load_from_yaml(config_path)
    return _config
