"""Tests for clinical domain intelligence module."""

import pytest
from src.pipeline.clinical_domain import (
    ClinicalDomainClassifier,
    TherapeuticDomain,
    detect_pk_pd_rows,
    get_extraction_hints,
    get_expected_procedures,
    get_profile,
    get_validation_rules,
)


class TestDomainClassifier:
    def setup_method(self):
        self.classifier = ClinicalDomainClassifier()

    def test_oncology_from_procedures(self):
        procs = ["CT scan", "RECIST assessment", "ECOG performance status", "Tumor biopsy"]
        domain = self.classifier.classify_from_procedures(procs)
        assert domain == TherapeuticDomain.ONCOLOGY

    def test_oncology_from_cycle_text(self):
        text = "Schedule of Activities — Cycle 1 Day 1 through Cycle 6 Day 1, tumor assessment"
        domain = self.classifier.classify_from_text(text)
        assert domain == TherapeuticDomain.ONCOLOGY

    def test_vaccine_from_procedures(self):
        procs = ["Vaccination", "Immunogenicity blood draw", "Reactogenicity", "e-Diary"]
        domain = self.classifier.classify_from_procedures(procs)
        assert domain == TherapeuticDomain.VACCINES

    def test_cardiology_from_procedures(self):
        procs = ["Echocardiogram", "6-minute walk test", "NT-proBNP", "NYHA class"]
        domain = self.classifier.classify_from_procedures(procs)
        assert domain == TherapeuticDomain.CARDIOLOGY

    def test_autoimmune_from_procedures(self):
        procs = ["DAS28", "ACR20/50/70", "HAQ-DI", "Joint count", "CRP"]
        domain = self.classifier.classify_from_procedures(procs)
        assert domain == TherapeuticDomain.AUTOIMMUNE

    def test_pk_intensive_from_text(self):
        text = "PK sampling: pre-dose, 0.5h, 1h, 2h, 4h, 8h, 12h, 24h post-dose. Dense PK on Day 1."
        domain = self.classifier.classify_from_text(text)
        assert domain == TherapeuticDomain.PK_INTENSIVE

    def test_respiratory_from_procedures(self):
        procs = ["Spirometry", "FEV1", "FeNO", "SGRQ", "Asthma exacerbation"]
        domain = self.classifier.classify_from_procedures(procs)
        assert domain == TherapeuticDomain.RESPIRATORY

    def test_dermatology_from_procedures(self):
        procs = ["PASI 75", "IGA score", "BSA assessment", "Pruritus NRS"]
        domain = self.classifier.classify_from_procedures(procs)
        assert domain == TherapeuticDomain.DERMATOLOGY

    def test_ophthalmology_from_procedures(self):
        procs = ["BCVA", "OCT assessment", "Intravitreal injection", "IOP measurement"]
        domain = self.classifier.classify_from_procedures(procs)
        assert domain == TherapeuticDomain.OPHTHALMOLOGY

    def test_infectious_disease_from_text(self):
        text = "HIV viral load, CD4 count, antiretroviral therapy, hepatitis B"
        domain = self.classifier.classify_from_text(text)
        assert domain == TherapeuticDomain.INFECTIOUS_DISEASE

    def test_unknown_returns_general(self):
        domain = self.classifier.classify_from_text("some random unrelated text")
        assert domain == TherapeuticDomain.GENERAL

    def test_empty_text_returns_general(self):
        domain = self.classifier.classify_from_text("")
        assert domain == TherapeuticDomain.GENERAL


class TestPkPdDetection:
    def test_detect_pk_rows(self):
        procs = ["Vital Signs", "ECG", "PK blood sample", "CBC", "Pre-dose trough"]
        pk_rows = detect_pk_pd_rows(procs)
        assert "PK blood sample" in pk_rows
        assert "Pre-dose trough" in pk_rows
        assert "Vital Signs" not in pk_rows
        assert "ECG" not in pk_rows

    def test_detect_immunogenicity(self):
        procs = ["Vaccination", "Immunogenicity sample", "ADA assessment", "CBC"]
        pk_rows = detect_pk_pd_rows(procs)
        assert "Immunogenicity sample" in pk_rows
        assert "ADA assessment" in pk_rows

    def test_no_pk_rows(self):
        procs = ["Vital Signs", "Physical Exam", "CBC", "Weight"]
        pk_rows = detect_pk_pd_rows(procs)
        assert pk_rows == []


class TestDomainProfiles:
    def test_oncology_has_cycle_patterns(self):
        profile = get_profile(TherapeuticDomain.ONCOLOGY)
        assert any("C\\d+D\\d+" in p for p in profile.visit_patterns)

    def test_vaccine_has_key_procedures(self):
        procs = get_expected_procedures(TherapeuticDomain.VACCINES)
        assert any("Vaccination" in p for p in procs)
        assert any("Immunogenicity" in p for p in procs)

    def test_extraction_hints_non_empty(self):
        for domain in [TherapeuticDomain.ONCOLOGY, TherapeuticDomain.VACCINES,
                       TherapeuticDomain.PK_INTENSIVE, TherapeuticDomain.CARDIOLOGY]:
            hints = get_extraction_hints(domain)
            assert len(hints) > 50, f"Hints too short for {domain}"

    def test_validation_rules_exist(self):
        rules = get_validation_rules(TherapeuticDomain.ONCOLOGY)
        assert len(rules) >= 3

    def test_general_profile_has_no_hints(self):
        hints = get_extraction_hints(TherapeuticDomain.GENERAL)
        assert hints == ""
