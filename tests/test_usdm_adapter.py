"""Tests for the USDM adapter — Protocol, ExtractionInput, and KE generation."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from src.models.protocol import KEType, Protocol
from src.smb.adapters.usdm import USDMAdapter
from src.smb.api.models import ExtractionInput

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def usdm_data():
    with open(FIXTURE_DIR / "usdm_synthetic.json") as f:
        return json.load(f)


@pytest.fixture
def adapter():
    return USDMAdapter()


# ---------------------------------------------------------------------------
# Protocol generation
# ---------------------------------------------------------------------------

class TestUSDMToProtocol:

    def test_to_protocol_returns_protocol(self, adapter, usdm_data):
        proto = adapter.to_protocol(usdm_data, "test.json")
        assert isinstance(proto, Protocol)

    def test_protocol_id_from_sponsor_identifier(self, adapter, usdm_data):
        proto = adapter.to_protocol(usdm_data)
        assert "usdm_" in proto.protocol_id
        assert "xyz" in proto.protocol_id.lower()

    def test_metadata_extracted(self, adapter, usdm_data):
        proto = adapter.to_protocol(usdm_data)
        m = proto.metadata
        assert "Phase III" in m.phase
        assert m.sponsor == "XYZ Therapeutics Inc"
        assert "NCT09876543" == m.nct_number
        assert "Non-Small Cell Lung" in m.indication
        assert len(m.arms) == 2
        assert "XYZ-123 Treatment" in m.arms

    def test_sections_generated(self, adapter, usdm_data):
        proto = adapter.to_protocol(usdm_data)
        assert len(proto.sections) >= 3  # Rationale, Design, Objectives, Eligibility
        titles = [s.title for s in proto.sections]
        assert "Study Rationale" in titles
        assert "Study Design" in titles

    def test_tables_generated(self, adapter, usdm_data):
        proto = adapter.to_protocol(usdm_data)
        assert len(proto.tables) == 1
        tbl = proto.tables[0]
        assert tbl["table_type"] == "SOA"

    def test_procedures_extracted(self, adapter, usdm_data):
        proto = adapter.to_protocol(usdm_data)
        assert len(proto.procedures) >= 5
        names = [p["canonical_name"] for p in proto.procedures]
        assert "Vital Signs Assessment" in names
        assert "Complete Blood Count" in names

    def test_knowledge_elements_generated(self, adapter, usdm_data):
        proto = adapter.to_protocol(usdm_data)
        assert len(proto.knowledge_elements) >= 8  # 3 obj + 3 ep + criteria
        ke_types = {ke.ke_type for ke in proto.knowledge_elements}
        assert KEType.OBJECTIVE in ke_types
        assert KEType.ENDPOINT in ke_types
        assert KEType.INCLUSION_CRITERIA in ke_types
        assert KEType.EXCLUSION_CRITERIA in ke_types

    def test_protocol_pipeline_version(self, adapter, usdm_data):
        proto = adapter.to_protocol(usdm_data)
        assert proto.pipeline_version == "usdm_import_1.0"


# ---------------------------------------------------------------------------
# ExtractionInput generation
# ---------------------------------------------------------------------------

class TestUSDMToExtractionInput:

    def test_returns_extraction_input(self, adapter, usdm_data):
        ei = adapter.to_extraction_input(usdm_data)
        assert isinstance(ei, ExtractionInput)

    def test_has_one_soa_table(self, adapter, usdm_data):
        ei = adapter.to_extraction_input(usdm_data)
        assert len(ei.tables) == 1
        assert ei.tables[0].table_type == "SOA"

    def test_visits_from_encounters(self, adapter, usdm_data):
        ei = adapter.to_extraction_input(usdm_data)
        visits = ei.tables[0].visits
        assert len(visits) == 6
        names = [v.visit_name for v in visits]
        assert "Screening Visit" in names
        assert "Cycle 1 Day 1" in names
        assert "Follow-up Visit 1" in names

    def test_visit_timing(self, adapter, usdm_data):
        ei = adapter.to_extraction_input(usdm_data)
        visits = {v.visit_name: v for v in ei.tables[0].visits}
        screening = visits["Screening Visit"]
        assert screening.target_day == -28
        assert screening.window_plus > 0  # has window

    def test_procedures_from_activities(self, adapter, usdm_data):
        ei = adapter.to_extraction_input(usdm_data)
        procs = ei.tables[0].procedures
        assert len(procs) >= 5
        names = [p.canonical_name for p in procs]
        assert "Vital Signs Assessment" in names
        assert "12-Lead ECG" in names

    def test_procedure_codes_preserved(self, adapter, usdm_data):
        ei = adapter.to_extraction_input(usdm_data)
        procs = {p.canonical_name: p for p in ei.tables[0].procedures}
        cbc = procs.get("Complete Blood Count")
        assert cbc is not None
        assert cbc.code == "85025"
        assert cbc.code_system == "CPT"

    def test_soa_matrix_cells(self, adapter, usdm_data):
        """SoA matrix should have Visit × Procedure cells with markers."""
        ei = adapter.to_extraction_input(usdm_data)
        cells = ei.tables[0].cells
        assert len(cells) > 0

        markers = [c for c in cells if c.data_type == "MARKER"]
        empties = [c for c in cells if c.data_type == "EMPTY"]
        assert len(markers) > 20  # At least 20 scheduled activities
        assert len(empties) > 0  # Some visits don't have all procedures

    def test_cell_headers_populated(self, adapter, usdm_data):
        """Each cell should have row_header (procedure) and col_header (visit)."""
        ei = adapter.to_extraction_input(usdm_data)
        for cell in ei.tables[0].cells:
            assert cell.row_header  # procedure name
            assert cell.col_header  # visit name

    def test_domain_config_present(self, adapter, usdm_data):
        ei = adapter.to_extraction_input(usdm_data)
        assert "cost_tiers" in ei.domain_config
        assert "visit_counting" in ei.domain_config


# ---------------------------------------------------------------------------
# Knowledge Elements
# ---------------------------------------------------------------------------

class TestUSDMKnowledgeElements:

    def test_objectives_mapped(self, adapter, usdm_data):
        kes = adapter.extract_knowledge_elements(usdm_data, "test_proto")
        objectives = [ke for ke in kes if ke.ke_type == KEType.OBJECTIVE]
        assert len(objectives) == 3
        levels = [ke.metadata.get("level") for ke in objectives]
        assert "Primary" in levels
        assert "Secondary" in levels

    def test_endpoints_mapped(self, adapter, usdm_data):
        kes = adapter.extract_knowledge_elements(usdm_data, "test_proto")
        endpoints = [ke for ke in kes if ke.ke_type == KEType.ENDPOINT]
        assert len(endpoints) == 3
        # Check PFS endpoint
        pfs = [e for e in endpoints if "progression-free" in e.content.lower()]
        assert len(pfs) == 1
        assert pfs[0].metadata.get("level") == "Primary"

    def test_criteria_mapped(self, adapter, usdm_data):
        kes = adapter.extract_knowledge_elements(usdm_data, "test_proto")
        inc = [ke for ke in kes if ke.ke_type == KEType.INCLUSION_CRITERIA]
        exc = [ke for ke in kes if ke.ke_type == KEType.EXCLUSION_CRITERIA]
        assert len(inc) == 3
        assert len(exc) == 2

    def test_ke_ids_contain_protocol_id(self, adapter, usdm_data):
        kes = adapter.extract_knowledge_elements(usdm_data, "my_protocol")
        for ke in kes:
            assert ke.ke_id.startswith("my_protocol:")

    def test_ke_source_metadata(self, adapter, usdm_data):
        kes = adapter.extract_knowledge_elements(usdm_data, "test")
        for ke in kes:
            assert ke.metadata.get("source") == "usdm_import"


# ---------------------------------------------------------------------------
# API import endpoint integration
# ---------------------------------------------------------------------------

class TestUSDMImportEndpoint:

    @pytest.fixture
    def client(self):
        from api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_import_usdm_json(self, client, usdm_data):
        content = json.dumps(usdm_data).encode("utf-8")
        resp = client.post(
            "/api/protocols/import",
            files={"file": ("usdm_study.json", io.BytesIO(content), "application/json")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["schema_type"] == "usdm"
        assert body["status"] == "imported"
        assert body["tables_count"] == 1
        assert body["procedures_count"] >= 5
        assert body["sections_count"] >= 3
        assert body["ke_count"] >= 5

    def test_import_usdm_retrievable(self, client, usdm_data):
        content = json.dumps(usdm_data).encode("utf-8")
        resp = client.post(
            "/api/protocols/import",
            files={"file": ("usdm_retrieve.json", io.BytesIO(content), "application/json")},
        )
        protocol_id = resp.json()["protocol_id"]
        get_resp = client.get(f"/api/protocols/{protocol_id}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert "XYZ" in body["metadata"].get("sponsor", "")

    def test_import_protocol_ir_still_works(self, client):
        """Existing Protocol IR import path is not broken."""
        data = {
            "protocol_id": "backward_compat_test",
            "document_name": "compat.pdf",
            "metadata": {"title": "Backward Compat"},
            "sections": [],
            "tables": [],
            "procedures": [],
        }
        content = json.dumps(data).encode("utf-8")
        resp = client.post(
            "/api/protocols/import",
            files={"file": ("compat.json", io.BytesIO(content), "application/json")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["schema_type"] == "protocol_ir"
        assert body["protocol_id"] == "backward_compat_test"
