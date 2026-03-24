"""Integration tests for the /api/compare endpoints."""

from __future__ import annotations

import json
import os
import shutil
import tempfile

import pytest
import yaml
from fastapi.testclient import TestClient

from portal.api.app import create_app


def _make_segment(seg_id: str, fields: dict[str, str]) -> dict:
    return {
        "segment": seg_id,
        "fields": [{"name": k, "content": v} for k, v in fields.items()],
    }


def _make_x12_json(match_value: str) -> dict:
    return {
        "document": {
            "segments": [
                _make_segment("ST", {"ST01": "810"}),
                _make_segment("BIG", {"BIG02": match_value}),
                _make_segment("N1", {"N101": "ST", "N102": "Acme Corp"}),
                _make_segment("SE", {"SE01": "4"}),
            ]
        }
    }


@pytest.fixture()
def test_env(tmp_path):
    """Set up a temporary config + rules + source/target dirs for testing."""
    # Create rules file
    rules_dir = tmp_path / "compare_rules"
    rules_dir.mkdir()
    rules = {
        "classification": [
            {"segment": "*", "field": "*", "severity": "hard"},
        ],
        "ignore": [
            {"segment": "SE", "field": "SE01", "reason": "segment count"},
        ],
    }
    rules_path = rules_dir / "test_rules.yaml"
    rules_path.write_text(yaml.dump(rules))

    # Create config
    config = {
        "compare": {
            "sqlite_db": str(tmp_path / "test.db"),
            "csv_dir": str(tmp_path / "csv_out"),
            "profiles": {
                "test_810": {
                    "description": "Test 810 profile",
                    "match_key": {"segment": "BIG", "field": "BIG02"},
                    "segment_qualifiers": {"N1": "N101"},
                    "rules_file": str(rules_path),
                }
            },
        }
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))

    # Create source/target dirs with test JSON
    src_dir = tmp_path / "source"
    tgt_dir = tmp_path / "target"
    src_dir.mkdir()
    tgt_dir.mkdir()
    (src_dir / "inv1.json").write_text(json.dumps(_make_x12_json("INV-001")))
    (tgt_dir / "inv1.json").write_text(json.dumps(_make_x12_json("INV-001")))

    # Patch the config path used by the routes
    import portal.api.routes.compare as compare_mod
    original_config = compare_mod._CONFIG_PATH
    compare_mod._CONFIG_PATH = str(config_path)

    yield {
        "config_path": str(config_path),
        "rules_path": str(rules_path),
        "src_dir": str(src_dir),
        "tgt_dir": str(tgt_dir),
        "db_path": str(tmp_path / "test.db"),
    }

    compare_mod._CONFIG_PATH = original_config


@pytest.fixture()
def client(test_env):
    """Create a FastAPI test client."""
    app = create_app()
    return TestClient(app)


class TestCompareProfiles:
    def test_list_profiles(self, client, test_env):
        resp = client.get("/api/compare/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "test_810"


class TestCompareRunAndQuery:
    def test_run_and_query(self, client, test_env):
        # Run comparison
        resp = client.post("/api/compare/run", json={
            "profile": "test_810",
            "source_dir": test_env["src_dir"],
            "target_dir": test_env["tgt_dir"],
        })
        assert resp.status_code == 200
        run = resp.json()
        assert run["total_pairs"] == 1
        run_id = run["run_id"]

        # List runs
        resp = client.get("/api/compare/runs")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        # Get run detail
        resp = client.get(f"/api/compare/runs/{run_id}")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == run_id

        # Get pairs
        resp = client.get(f"/api/compare/runs/{run_id}/pairs")
        assert resp.status_code == 200
        pairs = resp.json()
        assert len(pairs) == 1

        # Get diffs (may be empty if match)
        pair_id = pairs[0]["id"]
        resp = client.get(f"/api/compare/runs/{run_id}/pairs/{pair_id}/diffs")
        assert resp.status_code == 200


class TestCompareExport:
    def test_export_csv(self, client, test_env):
        # Run first
        resp = client.post("/api/compare/run", json={
            "profile": "test_810",
            "source_dir": test_env["src_dir"],
            "target_dir": test_env["tgt_dir"],
        })
        run_id = resp.json()["run_id"]

        # Export
        resp = client.get(f"/api/compare/runs/{run_id}/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")


class TestCompareRules:
    def test_read_rules(self, client, test_env):
        resp = client.get("/api/compare/profiles/test_810/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["classification"]) == 1
        assert len(data["ignore"]) == 1

    def test_update_rules(self, client, test_env):
        new_rules = {
            "classification": [
                {"segment": "N1", "field": "N102", "severity": "soft", "ignore_case": True},
                {"segment": "*", "field": "*", "severity": "hard"},
            ],
            "ignore": [],
        }
        resp = client.put("/api/compare/profiles/test_810/rules", json=new_rules)
        assert resp.status_code == 200

        # Verify persisted
        resp = client.get("/api/compare/profiles/test_810/rules")
        data = resp.json()
        assert len(data["classification"]) == 2
        assert len(data["ignore"]) == 0
