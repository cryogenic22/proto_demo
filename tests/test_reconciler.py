"""Tests for multi-pass reconciler."""

import pytest

from src.models.schema import (
    CellDataType,
    CellRef,
    ChallengeIssue,
    ChallengeType,
    CostTier,
    ExtractedCell,
    PipelineConfig,
    ReviewItem,
    ReviewType,
)
from src.pipeline.reconciler import Reconciler


def _cell(row: int, col: int, value: str, confidence: float = 1.0) -> ExtractedCell:
    return ExtractedCell(
        row=row, col=col, raw_value=value,
        data_type=CellDataType.MARKER if value in ("X", "✓") else CellDataType.TEXT,
        confidence=confidence,
    )


class TestReconciler:
    def setup_method(self):
        self.config = PipelineConfig(confidence_threshold=0.85)
        self.reconciler = Reconciler(self.config)

    def test_agreement_yields_high_confidence(self):
        """Two passes agree → confidence stays high."""
        pass1 = [_cell(0, 0, "X"), _cell(0, 1, "X")]
        pass2 = [_cell(0, 0, "X"), _cell(0, 1, "X")]

        result = self.reconciler.reconcile(pass1, pass2)
        assert all(c.confidence >= 0.9 for c in result.cells)
        assert result.flagged == []

    def test_disagreement_lowers_confidence(self):
        """Two passes disagree on a cell → confidence drops, cell flagged."""
        pass1 = [_cell(0, 0, "X"), _cell(0, 1, "X")]
        pass2 = [_cell(0, 0, "X"), _cell(0, 1, "")]  # Disagreement on (0,1)

        result = self.reconciler.reconcile(pass1, pass2)
        cell_01 = [c for c in result.cells if c.row == 0 and c.col == 1][0]
        assert cell_01.confidence < 0.85
        assert CellRef(row=0, col=1) in result.flagged

    def test_challenger_issues_lower_confidence(self):
        """Cells flagged by challenger have reduced confidence."""
        pass1 = [_cell(0, 0, "X", confidence=0.95)]
        challenges = [
            ChallengeIssue(
                cell_ref=CellRef(row=0, col=0),
                challenge_type=ChallengeType.HALLUCINATED_VALUE,
                description="Source image shows empty cell",
                severity=0.8,
            )
        ]

        result = self.reconciler.reconcile(pass1, pass1, challenges=challenges)
        cell = result.cells[0]
        assert cell.confidence < 0.95

    def test_cost_weighted_threshold(self):
        """High-cost procedures have stricter thresholds."""
        # Use single pass mode to preserve the 0.90 confidence
        pass1 = [_cell(0, 0, "X", confidence=0.90)]

        cost_map = {CellRef(row=0, col=0): CostTier.VERY_HIGH}
        result = self.reconciler.reconcile(
            pass1, None, cost_map=cost_map
        )
        # 0.90 is above normal threshold (0.85) but below high_cost_threshold (0.95)
        assert CellRef(row=0, col=0) in result.flagged

    def test_empty_passes(self):
        result = self.reconciler.reconcile([], [])
        assert result.cells == []
        assert result.flagged == []

    def test_single_pass_mode(self):
        """When only one pass is provided, use its values directly."""
        pass1 = [_cell(0, 0, "X", confidence=0.92)]
        result = self.reconciler.reconcile(pass1, None)
        assert len(result.cells) == 1
        assert result.cells[0].confidence == 0.92

    def test_review_items_generated(self):
        """Flagged cells should produce review items."""
        pass1 = [_cell(0, 0, "X")]
        pass2 = [_cell(0, 0, "")]  # Disagreement

        result = self.reconciler.reconcile(pass1, pass2)
        assert len(result.review_items) >= 1
        review = result.review_items[0]
        assert review.review_type == ReviewType.LOCAL_RESOLUTION
