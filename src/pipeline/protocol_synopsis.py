"""
Protocol Synopsis Extractor — extracts study design context before SoA processing.

Reads the first 10-15 pages of the protocol (title page, synopsis, study design)
to extract key context that informs SoA table interpretation:
- Phase (I, II, III, IV)
- Number of arms and arm descriptions
- Treatment periods (screening, treatment, follow-up, extension)
- Dosing regimen (cycle length, frequency)
- Primary endpoint
- Population (adult, pediatric, age range)
- Therapeutic area / indication

This context is injected into SoA extraction prompts as grounding.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.llm.client import LLMClient
from src.models.schema import PageImage, PipelineConfig

logger = logging.getLogger(__name__)

SYNOPSIS_PROMPT = """Read these pages from a clinical trial protocol. They contain the
title page, synopsis, and/or study design sections.

Extract the following study design information as a JSON object:

{
  "protocol_title": "full protocol title",
  "protocol_number": "e.g., C4591001",
  "sponsor": "sponsor name",
  "phase": "I", "II", "III", "IV", or "I/II", "II/III", etc.,
  "indication": "disease/condition being studied",
  "therapeutic_area": "e.g., Oncology, Cardiology, Vaccines",
  "study_design": "e.g., randomized, double-blind, placebo-controlled",
  "number_of_arms": 2,
  "arm_descriptions": ["Arm 1: Drug X 100mg", "Arm 2: Placebo"],
  "treatment_periods": [
    {"name": "Screening", "duration": "28 days"},
    {"name": "Treatment", "duration": "52 weeks"},
    {"name": "Follow-up", "duration": "30 days"}
  ],
  "dosing_regimen": "e.g., 100mg IV every 3 weeks, or 10mg oral daily",
  "cycle_length_days": null or 21,
  "population": {
    "age_range": "18-75 years",
    "pediatric": false,
    "estimated_enrollment": 500
  },
  "primary_endpoint": "e.g., Overall Survival, ORR, HbA1c change",
  "key_secondary_endpoints": ["PFS", "Safety"],
  "soa_hints": [
    "Cycle-based visits (C1D1 format)",
    "Separate screening and treatment SoA",
    "PK sampling on Day 1 and Day 15 of Cycle 1"
  ]
}

Extract as much as you can find. For fields not found, use null.
The "soa_hints" field should contain YOUR observations about what the SoA
table structure is likely to look like based on the study design.

Return ONLY valid JSON."""


@dataclass
class ProtocolSynopsis:
    """Extracted study design context."""
    protocol_title: str = ""
    protocol_number: str = ""
    sponsor: str = ""
    phase: str = ""
    indication: str = ""
    therapeutic_area: str = ""
    study_design: str = ""
    number_of_arms: int = 0
    arm_descriptions: list[str] = field(default_factory=list)
    treatment_periods: list[dict[str, str]] = field(default_factory=list)
    dosing_regimen: str = ""
    cycle_length_days: int | None = None
    population: dict[str, Any] = field(default_factory=dict)
    primary_endpoint: str = ""
    key_secondary_endpoints: list[str] = field(default_factory=list)
    soa_hints: list[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Generate context string for SoA extraction prompts."""
        parts = []
        if self.protocol_title:
            parts.append(f"Protocol: {self.protocol_title}")
        if self.phase:
            parts.append(f"Phase: {self.phase}")
        if self.indication:
            parts.append(f"Indication: {self.indication}")
        if self.therapeutic_area:
            parts.append(f"Therapeutic Area: {self.therapeutic_area}")
        if self.study_design:
            parts.append(f"Design: {self.study_design}")
        if self.number_of_arms > 0:
            parts.append(f"Arms: {self.number_of_arms}")
            if self.arm_descriptions:
                for arm in self.arm_descriptions:
                    parts.append(f"  - {arm}")
        if self.dosing_regimen:
            parts.append(f"Dosing: {self.dosing_regimen}")
        if self.cycle_length_days:
            parts.append(f"Cycle Length: {self.cycle_length_days} days")
        if self.treatment_periods:
            parts.append("Periods:")
            for p in self.treatment_periods:
                parts.append(f"  - {p.get('name', '?')}: {p.get('duration', '?')}")
        if self.soa_hints:
            parts.append("Expected SoA patterns:")
            for h in self.soa_hints:
                parts.append(f"  - {h}")

        return "\n".join(parts)


class ProtocolSynopsisExtractor:
    """Extracts study design from the first pages of a protocol."""

    def __init__(self, config: PipelineConfig, llm_client: LLMClient | None = None):
        self.config = config
        self.llm = llm_client or LLMClient(config)

    async def extract(self, pages: list[PageImage], max_pages: int = 12) -> ProtocolSynopsis:
        """Extract protocol synopsis from the first N pages."""
        # Take only first max_pages pages (title, TOC, synopsis, design)
        synopsis_pages = pages[:min(max_pages, len(pages))]

        if not synopsis_pages:
            return ProtocolSynopsis()

        logger.info(f"Extracting protocol synopsis from first {len(synopsis_pages)} pages")

        try:
            images = [p.image_bytes for p in synopsis_pages]
            raw = await self.llm.vision_json_query_multi(
                images,
                SYNOPSIS_PROMPT,
                system="You are a clinical trial protocol analyst. Extract study design details. Return valid JSON only.",
                max_tokens=2048,
            )

            if not isinstance(raw, dict):
                logger.warning("Synopsis extraction did not return a dict")
                return ProtocolSynopsis()

            return self._parse(raw)

        except Exception as e:
            logger.error(f"Synopsis extraction failed: {e}")
            return ProtocolSynopsis()

    def _parse(self, raw: dict[str, Any]) -> ProtocolSynopsis:
        """Parse raw LLM response into ProtocolSynopsis."""
        pop = raw.get("population") or {}
        return ProtocolSynopsis(
            protocol_title=str(raw.get("protocol_title") or ""),
            protocol_number=str(raw.get("protocol_number") or ""),
            sponsor=str(raw.get("sponsor") or ""),
            phase=str(raw.get("phase") or ""),
            indication=str(raw.get("indication") or ""),
            therapeutic_area=str(raw.get("therapeutic_area") or ""),
            study_design=str(raw.get("study_design") or ""),
            number_of_arms=int(raw.get("number_of_arms") or 0),
            arm_descriptions=raw.get("arm_descriptions") or [],
            treatment_periods=raw.get("treatment_periods") or [],
            dosing_regimen=str(raw.get("dosing_regimen") or ""),
            cycle_length_days=raw.get("cycle_length_days"),
            population=pop if isinstance(pop, dict) else {},
            primary_endpoint=str(raw.get("primary_endpoint") or ""),
            key_secondary_endpoints=raw.get("key_secondary_endpoints") or [],
            soa_hints=raw.get("soa_hints") or [],
        )
