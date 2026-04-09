"""Tests for the JSON protocol import endpoint."""

from __future__ import annotations

import json
import io
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Create a test client with a temporary protocol store."""
    from api.main import app
    return TestClient(app)


def _minimal_protocol(protocol_id: str = "test_import_001") -> dict:
    """Return the smallest valid Protocol JSON."""
    return {
        "protocol_id": protocol_id,
        "document_name": "test_protocol.pdf",
        "metadata": {
            "title": "Test Protocol for Import",
            "sponsor": "TestCorp",
            "phase": "Phase 2",
        },
        "sections": [],
        "tables": [],
        "procedures": [],
    }


def _protocol_with_content() -> dict:
    """Return a Protocol JSON with sections, tables, and procedures."""
    return {
        "protocol_id": "test_rich_import",
        "document_name": "rich_protocol.pdf",
        "total_pages": 50,
        "metadata": {
            "title": "Rich Protocol with Full Content",
            "short_title": "RICH-001",
            "protocol_number": "RICH-2026-001",
            "nct_number": "NCT12345678",
            "sponsor": "RichPharma Inc",
            "phase": "Phase 3",
            "therapeutic_area": "Oncology",
            "indication": "Non-Small Cell Lung Cancer",
            "study_type": "interventional",
            "arms": ["Arm A: Treatment", "Arm B: Placebo"],
        },
        "sections": [
            {
                "number": "1",
                "title": "Introduction",
                "page": 1,
                "end_page": 5,
                "level": 1,
                "content_html": "<p>This is the introduction.</p>",
                "children": [
                    {
                        "number": "1.1",
                        "title": "Background",
                        "page": 2,
                        "end_page": 3,
                        "level": 2,
                        "content_html": "<p>Background information.</p>",
                        "children": [],
                    }
                ],
            },
            {
                "number": "2",
                "title": "Study Objectives",
                "page": 6,
                "end_page": 8,
                "level": 1,
                "content_html": "<p>Primary and secondary objectives.</p>",
                "children": [],
            },
        ],
        "tables": [
            {
                "table_id": "soa_1",
                "table_type": "SOA",
                "title": "Schedule of Activities",
                "source_pages": [10, 11],
                "cells": [
                    {"row": 0, "col": 0, "raw_value": "Visit", "confidence": 0.95},
                    {"row": 0, "col": 1, "raw_value": "Week 1", "confidence": 0.90},
                ],
            }
        ],
        "procedures": [
            {
                "raw_name": "Blood Draw",
                "canonical_name": "Blood Draw",
                "category": "Laboratory",
                "estimated_cost_tier": "LOW",
            },
            {
                "raw_name": "CT Scan",
                "canonical_name": "CT Scan",
                "category": "Imaging",
                "estimated_cost_tier": "HIGH",
            },
        ],
    }


def _make_upload(data: dict | str, filename: str = "protocol.json") -> dict:
    """Create a file upload payload for TestClient."""
    if isinstance(data, dict):
        content = json.dumps(data).encode("utf-8")
    else:
        content = data.encode("utf-8")
    return {"file": (filename, io.BytesIO(content), "application/json")}


# ---------------------------------------------------------------------------
# Single import tests
# ---------------------------------------------------------------------------

class TestProtocolImport:
    """Tests for POST /api/protocols/import."""

    def test_import_minimal_protocol(self, client):
        """Minimal valid protocol JSON is accepted and persisted."""
        data = _minimal_protocol("test_minimal_import")
        resp = client.post("/api/protocols/import", files=_make_upload(data))
        assert resp.status_code == 200
        body = resp.json()
        assert body["protocol_id"] == "test_minimal_import"
        assert body["status"] == "imported"

    def test_import_rich_protocol(self, client):
        """Protocol with sections, tables, and procedures is imported with counts."""
        data = _protocol_with_content()
        resp = client.post("/api/protocols/import", files=_make_upload(data))
        assert resp.status_code == 200
        body = resp.json()
        assert body["protocol_id"] == "test_rich_import"
        assert body["tables_count"] == 1
        assert body["procedures_count"] == 2
        assert body["sections_count"] == 3  # 2 top-level + 1 child

    def test_import_protocol_retrievable(self, client):
        """Imported protocol is immediately retrievable via GET."""
        data = _minimal_protocol("test_retrieve_after_import")
        client.post("/api/protocols/import", files=_make_upload(data))
        resp = client.get("/api/protocols/test_retrieve_after_import")
        assert resp.status_code == 200
        body = resp.json()
        assert body["protocol_id"] == "test_retrieve_after_import"
        assert body["metadata"]["title"] == "Test Protocol for Import"

    def test_import_auto_generates_protocol_id(self, client):
        """When protocol_id is missing, one is generated from the filename."""
        data = _minimal_protocol()
        del data["protocol_id"]
        resp = client.post(
            "/api/protocols/import",
            files=_make_upload(data, filename="my_study_protocol.json"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["protocol_id"]  # Not empty
        assert "my_study_protocol" in body["protocol_id"]
        assert len(body["warnings"]) > 0
        assert "generated" in body["warnings"][0].lower()

    def test_import_auto_fills_document_name(self, client):
        """When document_name is missing, filename is used."""
        data = _minimal_protocol("test_auto_docname")
        del data["document_name"]
        resp = client.post(
            "/api/protocols/import",
            files=_make_upload(data, filename="uploaded_protocol.json"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["document_name"] == "uploaded_protocol.json"

    def test_import_auto_fills_metadata(self, client):
        """When metadata block is missing, empty metadata is created."""
        data = {"protocol_id": "test_no_metadata", "document_name": "test.pdf"}
        resp = client.post("/api/protocols/import", files=_make_upload(data))
        assert resp.status_code == 200
        body = resp.json()
        assert any("metadata" in w.lower() for w in body["warnings"])

    def test_import_warns_on_overwrite(self, client):
        """Importing with the same protocol_id warns about overwrite."""
        data = _minimal_protocol("test_overwrite_warning")
        # First import
        client.post("/api/protocols/import", files=_make_upload(data))
        # Second import — should warn
        resp = client.post("/api/protocols/import", files=_make_upload(data))
        assert resp.status_code == 200
        body = resp.json()
        assert any("overwrite" in w.lower() for w in body["warnings"])


# ---------------------------------------------------------------------------
# Validation / rejection tests
# ---------------------------------------------------------------------------

class TestProtocolImportValidation:
    """Tests for import validation and error handling."""

    def test_rejects_non_json_file(self, client):
        """Non-.json file extension is rejected."""
        content = b"not json"
        resp = client.post(
            "/api/protocols/import",
            files={"file": ("protocol.pdf", io.BytesIO(content), "application/pdf")},
        )
        assert resp.status_code == 400
        assert "JSON" in resp.json()["detail"]

    def test_rejects_empty_file(self, client):
        """Empty file is rejected."""
        resp = client.post(
            "/api/protocols/import",
            files={"file": ("empty.json", io.BytesIO(b""), "application/json")},
        )
        assert resp.status_code == 400

    def test_rejects_invalid_json(self, client):
        """Malformed JSON is rejected with parse error details."""
        resp = client.post(
            "/api/protocols/import",
            files=_make_upload("{bad json", filename="bad.json"),
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["detail"]

    def test_rejects_json_array(self, client):
        """JSON array at root level is rejected."""
        content = json.dumps([{"protocol_id": "x"}]).encode()
        resp = client.post(
            "/api/protocols/import",
            files={"file": ("array.json", io.BytesIO(content), "application/json")},
        )
        assert resp.status_code == 400
        assert "object" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Batch import tests
# ---------------------------------------------------------------------------

class TestProtocolBatchImport:
    """Tests for POST /api/protocols/import-batch."""

    def test_batch_import_multiple(self, client):
        """Multiple valid files are imported successfully."""
        files = [
            ("files", ("p1.json", io.BytesIO(json.dumps(
                _minimal_protocol("batch_p1")).encode()), "application/json")),
            ("files", ("p2.json", io.BytesIO(json.dumps(
                _minimal_protocol("batch_p2")).encode()), "application/json")),
        ]
        resp = client.post("/api/protocols/import-batch", files=files)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["imported"] == 2
        assert body["failed"] == 0

    def test_batch_import_partial_failure(self, client):
        """Mix of valid and invalid files: valid ones succeed, invalid fail."""
        files = [
            ("files", ("good.json", io.BytesIO(json.dumps(
                _minimal_protocol("batch_good")).encode()), "application/json")),
            ("files", ("bad.json", io.BytesIO(b"{invalid json}"), "application/json")),
        ]
        resp = client.post("/api/protocols/import-batch", files=files)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["imported"] == 1
        assert body["failed"] == 1


# ---------------------------------------------------------------------------
# Real protocol file import test
# ---------------------------------------------------------------------------

class TestRealProtocolImport:
    """Integration test using actual protocol JSONs from data/protocols/."""

    @pytest.fixture
    def protocol_dir(self):
        return Path("data/protocols")

    def test_import_existing_protocol_json(self, client, protocol_dir):
        """Existing protocol JSONs from data/protocols/ can be re-imported."""
        if not protocol_dir.exists():
            pytest.skip("data/protocols/ directory not found")

        json_files = [
            f for f in protocol_dir.glob("*.json")
            if not f.stem.endswith("_kes")
        ]
        if not json_files:
            pytest.skip("No protocol JSON files found")

        # Use the smallest file for speed
        target = min(json_files, key=lambda f: f.stat().st_size)
        content = target.read_bytes()

        resp = client.post(
            "/api/protocols/import",
            files={"file": (target.name, io.BytesIO(content), "application/json")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "imported"
        assert body["protocol_id"]
