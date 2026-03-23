"""Tests for trust computation engine — TDD: write tests first."""

import pytest

from src.trust.models import (
    CellEvidence,
    ProtocolTrust,
    RowTrust,
    VerificationStep,
)
from src.trust.engine import (
    compute_cell_trust,
    compute_row_trust,
    compute_protocol_trust,
    estimate_review_minutes,
    build_cell_evidence,
)


class TestComputeCellTrust:
    """Cell-level trust from evidence chain."""

    def test_both_passes_agree_high_confidence(self):
        ev = CellEvidence(
            pass1_value="X", pass2_value="X", passes_agree=True,
            ocr_grounded=True, challenger_issues=[],
            resolution_method="both_agree",
        )
        score = compute_cell_trust(ev)
        assert score >= 0.90

    def test_passes_disagree_low_confidence(self):
        ev = CellEvidence(
            pass1_value="X", pass2_value="", passes_agree=False,
            ocr_grounded=None, challenger_issues=[],
            resolution_method="pass1_preferred",
        )
        score = compute_cell_trust(ev)
        assert score < 0.75

    def test_single_pass_moderate_confidence(self):
        ev = CellEvidence(
            pass1_value="X", pass2_value=None, passes_agree=True,
            ocr_grounded=None, challenger_issues=[],
            resolution_method="single_pass",
        )
        score = compute_cell_trust(ev)
        assert 0.60 <= score <= 0.85

    def test_ocr_confirmation_boosts_confidence(self):
        ev_no_ocr = CellEvidence(
            pass1_value="X", pass2_value="X", passes_agree=True,
            ocr_grounded=None, challenger_issues=[],
        )
        ev_with_ocr = CellEvidence(
            pass1_value="X", pass2_value="X", passes_agree=True,
            ocr_grounded=True, challenger_issues=[],
        )
        assert compute_cell_trust(ev_with_ocr) >= compute_cell_trust(ev_no_ocr)

    def test_challenger_issues_reduce_confidence(self):
        ev_clean = CellEvidence(
            pass1_value="X", pass2_value="X", passes_agree=True,
            challenger_issues=[],
        )
        ev_flagged = CellEvidence(
            pass1_value="X", pass2_value="X", passes_agree=True,
            challenger_issues=[{"severity": 0.7, "challenge_type": "HALLUCINATED_VALUE"}],
        )
        assert compute_cell_trust(ev_flagged) < compute_cell_trust(ev_clean)

    def test_manual_override_full_confidence(self):
        ev = CellEvidence(
            pass1_value="X", pass2_value="", passes_agree=False,
            resolution_method="manual",
        )
        score = compute_cell_trust(ev)
        assert score == 1.0

    def test_empty_evidence_returns_default(self):
        ev = CellEvidence()
        score = compute_cell_trust(ev)
        assert 0.0 <= score <= 1.0


class TestBuildCellEvidence:
    """Build evidence from pipeline stage data."""

    def test_both_passes_agree(self):
        ev = build_cell_evidence(
            pass1_value="X", pass1_conf=0.9,
            pass2_value="X", pass2_conf=0.85,
        )
        assert ev.passes_agree is True
        assert ev.resolution_method == "both_agree"
        # Should have a DUAL_PASS verification step
        methods = [s.method for s in ev.verification_steps]
        assert "DUAL_PASS" in methods

    def test_passes_disagree(self):
        ev = build_cell_evidence(
            pass1_value="X", pass1_conf=0.9,
            pass2_value="", pass2_conf=0.8,
        )
        assert ev.passes_agree is False
        dual_step = next(s for s in ev.verification_steps if s.method == "DUAL_PASS")
        assert dual_step.status == "FAIL"

    def test_single_pass(self):
        ev = build_cell_evidence(pass1_value="X", pass1_conf=0.9)
        assert ev.pass2_value is None
        assert ev.resolution_method == "single_pass"
        dual_step = next(s for s in ev.verification_steps if s.method == "DUAL_PASS")
        assert dual_step.status == "SKIPPED"

    def test_with_ocr_grounded(self):
        ev = build_cell_evidence(
            pass1_value="X", pass1_conf=0.9,
            ocr_value="X", ocr_grounded=True,
        )
        assert ev.ocr_grounded is True
        ocr_step = next(s for s in ev.verification_steps if s.method == "OCR_GROUNDING")
        assert ocr_step.status == "PASS"

    def test_with_ocr_failed(self):
        ev = build_cell_evidence(
            pass1_value="X", pass1_conf=0.9,
            ocr_value="Y", ocr_grounded=False,
        )
        ocr_step = next(s for s in ev.verification_steps if s.method == "OCR_GROUNDING")
        assert ocr_step.status == "FAIL"

    def test_with_challenger_clear(self):
        ev = build_cell_evidence(
            pass1_value="X", pass1_conf=0.9,
            challenger_issues=[],
        )
        ch_step = next(s for s in ev.verification_steps if s.method == "CHALLENGER_CLEAR")
        assert ch_step.status == "PASS"

    def test_with_challenger_flagged(self):
        ev = build_cell_evidence(
            pass1_value="X", pass1_conf=0.9,
            challenger_issues=[{"severity": 0.6, "challenge_type": "MISSING_VALUE"}],
        )
        ch_step = next(s for s in ev.verification_steps if s.method == "CHALLENGER_CLEAR")
        assert ch_step.status == "FAIL"


