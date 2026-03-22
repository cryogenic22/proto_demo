"""Shared fixtures for protocol workspace tests."""

from __future__ import annotations

import pytest

from src.models.protocol import Protocol, ProtocolMetadata
from src.persistence.ke_store import JsonKEStore, reset_ke_store


@pytest.fixture()
def fake_protocol() -> Protocol:
    """Return a minimal Protocol with 1 table and 1 cell."""
    return Protocol(
        protocol_id="test_proto_001",
        document_name="test_protocol.pdf",
        total_pages=10,
        metadata=ProtocolMetadata(
            title="Test Protocol",
            sponsor="TestCorp",
            phase="Phase 1",
        ),
        tables=[
            {
                "table_id": "t1",
                "table_type": "SOA",
                "title": "Schedule of Activities",
                "source_pages": [3, 4],
                "schema_info": {
                    "table_id": "t1",
                    "column_headers": [],
                    "row_groups": [],
                    "merged_regions": [],
                    "footnote_markers": [],
                    "num_rows": 2,
                    "num_cols": 3,
                },
                "cells": [
                    {
                        "row": 0,
                        "col": 1,
                        "raw_value": "X",
                        "normalized_value": None,
                        "data_type": "MARKER",
                        "footnote_markers": [],
                        "resolved_footnotes": [],
                        "confidence": 0.85,
                        "row_header": "ECG",
                        "col_header": "Screening",
                    },
                ],
                "footnotes": [],
                "procedures": [],
                "visit_windows": [],
                "overall_confidence": 0.91,
                "flagged_cells": [],
                "review_items": [],
                "extraction_metadata": {
                    "passes_run": 2,
                    "challenger_issues_found": 0,
                    "reconciliation_conflicts": 0,
                    "processing_time_seconds": 1.0,
                    "timestamp": "",
                    "model_used": "test",
                },
            },
        ],
    )


@pytest.fixture()
def fake_store(tmp_path) -> JsonKEStore:
    """Return a JsonKEStore pointing at a temp directory."""
    return JsonKEStore(base_dir=str(tmp_path))


@pytest.fixture(autouse=False)
def _patch_ke_store(fake_store, monkeypatch):
    """Patch create_ke_store to return fake_store in endpoint tests."""
    monkeypatch.setattr(
        "src.persistence.ke_store._store_instance",
        fake_store,
    )
    monkeypatch.setattr(
        "api.main.create_ke_store",
        lambda: fake_store,
    )
    yield
    reset_ke_store()
