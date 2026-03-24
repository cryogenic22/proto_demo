"""Tests for SMB inference rules — Week 2: 7 rules + validation engine."""

import pytest

from src.smb.core.entity import Entity, ConfidenceLevel
from src.smb.core.model import StructuredModel
from src.smb.core.inference import (
    InferenceEngine,
    InferenceRule,
    CycleInference,
    SpanInference,
    FrequencyModifierInference,
    ConditionalInference,
    SubsetInference,
    CostOverrideInference,
    PhoneCallInference,
)
from src.smb.core.validator import ValidationEngine, ValidationReport


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_model(
    visits=None,
    procedures=None,
    entries=None,
    footnotes=None,
    doc_id="test-inf",
) -> StructuredModel:
    """Build a minimal StructuredModel for testing."""
    model = StructuredModel(document_id=doc_id)
    for v in (visits or []):
        model.entities.append(v)
    for p in (procedures or []):
        model.entities.append(p)
    for e in (entries or []):
        model.entities.append(e)
    for f in (footnotes or []):
        model.entities.append(f)
    return model


def _visit(name: str, day: int | None = None, cycle: int | None = None,
           vid: str | None = None) -> Entity:
    return Entity(
        id=vid or f"v-{name}",
        entity_type="Visit",
        name=name,
        properties={"day_number": day, "cycle": cycle, "visit_label": name},
    )


def _procedure(name: str, canonical: str | None = None,
               cost_tier: str = "LOW", pid: str | None = None) -> Entity:
    return Entity(
        id=pid or f"p-{name}",
        entity_type="Procedure",
        name=canonical or name,
        properties={
            "raw_name": name,
            "canonical_name": canonical or name,
            "cost_tier": cost_tier,
        },
    )


def _entry(
    proc_name: str,
    visit_name: str,
    mark_type: str = "firm",
    occurrence_count: int = 1,
    footnote_markers: list[str] | None = None,
    is_span: bool = False,
    raw_mark: str = "X",
    span_frequency: str | None = None,
    span_start_day: int | None = None,
    span_end_day: int | None = None,
    proc_id: str | None = None,
    visit_id: str | None = None,
    eid: str | None = None,
) -> Entity:
    return Entity(
        id=eid or f"se-{proc_name}-{visit_name}",
        entity_type="ScheduleEntry",
        name=f"{proc_name} @ {visit_name}",
        properties={
            "visit_entity_id": visit_id or f"v-{visit_name}",
            "procedure_entity_id": proc_id or f"p-{proc_name}",
            "mark_type": mark_type,
            "raw_mark": raw_mark,
            "occurrence_count": occurrence_count,
            "total_occurrences": occurrence_count,
            "footnote_markers": footnote_markers or [],
            "is_span": is_span,
            "span_frequency": span_frequency,
            "span_start_day": span_start_day,
            "span_end_day": span_end_day,
            "inference_trail": [],
            "cost_multiplier": 1.0,
            "subset_fraction": 1.0,
            "conditions": [],
        },
    )


def _footnote(marker: str, text: str, classification: str = "CLARIFICATION",
              fid: str | None = None) -> Entity:
    return Entity(
        id=fid or f"fn-{marker}",
        entity_type="Footnote",
        name=f"Footnote {marker}",
        properties={
            "footnote_marker": marker,
            "footnote_text": text,
            "classification": classification,
        },
    )


# ── Oncology domain config fixture ──────────────────────────────────────

