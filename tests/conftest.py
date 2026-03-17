"""
Shared test fixtures and autouse singleton resets.
"""

import os
import tempfile

import pytest


# ---------------------------------------------------------------------------
# Shared fixtures (migrated from test_core.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_manifest():
    """Create a temporary manifest file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.processed') as f:
        manifest_path = f.name
    yield manifest_path
    if os.path.exists(manifest_path):
        os.unlink(manifest_path)


@pytest.fixture
def temp_failed_dir(tmp_path):
    """Create a temporary failed directory."""
    failed_dir = tmp_path / "failed"
    failed_dir.mkdir()
    return str(failed_dir)


# ---------------------------------------------------------------------------
# Autouse singleton resets — prevent test pollution
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_driver_registry():
    """Snapshot and restore DriverRegistry._drivers around each test."""
    from pyedi_core.drivers.base import DriverRegistry

    snapshot = dict(DriverRegistry._drivers)
    yield
    DriverRegistry._drivers = snapshot


@pytest.fixture(autouse=True)
def _reset_logger():
    """Snapshot and restore logger module globals around each test."""
    from pyedi_core.core import logger as log_mod

    config_snapshot = dict(log_mod._config)
    logger_snapshot = log_mod._logger
    yield
    log_mod._config = config_snapshot
    log_mod._logger = logger_snapshot
