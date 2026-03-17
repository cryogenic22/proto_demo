"""
Clinical Domain Intelligence — embeds therapeutic area knowledge into extraction.

Provides:
1. Protocol classification (oncology, vaccine, PK-intensive, etc.)
2. Domain-specific SoA interpretation hints for VLM prompts
3. Expected procedure patterns for validation
4. PK/PD sub-schedule detection
5. Clinical plausibility rules per domain
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TherapeuticDomain(str, Enum):
    ONCOLOGY = "ONCOLOGY"
    HEMATOLOGY = "HEMATOLOGY"
    VACCINES = "VACCINES"
    CARDIOLOGY = "CARDIOLOGY"
    NEUROLOGY = "NEUROLOGY"
    AUTOIMMUNE = "AUTOIMMUNE"
    RARE_DISEASE = "RARE_DISEASE"
    RESPIRATORY = "RESPIRATORY"
    INFECTIOUS_DISEASE = "INFECTIOUS_DISEASE"
    ENDOCRINOLOGY = "ENDOCRINOLOGY"
    DERMATOLOGY = "DERMATOLOGY"
    OPHTHALMOLOGY = "OPHTHALMOLOGY"
    PSYCHIATRY = "PSYCHIATRY"
    PK_INTENSIVE = "PK_INTENSIVE"  # Phase I dose-escalation
    GENERAL = "GENERAL"


@dataclass
class DomainProfile:
    """Domain-specific knowledge for SoA interpretation."""
    domain: TherapeuticDomain
    visit_patterns: list[str]          # Expected visit header patterns
    expected_row_groups: list[str]     # Expected procedure group names
    key_procedures: list[str]          # Domain-specific procedures to look for
    pk_pd_indicators: list[str]        # Markers of PK/PD sub-schedules
    frequency_rules: dict[str, str]    # procedure → typical frequency expectation
    plausibility_rules: list[str]      # Clinical validation rules
    prompt_hints: str                  # Extra context for VLM prompts


# ---------------------------------------------------------------------------
# Domain profiles
# ---------------------------------------------------------------------------

ONCOLOGY_PROFILE = DomainProfile(
    domain=TherapeuticDomain.ONCOLOGY,
    visit_patterns=[
        r"C\d+D\d+",                    # Cycle 1 Day 1 (C1D1)
        r"Cycle\s+\d+\s+Day\s+\d+",     # Cycle 1 Day 1 (long form)
        r"Day\s+\d+\s+of\s+Cycle",      # Day 1 of Cycle 2
        r"Q\d+W",                         # Q3W, Q4W dosing intervals
        r"Every\s+\d+\s+weeks",           # Every 3 weeks
    ],
    expected_row_groups=[
        "Efficacy Assessments", "Safety Assessments", "Tumor Assessments",
        "Laboratory Assessments", "PK Assessments", "Biomarker Assessments",
        "Imaging", "Drug Administration", "Other Assessments",
    ],
    key_procedures=[
        "CT scan", "MRI", "PET/CT", "Tumor biopsy", "RECIST assessment",
        "Bone scan", "Study drug administration", "Response assessment",
        "Tumor marker", "ctDNA", "CEA", "CA-125", "PSA",
        "ECOG performance status", "BSA calculation",
        "Dose modification assessment", "DLT assessment",
    ],
    pk_pd_indicators=[
        "PK sample", "Pharmacokinetic", "Ctrough", "Cmax", "AUC",
        "Pre-dose", "Post-dose", "trough", "sparse PK", "dense PK",
        "Immunogenicity sample", "ADA", "Anti-drug antibody",
    ],
    frequency_rules={
        "PET/CT": "Typically screening + every 2-4 cycles or at response assessment",
        "CT scan": "Typically every 6-12 weeks",
        "Tumor biopsy": "Typically screening ± end of treatment, rarely more than 2-3",
        "ECOG": "Every visit or every cycle",
        "DLT assessment": "Phase I only, during DLT evaluation window",
    },
    plausibility_rules=[
        "Tumor assessments (CT/MRI/PET) should NOT be at every visit — typically every 6-12 weeks",
        "Dose modification decisions happen at the start of each new cycle",
        "RECIST assessment aligns with imaging timepoints, not independently",
        "Bone scan frequency is less than CT/MRI frequency",
        "DLT assessment is Phase I specific — absent in Phase III",
    ],
    prompt_hints="""This is an ONCOLOGY protocol. Key patterns:
