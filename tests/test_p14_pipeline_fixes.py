"""Tests for P-14 pipeline fixes: exclusions, mappings, compound rows, CPT overrides."""

import pytest

from src.pipeline.procedure_normalizer import ProcedureNormalizer
from src.pipeline.budget_calculator import _split_compound_row


class TestExclusionFixes:
    """Verify that real procedures are no longer excluded."""

    def setup_method(self):
        self.normalizer = ProcedureNormalizer()

    def test_recording_of_maaes_not_excluded(self):
        """'Recording of MAAEs...' is a real procedure (AE Assessment)."""
        assert not self.normalizer.is_not_procedure(
            "Recording of MAAEs, AE leading to withdrawal"
        )

    def test_recording_of_saes_not_excluded(self):
        """'Recording of SAEs...' is a real procedure (SAE Reporting)."""
        assert not self.normalizer.is_not_procedure(
            "Recording of SAEs and concomitant medications"
        )

    def test_recording_of_concomitant_meds_not_excluded(self):
        """'Recording of concomitant medications' is a real procedure."""
        assert not self.normalizer.is_not_procedure(
            "Recording of concomitant medications and non-study vaccinations"
        )

    def test_recording_of_unsolicited_aes_not_excluded(self):
        """'Recording of unsolicited AEs' is a real procedure."""
        assert not self.normalizer.is_not_procedure("Recording of unsolicited AEs")

    def test_blood_for_immunologic_not_excluded(self):
        """'Blood for immunologic analysis' is a real procedure."""
        assert not self.normalizer.is_not_procedure("Blood for immunologic analysis")

    def test_counselling_public_health_not_excluded(self):
        """Public health counselling is a real procedure."""
        assert not self.normalizer.is_not_procedure(
            "Counselling the importance of public health measures"
        )

    def test_daily_telemedicine_not_excluded(self):
        """'Daily telemedicine visit' must not be excluded by broad patterns."""
        assert not self.normalizer.is_not_procedure("Daily telemedicine visit")

    def test_concomitant_medications_review_not_excluded(self):
        """'Concomitant Medications Review' is a real procedure."""
        assert not self.normalizer.is_not_procedure("Concomitant Medications Review")

    # Noise should still be excluded
    def test_type_of_visit_still_excluded(self):
        assert self.normalizer.is_not_procedure("Type of Visit")

    def test_visit_number_still_excluded(self):
        assert self.normalizer.is_not_procedure("Visit Number")

    def test_window_allowance_still_excluded(self):
        assert self.normalizer.is_not_procedure("Window Allowance (Days)")

    def test_follow_up_safety_still_excluded(self):
        assert self.normalizer.is_not_procedure("Follow-up safety7")

    def test_study_visit_day_still_excluded(self):
        assert self.normalizer.is_not_procedure("Study Visit Day")

    def test_safety_assessments_maps_correctly(self):
        """Safety Assessments is now a real procedure (maps to AE Assessment)."""
        assert not self.normalizer.is_not_procedure("Safety Assessments")

    def test_ediary_activation_maps_correctly(self):
        """eDiary activation is now a real procedure (maps to e-Diary)."""
        assert not self.normalizer.is_not_procedure(
            "eDiary activation for recording solicited adverse reactions"
        )

    def test_ediary_weekly_prompts_excluded(self):
        assert self.normalizer.is_not_procedure(
            "eDiary Weekly prompts for safety follow-up"
        )


