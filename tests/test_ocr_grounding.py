"""Tests for OCR grounding verification module."""

import pytest
from src.models.schema import (
    BoundingBox,
    CellDataType,
    CellRef,
    ChallengeType,
    ExtractedCell,
    PageImage,
    PipelineConfig,
    TableRegion,
    TableType,
)
from src.pipeline.ocr_grounding import (
    OCRGroundingVerifier,
    OCRResult,
    OCRWord,
)


def _cell(row, col, value, dtype=CellDataType.TEXT):
    return ExtractedCell(row=row, col=col, raw_value=value, data_type=dtype)


class TestGroundingVerifier:
    def setup_method(self):
        self.config = PipelineConfig(soa_only=False)
        self.verifier = OCRGroundingVerifier(self.config)

    def test_empty_cell_always_grounded(self):
        """Empty cells should always pass grounding."""
        cell = _cell(0, 0, "", CellDataType.EMPTY)
        ocr_text = "some random text"
        verdict = self.verifier._verify_one_cell(cell, ocr_text, [])
        assert verdict.grounded is True
        assert verdict.confidence_adjustment == 1.0

    def test_marker_cell_passes(self):
        """Single character markers (X, ✓) should pass grounding."""
        cell = _cell(0, 0, "X", CellDataType.MARKER)
        ocr_text = "x mark here"
        verdict = self.verifier._verify_one_cell(cell, ocr_text, [])
        assert verdict.grounded is True

    def test_text_confirmed_by_ocr(self):
        """Text cell where OCR confirms the words → grounded."""
        cell = _cell(0, 0, "Complete Blood Count")
        ocr_text = "screening complete blood count and chemistry panel"
        verdict = self.verifier._verify_one_cell(cell, ocr_text, [])
        assert verdict.grounded is True
        assert verdict.confidence_adjustment == 1.0

    def test_text_not_in_ocr_flagged(self):
        """Text cell where OCR does NOT find the words → ungrounded."""
        cell = _cell(0, 0, "Fabricated Procedure Name")
        ocr_text = "vital signs physical exam ecg laboratory tests"
        verdict = self.verifier._verify_one_cell(cell, ocr_text, [])
        assert verdict.grounded is False
        assert verdict.confidence_adjustment < 1.0

    def test_partial_match_partial_confidence(self):
        """Cell with some words confirmed, some not → partial confidence."""
        cell = _cell(0, 0, "Review hematology and chemistry results")
        ocr_text = "review hematology results from central laboratory"
        verdict = self.verifier._verify_one_cell(cell, ocr_text, [])
        # "review", "hematology", "results" confirmed; "chemistry" not
        assert verdict.grounded is True  # Majority confirmed
        assert verdict.confidence_adjustment >= 0.85

    def test_verdicts_to_challenges(self):
        """Ungrounded verdicts should produce ChallengeIssues."""
        from src.pipeline.ocr_grounding import GroundingVerdict
        verdicts = [
            GroundingVerdict(
                cell_ref=CellRef(row=0, col=0),
                extracted_value="Invented Procedure",
                grounded=False,
                ocr_evidence="actual text here",
                confidence_adjustment=0.5,
            ),
            GroundingVerdict(
                cell_ref=CellRef(row=0, col=1),
                extracted_value="X",
                grounded=True,
                ocr_evidence="",
                confidence_adjustment=1.0,
            ),
        ]
        challenges = self.verifier.verdicts_to_challenges(verdicts)
        assert len(challenges) == 1
        assert challenges[0].challenge_type == ChallengeType.HALLUCINATED_VALUE
        assert "Invented Procedure" in challenges[0].description

    def test_available_property(self):
        """available should reflect whether an OCR backend was loaded."""
        # On test machines, OCR may or may not be available
        assert isinstance(self.verifier.available, bool)

    def test_empty_value_not_flagged(self):
        """Empty extracted values should NOT generate challenges."""
        from src.pipeline.ocr_grounding import GroundingVerdict
        verdicts = [
            GroundingVerdict(
                cell_ref=CellRef(row=0, col=0),
                extracted_value="",
                grounded=False,
                ocr_evidence="",
                confidence_adjustment=0.5,
            ),
        ]
        challenges = self.verifier.verdicts_to_challenges(verdicts)
        assert len(challenges) == 0  # Empty values not flagged