ONCOLOGY_CONFIG = {
    "domain": {
        "name": "Oncology",
        "visit_structure": "cycle_based",
    },
    "visit_counting": {
        "default_cycles": 6,
    },
    "ta_specific": {
        "cycle_based": True,
        "treat_to_progression": {
            "enabled": True,
            "default_median_months": 9,
        },
        "cycle_length_days": 21,
    },
    "cost_tiers": {
        "LOW": 75,
        "MEDIUM": 350,
        "HIGH": 1200,
        "VERY_HIGH": 3500,
        "INFUSION": 2500,
        "PHONE_CALL": 35,
        "BIOPSY": 4000,
    },
    "procedure_cost_overrides": {
        "CT Scan": "HIGH",
        "PET Scan": "VERY_HIGH",
        "Complete Blood Count": "LOW",
        "Study Drug Administration": "INFUSION",
    },
    "footnote_rules": {
        "phone_call_keywords": ["call", "telephone", "phone"],
        "conditional_probability": 0.6,
    },
}

FIXED_CONFIG = {
    "domain": {"visit_structure": "fixed_duration"},
    "cost_tiers": {"LOW": 75, "MEDIUM": 350},
    "procedure_cost_overrides": {},
    "footnote_rules": {},
}


# ── Test: CycleInference ────────────────────────────────────────────────


class TestCycleInference:
    def test_cycle_multiplication_oncology(self):
        """With 3 represented cycles and treat-to-progression, should multiply."""
        visits = [
            _visit("C1D1", day=1, cycle=1),
            _visit("C1D8", day=8, cycle=1),
            _visit("C2D1", day=22, cycle=2),
            _visit("C3D1", day=43, cycle=3),
        ]
        entries = [
            _entry("CBC", "C1D1"),
            _entry("CBC", "C2D1"),
            _entry("CBC", "C3D1"),
        ]
        model = _make_model(visits=visits, entries=entries)
        rule = CycleInference()
        mods = rule.apply(model, ONCOLOGY_CONFIG)

        assert len(mods) > 0
        # 9 months * 30 / 21 = 12.857 → 12 total cycles
        # 3 represented → multiplier ~4.0
        for e in model.get_schedule_entries():
            assert e.get_property("applied_cycle_count") == 12
            assert e.get_property("total_occurrences") == 4  # 1 * 4.0
            assert "CycleInference" in e.get_property("inference_trail")

    def test_no_multiplication_fixed_duration(self):
        """Fixed-duration protocols should not trigger cycle inference."""
        model = _make_model(
            visits=[_visit("Day 1", day=1, cycle=1), _visit("Day 29", day=29, cycle=2)],
            entries=[_entry("CBC", "Day 1")],
        )
        rule = CycleInference()
        mods = rule.apply(model, FIXED_CONFIG)
        assert mods == []

    def test_no_multiplication_single_cycle(self):
        """Single cycle should not trigger multiplication."""
        model = _make_model(
            visits=[_visit("C1D1", day=1, cycle=1), _visit("C1D8", day=8, cycle=1)],
            entries=[_entry("CBC", "C1D1")],
        )
        rule = CycleInference()
        mods = rule.apply(model, ONCOLOGY_CONFIG)
        assert mods == []

    def test_excluded_entries_not_multiplied(self):
        """Excluded entries should be skipped by cycle multiplication."""
        visits = [
            _visit("C1D1", day=1, cycle=1),
            _visit("C2D1", day=22, cycle=2),
            _visit("C3D1", day=43, cycle=3),
        ]
        entries = [
            _entry("CBC", "C1D1", mark_type="firm"),
            _entry("Optional", "C1D1", mark_type="excluded"),
        ]
        model = _make_model(visits=visits, entries=entries)
        rule = CycleInference()
        rule.apply(model, ONCOLOGY_CONFIG)

        excluded = [e for e in model.get_schedule_entries()
                    if e.get_property("mark_type") == "excluded"]
        assert len(excluded) == 1
        # Excluded entry should NOT have cycle_multiplier
        assert excluded[0].get_property("cycle_multiplier") is None


# ── Test: SpanInference ─────────────────────────────────────────────────