- Visit headers are likely CYCLE-based (C1D1, C2D1, etc.) not calendar-based
- Look for separate rows for each chemotherapy/immunotherapy drug
- RECIST/tumor assessments are tied to imaging timepoints
- PK sampling rows may have sub-timepoints (pre-dose, 1h, 2h, 4h post-dose)
- Dose modification criteria may be footnoted on the drug administration row
- Different treatment arms may have different cycle lengths""",
)

VACCINE_PROFILE = DomainProfile(
    domain=TherapeuticDomain.VACCINES,
    visit_patterns=[
        r"Day\s+\d+",                    # Day 1, Day 29
        r"Visit\s+\d+",                  # Visit 1, Visit 2
        r"Month\s+\d+",                  # Month 6, Month 12
        r"Dose\s+\d+",                   # Dose 1, Dose 2
        r"Post-vaccination",             # Post-vaccination day 7
    ],
    expected_row_groups=[
        "Vaccination", "Safety Assessments", "Immunogenicity",
        "Reactogenicity", "Laboratory Assessments",
    ],
    key_procedures=[
        "Vaccination", "Immunogenicity blood draw", "Serology",
        "Neutralizing antibody", "IgG titer", "T-cell assay",
        "Reactogenicity assessment", "e-Diary", "Telephone contact",
        "Solicited adverse events", "Unsolicited adverse events",
    ],
    pk_pd_indicators=[
        "Immunogenicity", "Antibody titer", "Seroconversion",
        "GMT", "Geometric mean titer", "Fold-rise",
        "Neutralizing antibody", "Binding antibody",
    ],
    frequency_rules={
        "Vaccination": "Fixed schedule (e.g., Day 1, Day 29 for 2-dose)",
        "Immunogenicity": "Pre-vaccination + multiple post-vaccination timepoints",
        "e-Diary": "Daily for 7 days post each vaccination",
        "Serology": "Pre + 28 days post each dose",
    },
    plausibility_rules=[
        "Vaccination visits are fixed, not window-based",
        "Immunogenicity draws cluster around vaccination dates (pre-dose, Day 7, Day 28)",
        "Telephone contacts fill gaps between in-clinic visits",
        "Reactogenicity is solicited for 7 days post-vaccination only",
        "Different age groups may have different blood draw volumes",
    ],
    prompt_hints="""This is a VACCINE protocol. Key patterns:
- Visit headers are typically Day-based or Visit-number-based
- Look for separate rows for vaccination vs. blood draws vs. telephone contacts
- Immunogenicity sampling has precise timing (pre-dose, Day 7, Day 28 post each dose)
- e-Diary/reactogenicity rows are only active for ~7 days post-vaccination
- Multiple dose groups or age cohorts may have slightly different schedules
- Telephone contacts are distinct from in-clinic visits""",
)

PK_INTENSIVE_PROFILE = DomainProfile(
    domain=TherapeuticDomain.PK_INTENSIVE,
    visit_patterns=[
        r"Pre[-\s]?dose",                # Pre-dose
        r"\d+\.?\d*\s*h",                # 0.5h, 1h, 2h, 4h, 8h, 12h, 24h
        r"Post[-\s]?dose",               # Post-dose
        r"Day\s+\d+",                    # Day 1, Day 2
        r"\d+\s*min",                    # 15 min, 30 min
    ],
    expected_row_groups=[
        "PK Sampling", "Safety Assessments", "Drug Administration",
        "Laboratory Assessments", "Vital Signs",
    ],
    key_procedures=[
        "PK blood sample", "Pre-dose sample", "Post-dose sample",
        "Urine PK collection", "Sparse PK sample", "Dense PK sample",
        "Metabolite sample", "Drug concentration",
        "Dose administration", "ECG (triplicate)", "Vital signs",
        "QTc assessment",
    ],
    pk_pd_indicators=[
        "PK", "Pharmacokinetic", "Cmax", "Tmax", "AUC", "t1/2",
        "Ctrough", "Pre-dose", "Post-dose",
        "Dense sampling", "Sparse sampling",
        "0h", "0.5h", "1h", "2h", "4h", "8h", "12h", "24h",
        "Urine collection",
    ],
    frequency_rules={
        "Dense PK": "Multiple timepoints on dosing days (0, 0.5, 1, 2, 4, 8, 12, 24h)",
        "Sparse PK": "Pre-dose + 1-2 post-dose timepoints",
        "ECG triplicate": "Aligned with PK sampling timepoints for QTc analysis",
        "Vital signs": "Pre-dose and at key PK timepoints",
    },
    plausibility_rules=[
        "Dense PK days have 8-12 sampling timepoints, NOT the whole study",
        "PK sub-table often has intra-day columns (hours) while main SoA has day/week columns",
        "ECG and vital signs align with PK sampling timepoints on dense PK days",
        "Pre-dose samples are ALWAYS collected before drug administration",
        "24h sample may be collected on the following calendar day",
    ],
    prompt_hints="""This is a PK-INTENSIVE protocol (likely Phase I). Key patterns:
