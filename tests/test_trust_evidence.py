"""Tests for evidence preservation through the reconciler."""

import pytest

from src.models.schema import (
    CellRef,
    ChallengeIssue,
    ChallengeType,
    CostTier,
    ExtractedCell,
    PipelineConfig,
)
from src.pipeline.reconciler import Reconciler
from src.trust.models import CellEvidence


def _cell(row: int, col: int, value: str = "X", confidence: float = 0.9) -> ExtractedCell:
    return ExtractedCell(row=row, col=col, raw_value=value, confidence=confidence)


class TestReconcilerEvidence:
    """Verify reconciler preserves per-cell evidence."""

    def setup_method(self):
        self.config = PipelineConfig()
        self.reconciler = Reconciler(self.config)

    def test_single_pass_attaches_evidence(self):
        cells = [_cell(0, 0, "X"), _cell(0, 1, "")]
        result = self.reconciler.reconcile(cells)
        for cell in result.cells:
            assert cell.evidence is not None
            ev = CellEvidence(**cell.evidence)
            assert ev.pass1_value in ("X", "")
            assert ev.pass2_value is None
            assert ev.resolution_method == "single_pass"

    def test_dual_pass_agree_evidence(self):
        pass1 = [_cell(0, 0, "X"), _cell(0, 1, "")]
        pass2 = [_cell(0, 0, "X"), _cell(0, 1, "")]
        result = self.reconciler.reconcile(pass1, pass2)
        cell = result.cells[0]
        ev = CellEvidence(**cell.evidence)
        assert ev.pass1_value == "X"
        assert ev.pass2_value == "X"
        assert ev.passes_agree is True
        assert ev.resolution_method == "both_agree"
        # Should have DUAL_PASS verification step
        methods = [s.method for s in ev.verification_steps]
        assert "DUAL_PASS" in methods

    def test_dual_pass_disagree_evidence(self):
        pass1 = [_cell(0, 0, "X")]
        pass2 = [_cell(0, 0, "")]
        result = self.reconciler.reconcile(pass1, pass2)
        cell = result.cells[0]
        ev = CellEvidence(**cell.evidence)
        assert ev.pass1_value == "X"
        assert ev.pass2_value == ""
        assert ev.passes_agree is False
        dual_step = next(s for s in ev.verification_steps if s.method == "DUAL_PASS")
        assert dual_step.status == "FAIL"

    def test_challenger_issues_in_evidence(self):
        pass1 = [_cell(0, 0, "X")]
        challenges = [ChallengeIssue(
            cell_ref=CellRef(row=0, col=0),
            challenge_type=ChallengeType.HALLUCINATED_VALUE,
            description="OCR says empty",
            severity=0.6,
        )]
        result = self.reconciler.reconcile(pass1, challenges=challenges)
        cell = result.cells[0]
        ev = CellEvidence(**cell.evidence)
        assert len(ev.challenger_issues) == 1
        assert ev.challenger_issues[0]["severity"] == 0.6
        ch_step = next(s for s in ev.verification_steps if s.method == "CHALLENGER_CLEAR")
        assert ch_step.status == "FAIL"

    def test_evidence_backward_compatible(self):
        """Cells without evidence (old protocols) should still work."""
        cell = ExtractedCell(row=0, col=0, raw_value="X")
        assert cell.evidence is None  # Default

    def test_evidence_serialization_roundtrip(self):
        """Evidence survives JSON serialization."""
        pass1 = [_cell(0, 0, "X")]
        pass2 = [_cell(0, 0, "X")]
        result = self.reconciler.reconcile(pass1, pass2)
        cell = result.cells[0]

        # Serialize to JSON and back
        json_str = cell.model_dump_json()
        restored = ExtractedCell.model_validate_json(json_str)
        assert restored.evidence is not None
        ev = CellEvidence(**restored.evidence)
        assert ev.passes_agree is True