class TestSpanInference:
    def test_span_weekly_day_range(self):
        """Weekly span with Day 1 through Day 28 should give 4 occurrences."""
        e = _entry(
            "eDiary", "Day 1", is_span=True,
            raw_mark="--Weekly (Day 1 through Day 28)--",
            span_frequency="weekly", span_start_day=1, span_end_day=28,
        )
        model = _make_model(entries=[e])
        rule = SpanInference()
        mods = rule.apply(model, {})

        assert len(mods) == 1
        assert e.get_property("total_occurrences") == 4
        assert "SpanInference" in e.get_property("inference_trail")

    def test_span_daily_day_range(self):
        """Daily span Day 1 through Day 14 → 14 occurrences."""
        e = _entry(
            "Diary", "Day 1", is_span=True,
            raw_mark="Daily Day 1 through Day 14",
            span_frequency="daily", span_start_day=1, span_end_day=14,
        )
        model = _make_model(entries=[e])
        rule = SpanInference()
        mods = rule.apply(model, {})

        assert e.get_property("total_occurrences") == 14

    def test_span_reparse_from_raw(self):
        """If span_start_day/end_day are None, parse from raw_mark."""
        e = _entry(
            "eDiary", "Day 1", is_span=True,
            raw_mark="--Weekly eDiary (Day 64 through Day 759)--",
        )
        model = _make_model(entries=[e])
        rule = SpanInference()
        mods = rule.apply(model, {})

        assert len(mods) == 1
        assert e.get_property("span_start_day") == 64
        assert e.get_property("span_end_day") == 759
        # (759 - 64 + 1) / 7 = 99.43 → 99
        assert e.get_property("total_occurrences") == 99

    def test_span_no_day_range_skipped(self):
        """Span without day range and no frequency data should not modify."""
        e = _entry("Drug", "Day 1", is_span=True, raw_mark="---continuous---")
        model = _make_model(entries=[e])
        rule = SpanInference()
        mods = rule.apply(model, {})
        assert mods == []


# ── Test: FrequencyModifierInference ────────────────────────────────────


class TestFrequencyModifierInference:
    def test_frequency_modifier_applied(self):
        """A FREQUENCY_MODIFIER footnote with '3 times per cycle' → 3x."""
        fn = _footnote("f", "Perform 3 times per cycle", "FREQUENCY_MODIFIER")
        e = _entry("Lab", "C1D1", footnote_markers=["f"])
        model = _make_model(entries=[e], footnotes=[fn])

        rule = FrequencyModifierInference()
        mods = rule.apply(model, {})

        assert len(mods) == 1
        assert e.get_property("total_occurrences") == 3
        assert "FrequencyModifierInference" in e.get_property("inference_trail")

    def test_no_frequency_modifier_footnotes(self):
        """Non-FREQUENCY_MODIFIER footnotes should be ignored."""
        fn = _footnote("a", "As clinically indicated", "CONDITIONAL")
        e = _entry("ECG", "Day 1", footnote_markers=["a"])
        model = _make_model(entries=[e], footnotes=[fn])

        rule = FrequencyModifierInference()
        mods = rule.apply(model, {})
        assert mods == []

    def test_twice_weekly(self):
        """'twice weekly' should give 2x multiplier."""
        fn = _footnote("g", "Administer twice weekly", "FREQUENCY_MODIFIER")
        e = _entry("Drug", "C1D1", footnote_markers=["g"])
        model = _make_model(entries=[e], footnotes=[fn])

        rule = FrequencyModifierInference()
        mods = rule.apply(model, {})

        assert e.get_property("total_occurrences") == 2


# ── Test: ConditionalInference ──────────────────────────────────────────