- Look for a PK SAMPLING SUB-TABLE within or alongside the main SoA
- PK sub-tables have INTRA-DAY columns: pre-dose, 0.5h, 1h, 2h, 4h, 8h, 12h, 24h
- This is DIFFERENT from the main SoA which has Day/Week columns
- Triplicate ECGs and vital signs are timed to PK sampling windows
- Dense PK days (often Day 1 and a steady-state day) have many more timepoints
- Sparse PK at other visits = pre-dose trough only
- The sub-table may have its own set of footnotes""",
)

CARDIOLOGY_PROFILE = DomainProfile(
    domain=TherapeuticDomain.CARDIOLOGY,
    visit_patterns=[
        r"Week\s+\d+", r"Month\s+\d+", r"Day\s+\d+",
    ],
    expected_row_groups=[
        "Cardiac Assessments", "Safety Assessments",
        "Efficacy Assessments", "Laboratory Assessments",
    ],
    key_procedures=[
        "12-lead ECG", "Echocardiogram", "Holter monitor", "LVEF assessment",
        "NT-proBNP", "BNP", "Troponin", "6-minute walk test", "6MWD",
        "KCCQ", "NYHA class", "Blood pressure", "Heart rate",
        "QTcF assessment", "Cardiac MRI",
    ],
    pk_pd_indicators=[],
    frequency_rules={
        "Echocardiogram": "Screening + every 3-6 months",
        "6MWD": "Screening + every 3-6 months",
        "NT-proBNP": "Every visit or monthly",
        "Cardiac MRI": "Screening + end of treatment",
    },
    plausibility_rules=[
        "Echocardiograms are NOT at every visit — typically quarterly",
        "6MWD and echocardiogram often share the same visit schedule",
        "NT-proBNP/BNP is a blood test, much more frequent than imaging",
        "NYHA class is assessed at every visit (clinical assessment, not a test)",
    ],
    prompt_hints="""This is a CARDIOLOGY protocol. Key patterns:
