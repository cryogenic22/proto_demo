"""
ProtocolContextExtractor — reads protocol sections to extract structured context.

This is the bridge that makes the SMB read the WHOLE protocol, not just SoA cells.
Uses TA-specific YAML profiles to know what to look for in each section.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_TA_PROFILES_DIR = Path(__file__).parent.parent / "domains" / "ta_profiles"


@dataclass
class TreatmentRegimen:
    cycle_length_days: int | None = None
    expected_duration_months: int | None = None
    expected_cycles: int | None = None
    total_doses: int | None = None
    dose_interval_days: int | None = None
    treat_to_progression: bool = False
    treatment_cap: str = ""
    follow_up_duration_months: int | None = None
    raw_text: str = ""


@dataclass
class PopulationSubset:
    name: str = ""
    size: int | None = None
    fraction: float | None = None  # Fraction of total enrollment
    description: str = ""


@dataclass
class StudyDesign:
    arms: list[dict[str, Any]] = field(default_factory=list)
    phases: list[str] = field(default_factory=list)
    total_enrollment: int | None = None
    randomization_ratio: str = ""
    total_visits_described: int | None = None


@dataclass
class ProcedureContext:
    frequency_notes: dict[str, str] = field(default_factory=dict)  # proc_name → frequency text
    mentioned_procedures: set[str] = field(default_factory=set)
    ediary_span_days: tuple[int, int] | None = None  # (start_day, end_day)


@dataclass
class ProtocolContext:
    """Structured context extracted from the full protocol text."""
    therapeutic_area: str = "general"
    study_design: StudyDesign = field(default_factory=StudyDesign)
    treatment_regimen: TreatmentRegimen = field(default_factory=TreatmentRegimen)
    population_subsets: list[PopulationSubset] = field(default_factory=list)
    procedure_context: ProcedureContext = field(default_factory=ProcedureContext)
    screen_failure_rate: float | None = None
    early_discontinuation_rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage/API."""
        return {
            "therapeutic_area": self.therapeutic_area,
            "study_design": {
                "arms": self.study_design.arms,
                "phases": self.study_design.phases,
                "total_enrollment": self.study_design.total_enrollment,
                "randomization_ratio": self.study_design.randomization_ratio,
            },
            "treatment_regimen": {
                "cycle_length_days": self.treatment_regimen.cycle_length_days,
                "expected_duration_months": self.treatment_regimen.expected_duration_months,
                "expected_cycles": self.treatment_regimen.expected_cycles,
                "total_doses": self.treatment_regimen.total_doses,
                "treat_to_progression": self.treatment_regimen.treat_to_progression,
            },
            "population_subsets": [
                {"name": s.name, "size": s.size, "fraction": s.fraction}
                for s in self.population_subsets
            ],
            "procedure_context": {
                "ediary_span_days": self.procedure_context.ediary_span_days,
                "frequency_notes": self.procedure_context.frequency_notes,
            },
        }


# ── TA Detection ────────────────────────────────────────────────────────

_TA_KEYWORDS: dict[str, list[str]] = {
    "oncology": ["cancer", "tumor", "carcinoma", "lymphoma", "leukemia",
                 "melanoma", "sarcoma", "nsclc", "recist", "durvalumab",
                 "pembrolizumab", "nivolumab", "atezolizumab"],
    "vaccines": ["vaccine", "immunization", "vaccination", "mrna",
                 "bnt162", "mrna-1273", "reactogenicity", "immunogenicity"],
    "cns_neurology": ["epilepsy", "seizure", "alzheimer", "parkinson",
                      "multiple sclerosis", "stroke", "brivaracetam",
                      "c-ssrs", "neurological"],
    "autoimmune": ["rheumatoid", "lupus", "psoriasis", "crohn",
                   "colitis", "arthritis", "ulcerative"],
    "endocrine": ["diabetes", "thyroid", "insulin", "glucose",
                  "hba1c", "tirzepatide", "dulaglutide", "semaglutide"],
}


def detect_therapeutic_area(protocol_data: dict[str, Any]) -> str:
    """Detect TA from protocol metadata or content."""
    meta = protocol_data.get("metadata", {})
    if isinstance(meta, dict):
        ta = meta.get("therapeutic_area", "").lower()
        if ta:
            return ta

    indication = str(meta.get("indication", "")).lower() if isinstance(meta, dict) else ""
    title = str(meta.get("title", "")).lower() if isinstance(meta, dict) else ""
    doc_name = protocol_data.get("document_name", "").lower()
    text = f"{indication} {title} {doc_name}"

    for ta_name, keywords in _TA_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return ta_name
    return "general"


