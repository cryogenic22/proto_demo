"""
SMBEngine — orchestrates the structured model build pipeline.

    engine = SMBEngine(domain="protocol")
    result = engine.build(extraction_input)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.smb.api.models import BuildResult, ExtractionInput
from src.smb.core.inference import InferenceEngine
from src.smb.core.model import StructuredModel
from src.smb.core.validator import ValidationEngine

logger = logging.getLogger(__name__)


class SMBEngine:
    """Main entry point for building structured models."""

    def __init__(self, domain: str = "protocol"):
        self.domain = domain
        self._builder = self._load_builder(domain)
        self._inference_engine = InferenceEngine()
        self._validation_engine = ValidationEngine()

    def build(self, extraction_input: ExtractionInput) -> BuildResult:
        """Build a structured model from extraction input.

        Pipeline: adapter output → entity creation → relationship building
                  → inference → validation → result
        """
        start = time.time()

        # Step 1: Build the base model (entities + relationships)
        model = self._builder.build(extraction_input)

        # Step 2: Run inference rules
        rules_fired = self._inference_engine.run(
            model, extraction_input.domain_config
        )

        # Step 3: Validate the model
        report = self._validation_engine.validate(model)

        elapsed = time.time() - start

        logger.info(
            f"SMB build complete: {model.summary()} "
            f"in {elapsed:.2f}s, {len(rules_fired)} rules fired"
        )

        return BuildResult(
            model=model,
            build_time_seconds=round(elapsed, 3),
            inference_rules_fired=rules_fired,
            validation_passed=report.passed,
            validation_errors=report.errors,
            validation_warnings=report.warnings,
        )

    def build_from_protocol_json(self, protocol_data: dict[str, Any]) -> BuildResult:
        """Build from stored protocol JSON (convenience method).

        Uses the ProtoExtract adapter to convert protocol data to ExtractionInput,
        then enriches with whole-protocol context from sections.
        """
        from src.smb.adapters.protoextract import ProtoExtractAdapter
        from src.smb.core.context import ProtocolContextExtractor, detect_therapeutic_area

        adapter = ProtoExtractAdapter()
        extraction_input = adapter.convert(protocol_data)

        # Enrich with whole-protocol context (sections, study design, subsets)
        # If sections have no content, try to extract from PDF
        try:
            ta = detect_therapeutic_area(protocol_data)
            enriched_data = self._enrich_sections_from_pdf(protocol_data)
            extractor = ProtocolContextExtractor()
            context = extractor.extract(enriched_data)
            # Merge context into domain_config so inference rules can use it
            extraction_input.domain_config["protocol_context"] = context.to_dict()
            extraction_input.domain_config["therapeutic_area_detected"] = ta
            extraction_input.metadata["therapeutic_area"] = ta
            if context.study_design.total_enrollment:
                extraction_input.metadata["total_enrollment"] = context.study_design.total_enrollment
            if context.treatment_regimen.cycle_length_days:
                extraction_input.domain_config.setdefault("ta_specific", {})["cycle_length_days"] = context.treatment_regimen.cycle_length_days
            if context.treatment_regimen.treat_to_progression:
                extraction_input.domain_config.setdefault("ta_specific", {}).setdefault("treat_to_progression", {})["enabled"] = True
            logger.info(f"Protocol context enriched: TA={ta}, enrollment={context.study_design.total_enrollment}")
        except Exception as e:
            logger.warning(f"Protocol context extraction failed: {e}")

        return self.build(extraction_input)

    @staticmethod
    def _enrich_sections_from_pdf(protocol_data: dict[str, Any]) -> dict[str, Any]:
        """If sections lack content, try to extract text from the PDF."""
        sections = protocol_data.get("sections", [])
        has_content = any(
            (s.get("content_html") or s.get("content", "")).strip()
            for s in sections[:5]
        )
        if has_content or not sections:
            return protocol_data

        # Try to find and read the PDF
        try:
            from pathlib import Path
            import re as _re

            pid = protocol_data.get("protocol_id", "")
            num_match = _re.match(r"^[pP][-_]?(\d+)", pid)
            pid_dash = f"P-{num_match.group(1).zfill(2)}" if num_match else pid

            pdf_path = None
            for d in [Path("data/pdfs"), Path("golden_set/cached_pdfs")]:
                if not d.exists():
                    continue
                for pattern in [f"{pid}.pdf", f"{pid_dash}.pdf"]:
                    candidate = d / pattern
                    if candidate.exists():
                        pdf_path = candidate
                        break
                if not pdf_path:
                    for p in d.glob("*.pdf"):
                        stem_clean = _re.sub(r"[^a-zA-Z0-9]", "", p.stem).lower()
                        pid_clean = _re.sub(r"[^a-zA-Z0-9]", "", pid).lower()
                        if stem_clean == pid_clean or stem_clean.startswith(pid_clean):
                            pdf_path = p
                            break
                if pdf_path:
                    break

            if not pdf_path:
                return protocol_data

            from src.pipeline.section_parser import SectionParser
            parser = SectionParser()
            pdf_bytes = pdf_path.read_bytes()

            # Extract text for key sections only (synopsis, design, dosing, population, assessments)
            key_prefixes = ("1", "2", "4", "5", "6", "8", "9")
            enriched_sections = []
            for s in sections:
                num = s.get("number", "")
                if any(num.startswith(p) for p in key_prefixes) and not s.get("content_html"):
                    section_obj = parser.find(parser.parse(pdf_bytes), num)
                    if section_obj:
                        text = parser.get_section_text(pdf_bytes, section_obj)
                        s = dict(s)
                        s["content"] = text[:3000]  # Cap at 3K chars per section
                enriched_sections.append(s)

            enriched = dict(protocol_data)
            enriched["sections"] = enriched_sections
            return enriched
        except Exception as e:
            logger.debug(f"PDF enrichment skipped: {e}")
            return protocol_data

    def _load_builder(self, domain: str):
        """Load the domain-specific builder."""
        if domain == "protocol":
            from src.smb.domains.protocol.builder import ProtocolBuilder
            return ProtocolBuilder()
        raise ValueError(f"Unknown domain: {domain}")
