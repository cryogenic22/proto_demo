"""Tests for SMB foundation — Week 1: entity, relationship, model, engine, adapter."""

import json
import os
import pytest

from src.smb.core.entity import Entity, ProvenanceInfo, ConfidenceLevel
from src.smb.core.relationship import Relationship, RelationshipBuilder
from src.smb.core.model import StructuredModel
from src.smb.core.engine import SMBEngine
from src.smb.api.models import (
    ExtractionInput, TableInput, ExtractedCellInput,
    FootnoteInput, ProcedureInput, VisitInput, BuildResult,
)
from src.smb.adapters.protoextract import ProtoExtractAdapter
from src.smb.storage.memory_store import MemoryStore


class TestEntity:
    def test_create_entity(self):
        e = Entity(entity_type="Visit", name="Day 1")
        assert e.entity_type == "Visit"
        assert e.name == "Day 1"
        assert e.confidence == ConfidenceLevel.HIGH

    def test_entity_type_must_be_pascal(self):
        with pytest.raises(ValueError):
            Entity(entity_type="visit", name="Day 1")

    def test_entity_properties(self):
        e = Entity(entity_type="Visit", name="Day 1", properties={"day_number": 1})
        assert e.get_property("day_number") == 1
        assert e.get_property("missing", "default") == "default"
        assert e.has_property("day_number")

    def test_deterministic_id(self):
        e = Entity(entity_type="Visit", name="Day 1", properties={"day_number": 1})
        id1 = e.deterministic_id("proto-001")
        id2 = e.deterministic_id("proto-001")
        assert id1 == id2  # Deterministic
        id3 = e.deterministic_id("proto-002")
        assert id1 != id3  # Different doc = different ID

    def test_entity_serialization(self):
        e = Entity(entity_type="Procedure", name="CBC", properties={"cpt_code": "85025"})
        d = e.to_dict()
        assert d["entity_type"] == "Procedure"
        assert d["properties"]["cpt_code"] == "85025"


class TestRelationship:
    def test_create_relationship(self):
        r = Relationship(
            relationship_type="PERFORMED_AT",
            source_entity_id="proc-1",
            target_entity_id="visit-1",
        )
        assert r.relationship_type == "PERFORMED_AT"

    def test_relationship_builder(self):
        r = (RelationshipBuilder("MODIFIED_BY")
             .from_entity("entry-1")
             .to_entity("footnote-1")
             .with_property("modification_type", "CONDITIONAL")
             .with_confidence(0.9)
             .build())
        assert r.relationship_type == "MODIFIED_BY"
        assert r.source_entity_id == "entry-1"
        assert r.properties["modification_type"] == "CONDITIONAL"

    def test_builder_requires_both_entities(self):
        with pytest.raises(ValueError):
            RelationshipBuilder("TEST").from_entity("a").build()


class TestStructuredModel:
    def setup_method(self):
        self.model = StructuredModel(document_id="test-001")
        self.model.entities = [
            Entity(id="v1", entity_type="Visit", name="Day 1", properties={"day_number": 1}),
            Entity(id="v2", entity_type="Visit", name="Day 29", properties={"day_number": 29}),
            Entity(id="p1", entity_type="Procedure", name="CBC", properties={"cpt_code": "85025"}),
            Entity(id="se1", entity_type="ScheduleEntry", name="CBC @ Day 1",
                   properties={"mark_type": "firm", "visit_entity_id": "v1", "procedure_entity_id": "p1"}),
            Entity(id="se2", entity_type="ScheduleEntry", name="CBC @ Day 29",
                   properties={"mark_type": "conditional", "visit_entity_id": "v2", "procedure_entity_id": "p1"}),
        ]

    def test_get_entities_by_type(self):
        assert len(self.model.get_entities("Visit")) == 2
        assert len(self.model.get_entities("Procedure")) == 1
        assert len(self.model.get_entities("ScheduleEntry")) == 2

    def test_get_entity_by_name(self):
        e = self.model.get_entity_by_name("CBC", "Procedure")
        assert e is not None
        assert e.id == "p1"

    def test_get_schedule_entries(self):
        assert len(self.model.get_schedule_entries()) == 2

    def test_get_firm_entries(self):
        assert len(self.model.get_firm_entries()) == 1

    def test_get_conditional_entries(self):
        assert len(self.model.get_conditional_entries()) == 1

    def test_get_visit_timeline(self):
        timeline = self.model.get_visit_timeline()
        assert timeline[0].name == "Day 1"
        assert timeline[1].name == "Day 29"

    def test_summary(self):
        s = self.model.summary()
        assert s["total_entities"] == 5
        assert s["entity_types"]["Visit"] == 2

    def test_to_graph_dict(self):
        g = self.model.to_graph_dict()
        assert len(g["nodes"]) == 5
        assert "entity_counts" in g


