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

        Uses the ProtoExtract adapter to convert protocol data to ExtractionInput.
        """
        from src.smb.adapters.protoextract import ProtoExtractAdapter
        adapter = ProtoExtractAdapter()
        extraction_input = adapter.convert(protocol_data)
        return self.build(extraction_input)

    def _load_builder(self, domain: str):
        """Load the domain-specific builder."""
        if domain == "protocol":
            from src.smb.domains.protocol.builder import ProtocolBuilder
            return ProtocolBuilder()
        raise ValueError(f"Unknown domain: {domain}")