def load_ta_profile(ta: str) -> dict[str, Any]:
    """Load a TA YAML profile."""
    path = _TA_PROFILES_DIR / f"{ta}.yaml"
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load TA profile {ta}: {e}")

    # Try general fallback
    general = _TA_PROFILES_DIR / "general.yaml"
    if general.exists():
        try:
            with open(general, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


# ── Context Extractor ───────────────────────────────────────────────────

class ProtocolContextExtractor:
    """Reads protocol sections and extracts structured context for the SMB.

    Uses TA-specific YAML profiles to determine what to look for
    in each section. The extractor doesn't know about specific TAs —
    it follows the YAML patterns.
    """

    def extract(
        self,
        protocol_data: dict[str, Any],
        ta_profile: dict[str, Any] | None = None,
    ) -> ProtocolContext:
        """Extract structured context from protocol sections.

        Args:
            protocol_data: Full stored protocol JSON.
            ta_profile: TA-specific YAML profile. Auto-loaded if None.
        """
        ta = detect_therapeutic_area(protocol_data)
        if ta_profile is None:
            ta_profile = load_ta_profile(ta)

        context = ProtocolContext(therapeutic_area=ta)

        sections = protocol_data.get("sections", [])
        section_texts = self._build_section_text_map(sections)

        # Extract based on TA profile patterns
        extraction_config = ta_profile.get("section_extraction", {})

        # Treatment regimen
        if "treatment_regimen" in extraction_config:
            context.treatment_regimen = self._extract_treatment_regimen(
                section_texts, extraction_config["treatment_regimen"]
            )

        # Population subsets
        if "population_subsets" in extraction_config:
            context.population_subsets = self._extract_subsets(
                section_texts, extraction_config["population_subsets"]
            )

        # Procedure frequency context
        if "procedure_frequency" in extraction_config:
            context.procedure_context = self._extract_procedure_context(
                section_texts, extraction_config["procedure_frequency"]
            )

        # Study design from synopsis
        if "study_design" in extraction_config:
            context.study_design = self._extract_study_design(
                section_texts, extraction_config["study_design"]
            )

        # Apply inference defaults from profile
        defaults = ta_profile.get("inference_defaults", {})
        if defaults.get("screen_failure_rate"):
            context.screen_failure_rate = defaults["screen_failure_rate"]
        if defaults.get("early_discontinuation_rate"):
            context.early_discontinuation_rate = defaults["early_discontinuation_rate"]

        # If no profile patterns worked, try generic extraction
        if not context.treatment_regimen.cycle_length_days and not context.treatment_regimen.total_doses:
            context.treatment_regimen = self._generic_treatment_extraction(section_texts)

        if not context.study_design.total_enrollment:
            context.study_design = self._generic_design_extraction(section_texts)

        logger.info(f"Protocol context extracted: TA={ta}, "
                     f"enrollment={context.study_design.total_enrollment}, "
                     f"subsets={len(context.population_subsets)}, "
                     f"cycle_days={context.treatment_regimen.cycle_length_days}")

        return context

    def _build_section_text_map(self, sections: list[dict]) -> dict[str, str]:
        """Build a map of section_number → section text content."""
        result: dict[str, str] = {}
        for s in sections:
            num = s.get("number", "")
            content = s.get("content_html", "") or s.get("content", "") or ""
            # Strip HTML tags for pattern matching
            text = re.sub(r"<[^>]+>", " ", content)
            text = re.sub(r"\s+", " ", text).strip()
            if num:
                result[num] = text
            # Also add by title keyword for broader matching
            title = s.get("title", "").lower()
            result[f"_title_{title}"] = text
            # Recurse into children
            for child in s.get("children", []):
                child_texts = self._build_section_text_map([child])
                result.update(child_texts)
        return result

    def _find_text_for_sections(
        self, section_texts: dict[str, str], search_sections: list[str],
        search_keywords: list[str] | None = None,
    ) -> str:
        """Find and concatenate text from target sections."""
        texts = []
        for sec_num in search_sections:
            if sec_num in section_texts:
                texts.append(section_texts[sec_num])
            # Also search subsections (5 → 5.1, 5.2, etc.)
            for key, text in section_texts.items():
                if key.startswith(sec_num + "."):
                    texts.append(text)

        combined = " ".join(texts)

        # If keywords specified, also search by title
        if search_keywords and not combined.strip():
            for key, text in section_texts.items():
                if key.startswith("_title_"):
                    title = key.replace("_title_", "")
                    if any(kw in title for kw in search_keywords):
                        combined += " " + text

        return combined

    def _extract_field(self, text: str, patterns: list[str]) -> str | None:
        """Extract a field value using a list of regex patterns."""
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def _extract_treatment_regimen(
        self, section_texts: dict[str, str], config: dict
    ) -> TreatmentRegimen:
        """Extract treatment regimen from protocol sections."""
        text = self._find_text_for_sections(
            section_texts,
            config.get("search_sections", ["6"]),
            config.get("search_keywords"),
        )

        regimen = TreatmentRegimen(raw_text=text[:500])

        for field_def in config.get("extract", []):
            value = self._extract_field(text, field_def.get("patterns", []))
            if value is None:
                continue

            field_name = field_def["field"]
            if field_name == "cycle_length_days":
                transform = field_def.get("transform", "")
                if transform == "weeks_to_days" and value.isdigit():
                    regimen.cycle_length_days = int(value) * 7
                elif value.isdigit():
                    regimen.cycle_length_days = int(value)
            elif field_name == "expected_duration" and value.isdigit():
                regimen.expected_duration_months = int(value)
            elif field_name == "expected_cycles" and value.isdigit():
                regimen.expected_cycles = int(value)
            elif field_name == "total_doses" and value.isdigit():
                regimen.total_doses = int(value)
            elif field_name == "dose_interval_days" and value.isdigit():
                regimen.dose_interval_days = int(value)
            elif field_name == "treat_to_progression":
                regimen.treat_to_progression = True
            elif field_name == "treatment_cap":
                regimen.treatment_cap = value
            elif field_name == "follow_up_duration" and value.isdigit():
                regimen.follow_up_duration_months = int(value)

        return regimen

    def _extract_subsets(
        self, section_texts: dict[str, str], config: dict
    ) -> list[PopulationSubset]:
        """Extract population subsets."""
        text = self._find_text_for_sections(
            section_texts,
            config.get("search_sections", ["5", "8"]),
        )

        subsets = []
        for field_def in config.get("extract", []):
            value = self._extract_field(text, field_def.get("patterns", []))
            if value and value.replace(",", "").isdigit():
                size = int(value.replace(",", ""))
                subsets.append(PopulationSubset(
                    name=field_def["field"],
                    size=size,
                    description=field_def.get("description", ""),
                ))
        return subsets

    def _extract_procedure_context(
        self, section_texts: dict[str, str], config: dict
    ) -> ProcedureContext:
        """Extract procedure-specific frequency and context info."""
        text = self._find_text_for_sections(
            section_texts,
            config.get("search_sections", ["8"]),
        )

        ctx = ProcedureContext()

        for field_def in config.get("extract", []):
            value = self._extract_field(text, field_def.get("patterns", []))
            if value:
                field_name = field_def["field"]
                if field_name == "ediary_span":
                    # Extract start and end days
                    m = re.search(r"Day\s*(\d+).*Day\s*(\d+)", value + text[text.find(value):text.find(value)+100] if value in text else "", re.IGNORECASE)
                    if m:
                        ctx.ediary_span_days = (int(m.group(1)), int(m.group(2)))
                else:
                    ctx.frequency_notes[field_name] = value

        return ctx

    def _extract_study_design(
        self, section_texts: dict[str, str], config: dict
    ) -> StudyDesign:
        """Extract study design from synopsis."""
        text = self._find_text_for_sections(
            section_texts,
            config.get("search_sections", ["1", "4"]),
            config.get("search_keywords"),
        )
        return self._parse_study_design(text)

    def _generic_treatment_extraction(self, section_texts: dict[str, str]) -> TreatmentRegimen:
        """Generic treatment extraction when no TA profile matches."""
        # Search all sections for treatment patterns
        all_text = " ".join(section_texts.values())
        regimen = TreatmentRegimen()

        # Cycle length
        m = re.search(r"every\s+(\d+)\s+weeks", all_text, re.IGNORECASE)
        if m:
            regimen.cycle_length_days = int(m.group(1)) * 7
        m = re.search(r"Q(\d+)W", all_text)
        if m:
            regimen.cycle_length_days = int(m.group(1)) * 7

        # Total doses
        m = re.search(r"(\d+)\s+(?:doses?|injections?|vaccinations?)", all_text, re.IGNORECASE)
        if m:
            regimen.total_doses = int(m.group(1))

        # Treat to progression
        if re.search(r"until\s+(?:disease\s+)?progression", all_text, re.IGNORECASE):
            regimen.treat_to_progression = True

        return regimen

    def _generic_design_extraction(self, section_texts: dict[str, str]) -> StudyDesign:
        """Generic study design extraction."""
        all_text = " ".join(section_texts.values())
        return self._parse_study_design(all_text)

    def _parse_study_design(self, text: str) -> StudyDesign:
        """Parse study design from text."""
        design = StudyDesign()

        # Total enrollment
        m = re.search(r"(?:approximately|about|up to)\s+([\d,]+)\s+(?:participants?|subjects?|patients?)", text, re.IGNORECASE)
        if m:
            design.total_enrollment = int(m.group(1).replace(",", ""))

        # Randomization
        m = re.search(r"randomized?\s+(\d+:\d+(?::\d+)?)", text, re.IGNORECASE)
        if m:
            design.randomization_ratio = m.group(1)

        # Phases
        for phase_name in ["screening", "treatment", "follow-up", "extension", "maintenance"]:
            if phase_name in text.lower():
                design.phases.append(phase_name.title())

        return design
