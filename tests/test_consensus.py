"""P2a tests: 3-way consensus voting for disagreement cells."""

import pytest
from src.models.schema import ExtractedCell, PipelineConfig, CellRef
from src.pipeline.reconciler import Reconciler


def _cell(row, col, value="X", confidence=0.9):
    return ExtractedCell(row=row, col=col, raw_value=value, confidence=confidence)


class TestConsensusVoting:
    def setup_method(self):
        self.config = PipelineConfig()
        self.reconciler = Reconciler(self.config)

    def test_majority_vote_resolves_disagreement(self):
        """When pass1='X', pass2='', pass3='X' → majority says 'X'."""
        pass1 = [_cell(0, 1, "X")]
        pass2 = [_cell(0, 1, "")]
        pass3 = [_cell(0, 1, "X")]
        result = self.reconciler.reconcile(pass1, pass2, pass3)
        assert result.cells[0].raw_value == "X"
        assert result.cells[0].confidence >= 0.85

    def test_no_consensus_stays_flagged(self):
        """When all 3 passes disagree, cell stays low confidence."""
        pass1 = [_cell(0, 1, "X")]
        pass2 = [_cell(0, 1, "")]
        pass3 = [_cell(0, 1, "Y")]
        result = self.reconciler.reconcile(pass1, pass2, pass3)
        # No 2-of-3 agreement — should remain low confidence
        assert result.cells[0].confidence < 0.85

    def test_agreement_cells_untouched(self):
        """Cells where pass1 and pass2 agree don't need pass3."""
        pass1 = [_cell(0, 1, "X"), _cell(0, 2, "X")]
        pass2 = [_cell(0, 1, "X"), _cell(0, 2, "X")]
        pass3 = [_cell(0, 1, ""), _cell(0, 2, "")]  # pass3 disagrees but doesn't matter
        result = self.reconciler.reconcile(pass1, pass2, pass3)
        # Both should be high confidence (pass1+pass2 agreed)
        assert all(c.confidence >= 0.9 for c in result.cells)

    def test_without_pass3_works_normally(self):
        """When pass3 is None, normal dual-pass reconciliation."""
        pass1 = [_cell(0, 1, "X")]
        pass2 = [_cell(0, 1, "X")]
        result = self.reconciler.reconcile(pass1, pass2)
        assert len(result.cells) == 1
        assert result.cells[0].confidence >= 0.9

    def test_conflicts_reduced_by_consensus(self):
        """Conflict count should decrease after consensus resolution."""
        pass1 = [_cell(0, 1, "X"), _cell(0, 2, "X")]
        pass2 = [_cell(0, 1, ""), _cell(0, 2, "")]  # Both disagree
        pass3 = [_cell(0, 1, "X"), _cell(0, 2, "X")]  # pass3 agrees with pass1
        result = self.reconciler.reconcile(pass1, pass2, pass3)
        assert result.conflicts == 0  # Both resolved by majority vote
