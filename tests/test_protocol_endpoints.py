"""Tests for the three new protocol workspace API endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from src.persistence.ke_store import JsonKEStore, reset_ke_store


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store(tmp_path):
    """Fresh temp-dir store for each test."""
    return JsonKEStore(base_dir=str(tmp_path))


@pytest.fixture()
def seeded_store(store, fake_protocol):
    """Store pre-loaded with one test protocol."""
    store.save_protocol(fake_protocol)
    return store


@pytest.fixture()
async def client(seeded_store, monkeypatch):
    """AsyncClient wired to the FastAPI app with store patched."""
    monkeypatch.setattr(
        "api.main.create_ke_store", lambda: seeded_store,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def client_empty(store, monkeypatch):
    """AsyncClient with an empty (no protocols) store."""
    monkeypatch.setattr(
        "api.main.create_ke_store", lambda: store,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# POST /api/protocols/{protocol_id}/ask
# ---------------------------------------------------------------------------

class TestAskEndpoint:
    async def test_ask_requires_question(self, client):
        """POST without 'question' field -> 422."""
        resp = await client.post(
            "/api/protocols/test_proto_001/ask",
            json={"section_context": "Section 1"},
        )
        assert resp.status_code == 422

    async def test_ask_404_unknown_protocol(self, client_empty):
        """POST to nonexistent protocol -> 404."""
        resp = await client_empty.post(
            "/api/protocols/nonexistent/ask",
            json={"question": "What is the primary endpoint?"},
        )
        assert resp.status_code == 404

    async def test_ask_returns_structured_response(self, client):
        """POST with valid question -> 200 with role/content/sources."""
        resp = await client.post(
            "/api/protocols/test_proto_001/ask",
            json={"question": "What visits include ECG?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "assistant"
        assert isinstance(body["content"], str)
        assert len(body["content"]) > 0
        assert isinstance(body["sources"], list)


# ---------------------------------------------------------------------------
# POST /api/protocols/{protocol_id}/review
# ---------------------------------------------------------------------------

class TestReviewEndpoint:
    async def test_review_accept_cell(self, client, seeded_store):
        """Accept action sets cell confidence to 1.0."""
        resp = await client.post(
            "/api/protocols/test_proto_001/review",
            json={
                "table_id": "t1",
                "row": 0,
                "col": 1,
                "action": "accept",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify cell confidence was updated
        proto = seeded_store.load_protocol("test_proto_001")
        cell = proto.tables[0]["cells"][0]
        assert cell["confidence"] == 1.0

    async def test_review_correct_cell(self, client, seeded_store):
        """Correct action updates cell raw_value."""
        resp = await client.post(
            "/api/protocols/test_proto_001/review",
            json={
                "table_id": "t1",
                "row": 0,
                "col": 1,
                "action": "correct",
                "correct_value": "Y",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        proto = seeded_store.load_protocol("test_proto_001")
        cell = proto.tables[0]["cells"][0]
        assert cell["raw_value"] == "Y"

    async def test_review_flag_cell(self, client, seeded_store):
        """Flag action appends to table review_items."""
        resp = await client.post(
            "/api/protocols/test_proto_001/review",
            json={
                "table_id": "t1",
                "row": 0,
                "col": 1,
                "action": "flag",
                "flag_reason": "Value looks wrong",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        proto = seeded_store.load_protocol("test_proto_001")
        items = proto.tables[0]["review_items"]
        assert len(items) >= 1
        assert items[-1]["reason"] == "Value looks wrong"

    async def test_review_404_unknown_protocol(self, client_empty):
        """POST to nonexistent protocol -> 404."""
        resp = await client_empty.post(
            "/api/protocols/nonexistent/review",
            json={
                "table_id": "t1",
                "row": 0,
                "col": 0,
                "action": "accept",
            },
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/procedures/library
# ---------------------------------------------------------------------------

class TestProceduresLibraryEndpoint:
    async def test_procedures_library_returns_list(self, client):
        """GET -> 200 with list of procedures."""
        resp = await client.get("/api/procedures/library")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0

    async def test_procedures_library_has_cpt_codes(self, client):
        """Response entries include cpt_code fields."""
        resp = await client.get("/api/procedures/library")
        body = resp.json()
        # At least some entries should have cpt_code
        has_cpt = [e for e in body if e.get("cpt_code")]
        assert len(has_cpt) > 0
