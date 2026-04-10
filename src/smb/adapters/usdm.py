"""
USDM Adapter — converts CDISC Unified Study Definitions Model JSON to
Protocol (for persistence + KE graph) and ExtractionInput (for SMB engine).

This is the coupling point between USDM and ProtoExtract's knowledge layer.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any

from src.models.protocol import (
    KEType,
    KnowledgeElement,
    Protocol,
    ProtocolMetadata,
    SectionNode,
)
from src.smb.api.models import (
    ExtractionInput,
    ExtractedCellInput,
    FootnoteInput,
    ProcedureInput,
    TableInput,
    VisitInput,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode(obj: dict | str | None) -> str:
    """Extract human-readable text from a USDM coded value."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    return obj.get("decode", obj.get("code", ""))


def _usdm_id(filename: str) -> str:
    """Generate a stable protocol_id from a USDM filename."""
    slug = re.sub(r"\.[^.]+$", "", filename)
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", slug).strip("_").lower()
    digest = hashlib.sha256(filename.encode()).hexdigest()[:8]
    return f"usdm_{slug}_{digest}" if slug else f"usdm_{digest}"


def _classify_epoch_type(epoch_type_str: str) -> str:
    """Map USDM epoch type decode to SMB phase_type."""
    low = epoch_type_str.lower()
    if "screen" in low:
        return "screening"
    if "run" in low and "in" in low:
        return "run_in"
    if "treat" in low:
        return "treatment"
    if "follow" in low:
        return "follow_up"
    if "extension" in low:
        return "extension"
    return "treatment"


def _classify_arm_type(arm_type_str: str) -> str:
    """Map USDM arm type decode to SMB arm_type."""
    low = arm_type_str.lower()
    if "placebo" in low:
        return "placebo"
    if "control" in low:
        return "control"
    if "comparator" in low:
        return "comparator"
    return "experimental"


def _infer_cost_tier(proc_type: str) -> str:
    """Infer cost tier from USDM procedure type."""
    low = proc_type.lower()
    if "imaging" in low or "scan" in low or "mri" in low:
        return "HIGH"
    if "laboratory" in low or "lab" in low:
        return "MEDIUM"
    if "treatment" in low or "infusion" in low or "administration" in low:
        return "HIGH"
    return "LOW"


# ---------------------------------------------------------------------------
# Main adapter
# ---------------------------------------------------------------------------