class TestConditionalInference:
    def test_conditional_probability_applied(self):
        """Conditional entries get probability=0.6."""
        entries = [
            _entry("ECG", "Day 1", mark_type="conditional"),
            _entry("CBC", "Day 1", mark_type="firm"),
        ]
        model = _make_model(entries=entries)
        rule = ConditionalInference()
        mods = rule.apply(model, {})

        assert len(mods) == 1
        conditional = [e for e in model.get_schedule_entries()
                       if e.get_property("mark_type") == "conditional"]
        assert conditional[0].get_property("probability") == 0.6
        assert "ConditionalInference" in conditional[0].get_property("inference_trail")

    def test_custom_probability_from_config(self):
        """Config can override default conditional probability."""
        e = _entry("ECG", "Day 1", mark_type="conditional")
        model = _make_model(entries=[e])
        config = {"footnote_rules": {"conditional_probability": 0.4}}

        rule = ConditionalInference()
        rule.apply(model, config)

        assert e.get_property("probability") == 0.4

    def test_no_conditionals_no_fire(self):
        """If no conditional entries, rule should not fire."""
        e = _entry("CBC", "Day 1", mark_type="firm")
        model = _make_model(entries=[e])
        rule = ConditionalInference()
        mods = rule.apply(model, {})
        assert mods == []


# ── Test: SubsetInference ───────────────────────────────────────────────


class TestSubsetInference:
    def test_subset_30_percent(self):
        """'30% of patients' → subset_fraction=0.3."""
        fn = _footnote("s", "Only 30% of patients require this", "SUBSET")
        e = _entry("Biopsy", "Day 1", footnote_markers=["s"])
        model = _make_model(entries=[e], footnotes=[fn])

        rule = SubsetInference()
        mods = rule.apply(model, {})

        assert len(mods) == 1
        assert e.get_property("subset_fraction") == 0.3
        assert "SubsetInference" in e.get_property("inference_trail")

    def test_subset_half(self):
        """'half of subjects' → subset_fraction=0.5."""
        fn = _footnote("h", "Performed in half of subjects", "SUBSET")
        e = _entry("MRI", "Day 1", footnote_markers=["h"])
        model = _make_model(entries=[e], footnotes=[fn])

        rule = SubsetInference()
        mods = rule.apply(model, {})
        assert e.get_property("subset_fraction") == 0.5

    def test_no_subset_footnotes(self):
        """Non-SUBSET footnotes should not trigger."""
        fn = _footnote("c", "As clinically indicated", "CONDITIONAL")
        e = _entry("ECG", "Day 1", footnote_markers=["c"])
        model = _make_model(entries=[e], footnotes=[fn])

        rule = SubsetInference()
        mods = rule.apply(model, {})
        assert mods == []


# ── Test: CostOverrideInference ─────────────────────────────────────────


class TestCostOverrideInference:
    def test_cost_override_from_domain_yaml(self):
        """CT Scan should be overridden to HIGH from LOW."""
        proc = _procedure("CT Scan", "CT Scan", cost_tier="LOW")
        e = _entry("CT Scan", "Day 1", proc_id=proc.id)
        model = _make_model(procedures=[proc], entries=[e])

        rule = CostOverrideInference()
        mods = rule.apply(model, ONCOLOGY_CONFIG)

        assert len(mods) == 1
        # LOW=75, HIGH=1200 → multiplier = 16.0
        assert e.get_property("cost_multiplier") == 16.0
        assert e.get_property("override_cost_tier") == "HIGH"
        assert "CostOverrideInference" in e.get_property("inference_trail")

    def test_no_override_when_same_tier(self):
        """If procedure already has the overridden tier cost, no change."""
        proc = _procedure("Complete Blood Count", "Complete Blood Count",
                          cost_tier="LOW")
        e = _entry("CBC", "Day 1", proc_id=proc.id)
        model = _make_model(procedures=[proc], entries=[e])

        rule = CostOverrideInference()
        mods = rule.apply(model, ONCOLOGY_CONFIG)

        # LOW → LOW: same cost, no modification
        assert mods == []

    def test_infusion_override(self):
        """Study Drug Administration → INFUSION tier."""
        proc = _procedure("Study Drug Administration",
                          "Study Drug Administration", cost_tier="MEDIUM")
        e = _entry("Drug", "C1D1", proc_id=proc.id)
        model = _make_model(procedures=[proc], entries=[e])

        rule = CostOverrideInference()
        mods = rule.apply(model, ONCOLOGY_CONFIG)

        assert e.get_property("override_cost_tier") == "INFUSION"
        # MEDIUM=350, INFUSION=2500 → 7.14
        assert abs(e.get_property("cost_multiplier") - 7.14) < 0.01

    def test_no_overrides_empty_config(self):
        """Empty config → no modifications."""
        proc = _procedure("CT Scan", "CT Scan")
        e = _entry("CT Scan", "Day 1", proc_id=proc.id)
        model = _make_model(procedures=[proc], entries=[e])

        rule = CostOverrideInference()
        mods = rule.apply(model, {})
        assert mods == []


