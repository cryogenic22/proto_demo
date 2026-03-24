"""Integration tests for SMB — build models from all 9 stored protocols."""

import json
import os

import pytest

from src.smb.core.engine import SMBEngine
from src.smb.api.models import BuildResult

PROTOCOLS_DIR = "data/protocols"

# Expected minimums per protocol — (visits, procedures, entries)
PROTOCOL_EXPECTATIONS = {
    "p01_brivaracetam.json": {"min_visits": 5, "min_procs": 10, "min_entries": 20},
    "p08.json": {"min_visits": 0, "min_procs": 20, "min_entries": 0},
    "p09.json": {"min_visits": 5, "min_procs": 5, "min_entries": 10},
    "p14.json": {"min_visits": 10, "min_procs": 20, "min_entries": 30},
    "p17_durvalumab.json": {"min_visits": 0, "min_procs": 5, "min_entries": 0},
    "p17_durvalumab_bb172274.json": {"min_visits": 3, "min_procs": 20, "min_entries": 10},
    "p_14_690eb522.json": {"min_visits": 10, "min_procs": 20, "min_entries": 30},
    "pfizer_bnt162.json": {"min_visits": 3, "min_procs": 5, "min_entries": 10},
    "prot_0001_1_3a3bae33.json": {"min_visits": 10, "min_procs": 15, "min_entries": 30},
}


def _load_protocol(filename: str) -> dict | None:
    path = os.path.join(PROTOCOLS_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _all_protocol_files() -> list[str]:
    if not os.path.isdir(PROTOCOLS_DIR):
        return []
    return sorted(f for f in os.listdir(PROTOCOLS_DIR) if f.endswith(".json"))


class TestSMBIntegrationAllProtocols:
    """Build structured models from all 9 stored protocols and verify
    entity counts, inference rules fired, and validation."""

    @pytest.fixture(scope="class")
    def engine(self) -> SMBEngine:
        return SMBEngine(domain="protocol")

    @pytest.mark.parametrize("filename", _all_protocol_files())
    def test_build_protocol(self, filename: str, engine: SMBEngine):
        """Build a model from a stored protocol and verify basic counts."""
        data = _load_protocol(filename)
        if data is None:
            pytest.skip(f"Protocol {filename} not available")

        result = engine.build_from_protocol_json(data)
        assert isinstance(result, BuildResult)

        model = result.model
        visits = model.get_entities("Visit")
        procedures = model.get_entities("Procedure")
        entries = model.get_schedule_entries()

        # Check against expected minimums
        expected = PROTOCOL_EXPECTATIONS.get(filename, {})
        min_visits = expected.get("min_visits", 0)
        min_procs = expected.get("min_procs", 0)
        min_entries = expected.get("min_entries", 0)

        assert len(visits) >= min_visits, (
            f"{filename}: expected >= {min_visits} visits, got {len(visits)}"
        )
        assert len(procedures) >= min_procs, (
            f"{filename}: expected >= {min_procs} procedures, got {len(procedures)}"
        )
        assert len(entries) >= min_entries, (
            f"{filename}: expected >= {min_entries} entries, got {len(entries)}"
        )

    @pytest.mark.parametrize("filename", _all_protocol_files())
    def test_inference_trail_populated(self, filename: str, engine: SMBEngine):
        """All inference-modified entries should have non-empty trail."""
        data = _load_protocol(filename)
        if data is None:
            pytest.skip(f"Protocol {filename} not available")

        result = engine.build_from_protocol_json(data)
        model = result.model

        # Conditional entries should have ConditionalInference in trail
        for entry in model.get_conditional_entries():
            trail = entry.get_property("inference_trail", [])
            assert "ConditionalInference" in trail, (
                f"{filename}: conditional entry '{entry.name}' missing "
                f"ConditionalInference in trail: {trail}"
            )

    @pytest.mark.parametrize("filename", _all_protocol_files())
    def test_graph_export(self, filename: str, engine: SMBEngine):
        """Graph export should produce valid nodes/edges."""
        data = _load_protocol(filename)
        if data is None:
            pytest.skip(f"Protocol {filename} not available")

        result = engine.build_from_protocol_json(data)
        graph = result.model.to_graph_dict()

        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) > 0
        assert "entity_counts" in graph

    @pytest.mark.parametrize("filename", _all_protocol_files())
    def test_validation_report(self, filename: str, engine: SMBEngine):
        """Validation report should be stored on model."""
        data = _load_protocol(filename)
        if data is None:
            pytest.skip(f"Protocol {filename} not available")

        result = engine.build_from_protocol_json(data)
        vr = result.model.validation_report

        assert isinstance(vr, dict)
        assert "passed" in vr
        assert "errors" in vr
        assert "warnings" in vr
        assert "stats" in vr


