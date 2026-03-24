"""Integration tests for the PyEDI Portal API."""

import pytest
from fastapi.testclient import TestClient

from portal.api.app import app

client = TestClient(app)


class TestHealth:
    def test_health(self) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestValidate:
    def test_validate_path(self) -> None:
        resp = client.post(
            "/api/validate",
            json={"dsl_path": "tpm810SourceFF.txt"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dsl_path"] == "tpm810SourceFF.txt"
        assert data["transaction_type"] == "810_INVOICE"
        assert len(data["columns"]) > 0

    def test_validate_upload(self) -> None:
        with open("tpm810SourceFF.txt", "rb") as f:
            resp = client.post(
                "/api/validate/upload",
                files={"dsl_file": ("tpm810SourceFF.txt", f, "text/plain")},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_type"] == "810_INVOICE"


class TestPipeline:
    def test_pipeline_results(self) -> None:
        resp = client.get("/api/pipeline/results")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestTestHarness:
    def test_test_cases(self) -> None:
        resp = client.get("/api/test/cases")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) > 0


class TestManifest:
    def test_manifest_stats(self) -> None:
        resp = client.get("/api/manifest/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "success" in data


class TestConfig:
    def test_config(self) -> None:
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "system" in data
        assert "directories" in data