- Look for cardiac-specific assessments: ECG, echo, 6MWD, KCCQ, NT-proBNP
- NYHA functional class is a clinical assessment, not a procedure
- Event-driven endpoints (MACE) may create unscheduled visit triggers in footnotes
- Dose titration may be reflected in footnotes modifying early visit procedures""",
)

AUTOIMMUNE_PROFILE = DomainProfile(
    domain=TherapeuticDomain.AUTOIMMUNE,
    visit_patterns=[
        r"Week\s+\d+", r"Month\s+\d+", r"Day\s+\d+",
    ],
    expected_row_groups=[
        "Efficacy Assessments", "Safety Assessments",
        "Laboratory Assessments", "Drug Administration",
    ],
    key_procedures=[
        "DAS28", "ACR20/50/70", "CDAI", "SDAI", "HAQ-DI",
        "PASI", "IGA", "EASI", "NRS pruritus", "BSA",
        "CRP", "ESR", "RF", "Anti-CCP",
        "Joint count", "Patient global assessment", "Physician global assessment",
        "Modified Mayo score", "Endoscopy", "Calprotectin",
    ],
    pk_pd_indicators=[
        "ADA", "Anti-drug antibody", "Immunogenicity",
        "Drug level", "Trough concentration",
    ],
    frequency_rules={
        "Endoscopy": "Screening + Week 8-12 (induction) + Week 52 (maintenance)",
        "Joint count": "Every visit in RA",
        "PASI": "Every visit in psoriasis",
        "DAS28": "Every visit in RA",
    },
    plausibility_rules=[
        "Disease activity scores (DAS28, CDAI, PASI, EASI) are at every visit",
        "Endoscopy is infrequent (2-3 times total) — it's invasive",
        "ADA/immunogenicity samples cluster at specific timepoints (pre-dose, Week 12, Week 52)",
        "Rescue therapy criteria may branch the SoA into separate tracks",
    ],
    prompt_hints="""This is an AUTOIMMUNE/RHEUMATOLOGY protocol. Key patterns:
- Disease activity scores are assessed at every visit (DAS28, PASI, EASI, etc.)
- Look for rescue therapy / escape criteria in footnotes that branch the schedule
- ADA (anti-drug antibody) sampling has its own schedule distinct from efficacy
- Multi-period designs are common: induction + maintenance + long-term extension""",
)

# General fallback
GENERAL_PROFILE = DomainProfile(
    domain=TherapeuticDomain.GENERAL,
    visit_patterns=[r"Day\s+\d+", r"Week\s+\d+", r"Month\s+\d+", r"Visit\s+\d+"],
    expected_row_groups=["Safety", "Efficacy", "Laboratory", "Other"],
    key_procedures=[],
    pk_pd_indicators=["PK", "Pharmacokinetic", "Pre-dose", "Post-dose"],
    frequency_rules={},
    plausibility_rules=[],
    prompt_hints="",
)

# All profiles indexed by domain
_PROFILES: dict[TherapeuticDomain, DomainProfile] = {
    TherapeuticDomain.ONCOLOGY: ONCOLOGY_PROFILE,
    TherapeuticDomain.VACCINES: VACCINE_PROFILE,
    TherapeuticDomain.PK_INTENSIVE: PK_INTENSIVE_PROFILE,
    TherapeuticDomain.CARDIOLOGY: CARDIOLOGY_PROFILE,
    TherapeuticDomain.AUTOIMMUNE: AUTOIMMUNE_PROFILE,
    TherapeuticDomain.GENERAL: GENERAL_PROFILE,
}


# ---------------------------------------------------------------------------
# Domain classifier
# ---------------------------------------------------------------------------

# Keywords for domain classification from SoA content
_DOMAIN_SIGNALS: dict[TherapeuticDomain, list[str]] = {
    TherapeuticDomain.ONCOLOGY: [
        "tumor", "tumour", "RECIST", "cycle", "C1D1", "chemotherapy",
        "immunotherapy", "progression", "response assessment", "ECOG",
        "dose escalation", "DLT", "MTD", "ORR", "PFS", "OS",
        "nivolumab", "pembrolizumab", "atezolizumab", "durvalumab",
        "biopsy", "ctDNA", "PD-L1",
    ],
    TherapeuticDomain.HEMATOLOGY: [
        "bone marrow", "CAR-T", "leukapheresis", "lymphodepletion",
        "CRS", "cytokine release", "engraftment", "MRD",
        "venetoclax", "ramp-up", "TLS", "tumor lysis",
    ],
    TherapeuticDomain.VACCINES: [
        "vaccination", "immunogenicity", "seroconversion", "GMT",
        "antibody titer", "reactogenicity", "e-diary", "booster",
        "adjuvant", "antigen", "dose 1", "dose 2",
    ],
    TherapeuticDomain.CARDIOLOGY: [
        "echocardiogram", "LVEF", "NT-proBNP", "BNP", "6MWD",
        "KCCQ", "NYHA", "heart failure", "ejection fraction",
        "MACE", "cardiovascular",
    ],
    TherapeuticDomain.AUTOIMMUNE: [
        "DAS28", "ACR20", "CDAI", "SDAI", "HAQ-DI",
        "PASI", "IGA", "EASI", "endoscopy", "Mayo score",
        "calprotectin", "rheumatoid", "psoriasis", "colitis",
    ],
    TherapeuticDomain.PK_INTENSIVE: [
        "pre-dose", "post-dose", "Cmax", "AUC", "trough",
        "dense PK", "sparse PK", "dose escalation",
        "0.5h", "1h", "2h", "4h", "8h", "12h", "24h",
        "sentinel", "cohort", "MAD", "SAD",
    ],
    TherapeuticDomain.RESPIRATORY: [
        "FEV1", "spirometry", "FeNO", "eosinophil", "asthma",
        "COPD", "exacerbation", "SGRQ", "ACQ",
    ],
    TherapeuticDomain.INFECTIOUS_DISEASE: [
        "viral load", "CD4", "HIV", "HBV", "HCV", "hepatitis",
        "seroconversion", "antiretroviral", "PrEP",
    ],
    TherapeuticDomain.DERMATOLOGY: [
        "PASI", "IGA", "EASI", "BSA", "pruritus", "NRS",
        "atopic", "psoriasis", "eczema",
    ],
    TherapeuticDomain.OPHTHALMOLOGY: [
        "BCVA", "OCT", "intravitreal", "macular", "retinal",
        "IOP", "fundoscopy", "aflibercept", "ranibizumab",
    ],
}


class ClinicalDomainClassifier:
    """Classifies the therapeutic domain of a protocol from its content."""

    def classify_from_text(self, text: str) -> TherapeuticDomain:
        """Classify domain from any text (table titles, procedure names, etc.)."""
        text_lower = text.lower()
        scores: dict[TherapeuticDomain, int] = {}

        for domain, keywords in _DOMAIN_SIGNALS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                scores[domain] = score

        if not scores:
            return TherapeuticDomain.GENERAL

        # Return the domain with the highest signal count
        best = max(scores, key=scores.get)  # type: ignore
        logger.info(f"Domain classified as {best.value} (score={scores[best]}, signals={scores})")
        return best

    def classify_from_procedures(self, procedure_names: list[str]) -> TherapeuticDomain:
        """Classify from a list of extracted procedure names."""
        combined = " ".join(procedure_names)
        return self.classify_from_text(combined)


def get_profile(domain: TherapeuticDomain) -> DomainProfile:
    """Get the domain profile for a given therapeutic area."""
    return _PROFILES.get(domain, GENERAL_PROFILE)


def get_extraction_hints(domain: TherapeuticDomain) -> str:
    """Get domain-specific hints to append to VLM extraction prompts."""
    profile = get_profile(domain)
    if not profile.prompt_hints:
        return ""

    hints = profile.prompt_hints

    # Add PK/PD detection hints if the domain has PK indicators
    if profile.pk_pd_indicators:
        pk_keywords = ", ".join(profile.pk_pd_indicators[:10])
        hints += f"""

IMPORTANT — PK/PD Sub-Schedule Detection:
This protocol may contain a PK/PD sampling sub-table embedded within the SoA.
Look for rows containing: {pk_keywords}
PK sub-tables often have DIFFERENT column headers from the main SoA
(hours instead of days/weeks). Extract these as a separate row group."""

    return hints


def get_validation_rules(domain: TherapeuticDomain) -> list[str]:
    """Get domain-specific plausibility rules for output validation."""
    profile = get_profile(domain)
    return profile.plausibility_rules


def detect_pk_pd_rows(procedure_names: list[str]) -> list[str]:
    """Identify which procedures are PK/PD-related."""
    pk_keywords = set()
    for profile in _PROFILES.values():
        pk_keywords.update(kw.lower() for kw in profile.pk_pd_indicators)

    pk_rows = []
    for name in procedure_names:
        name_lower = name.lower()
        if any(kw in name_lower for kw in pk_keywords):
            pk_rows.append(name)

    return pk_rows


def get_expected_procedures(domain: TherapeuticDomain) -> list[str]:
    """Get the list of procedures expected for this domain."""
    profile = get_profile(domain)
    return profile.key_procedures