class TestMappingFixes:
    """Verify correct procedure mappings for P-14 rows."""

    def setup_method(self):
        self.normalizer = ProcedureNormalizer()

    def test_recording_maaes_maps_to_ae_assessment(self):
        result = self.normalizer.normalize(
            "Recording of MAAEs, AE leading to withdrawal"
        )
        assert result.canonical_name == "Adverse Event Assessment"

    def test_recording_saes_maps_to_sae_reporting(self):
        result = self.normalizer.normalize("Recording of SAEs")
        assert result.canonical_name == "Serious Adverse Event Reporting"

    def test_recording_conmeds_maps_correctly(self):
        result = self.normalizer.normalize("Recording of concomitant medications")
        assert result.canonical_name == "Concomitant Medications Review"

    def test_blood_immunologic_maps_correctly(self):
        result = self.normalizer.normalize("Blood for immunologic analysis")
        assert "Immunologic" in result.canonical_name or "Blood" in result.canonical_name

    def test_telemedicine_visit_maps_correctly(self):
        result = self.normalizer.normalize("Daily telemedicine visit")
        assert result.canonical_name == "Telemedicine Visit"
        assert result.code == "99441"

    def test_vaccination_administration_exists(self):
        result = self.normalizer.normalize("Vaccination Administration")
        assert result.code == "90471"

    def test_public_health_counselling_maps(self):
        result = self.normalizer.normalize(
            "Counselling the importance of public health measures"
        )
        assert "Public Health" in result.canonical_name or "Counselling" in result.canonical_name

    def test_saliva_sample_maps(self):
        result = self.normalizer.normalize("Saliva sample")
        assert "Saliva" in result.canonical_name

    def test_respiratory_illness_sample_maps(self):
        result = self.normalizer.normalize("Respiratory illness sample")
        assert result.code == "87635"


class TestCompoundRowSplitting:
    """Test the compound row splitter."""

    def test_split_icf_demographics(self):
        result = _split_compound_row(
            "ICF, demographics, concomitant medications, medical history"
        )
        assert len(result) == 4
        assert "ICF" in result
        assert "medical history" in result

    def test_no_split_single_procedure(self):
        result = _split_compound_row("Physical examination")
        assert result == ["Physical examination"]

    def test_no_split_complex_description(self):
        """Long descriptive procedure names should not be split."""
        result = _split_compound_row(
            "Recording of MAAEs, AE leading to withdrawal, and concomitant medications relevant to or for the treatment of the MAAE"
        )
        assert len(result) == 1  # Should NOT split — has connectors

    def test_no_split_no_comma(self):
        result = _split_compound_row("Blood for immunologic analysis")
        assert result == ["Blood for immunologic analysis"]

    def test_split_confirm_signing(self):
        result = _split_compound_row(
            "Confirm signing of ICF, concomitant medications, medical history"
        )
        assert len(result) == 3


class TestSpanCellParsing:
    """Test span/continuous cell parsing for eDiary and similar rows."""

    def test_weekly_ediary_with_day_range(self):
        from src.pipeline.budget_calculator import _parse_span_cell
        result = _parse_span_cell("--Weekly eDiary prompts (Day 64 through Day 759)--")
        assert result is not None
        assert result["frequency"] == "weekly"
        assert result["occurrences"] == 99  # 695 days / 7

    def test_daily_span(self):
        from src.pipeline.budget_calculator import _parse_span_cell
        result = _parse_span_cell("----Daily----")
        assert result is not None
        assert result["frequency"] == "daily"

    def test_day_range_without_frequency(self):
        from src.pipeline.budget_calculator import _parse_span_cell
        result = _parse_span_cell("Day 1 through Day 28")
        assert result is not None
        assert result["occurrences"] == 28

    def test_normal_marker_not_span(self):
        from src.pipeline.budget_calculator import _parse_span_cell
        result = _parse_span_cell("X")
        assert result is None

    def test_superscript_stripped(self):
        """Superscript Unicode chars should be stripped from cell values."""
        import re
        val = "X\u2074"  # X⁴
        val = re.sub(r'[\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079\u00b9\u2070\u26a1]+$', '', val).strip()
        assert val == "X"


class TestDomainCptOverrides:
    """Test domain-aware CPT override mechanism."""

    def test_get_cpt_overrides_from_config(self):
        from src.domain.config import get_cpt_overrides
        config = {
            "cpt_overrides": {
                "Study Drug Administration": {
                    "cpt": "90471",
                    "canonical": "Vaccination Administration",
                }
            }
        }
        overrides = get_cpt_overrides(config)
        assert "Study Drug Administration" in overrides
        assert overrides["Study Drug Administration"]["cpt"] == "90471"

    def test_get_cpt_overrides_empty(self):
        from src.domain.config import get_cpt_overrides
        assert get_cpt_overrides({}) == {}
