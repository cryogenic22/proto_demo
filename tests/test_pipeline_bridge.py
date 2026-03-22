"""Tests for the PipelineOutput -> Protocol bridge converter."""

import pytest

from src.models.protocol import Protocol
from src.persistence.protocol_bridge import pipeline_output_to_protocol


class TestPipelineBridge:
    def _make_result(self, **overrides) -> dict:
        """Minimal PipelineOutput-shaped dict."""
        base = {
            "document_name": "study_abc.pdf",
            "document_hash": "abc123",
            "total_pages": 20,
            "tables": [
                {
                    "table_id": "t1",
                    "title": "Schedule of Activities",
                    "table_type": "SOA",
                    "source_pages": [4, 5],
                    "cells": [
                        {"row": 0, "col": 0, "raw_value": "X", "confidence": 0.9},
                    ],
                    "overall_confidence": 0.92,
                    "review_items": [],
                },
            ],
            "pipeline_version": "0.1.0",
            "processing_time_seconds": 12.5,
            "warnings": [],
        }
        base.update(overrides)
        return base

    def test_converts_output_to_protocol(self):
        result = self._make_result()
        proto = pipeline_output_to_protocol(result, "study_abc.pdf")
        assert isinstance(proto, Protocol)
        assert proto.document_name == "study_abc.pdf"
        assert proto.total_pages == 20

    def test_preserves_tables(self):
        result = self._make_result()
        proto = pipeline_output_to_protocol(result, "study_abc.pdf")
        assert len(proto.tables) == 1
        t = proto.tables[0]
        assert t.get("table_id") == "t1" or getattr(t, "table_id", None) == "t1"

    def test_generates_protocol_id(self):
        result = self._make_result()
        proto = pipeline_output_to_protocol(result, "study_abc.pdf")
        assert proto.protocol_id  # non-empty
        assert "study_abc" in proto.protocol_id

    def test_handles_empty_tables(self):
        result = self._make_result(tables=[])
        proto = pipeline_output_to_protocol(result, "empty.pdf")
        assert isinstance(proto, Protocol)
        assert proto.tables == []

    def test_metadata_populated(self):
        result = self._make_result()
        proto = pipeline_output_to_protocol(result, "study_abc.pdf")
        # metadata is now a ProtocolMetadata object, hash goes into document_hash
        assert proto.document_hash == "abc123"
        assert proto.pipeline_version == "0.1.0"

    def test_different_filenames_different_ids(self):
        result = self._make_result()
        proto_a = pipeline_output_to_protocol(result, "study_a.pdf")
        proto_b = pipeline_output_to_protocol(result, "study_b.pdf")
        assert proto_a.protocol_id != proto_b.protocol_id
