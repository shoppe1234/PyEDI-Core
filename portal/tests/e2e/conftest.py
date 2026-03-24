"""E2E test fixtures — server lifecycle, test data, base URL."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # pycoreEdi/
E2E_PORT = 8321
BASE_URL = f"http://localhost:{E2E_PORT}"


# ---------------------------------------------------------------------------
# Synthetic X12 JSON helpers (mirrors portal/tests/test_compare_api.py)
# ---------------------------------------------------------------------------

def _make_segment(seg_id: str, fields: dict[str, str]) -> dict:
    return {
        "segment": seg_id,
        "fields": [{"name": k, "content": v} for k, v in fields.items()],
    }


def _make_x12_json(match_value: str, n102: str = "Acme Corp") -> dict:
    return {
        "document": {
            "segments": [
                _make_segment("ST", {"ST01": "810"}),
                _make_segment("BIG", {"BIG02": match_value}),
                _make_segment("N1", {"N101": "ST", "N102": n102}),
                _make_segment("SE", {"SE01": "4"}),
            ]
        }
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _build_frontend() -> None:
    """Build the React frontend so FastAPI can serve static files."""
    dist_dir = PROJECT_ROOT / "portal" / "ui" / "dist"
    if dist_dir.exists() and any(dist_dir.iterdir()):
        return  # already built
    subprocess.run(
        ["npm", "run", "build"],
        cwd=str(PROJECT_ROOT / "portal" / "ui"),
        check=True,
        shell=True,
    )


@pytest.fixture(scope="session")
def api_server(_build_frontend: None) -> str:
    """Start uvicorn on E2E_PORT, wait for health, yield base URL, kill on teardown."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    kwargs: dict = dict(
        env=env,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "portal.api.app:app",
            "--port", str(E2E_PORT),
            "--log-level", "warning",
        ],
        **kwargs,
    )

    # Wait for server to be ready
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            resp = urlopen(f"{BASE_URL}/api/health", timeout=2)
            if resp.status == 200:
                break
        except (URLError, OSError):
            pass
        time.sleep(0.5)
    else:
        proc.kill()
        stdout, stderr = proc.communicate(timeout=5)
        pytest.fail(
            f"Server did not start within 20s.\n"
            f"stdout: {stdout.decode()}\nstderr: {stderr.decode()}"
        )

    yield BASE_URL

    # Teardown
    if sys.platform == "win32":
        proc.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


@pytest.fixture(scope="session")
def base_url(api_server: str) -> str:
    """Provide the base URL to pytest-playwright."""
    return api_server


@pytest.fixture(scope="session")
def compare_test_data(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """Create temp dirs with synthetic X12 JSON for compare E2E tests.

    Returns dict with keys: source_dir, target_dir.
    Creates 3 scenarios: matched, mismatched, unmatched.
    """
    base = tmp_path_factory.mktemp("compare_e2e")
    src_dir = base / "source"
    tgt_dir = base / "target"
    src_dir.mkdir()
    tgt_dir.mkdir()

    # MATCH: identical pair
    (src_dir / "inv_001.json").write_text(json.dumps(_make_x12_json("INV-001", "Acme Corp")))
    (tgt_dir / "inv_001.json").write_text(json.dumps(_make_x12_json("INV-001", "Acme Corp")))

    # MISMATCH: same match key, different N102
    (src_dir / "inv_002.json").write_text(json.dumps(_make_x12_json("INV-002", "Acme Corp")))
    (tgt_dir / "inv_002.json").write_text(json.dumps(_make_x12_json("INV-002", "Beta Inc")))

    # UNMATCHED: source only, no target
    (src_dir / "inv_003.json").write_text(json.dumps(_make_x12_json("INV-003", "Gamma LLC")))

    return {
        "source_dir": str(src_dir),
        "target_dir": str(tgt_dir),
    }


@pytest.fixture(scope="session")
def dsl_path() -> str:
    """Absolute path to a real DSL file for validation tests."""
    p = PROJECT_ROOT / "tpm810SourceFF.txt"
    assert p.exists(), f"DSL file not found: {p}"
    return str(p)
