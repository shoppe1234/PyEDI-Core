"""Tests for the standards-driven onboard API endpoints."""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

_STANDARDS_DIR = Path(__file__).resolve().parent.parent / "standards"
_SKIP_NO_STANDARDS = pytest.mark.skipif(
    not (_STANDARDS_DIR / "x12").exists(),
    reason="standards directory not present"
)


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the portal API."""
    from portal.api.app import create_app
    app = create_app()
    return TestClient(app)


@_SKIP_NO_STANDARDS
class TestStandardsCatalog:
    """Tests for GET /api/onboard/standards."""

    def test_returns_x12(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards")
        assert resp.status_code == 200
        data = resp.json()
        standards = [s["standard"] for s in data["standards"]]
        assert "x12" in standards

    def test_x12_has_versions(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards")
        data = resp.json()
        x12 = next(s for s in data["standards"] if s["standard"] == "x12")
        assert len(x12["versions"]) == 5


@_SKIP_NO_STANDARDS
class TestStandardsTransactions:
    """Tests for GET /api/onboard/standards/{standard}/{version}/transactions."""

    def test_x12_4010_returns_transactions(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/x12/4010/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["standard"] == "x12"
        assert data["version"] == "4010"
        assert len(data["transactions"]) == 294

    def test_810_has_mapping_flag(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/x12/4010/transactions")
        data = resp.json()
        t810 = next(t for t in data["transactions"] if t["code"] == "810")
        assert t810["has_mapping"] is True

    def test_invalid_version_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/x12/9999/transactions")
        assert resp.status_code == 404

    def test_invalid_standard_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/hl7/4010/transactions")
        assert resp.status_code == 404


@_SKIP_NO_STANDARDS
class TestStandardsSchema:
    """Tests for GET /api/onboard/standards/{standard}/{version}/{code}/schema."""

    def test_810_schema(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/x12/4010/810/schema")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "810"
        assert data["name"] == "Invoice"
        assert data["version"] == "004010"
        assert len(data["areas"]) >= 2
        assert "BIG" in data["segment_defs"]

    def test_997_schema(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/x12/4010/997/schema")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "997"

    def test_nonexistent_code_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/x12/4010/999/schema")
        assert resp.status_code == 404


@_SKIP_NO_STANDARDS
class TestLegacyEndpointsStillWork:
    """Ensure existing endpoints remain backward compatible."""

    def test_x12_types_returns_data(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/x12-types")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["types"]) > 0
        entry = data["types"][0]
        assert "code" in entry
        assert "label" in entry
        assert "has_mapping" in entry

    def test_x12_schema_810(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/x12-schema?type=810")
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_type"] is not None

    def test_x12_versions_810(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/x12-types/810/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert "5010" in data["versions"]
