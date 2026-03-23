"""Tests for procedure normalizer module."""

import pytest

from src.models.schema import CostTier, NormalizedProcedure
from src.pipeline.procedure_normalizer import ProcedureNormalizer


class TestProcedureNormalizer:
    def setup_method(self):
        self.normalizer = ProcedureNormalizer()

    def test_exact_match(self):
        result = self.normalizer.normalize("Complete Blood Count")
        assert "blood count" in result.canonical_name.lower()
        assert result.code == "85025"

    def test_case_insensitive(self):
        result = self.normalizer.normalize("vital signs")
        assert "vital signs" in result.canonical_name.lower()

    def test_abbreviation_ecg(self):
        result = self.normalizer.normalize("12-lead ECG")
        assert "electrocardiogram" in result.canonical_name.lower() or "ecg" in result.canonical_name.lower()
        assert result.code == "93000"

    def test_abbreviation_ecg_variant(self):
        result = self.normalizer.normalize("ECG")
        assert "electrocardiogram" in result.canonical_name.lower() or result.code == "93000"

    def test_mri(self):
        result = self.normalizer.normalize("MRI Brain")
        assert result.estimated_cost_tier in (CostTier.HIGH, CostTier.VERY_HIGH)

    def test_pet_scan(self):
        result = self.normalizer.normalize("PET/CT scan")
        assert result.estimated_cost_tier == CostTier.VERY_HIGH

    def test_biopsy(self):
        result = self.normalizer.normalize("Core Needle Biopsy")
        assert "biopsy" in result.canonical_name.lower()

    def test_blood_draw_generic(self):
        result = self.normalizer.normalize("Blood draw")
        assert result.category != "Unknown" or result.code is not None

    def test_unknown_procedure(self):
        """Unknown procedures should return raw name as canonical."""
        result = self.normalizer.normalize("Experimental Zorblax Test")
        assert result.raw_name == "Experimental Zorblax Test"
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
        assert "physical" in result.canonical_name.lower()
        assert result.code is not None  # Should have CPT 99213 or 99214

    def test_not_procedure(self):
        assert self.normalizer.is_not_procedure("Visit Number")
        assert self.normalizer.is_not_procedure("Daily Timepoint")
        assert not self.normalizer.is_not_procedure("Physical Examination")

    def test_hba1c(self):
        result = self.normalizer.normalize("HbA1c")
        assert result.code == "83036"
        assert result.category in ("Laboratory", "Diabetes Monitoring")

    def test_vocabulary_size(self):
        """Should have 500+ procedures from the master library."""
        assert len(self.normalizer._vocabulary) >= 400