class TestProtoExtractAdapter:
    def test_convert_minimal(self):
        adapter = ProtoExtractAdapter()
        data = {
            "protocol_id": "test-001",
            "document_name": "Test.pdf",
            "tables": [{
                "table_id": "t1",
                "table_type": "SOA",
                "cells": [
                    {"row": 0, "col": 0, "raw_value": "CBC", "row_header": "CBC"},
                    {"row": 0, "col": 1, "raw_value": "X", "row_header": "CBC", "col_header": "Day 1"},
                ],
                "procedures": [
                    {"raw_name": "CBC", "canonical_name": "Complete Blood Count", "code": "85025", "category": "Laboratory"},
                ],
                "visit_windows": [
                    {"visit_name": "Day 1", "col_index": 1, "target_day": 1},
                ],
                "footnotes": [],
            }],
        }
        result = adapter.convert(data)
        assert result.document_id == "test-001"
        assert len(result.tables) == 1
        assert len(result.tables[0].cells) == 2
        assert len(result.tables[0].procedures) == 1


class TestSMBEngine:
    def test_build_minimal(self):
        engine = SMBEngine(domain="protocol")
        extraction = ExtractionInput(
            document_id="test-001",
            document_name="Test Protocol",
            tables=[TableInput(
                table_id="t1",
                cells=[
                    ExtractedCellInput(row=0, col=0, raw_value="CBC", row_header="CBC"),
                    ExtractedCellInput(row=0, col=1, raw_value="X", row_header="CBC", col_header="Day 1"),
                ],
                procedures=[
                    ProcedureInput(raw_name="CBC", canonical_name="Complete Blood Count", code="85025"),
                ],
                visits=[
                    VisitInput(visit_name="Day 1", col_index=1, target_day=1),
                ],
            )],
        )
        result = engine.build(extraction)
        assert isinstance(result, BuildResult)
        assert result.model.document_id == "test-001"
        assert len(result.model.get_entities("Visit")) == 1
        assert len(result.model.get_entities("Procedure")) == 1
        assert len(result.model.get_entities("ScheduleEntry")) == 1

    def test_build_with_conditional_footnote(self):
        engine = SMBEngine(domain="protocol")
        extraction = ExtractionInput(
            document_id="test-fn",
            tables=[TableInput(
                table_id="t1",
                cells=[
                    ExtractedCellInput(row=0, col=0, raw_value="ECG", row_header="ECG"),
                    ExtractedCellInput(row=0, col=1, raw_value="X", row_header="ECG",
                                       col_header="Day 1", footnote_markers=["a"]),
                ],
                procedures=[
                    ProcedureInput(raw_name="ECG", canonical_name="ECG"),
                ],
                visits=[
                    VisitInput(visit_name="Day 1", col_index=1, target_day=1),
                ],
                footnotes=[
                    FootnoteInput(marker="a", text="If clinically indicated",
                                  footnote_type="CONDITIONAL",
                                  applies_to=[{"row": 0, "col": 1}]),
                ],
            )],
        )
        result = engine.build(extraction)
        entries = result.model.get_schedule_entries()
        assert len(entries) == 1
        assert entries[0].get_property("mark_type") == "conditional"

    def test_build_span_cell(self):
        engine = SMBEngine(domain="protocol")
        extraction = ExtractionInput(
            document_id="test-span",
            tables=[TableInput(
                table_id="t1",
                cells=[
                    ExtractedCellInput(row=0, col=0, raw_value="eDiary", row_header="eDiary"),
                    ExtractedCellInput(row=0, col=1,
                                       raw_value="--Weekly (Day 1 through Day 28)--",
                                       row_header="eDiary", col_header="Day 1"),
                ],
                procedures=[
                    ProcedureInput(raw_name="eDiary", canonical_name="e-Diary"),
                ],
                visits=[
                    VisitInput(visit_name="Day 1", col_index=1, target_day=1),
                ],
            )],
        )
        result = engine.build(extraction)
        entries = result.model.get_schedule_entries()
        assert len(entries) == 1
        assert entries[0].get_property("is_span") is True
        assert entries[0].get_property("total_occurrences") == 4  # 28 days / 7 = 4 weekly