# ── Test: PhoneCallInference ────────────────────────────────────────────


class TestPhoneCallInference:
    def test_phone_call_detection(self):
        """Footnote about 'will call participants' → PHONE_CALL override."""
        fn = _footnote(
            "7",
            "Trained study personnel will call all participants to collect info",
            "CLARIFICATION",
        )
        e = _entry("Follow-up", "Day 30", footnote_markers=["7"])
        model = _make_model(entries=[e], footnotes=[fn])

        rule = PhoneCallInference()
        mods = rule.apply(model, ONCOLOGY_CONFIG)

        assert len(mods) == 1
        assert e.get_property("override_cost_tier") == "PHONE_CALL"
        assert e.get_property("is_phone_call") is True
        assert "PhoneCallInference" in e.get_property("inference_trail")

    def test_telephone_visit(self):
        """Footnote about 'telephone visit' → PHONE_CALL."""
        fn = _footnote("t", "May be conducted as a telephone visit",
                        "CLARIFICATION")
        e = _entry("AE Check", "Week 4", footnote_markers=["t"])
        model = _make_model(entries=[e], footnotes=[fn])

        rule = PhoneCallInference()
        mods = rule.apply(model, ONCOLOGY_CONFIG)

        assert e.get_property("is_phone_call") is True

    def test_via_phone(self):
        """Footnote with 'via phone' → PHONE_CALL."""
        fn = _footnote("p", "Assessment may be done via phone",
                        "CLARIFICATION")
        e = _entry("Survey", "Day 7", footnote_markers=["p"])
        model = _make_model(entries=[e], footnotes=[fn])

        rule = PhoneCallInference()
        mods = rule.apply(model, ONCOLOGY_CONFIG)

        assert len(mods) == 1

    def test_incidental_mention_not_matched(self):
        """Incidental mention of 'call' should not trigger."""
        fn = _footnote("x", "Patients should report any adverse events",
                        "CLARIFICATION")
        e = _entry("AE Check", "Day 1", footnote_markers=["x"])
        model = _make_model(entries=[e], footnotes=[fn])

        rule = PhoneCallInference()
        mods = rule.apply(model, ONCOLOGY_CONFIG)
        assert mods == []

    def test_telemedicine_detected(self):
        """'telemedicine visit' → phone call."""
        fn = _footnote("4",
                        "Participants will have daily telemedicine visits (via video or phone)",
                        "CLARIFICATION")
        e = _entry("Check-in", "Day 3", footnote_markers=["4"])
        model = _make_model(entries=[e], footnotes=[fn])

        rule = PhoneCallInference()
        mods = rule.apply(model, ONCOLOGY_CONFIG)
        assert e.get_property("is_phone_call") is True


# ── Test: InferenceEngine ───────────────────────────────────────────────