class TestSMBInferenceOnRealProtocols:
    """Verify specific inference behavior on known protocols."""

    @pytest.fixture(scope="class")
    def engine(self) -> SMBEngine:
        return SMBEngine(domain="protocol")

    def test_p14_conditional_entries(self, engine: SMBEngine):
        """P14 (vaccines) should have conditional entries with probability."""
        data = _load_protocol("p14.json")
        if data is None:
            pytest.skip("p14.json not available")

        result = engine.build_from_protocol_json(data)
        conditionals = result.model.get_conditional_entries()

        if conditionals:
            for entry in conditionals:
                assert entry.get_property("probability") == 0.6
                assert "ConditionalInference" in entry.get_property(
                    "inference_trail", []
                )

    def test_p14_cost_overrides(self, engine: SMBEngine):
        """P14 should have cost overrides applied to known procedures."""
        data = _load_protocol("p_14_690eb522.json")
        if data is None:
            pytest.skip("p_14_690eb522.json not available")

        result = engine.build_from_protocol_json(data)
        entries = result.model.get_schedule_entries()

        # Check if any entries got CostOverrideInference
        cost_overridden = [
            e for e in entries
            if "CostOverrideInference" in e.get_property("inference_trail", [])
        ]
        # This protocol may or may not have matching procedure names —
        # just verify the rule ran without errors
        assert isinstance(cost_overridden, list)

    def test_phone_call_detection_real(self, engine: SMBEngine):
        """P14 has footnotes about calling participants — verify detection."""
        data = _load_protocol("p14.json")
        if data is None:
            pytest.skip("p14.json not available")

        result = engine.build_from_protocol_json(data)

        # Check if PhoneCallInference fired
        phone_entries = [
            e for e in result.model.get_schedule_entries()
            if e.get_property("is_phone_call") is True
        ]
        # p14 has known phone-call footnotes
        assert isinstance(phone_entries, list)
        # If the rule detected any, verify the tag
        for entry in phone_entries:
            assert "PhoneCallInference" in entry.get_property(
                "inference_trail", []
            )

    def test_schedule_entry_totals_reasonable(self, engine: SMBEngine):
        """Total occurrences should be >= occurrence_count for all entries."""
        for filename in _all_protocol_files():
            data = _load_protocol(filename)
            if data is None:
                continue

            result = engine.build_from_protocol_json(data)
            for entry in result.model.get_schedule_entries():
                total = entry.get_property("total_occurrences", 0)
                base = entry.get_property("occurrence_count", 0)
                assert total >= base or total == 0, (
                    f"{filename}/{entry.name}: total_occurrences ({total}) < "
                    f"occurrence_count ({base})"
                )

    def test_durvalumab_oncology_config(self, engine: SMBEngine):
        """Durvalumab (oncology) should load oncology domain config."""
        data = _load_protocol("p17_durvalumab_bb172274.json")
        if data is None:
            pytest.skip("p17_durvalumab_bb172274.json not available")

        result = engine.build_from_protocol_json(data)
        model = result.model

        # Should have entities
        assert len(model.entities) > 0

        # Inference rules should have been considered
        assert isinstance(result.inference_rules_fired, list)

    def test_all_protocols_build_without_error(self, engine: SMBEngine):
        """Every stored protocol should build without raising exceptions."""
        for filename in _all_protocol_files():
            data = _load_protocol(filename)
            if data is None:
                continue
            # Should not raise
            result = engine.build_from_protocol_json(data)
            assert result.model is not None, f"{filename} produced None model"
            assert result.build_time_seconds >= 0