class TestSMBOnRealProtocol:
    """Test SMB against real stored protocol data."""

    def _load_protocol(self, filename: str) -> dict | None:
        path = f"data/protocols/{filename}"
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def test_p14_moderna(self):
        data = self._load_protocol("p_14_690eb522.json")
        if data is None:
            pytest.skip("P-14 protocol not available")
        engine = SMBEngine(domain="protocol")
        result = engine.build_from_protocol_json(data)
        model = result.model

        visits = model.get_entities("Visit")
        procedures = model.get_entities("Procedure")
        entries = model.get_schedule_entries()

        assert len(visits) >= 5, f"Expected ≥5 visits, got {len(visits)}"
        assert len(procedures) >= 10, f"Expected ≥10 procedures, got {len(procedures)}"
        assert len(entries) >= 20, f"Expected ≥20 schedule entries, got {len(entries)}"
        assert result.validation_passed or len(result.validation_errors) == 0

    def test_pfizer_bnt162(self):
        data = self._load_protocol("prot_0001_1_3a3bae33.json")
        if data is None:
            pytest.skip("Pfizer BNT162 protocol not available")
        engine = SMBEngine(domain="protocol")
        result = engine.build_from_protocol_json(data)
        model = result.model

        visits = model.get_entities("Visit")
        procedures = model.get_entities("Procedure")
        entries = model.get_schedule_entries()

        assert len(visits) >= 3
        assert len(procedures) >= 5
        assert len(entries) >= 10

    def test_p09_tirzepatide(self):
        data = self._load_protocol("p09.json")
        if data is None:
            pytest.skip("P-09 protocol not available")
        engine = SMBEngine(domain="protocol")
        result = engine.build_from_protocol_json(data)
        model = result.model

        assert len(model.get_entities("Visit")) >= 3
        assert len(model.get_entities("Procedure")) >= 5

    def test_graph_export(self):
        data = self._load_protocol("p_14_690eb522.json")
        if data is None:
            pytest.skip("P-14 protocol not available")
        engine = SMBEngine(domain="protocol")
        result = engine.build_from_protocol_json(data)
        graph = result.model.to_graph_dict()

        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) > 0
        assert "entity_counts" in graph


class TestMemoryStore:
    def test_save_and_load(self):
        store = MemoryStore()
        model = StructuredModel(document_id="test-store")
        model.entities.append(Entity(entity_type="Visit", name="Day 1"))

        store.save_model(model)
        loaded = store.load_model("test-store")
        assert loaded is not None
        assert len(loaded.entities) == 1

    def test_list_models(self):
        store = MemoryStore()
        store.save_model(StructuredModel(document_id="a"))
        store.save_model(StructuredModel(document_id="b"))
        assert set(store.list_models()) == {"a", "b"}

    def test_delete_model(self):
        store = MemoryStore()
        store.save_model(StructuredModel(document_id="x"))
        assert store.delete_model("x") is True
        assert store.load_model("x") is None
        assert store.delete_model("x") is False