class TestInferenceEngine:
    def test_engine_fires_rules_in_priority_order(self):
        """Engine should fire rules sorted by priority."""
        model = _make_model(
            entries=[_entry("ECG", "Day 1", mark_type="conditional")],
        )
        engine = InferenceEngine()
        fired = engine.run(model, FIXED_CONFIG)

        # ConditionalInference should fire (there is a conditional entry)
        assert "ConditionalInference" in fired

    def test_engine_default_rules_count(self):
        """Default engine should have 7 rules."""
        engine = InferenceEngine()
        assert len(engine.rules) == 7

    def test_engine_custom_rules(self):
        """Engine with custom rules list."""
        engine = InferenceEngine(rules=[ConditionalInference()])
        assert len(engine.rules) == 1

    def test_engine_logs_modifications(self):
        """Fired rules should produce entries in model.inference_log."""
        model = _make_model(
            entries=[_entry("ECG", "Day 1", mark_type="conditional")],
        )
        engine = InferenceEngine()
        engine.run(model, {})

        assert len(model.inference_log) > 0
        log_rules = [entry["rule"] for entry in model.inference_log]
        assert "ConditionalInference" in log_rules


# ── Test: ValidationEngine ──────────────────────────────────────────────


class TestValidationEngine:
    def test_valid_model_passes(self):
        """Model with visits, procedures, entries should pass."""
        model = _make_model(
            visits=[_visit("Day 1", day=1)],
            procedures=[_procedure("CBC")],
            entries=[_entry("CBC", "Day 1")],
        )
        engine = ValidationEngine()
        report = engine.validate(model)

        assert report.passed is True
        assert len(report.errors) == 0

    def test_no_visits_fails(self):
        """Model with no visits should have errors."""
        model = _make_model(
            procedures=[_procedure("CBC")],
            entries=[_entry("CBC", "Day 1")],
        )
        engine = ValidationEngine()
        report = engine.validate(model)

        assert report.passed is False
        assert any("No Visit" in e for e in report.errors)

    def test_no_procedures_fails(self):
        """Model with no procedures should have errors."""
        model = _make_model(
            visits=[_visit("Day 1", day=1)],
        )
        engine = ValidationEngine()
        report = engine.validate(model)

        assert report.passed is False
        assert any("No Procedure" in e for e in report.errors)

    def test_unknown_mark_type_fails(self):
        """ScheduleEntry with mark_type=unknown should be an error."""
        model = _make_model(
            visits=[_visit("Day 1", day=1)],
            procedures=[_procedure("CBC")],
            entries=[_entry("CBC", "Day 1", mark_type="unknown")],
        )
        engine = ValidationEngine()
        report = engine.validate(model)

        assert report.passed is False
        assert any("unknown" in e for e in report.errors)

    def test_unresolved_footnote_warning(self):
        """Footnote marker on entry but not defined → warning."""
        e = _entry("CBC", "Day 1", footnote_markers=["z"])
        model = _make_model(
            visits=[_visit("Day 1", day=1)],
            procedures=[_procedure("CBC")],
            entries=[e],
        )
        engine = ValidationEngine()
        report = engine.validate(model)

        assert any("unresolved" in w for w in report.warnings)

    def test_visit_without_entries_warning(self):
        """Visit with no ScheduleEntries → warning."""
        model = _make_model(
            visits=[_visit("Day 1", day=1, vid="v-day1"),
                    _visit("Day 29", day=29, vid="v-day29")],
            procedures=[_procedure("CBC")],
            entries=[_entry("CBC", "Day 1", visit_id="v-day1")],
        )
        engine = ValidationEngine()
        report = engine.validate(model)

        assert any("Day 29" in w for w in report.warnings)

    def test_stats_computed(self):
        """Report should include entity count stats."""
        model = _make_model(
            visits=[_visit("Day 1", day=1)],
            procedures=[_procedure("CBC")],
            entries=[_entry("CBC", "Day 1")],
        )
        engine = ValidationEngine()
        report = engine.validate(model)

        assert report.stats["visits"] == 1
        assert report.stats["procedures"] == 1
        assert report.stats["schedule_entries"] == 1

    def test_report_to_dict(self):
        """ValidationReport.to_dict() should be serializable."""
        report = ValidationReport(
            errors=["E1"], warnings=["W1"], info=["I1"],
            stats={"visits": 5},
        )
        d = report.to_dict()
        assert d["passed"] is False
        assert d["stats"]["visits"] == 5
