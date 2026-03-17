"""
Reconciler — multi-pass consistency checking and confidence scoring.

Reconciles results from multiple extraction passes, incorporates
challenger findings, and produces final per-cell confidence scores.
Flags cells below threshold for human review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.models.schema import (
    CellRef,
    ChallengeIssue,
    CostTier,
    ExtractedCell,
    PipelineConfig,
    ReviewItem,
    ReviewType,
)

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationResult:
    cells: list[ExtractedCell] = field(default_factory=list)
    flagged: list[CellRef] = field(default_factory=list)
    review_items: list[ReviewItem] = field(default_factory=list)
    conflicts: int = 0


class Reconciler:
    """Reconciles multi-pass extractions and produces confidence scores."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def reconcile(
        self,
        pass1: list[ExtractedCell],
        pass2: list[ExtractedCell] | None = None,
        *,
        challenges: list[ChallengeIssue] | None = None,
        cost_map: dict[CellRef, CostTier] | None = None,
    ) -> ReconciliationResult:
        """
        Reconcile extraction passes and produce final cells with confidence.

        Args:
            pass1: First extraction pass results.
            pass2: Optional second extraction pass results.
            challenges: Issues found by the challenger agent.
            cost_map: Optional mapping of cell → cost tier for weighted thresholds.

        Returns:
            ReconciliationResult with final cells, flags, and review items.
        """
        challenges = challenges or []
        cost_map = cost_map or {}

        if not pass1:
            return ReconciliationResult()

        # Single pass mode
        if pass2 is None:
            return self._single_pass_result(pass1, challenges, cost_map)

        # Multi-pass reconciliation
        return self._multi_pass_result(pass1, pass2, challenges, cost_map)

    def _single_pass_result(
        self,
        cells: list[ExtractedCell],
        challenges: list[ChallengeIssue],
        cost_map: dict[CellRef, CostTier],
    ) -> ReconciliationResult:
        """Handle single-pass mode — just apply challenges and cost thresholds."""
        challenge_map = self._build_challenge_map(challenges)
        result_cells: list[ExtractedCell] = []
        flagged: list[CellRef] = []
        review_items: list[ReviewItem] = []

        for cell in cells:
            ref = CellRef(row=cell.row, col=cell.col)
            confidence = cell.confidence

            # Apply challenger penalty
            if ref in challenge_map:
                max_severity = max(c.severity for c in challenge_map[ref])
                confidence *= (1.0 - max_severity * 0.5)

            # Apply cost-weighted threshold
            threshold = self._get_threshold(ref, cost_map)
            if confidence < threshold:
                flagged.append(ref)
                review_items.append(ReviewItem(
                    cell_ref=ref,
                    review_type=ReviewType.LOCAL_RESOLUTION,
                    reason=f"Confidence {confidence:.2f} below threshold {threshold:.2f}",
                    extracted_value=cell.raw_value,
                    source_page=cell.source.page if cell.source else 0,
                    cost_tier=cost_map.get(ref, CostTier.LOW),
                ))

            result_cells.append(cell.model_copy(update={"confidence": confidence}))

        return ReconciliationResult(
            cells=result_cells,
            flagged=flagged,
            review_items=review_items,
        )

    def _multi_pass_result(
        self,
        pass1: list[ExtractedCell],
        pass2: list[ExtractedCell],
        challenges: list[ChallengeIssue],
        cost_map: dict[CellRef, CostTier],
    ) -> ReconciliationResult:
        """Reconcile two extraction passes."""
        # Build lookup maps
        map1 = {(c.row, c.col): c for c in pass1}
        map2 = {(c.row, c.col): c for c in pass2}
        all_keys = set(map1.keys()) | set(map2.keys())

        challenge_map = self._build_challenge_map(challenges)
        result_cells: list[ExtractedCell] = []
        flagged: list[CellRef] = []
        review_items: list[ReviewItem] = []
        conflicts = 0

        for key in sorted(all_keys):
            cell1 = map1.get(key)
            cell2 = map2.get(key)
            ref = CellRef(row=key[0], col=key[1])

            if cell1 and cell2:
                # Both passes have this cell — check agreement
                if self._values_agree(cell1, cell2):
                    confidence = 0.95  # High confidence when both agree
                    merged = cell1.model_copy(update={"confidence": confidence})
                else:
                    conflicts += 1
                    confidence = 0.50  # Low confidence on disagreement
                    # Prefer pass 1 value but mark as uncertain
                    merged = cell1.model_copy(update={"confidence": confidence})
            elif cell1:
                # Only in pass 1
                merged = cell1.model_copy(update={"confidence": 0.70})
            else:
                # Only in pass 2
                merged = cell2.model_copy(update={"confidence": 0.70})  # type: ignore

            # Apply challenger penalties
            confidence = merged.confidence
            if ref in challenge_map:
                max_severity = max(c.severity for c in challenge_map[ref])
                confidence *= (1.0 - max_severity * 0.5)
                merged = merged.model_copy(update={"confidence": confidence})

            # Check threshold
            threshold = self._get_threshold(ref, cost_map)
            if merged.confidence < threshold:
                flagged.append(ref)
                reason = (
                    f"Confidence {merged.confidence:.2f} below threshold {threshold:.2f}"
                )
                if cell1 and cell2 and not self._values_agree(cell1, cell2):
                    reason = (
                        f"Pass disagreement: '{cell1.raw_value}' vs '{cell2.raw_value}'. "
                        + reason
                    )
                review_items.append(ReviewItem(
                    cell_ref=ref,
                    review_type=ReviewType.LOCAL_RESOLUTION,
                    reason=reason,
                    extracted_value=merged.raw_value,
                    source_page=merged.source.page if merged.source else 0,
                    cost_tier=cost_map.get(ref, CostTier.LOW),
                ))

            result_cells.append(merged)

        logger.info(
            f"Reconciliation: {len(result_cells)} cells, "
            f"{conflicts} conflicts, {len(flagged)} flagged"
        )
        return ReconciliationResult(
            cells=result_cells,
            flagged=flagged,
            review_items=review_items,
            conflicts=conflicts,
        )

    def _get_threshold(
        self, ref: CellRef, cost_map: dict[CellRef, CostTier]
    ) -> float:
        """Get the confidence threshold for a cell, considering cost tier."""
        cost_tier = cost_map.get(ref, CostTier.LOW)
        if cost_tier in (CostTier.HIGH, CostTier.VERY_HIGH):
            return self.config.high_cost_threshold
        return self.config.confidence_threshold

    @staticmethod
    def _values_agree(cell1: ExtractedCell, cell2: ExtractedCell) -> bool:
        """Check if two cells agree on their value."""
        v1 = cell1.raw_value.strip().lower()
        v2 = cell2.raw_value.strip().lower()
        return v1 == v2

    @staticmethod
    def _build_challenge_map(
        challenges: list[ChallengeIssue],
    ) -> dict[CellRef, list[ChallengeIssue]]:
        """Build a lookup map from cell ref to challenges."""
        result: dict[CellRef, list[ChallengeIssue]] = {}
        for ch in challenges:
            if ch.cell_ref:
                if ch.cell_ref not in result:
                    result[ch.cell_ref] = []
                result[ch.cell_ref].append(ch)
        return result