class USDMAdapter:
    """Converts CDISC USDM JSON to Protocol and ExtractionInput."""

    def to_protocol(
        self, usdm_data: dict, filename: str = ""
    ) -> Protocol:
        """Convert USDM JSON to a Protocol for persistence + KE generation."""
        study = usdm_data.get("study", usdm_data)
        designs = study.get("studyDesigns", [])
        design = designs[0] if designs else {}

        protocol_id = self._extract_protocol_id(study, filename)
        metadata = self._extract_metadata(study, design)
        sections = self._build_sections(study, design)
        tables_raw = self._build_tables_raw(design)
        procedures_raw = self._extract_procedures_raw(design)
        kes = self.extract_knowledge_elements(usdm_data, protocol_id)

        return Protocol(
            protocol_id=protocol_id,
            document_name=filename or f"{study.get('studyTitle', 'USDM Study')}.json",
            document_hash=hashlib.sha256(
                str(usdm_data).encode()
            ).hexdigest()[:16],
            total_pages=0,
            metadata=metadata,
            sections=sections,
            tables=tables_raw,
            procedures=procedures_raw,
            knowledge_elements=kes,
            pipeline_version="usdm_import_1.0",
        )

    def to_extraction_input(
        self, usdm_data: dict, filename: str = ""
    ) -> ExtractionInput:
        """Convert USDM JSON to ExtractionInput for the SMB engine."""
        study = usdm_data.get("study", usdm_data)
        designs = study.get("studyDesigns", [])
        design = designs[0] if designs else {}

        protocol_id = self._extract_protocol_id(study, filename)
        metadata = self._extract_metadata(study, design)
        table_input = self._build_soa_table_input(design)
        domain_config = self._build_domain_config(metadata)

        return ExtractionInput(
            document_id=protocol_id,
            document_name=filename or study.get("studyTitle", ""),
            domain="protocol",
            tables=[table_input] if table_input else [],
            metadata=metadata.model_dump(),
            domain_config=domain_config,
        )

    def extract_knowledge_elements(
        self, usdm_data: dict, protocol_id: str
    ) -> list[KnowledgeElement]:
        """Extract USDM-specific Knowledge Elements (objectives, endpoints, criteria)."""
        study = usdm_data.get("study", usdm_data)
        kes: list[KnowledgeElement] = []

        # Objectives
        for obj in study.get("studyObjectives", []):
            level = _decode(obj.get("objectiveLevel"))
            desc = obj.get("objectiveDescription", "")
            kes.append(KnowledgeElement(
                ke_id=f"{protocol_id}:OBJECTIVE:{obj.get('id', '')}",
                ke_type=KEType.OBJECTIVE,
                title=f"{level} Objective",
                content=desc,
                metadata={
                    "level": level,
                    "endpoint_ids": obj.get("objectiveEndpoints", []),
                    "source": "usdm_import",
                },
            ))

        # Endpoints
        for ep in study.get("studyEndpoints", []):
            level = _decode(ep.get("endpointLevel"))
            desc = ep.get("endpointDescription", "")
            purpose = ep.get("endpointPurposeDescription", "")
            kes.append(KnowledgeElement(
                ke_id=f"{protocol_id}:ENDPOINT:{ep.get('id', '')}",
                ke_type=KEType.ENDPOINT,
                title=f"{level} Endpoint",
                content=desc,
                metadata={
                    "level": level,
                    "purpose": purpose,
                    "source": "usdm_import",
                },
            ))

        # Eligibility criteria
        for crit in study.get("studyEligibilityCriteria", []):
            crit_type = crit.get("criteriaType", "Inclusion")
            ke_type = (
                KEType.INCLUSION_CRITERIA if crit_type == "Inclusion"
                else KEType.EXCLUSION_CRITERIA
            )
            kes.append(KnowledgeElement(
                ke_id=f"{protocol_id}:{ke_type.value}:{crit.get('id', '')}",
                ke_type=ke_type,
                title=f"{crit_type} Criterion",
                content=crit.get("criteriaText", ""),
                metadata={"source": "usdm_import"},
            ))

        return kes

    # -- Internal helpers --

    def _extract_protocol_id(self, study: dict, filename: str) -> str:
        """Generate protocol_id from USDM study identifiers or filename."""
        for ident in study.get("studyIdentifiers", []):
            scope = ident.get("studyIdentifierScope", {})
            org_type = _decode(scope.get("organizationType")).lower()
            if "sponsor" in org_type:
                slug = re.sub(r"[^a-zA-Z0-9]+", "_", ident["studyIdentifier"]).lower()
                return f"usdm_{slug}"
        return _usdm_id(filename or study.get("studyTitle", "unknown"))

    def _extract_metadata(self, study: dict, design: dict) -> ProtocolMetadata:
        """Extract ProtocolMetadata from USDM study structure."""
        # Find sponsor identifier and NCT number
        sponsor = ""
        protocol_number = ""
        nct_number = ""
        for ident in study.get("studyIdentifiers", []):
            scope = ident.get("studyIdentifierScope", {})
            org_type = _decode(scope.get("organizationType")).lower()
            if "sponsor" in org_type:
                sponsor = scope.get("organizationName", "")
                protocol_number = ident.get("studyIdentifier", "")
            elif "registry" in org_type:
                nct_number = ident.get("studyIdentifier", "")

        # Phase
        phase = _decode(study.get("studyPhase", {}).get("standardCode"))

        # Therapeutic area
        ta_list = design.get("therapeuticAreas", [])
        therapeutic_area = _decode(ta_list[0]) if ta_list else ""

        # Indication
        ind_list = design.get("studyIndications", [])
        indication = ind_list[0].get("indicationDescription", "") if ind_list else ""

        # Study type
        study_type = _decode(study.get("studyType"))

        # Arms
        arms = [a.get("studyArmName", "") for a in design.get("studyArms", [])]

        return ProtocolMetadata(
            title=study.get("studyTitle", ""),
            protocol_number=protocol_number,
            nct_number=nct_number,
            sponsor=sponsor,
            phase=phase,
            therapeutic_area=therapeutic_area,
            indication=indication,
            study_type=study_type.lower() if study_type else "",
            arms=arms,
            version=study.get("studyVersion", ""),
        )

    def _build_sections(self, study: dict, design: dict) -> list[SectionNode]:
        """Build a section tree from USDM study structure."""
        sections: list[SectionNode] = []
        page = 1

        # Synopsis section
        rationale = study.get("studyRationale", "")
        if rationale:
            sections.append(SectionNode(
                number="1", title="Study Rationale", page=page, level=1,
                content_html=f"<p>{rationale}</p>",
            ))
            page += 1

        # Study Design section
        arms = design.get("studyArms", [])
        epochs = design.get("studyEpochs", [])
        if arms or epochs:
            children = []
            if arms:
                arms_html = "<ul>" + "".join(
                    f"<li><b>{a.get('studyArmName', '')}</b> "
                    f"({_decode(a.get('studyArmType'))}): "
                    f"{a.get('studyArmDescription', '')}</li>"
                    for a in arms
                ) + "</ul>"
                children.append(SectionNode(
                    number="2.1", title="Study Arms", page=page, level=2,
                    content_html=arms_html,
                ))
            if epochs:
                epochs_html = "<ul>" + "".join(
                    f"<li><b>{e.get('studyEpochName', '')}</b>: "
                    f"{e.get('studyEpochDescription', '')}</li>"
                    for e in sorted(epochs, key=lambda x: x.get("sequenceNumber", 0))
                ) + "</ul>"
                children.append(SectionNode(
                    number="2.2", title="Study Epochs", page=page, level=2,
                    content_html=epochs_html,
                ))
            sections.append(SectionNode(
                number="2", title="Study Design", page=page, level=1,
                children=children,
            ))
            page += 1

        # Objectives section
        objectives = study.get("studyObjectives", [])
        if objectives:
            obj_html = "<ol>" + "".join(
                f"<li><b>{_decode(o.get('objectiveLevel'))}</b>: "
                f"{o.get('objectiveDescription', '')}</li>"
                for o in objectives
            ) + "</ol>"
            sections.append(SectionNode(
                number="3", title="Study Objectives", page=page, level=1,
                ke_type=KEType.OBJECTIVE,
                content_html=obj_html,
            ))
            page += 1

        # Eligibility section
        criteria = study.get("studyEligibilityCriteria", [])
        if criteria:
            inc = [c for c in criteria if c.get("criteriaType") == "Inclusion"]
            exc = [c for c in criteria if c.get("criteriaType") == "Exclusion"]
            html_parts = []
            if inc:
                html_parts.append("<h4>Inclusion Criteria</h4><ol>" + "".join(
                    f"<li>{c.get('criteriaText', '')}</li>" for c in inc
                ) + "</ol>")
            if exc:
                html_parts.append("<h4>Exclusion Criteria</h4><ol>" + "".join(
                    f"<li>{c.get('criteriaText', '')}</li>" for c in exc
                ) + "</ol>")
            sections.append(SectionNode(
                number="4", title="Eligibility Criteria", page=page, level=1,
                ke_type=KEType.INCLUSION_CRITERIA,
                content_html="".join(html_parts),
            ))

        return sections

    def _build_tables_raw(self, design: dict) -> list[dict]:
        """Build raw table dicts (Protocol schema) from USDM schedule data."""
        table_input = self._build_soa_table_input(design)
        if not table_input:
            return []
        # Convert to raw dict format expected by Protocol.tables
        return [table_input.model_dump()]

    def _extract_procedures_raw(self, design: dict) -> list[dict]:
        """Extract procedure dicts for Protocol.procedures."""
        procedures = []
        for act in design.get("activities", []):
            for proc in act.get("definedProcedures", []):
                codes = proc.get("codes", [])
                code = codes[0].get("code", "") if codes else None
                code_system = codes[0].get("codeSystem", "") if codes else None
                proc_type = proc.get("procedureType", "Unknown")
                procedures.append({
                    "raw_name": proc.get("procedureName", act.get("activityName", "")),
                    "canonical_name": proc.get("procedureName", act.get("activityName", "")),
                    "code": code,
                    "code_system": code_system,
                    "category": proc_type,
                    "estimated_cost_tier": _infer_cost_tier(proc_type),
                })
        return procedures

    def _build_soa_table_input(self, design: dict) -> TableInput | None:
        """Reconstruct Schedule of Activities as a TableInput for SMB."""
        encounters = design.get("encounters", [])
        activities = design.get("activities", [])
        timelines = design.get("scheduleTimelines", [])
        if not encounters or not activities or not timelines:
            return None

        # Build timing lookup
        timings = {t["id"]: t for t in design.get("timings", [])}

        # Sort encounters by timing
        enc_order = sorted(encounters, key=lambda e: timings.get(
            e.get("encounterScheduledAtTimingId", ""), {}
        ).get("timingValue", 0))

        # Build activity → encounter set from schedule instances
        act_enc_map: dict[str, set[str]] = {a["id"]: set() for a in activities}
        for timeline in timelines:
            for instance in timeline.get("scheduledInstances", []):
                enc_id = instance.get("encounterId", "")
                for act_id in instance.get("activityIds", []):
                    if act_id in act_enc_map:
                        act_enc_map[act_id].add(enc_id)

        # Only include activities with defined procedures and schedule instances
        scheduled = [a for a in activities if act_enc_map.get(a["id"])]

        # Build visits
        visits: list[VisitInput] = []
        for ci, enc in enumerate(enc_order):
            timing = timings.get(enc.get("encounterScheduledAtTimingId", ""), {})
            window = timing.get("timingWindow", {})
            visits.append(VisitInput(
                visit_name=enc.get("encounterName", ""),
                col_index=ci + 1,  # col 0 is procedure name
                target_day=timing.get("timingValue"),
                window_minus=window.get("windowLower", 0),
                window_plus=window.get("windowUpper", 0),
                window_unit="DAYS",
                relative_to=timing.get("timingRelativeToFrom", "randomization").lower(),
            ))

        # Build procedures
        procedures: list[ProcedureInput] = []
        act_to_proc_name: dict[str, str] = {}
        for act in scheduled:
            defined_procs = act.get("definedProcedures", [])
            if defined_procs:
                proc = defined_procs[0]
                name = proc.get("procedureName", act.get("activityName", ""))
                codes = proc.get("codes", [])
                code = codes[0].get("code", "") if codes else None
                code_system = codes[0].get("codeSystem", "") if codes else None
                proc_type = proc.get("procedureType", "Unknown")
            else:
                name = act.get("activityName", "")
                code, code_system, proc_type = None, None, "Unknown"

            act_to_proc_name[act["id"]] = name
            procedures.append(ProcedureInput(
                raw_name=name,
                canonical_name=name,
                code=code,
                code_system=code_system,
                category=proc_type,
                cost_tier=_infer_cost_tier(proc_type),
            ))

        # Build cells (SoA matrix)
        cells: list[ExtractedCellInput] = []
        for ri, act in enumerate(scheduled):
            proc_name = act_to_proc_name.get(act["id"], "")
            for ci, enc in enumerate(enc_order):
                has_activity = enc["id"] in act_enc_map.get(act["id"], set())
                cells.append(ExtractedCellInput(
                    row=ri + 1,  # row 0 is header (implicit)
                    col=ci + 1,
                    raw_value="X" if has_activity else "",
                    data_type="MARKER" if has_activity else "EMPTY",
                    confidence=0.95,
                    row_header=proc_name,
                    col_header=enc.get("encounterName", ""),
                ))

        return TableInput(
            table_id="usdm_soa_001",
            table_type="SOA",
            title="Schedule of Activities (from USDM)",
            source_pages=[],
            cells=cells,
            procedures=procedures,
            visits=visits,
            overall_confidence=0.95,
        )

    def _build_domain_config(self, metadata: ProtocolMetadata) -> dict[str, Any]:
        """Build domain config from USDM metadata."""
        try:
            from src.domain.config import load_domain_config
            config = load_domain_config(
                therapeutic_area=metadata.therapeutic_area,
                sponsor=metadata.sponsor,
            )
            if config:
                return config
        except Exception:
            pass

        return {
            "domain": {"name": "General", "visit_structure": "fixed_duration"},
            "visit_counting": {"marker_patterns": ["X", "x", "Y", "YES", "\u2713", "\u2714"]},
            "cost_tiers": {"LOW": 75, "MEDIUM": 350, "HIGH": 1200, "VERY_HIGH": 3500},
            "footnote_rules": {
                "conditional_handling": "include",
                "conditional_probability": 0.6,
            },
        }
