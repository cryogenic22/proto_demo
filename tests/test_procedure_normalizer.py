"""Tests for procedure normalizer module."""

import pytest

from src.models.schema import CostTier, NormalizedProcedure
from src.pipeline.procedure_normalizer import ProcedureNormalizer


class TestProcedureNormalizer:
    def setup_method(self):
        self.normalizer = ProcedureNormalizer()

    def test_exact_match(self):
        result = self.normalizer.normalize("Vital Signs")
        assert result.canonical_name == "Vital Signs"
        assert result.estimated_cost_tier == CostTier.LOW

    def test_case_insensitive(self):
        result = self.normalizer.normalize("vital signs")
        assert result.canonical_name == "Vital Signs"

    def test_abbreviation_ecg(self):
        result = self.normalizer.normalize("12-lead ECG")
        assert result.canonical_name == "Electrocardiogram, 12-lead"
        assert result.estimated_cost_tier == CostTier.MEDIUM

    def test_abbreviation_ecg_variant(self):
        result = self.normalizer.normalize("ECG (12L)")
        assert result.canonical_name == "Electrocardiogram, 12-lead"

    def test_mri(self):
        result = self.normalizer.normalize("MRI")
        assert result.estimated_cost_tier == CostTier.HIGH

    def test_pet_scan(self):
        result = self.normalizer.normalize("PET/CT scan")
        assert result.estimated_cost_tier == CostTier.VERY_HIGH

    def test_biopsy(self):
        result = self.normalizer.normalize("Tumor biopsy")
        assert result.estimated_cost_tier == CostTier.VERY_HIGH

    def test_blood_draw_generic(self):
        result = self.normalizer.normalize("Blood draw")
        assert result.category in ["Laboratory", "General"]

    def test_unknown_procedure(self):
        """Unknown procedures should return raw name as canonical with LOW tier."""
        result = self.normalizer.normalize("Experimental Zorblax Test")
        assert result.raw_name == "Experimental Zorblax Test"
        assert result.canonical_name == "Experimental Zorblax Test"
        assert result.code is None

    def test_normalize_batch(self):
        names = ["Vital Signs", "ECG", "MRI", "Blood draw"]
        results = self.normalizer.normalize_batch(names)
        assert len(results) == 4
        assert all(isinstance(r, NormalizedProcedure) for r in results)

    def test_cpt_code_present_for_known(self):
        result = self.normalizer.normalize("Complete Blood Count")
        assert result.code is not None
        assert result.code_system == "CPT"

    def test_physical_examination(self):
        result = self.normalizer.normalize("Physical Exam")
        assert result.canonical_name == "Physical Examination"
        assert result.estimated_cost_tier in (CostTier.LOW, CostTier.MEDIUM)