class TestComputeRowTrust:
    """Row-level composite trust."""

    def test_high_confidence_exact_match(self):
        rt = compute_row_trust(
            procedure_name="CBC",
            cell_confidences=[0.95, 0.95, 0.95, 0.90],
            match_method="exact",
            match_score=1.0,
            cpt_code="85025",
            footnotes_total=2,
            footnotes_resolved=2,
        )
        assert rt.composite_score >= 0.85
        assert rt.cpt_status == "mapped"

    def test_low_confidence_unmatched(self):
        rt = compute_row_trust(
            procedure_name="Unknown Procedure",
            cell_confidences=[0.60, 0.50],
            match_method="unmatched",
            match_score=0.0,
            cpt_code=None,
            footnotes_total=1,
            footnotes_resolved=0,
        )
        assert rt.composite_score < 0.50

    def test_effort_based_no_cpt_is_ok(self):
        rt = compute_row_trust(
            procedure_name="Informed Consent",
            cell_confidences=[0.95, 0.95],
            match_method="exact",
            match_score=1.0,
            cpt_code=None,
            footnotes_total=0,
            footnotes_resolved=0,
            is_effort_based=True,
        )
        assert rt.cpt_status == "effort_based"
        assert rt.composite_score >= 0.80

    def test_flagged_cells_reduce_trust(self):
        rt = compute_row_trust(
            procedure_name="ECG",
            cell_confidences=[0.95, 0.50, 0.95],
            match_method="alias",
            match_score=0.95,
            cpt_code="93000",
            flagged_count=1,
        )
        assert rt.flagged_cells == 1
        assert rt.composite_score < 0.90


class TestComputeProtocolTrust:
    """Protocol-level aggregate trust."""

    def test_empty_protocol(self):
        pt = compute_protocol_trust(tables=[], domain_config=None)
        assert pt.overall_score == 0.0
        assert pt.total_cells == 0

    def test_high_quality_protocol(self):
        # Simulate a protocol with all high-confidence cells
        from src.models.schema import (
            ExtractedTable, TableSchema, TableType, ExtractionMetadata,
            NormalizedProcedure, CostTier, ResolvedFootnote, FootnoteType,
        )
        table = ExtractedTable(
            table_id="t1",
            table_type=TableType.SOA,
            schema_info=TableSchema(table_id="t1", num_rows=3, num_cols=5),
            cells=[],
            procedures=[
                NormalizedProcedure(
                    raw_name="CBC", canonical_name="CBC",
                    code="85025", code_system="CPT",
                    category="Lab", estimated_cost_tier=CostTier.LOW,
                ),
            ],
            footnotes=[
                ResolvedFootnote(marker="a", text="test", footnote_type=FootnoteType.CLARIFICATION),
            ],
            extraction_metadata=ExtractionMetadata(
                passes_run=2, challenger_issues_found=0, reconciliation_conflicts=0,
            ),
            overall_confidence=0.95,
        )
        pt = compute_protocol_trust(tables=[table])
        assert pt.tables_count == 1
        assert pt.passes_run == 2
        assert pt.procedures_total >= 1


class TestEstimateReviewMinutes:
    def test_no_flagged_items(self):
        pt = ProtocolTrust(flagged_cells=0, procedures_total=10, procedures_mapped=10)
        assert estimate_review_minutes(pt) == 0

    def test_flagged_cells_add_time(self):
        pt = ProtocolTrust(flagged_cells=10, procedures_total=10, procedures_mapped=10)
        minutes = estimate_review_minutes(pt)
        assert minutes >= 5  # At least 0.5 min per flagged cell

    def test_unmapped_procedures_add_time(self):
        pt = ProtocolTrust(flagged_cells=0, procedures_total=10, procedures_mapped=6)
        minutes = estimate_review_minutes(pt)
        assert minutes >= 8  # 4 unmapped × 2 min each
