"""
Procedure Normalizer — maps free-text procedure names to canonical codes.

Uses a built-in vocabulary of common clinical trial procedures with
CPT/SNOMED mappings and cost tiers. Falls back to fuzzy matching
for variants and abbreviations.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from src.models.schema import CostTier, NormalizedProcedure

logger = logging.getLogger(__name__)


@dataclass
class ProcedureEntry:
    canonical_name: str
    code: str | None
    code_system: str | None
    category: str
    cost_tier: CostTier
    aliases: list[str]


# ---------------------------------------------------------------------------
# Built-in procedure vocabulary
# ---------------------------------------------------------------------------
_VOCABULARY: list[ProcedureEntry] = [
    # General
    ProcedureEntry("Vital Signs", "99000", "CPT", "General", CostTier.LOW,
                   ["vital signs", "vitals", "vs"]),
    ProcedureEntry("Physical Examination", "99213", "CPT", "General", CostTier.LOW,
                   ["physical exam", "physical examination", "pe", "full physical",
                    "complete physical", "targeted physical"]),
    ProcedureEntry("Body Weight", None, None, "General", CostTier.LOW,
                   ["body weight", "weight", "body mass"]),
    ProcedureEntry("Height", None, None, "General", CostTier.LOW,
                   ["height", "stature"]),
    ProcedureEntry("BMI", None, None, "General", CostTier.LOW,
                   ["bmi", "body mass index"]),
    ProcedureEntry("Informed Consent", None, None, "General", CostTier.LOW,
                   ["informed consent", "consent", "icf"]),
    ProcedureEntry("Medical History", None, None, "General", CostTier.LOW,
                   ["medical history", "history", "med history"]),
    ProcedureEntry("Concomitant Medications", None, None, "General", CostTier.LOW,
                   ["concomitant medications", "con meds", "conmeds",
                    "prior/concomitant medications", "medications review"]),
    ProcedureEntry("Adverse Events", None, None, "General", CostTier.LOW,
                   ["adverse events", "ae", "aes", "ae assessment",
                    "adverse event assessment"]),

    # Cardiac
    ProcedureEntry("Electrocardiogram, 12-lead", "93000", "CPT", "Cardiac", CostTier.MEDIUM,
                   ["12-lead ecg", "ecg (12l)", "ecg", "12 lead ecg",
                    "electrocardiogram", "ekg", "12-lead electrocardiogram",
                    "triplicate ecg"]),
    ProcedureEntry("Echocardiogram", "93306", "CPT", "Cardiac", CostTier.HIGH,
                   ["echocardiogram", "echo", "cardiac echo", "transthoracic echo",
                    "tte"]),
    ProcedureEntry("Holter Monitor", "93224", "CPT", "Cardiac", CostTier.MEDIUM,
                   ["holter", "holter monitor", "24-hour ecg", "ambulatory ecg"]),

    # Laboratory
    ProcedureEntry("Complete Blood Count", "85025", "CPT", "Laboratory", CostTier.LOW,
                   ["complete blood count", "cbc", "full blood count", "fbc",
                    "blood count"]),
    ProcedureEntry("Comprehensive Metabolic Panel", "80053", "CPT", "Laboratory", CostTier.LOW,
                   ["comprehensive metabolic panel", "cmp", "metabolic panel",
                    "chemistry panel"]),
    ProcedureEntry("Liver Function Tests", "80076", "CPT", "Laboratory", CostTier.LOW,
                   ["liver function tests", "lft", "lfts", "hepatic panel",
                    "hepatic function"]),
    ProcedureEntry("Renal Function Tests", "80069", "CPT", "Laboratory", CostTier.LOW,
                   ["renal function", "renal panel", "kidney function"]),
    ProcedureEntry("Coagulation Panel", "85610", "CPT", "Laboratory", CostTier.LOW,
                   ["coagulation", "coag panel", "pt/inr", "coagulation panel",
                    "pt", "aptt", "inr"]),
    ProcedureEntry("Urinalysis", "81003", "CPT", "Laboratory", CostTier.LOW,
                   ["urinalysis", "ua", "urine analysis", "urine dipstick"]),
    ProcedureEntry("Pregnancy Test", "81025", "CPT", "Laboratory", CostTier.LOW,
                   ["pregnancy test", "serum pregnancy", "urine pregnancy",
                    "bhcg", "b-hcg", "hcg"]),
    ProcedureEntry("Thyroid Function Tests", "84443", "CPT", "Laboratory", CostTier.LOW,
                   ["thyroid function", "tft", "tfts", "tsh", "thyroid panel"]),
    ProcedureEntry("Lipid Panel", "80061", "CPT", "Laboratory", CostTier.LOW,
                   ["lipid panel", "lipid profile", "fasting lipids", "cholesterol panel"]),
    ProcedureEntry("HbA1c", "83036", "CPT", "Laboratory", CostTier.LOW,
                   ["hba1c", "glycated hemoglobin", "a1c", "hemoglobin a1c"]),
    ProcedureEntry("Blood Draw", None, None, "Laboratory", CostTier.LOW,
                   ["blood draw", "blood sample", "phlebotomy", "venipuncture",
                    "blood collection"]),
    ProcedureEntry("PK Sample", None, None, "PK", CostTier.LOW,
                   ["pk sample", "pharmacokinetic sample", "pk blood sample",
                    "pk sampling"]),
    ProcedureEntry("PD Sample", None, None, "PK", CostTier.LOW,
                   ["pd sample", "pharmacodynamic sample"]),
    ProcedureEntry("Biomarker Sample", None, None, "Laboratory", CostTier.MEDIUM,
                   ["biomarker", "biomarker sample", "exploratory biomarker"]),

    # Imaging
    ProcedureEntry("MRI", "70553", "CPT", "Imaging", CostTier.HIGH,
                   ["mri", "magnetic resonance imaging", "mri scan",
                    "brain mri", "cardiac mri"]),
    ProcedureEntry("CT Scan", "74178", "CPT", "Imaging", CostTier.HIGH,
                   ["ct scan", "ct", "computed tomography", "cat scan"]),
    ProcedureEntry("X-Ray", "71046", "CPT", "Imaging", CostTier.MEDIUM,
                   ["x-ray", "xray", "radiograph", "chest x-ray", "cxr"]),
    ProcedureEntry("PET/CT Scan", "78816", "CPT", "Imaging", CostTier.VERY_HIGH,
                   ["pet/ct", "pet scan", "pet/ct scan", "pet-ct",
                    "positron emission tomography"]),
    ProcedureEntry("DEXA Scan", "77080", "CPT", "Imaging", CostTier.MEDIUM,
                   ["dexa", "dxa", "bone density", "dexa scan"]),
    ProcedureEntry("Ultrasound", "76700", "CPT", "Imaging", CostTier.MEDIUM,
                   ["ultrasound", "us", "sonography", "doppler"]),

    # Procedures
    ProcedureEntry("Tumor Biopsy", "20206", "CPT", "Procedure", CostTier.VERY_HIGH,
                   ["tumor biopsy", "biopsy", "tissue biopsy", "core biopsy",
                    "skin biopsy", "punch biopsy"]),
    ProcedureEntry("Bone Marrow Biopsy", "38221", "CPT", "Procedure", CostTier.VERY_HIGH,
                   ["bone marrow biopsy", "bone marrow aspirate", "bma"]),
    ProcedureEntry("Lumbar Puncture", "62270", "CPT", "Procedure", CostTier.VERY_HIGH,
                   ["lumbar puncture", "lp", "spinal tap", "csf collection"]),
    ProcedureEntry("Spirometry", "94010", "CPT", "Respiratory", CostTier.MEDIUM,
                   ["spirometry", "pulmonary function", "pft", "lung function"]),

    # Questionnaires / Scales
    ProcedureEntry("Quality of Life Questionnaire", None, None, "PRO", CostTier.LOW,
                   ["qol", "quality of life", "eq-5d", "sf-36", "sf36"]),
    ProcedureEntry("Pain Assessment", None, None, "PRO", CostTier.LOW,
                   ["pain assessment", "vas", "visual analog scale", "nrs",
                    "numeric rating scale", "pain score"]),
    ProcedureEntry("RECIST Assessment", None, None, "Efficacy", CostTier.MEDIUM,
                   ["recist", "tumor assessment", "response assessment"]),

    # Genetic / Specialized
    ProcedureEntry("Genetic Testing", "81479", "CPT", "Genetics", CostTier.VERY_HIGH,
                   ["genetic testing", "genomic testing", "genotyping",
                    "pharmacogenomics", "dna sequencing"]),
    ProcedureEntry("Flow Cytometry", "88182", "CPT", "Laboratory", CostTier.HIGH,
                   ["flow cytometry", "facs", "immunophenotyping"]),

    # Study Drug
    ProcedureEntry("Study Drug Administration", None, None, "Treatment", CostTier.MEDIUM,
                   ["study drug", "ip administration", "investigational product",
                    "drug administration", "dosing", "study drug administration"]),
    ProcedureEntry("Randomization", None, None, "General", CostTier.LOW,
                   ["randomization", "randomisation", "treatment assignment"]),
]


class ProcedureNormalizer:
    """Maps free-text procedure names to canonical entries."""

    def __init__(self):
        # Build lookup: lowercase alias → ProcedureEntry
        self._alias_map: dict[str, ProcedureEntry] = {}
        for entry in _VOCABULARY:
            for alias in entry.aliases:
                self._alias_map[alias.lower()] = entry

    def normalize(self, raw_name: str) -> NormalizedProcedure:
        """Normalize a single procedure name."""
        cleaned = raw_name.strip()
        lookup_key = cleaned.lower()

        # Exact match
        if lookup_key in self._alias_map:
            return self._to_model(cleaned, self._alias_map[lookup_key])

        # Substring match: check if any alias is a whole-word match in the input
        # Use word boundaries to avoid "exam" matching "experimental"
        import re
        for alias, entry in self._alias_map.items():
            # Only match if alias appears as complete words in the input
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, lookup_key):
                return self._to_model(cleaned, entry)

        # Fuzzy match: check for key terms
        match = self._fuzzy_match(lookup_key)
        if match:
            return self._to_model(cleaned, match)

        # Unknown procedure
        logger.debug(f"No match found for procedure: '{raw_name}'")
        return NormalizedProcedure(
            raw_name=cleaned,
            canonical_name=cleaned,
            code=None,
            code_system=None,
            category="Unknown",
            estimated_cost_tier=CostTier.LOW,
        )

    def normalize_batch(self, names: list[str]) -> list[NormalizedProcedure]:
        """Normalize a list of procedure names."""
        return [self.normalize(name) for name in names]

    def _fuzzy_match(self, text: str) -> ProcedureEntry | None:
        """Attempt fuzzy matching using key clinical terms."""
        # Check for key diagnostic terms
        key_terms = {
            "ecg": "ecg",
            "electrocardiogram": "ecg",
            "mri": "mri",
            "ct": "ct scan",
            "pet": "pet/ct",
            "biopsy": "tumor biopsy",
            "x-ray": "x-ray",
            "xray": "x-ray",
            "spirometry": "spirometry",
            "echo": "echocardiogram",
        }
        for term, alias in key_terms.items():
            if term in text:
                if alias in self._alias_map:
                    return self._alias_map[alias]

        return None

    @staticmethod
    def _to_model(raw_name: str, entry: ProcedureEntry) -> NormalizedProcedure:
        return NormalizedProcedure(
            raw_name=raw_name,
            canonical_name=entry.canonical_name,
            code=entry.code,
            code_system=entry.code_system,
            category=entry.category,
            estimated_cost_tier=entry.cost_tier,
        )
