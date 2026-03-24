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
from src.smb.core.model import StructuredModel

logger = logging.getLogger(__name__)


class SMBEngine:
    """Main entry point for building structured models."""

    def __init__(self, domain: str = "protocol"):
        self.domain = domain
        self._builder = self._load_builder(domain)

    def build(self, extraction_input: ExtractionInput) -> BuildResult:
        """Build a structured model from extraction input.

        Pipeline: adapter output → entity creation → relationship building
                  → inference → validation → result
        """
        start = time.time()

        # Step 1: Build the base model (entities + relationships)
        model = self._builder.build(extraction_input)

        # Step 2: Run inference rules (Week 2 — placeholder)
        rules_fired = self._run_inference(model, extraction_input)

        # Step 3: Validate the model (Week 2 — placeholder)
        errors, warnings = self._validate(model)

        elapsed = time.time() - start

        logger.info(
            f"SMB build complete: {model.summary()} "
            f"in {elapsed:.2f}s, {len(rules_fired)} rules fired"
        )

        return BuildResult(
            model=model,
            build_time_seconds=round(elapsed, 3),
            inference_rules_fired=rules_fired,
            validation_passed=len(errors) == 0,
            validation_errors=errors,
            validation_warnings=warnings,
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

    def _run_inference(
        self, model: StructuredModel, extraction_input: ExtractionInput
    ) -> list[str]:
        """Run inference rules on the model. Returns list of rule names fired."""
        rules_fired = []

        # Cycle inference — detect representative cycles and multiply
        cycle_rule = self._infer_cycles(model, extraction_input)
        if cycle_rule:
            rules_fired.append(cycle_rule)

        # Conditional probability inference
        cond_rule = self._infer_conditionals(model)
        if cond_rule:
            rules_fired.append(cond_rule)

        return rules_fired

    def _infer_cycles(
        self, model: StructuredModel, extraction_input: ExtractionInput
    ) -> str | None:
        """Detect cycle-based protocols and apply cycle multiplication."""
        domain_config = extraction_input.domain_config
        visit_structure = domain_config.get("domain", {}).get("visit_structure", "fixed_duration")

        if visit_structure != "cycle_based":
            return None

        # Count unique cycles from Visit entities
        visits = model.get_entities("Visit")
        cycles_seen = set()
        for v in visits:
            cycle = v.get_property("cycle")
            if cycle is not None:
                cycles_seen.add(cycle)

        if len(cycles_seen) <= 1:
            return None

        # Get expected total from domain config
        ta = domain_config.get("ta_specific", {})
        ttp = ta.get("treat_to_progression", {})
        if ttp.get("enabled"):
            median_months = ttp.get("default_median_months", 9)
            cycle_days = ta.get("cycle_length_days", 21)
            total_cycles = int(median_months * 30 / max(cycle_days, 1))
        else:
            total_cycles = domain_config.get("visit_counting", {}).get("default_cycles", 6)

        represented = len(cycles_seen)
        if represented >= total_cycles:
            return None

        multiplier = total_cycles / represented

        # Apply to all ScheduleEntries
        for entry in model.get_schedule_entries():
            if entry.get_property("mark_type") != "excluded":
                base = entry.get_property("occurrence_count", 1)
                entry.properties["applied_cycle_count"] = total_cycles
                entry.properties["cycle_multiplier"] = multiplier
                entry.properties["total_occurrences"] = int(base * multiplier)
                entry.properties["inference_trail"].append("CycleInference")

        model.inference_log.append({
            "rule": "CycleInference",
            "represented_cycles": represented,
            "total_cycles": total_cycles,
            "multiplier": round(multiplier, 2),
            "entries_modified": len(model.get_schedule_entries()),
        })

        return "CycleInference"

    def _infer_conditionals(self, model: StructuredModel) -> str | None:
        """Apply conditional probability to conditional entries."""
        conditional_entries = model.get_conditional_entries()
        if not conditional_entries:
            return None

        probability = 0.6  # Default conditional probability
        for entry in conditional_entries:
            entry.properties["probability"] = probability
            entry.properties["inference_trail"].append("ConditionalInference")

        model.inference_log.append({
            "rule": "ConditionalInference",
            "entries_modified": len(conditional_entries),
            "probability": probability,
        })

        return "ConditionalInference"

    def _validate(self, model: StructuredModel) -> tuple[list[str], list[str]]:
        """Validate the model. Returns (errors, warnings)."""
        errors = []
        warnings = []

        visits = model.get_entities("Visit")
        procedures = model.get_entities("Procedure")
        entries = model.get_schedule_entries()

        if not visits:
            errors.append("No Visit entities found")
        if not procedures:
            errors.append("No Procedure entities found")
        if not entries:
            warnings.append("No ScheduleEntry entities found — empty SoA?")

        # Check every procedure has at least one schedule entry
        proc_ids_with_entries = {
            e.get_property("procedure_entity_id") for e in entries
        }
        for proc in procedures:
            if proc.id not in proc_ids_with_entries:
                warnings.append(f"Procedure '{proc.name}' has no schedule entries")

        model.validation_report = {
            "errors": errors,
            "warnings": warnings,
            "visits": len(visits),
            "procedures": len(procedures),
            "schedule_entries": len(entries),
            "firm_entries": len(model.get_firm_entries()),
            "conditional_entries": len(model.get_conditional_entries()),
        }

        return errors, warnings
