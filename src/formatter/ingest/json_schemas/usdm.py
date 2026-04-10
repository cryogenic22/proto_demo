"""
USDM Schema — detector + parser for CDISC Unified Study Definitions Model JSON.

Detects USDM v3+ JSON by checking for study.studyDesigns or usdmVersion key.
Converts the study structure to a FormattedDocument representing the protocol
as a readable document (synopsis, design, SoA table, objectives, eligibility).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.formatter.extractor import (
    FormattedDocument,
    FormattedLine,
    FormattedPage,
    FormattedParagraph,
    FormattedSpan,
    FormattedTable,
    FormattedTableCell,
)
from src.formatter.ingest.json_ingestor import JsonSchemaDetector, JsonSchemaParser

logger = logging.getLogger(__name__)

_SCHEMA_ID = "usdm"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode(obj: dict | str | None) -> str:
    """Extract human-readable text from a USDM coded value or plain string."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    return obj.get("decode", obj.get("code", str(obj)))


def _make_para(
    text: str, style: str = "body", bold: bool = False, size: float = 11.0,
    alignment: str = "left",
) -> FormattedParagraph:
    span = FormattedSpan(
        text=text, x0=0, y0=0, x1=0, y1=0,
        font="Arial", size=size, color=0, bold=bold,
    )
    line = FormattedLine(spans=[span], y_center=0.0, indent=0.0)
    return FormattedParagraph(lines=[line], style=style, alignment=alignment)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class USDMDetector(JsonSchemaDetector):
    """Detects USDM JSON by checking for study + studyDesigns structure."""

    def schema_id(self) -> str:
        return _SCHEMA_ID

    def detect(self, data: dict) -> bool:
        # Explicit version marker
        if "usdmVersion" in data:
            return True
        # Structural detection: study with studyDesigns
        study = data.get("study")
        if isinstance(study, dict):
            return (
                "studyDesigns" in study
                or "studyTitle" in study
            )
        return False

    def priority(self) -> int:
        return 10  # Highest priority — most specific detection


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class USDMDocumentParser(JsonSchemaParser):
    """Converts USDM JSON to a FormattedDocument representing the protocol.

    Creates a multi-page document:
    1. Cover page (title, sponsor, phase, identifiers)
    2. Synopsis page (rationale, design description, arms)
    3. Objectives & Endpoints page
    4. Eligibility Criteria page
    5. Schedule of Activities table page
    """

    def schema_id(self) -> str:
        return _SCHEMA_ID

    def to_formatted_document(self, data: dict, filename: str = "") -> FormattedDocument:
        study = data.get("study", data)
        designs = study.get("studyDesigns", [])
        design = designs[0] if designs else {}

        pages: list[FormattedPage] = []
        style_inv: dict[str, int] = {}

        # Page 1: Cover
        pages.append(self._build_cover_page(study, design, style_inv))

        # Page 2: Synopsis
        pages.append(self._build_synopsis_page(study, design, style_inv))

        # Page 3: Objectives & Endpoints
        obj_page = self._build_objectives_page(study, style_inv)
        if obj_page:
            pages.append(obj_page)

        # Page 4: Eligibility Criteria
        elig_page = self._build_eligibility_page(study, style_inv)
        if elig_page:
            pages.append(elig_page)

        # Page 5: Schedule of Activities
        soa_page = self._build_soa_page(design, style_inv)
        if soa_page:
            pages.append(soa_page)

        # Fix page numbers
        for i, page in enumerate(pages):
            page.page_number = i

        font_inv = {"Arial": sum(
            sum(len(s.text) for ln in p.lines for s in ln.spans)
            for pg in pages for p in pg.paragraphs
        )}

        return FormattedDocument(
            filename=filename or f"{study.get('studyTitle', 'usdm_study')}.json",
            pages=pages,
            font_inventory=font_inv,
            color_inventory={"#000000": 1},
            style_inventory=style_inv,
        )

    def to_protocol(self, data: dict, filename: str = ""):
        """Delegate to USDMAdapter for Protocol generation."""
        try:
            from src.smb.adapters.usdm import USDMAdapter
            return USDMAdapter().to_protocol(data, filename)
        except ImportError:
            return None

    def to_extraction_input(self, data: dict, filename: str = ""):
        """Delegate to USDMAdapter for ExtractionInput generation."""
        try:
            from src.smb.adapters.usdm import USDMAdapter
            return USDMAdapter().to_extraction_input(data, filename)
        except ImportError:
            return None

    # -- Page builders --

    def _build_cover_page(
        self, study: dict, design: dict, si: dict
    ) -> FormattedPage:
        paras: list[FormattedParagraph] = []

        title = study.get("studyTitle", "Untitled Study")
        paras.append(_make_para(title, "heading1", bold=True, size=18.0, alignment="center"))
        si["heading1"] = si.get("heading1", 0) + 1

        # Identifiers
        for ident in study.get("studyIdentifiers", []):
            scope = ident.get("studyIdentifierScope", {})
            org_type = _decode(scope.get("organizationType"))
            org_name = scope.get("organizationName", "")
            value = ident.get("studyIdentifier", "")
            paras.append(_make_para(f"{org_type} ({org_name}): {value}"))
            si["body"] = si.get("body", 0) + 1

        # Phase
        phase = _decode(study.get("studyPhase", {}).get("standardCode"))
        if phase:
            paras.append(_make_para(f"Study Phase: {phase}", bold=True))
            si["body"] = si.get("body", 0) + 1

        # Study type
        study_type = _decode(study.get("studyType"))
        if study_type:
            paras.append(_make_para(f"Study Type: {study_type}"))
            si["body"] = si.get("body", 0) + 1

        # Therapeutic area and indication
        for ta in design.get("therapeuticAreas", []):
            paras.append(_make_para(f"Therapeutic Area: {_decode(ta)}"))
            si["body"] = si.get("body", 0) + 1
        for ind in design.get("studyIndications", []):
            desc = ind.get("indicationDescription", "")
            if desc:
                paras.append(_make_para(f"Indication: {desc}"))
                si["body"] = si.get("body", 0) + 1

        return FormattedPage(page_number=0, width=612.0, height=792.0, paragraphs=paras)

    def _build_synopsis_page(
        self, study: dict, design: dict, si: dict
    ) -> FormattedPage:
        paras: list[FormattedParagraph] = []

        paras.append(_make_para("Study Synopsis", "heading2", bold=True, size=16.0))
        si["heading2"] = si.get("heading2", 0) + 1

        # Rationale
        rationale = study.get("studyRationale", "")
        if rationale:
            paras.append(_make_para("Study Rationale", "heading3", bold=True, size=13.0))
            si["heading3"] = si.get("heading3", 0) + 1
            paras.append(_make_para(rationale))
            si["body"] = si.get("body", 0) + 1

        # Arms
        arms = design.get("studyArms", [])
        if arms:
            paras.append(_make_para("Study Arms", "heading3", bold=True, size=13.0))
            si["heading3"] = si.get("heading3", 0) + 1
            for arm in arms:
                name = arm.get("studyArmName", "")
                desc = arm.get("studyArmDescription", "")
                arm_type = _decode(arm.get("studyArmType"))
                paras.append(_make_para(f"  - {name} ({arm_type}): {desc}", "list_bullet"))
                si["list_bullet"] = si.get("list_bullet", 0) + 1

        # Epochs
        epochs = design.get("studyEpochs", [])
        if epochs:
            paras.append(_make_para("Study Epochs", "heading3", bold=True, size=13.0))
            si["heading3"] = si.get("heading3", 0) + 1
            for epoch in sorted(epochs, key=lambda e: e.get("sequenceNumber", 0)):
                name = epoch.get("studyEpochName", "")
                desc = epoch.get("studyEpochDescription", "")
                paras.append(_make_para(f"  - {name}: {desc}", "list_bullet"))
                si["list_bullet"] = si.get("list_bullet", 0) + 1

        # Interventions
        interventions = design.get("studyInvestigationalInterventions", [])
        if interventions:
            paras.append(_make_para("Investigational Interventions", "heading3", bold=True, size=13.0))
            si["heading3"] = si.get("heading3", 0) + 1
            for intv in interventions:
                desc = intv.get("interventionDescription", "")
                paras.append(_make_para(f"  - {desc}", "list_bullet"))
                si["list_bullet"] = si.get("list_bullet", 0) + 1

        return FormattedPage(page_number=1, width=612.0, height=792.0, paragraphs=paras)

    def _build_objectives_page(self, study: dict, si: dict) -> FormattedPage | None:
        objectives = study.get("studyObjectives", [])
        endpoints = study.get("studyEndpoints", [])
        if not objectives and not endpoints:
            return None

        paras: list[FormattedParagraph] = []
        ep_map = {ep["id"]: ep for ep in endpoints}

        paras.append(_make_para("Study Objectives and Endpoints", "heading2", bold=True, size=16.0))
        si["heading2"] = si.get("heading2", 0) + 1

        for obj in objectives:
            level = _decode(obj.get("objectiveLevel"))
            desc = obj.get("objectiveDescription", "")
            paras.append(_make_para(f"{level} Objective", "heading3", bold=True, size=13.0))
            si["heading3"] = si.get("heading3", 0) + 1
            paras.append(_make_para(desc))
            si["body"] = si.get("body", 0) + 1

            for ep_id in obj.get("objectiveEndpoints", []):
                ep = ep_map.get(ep_id, {})
                ep_desc = ep.get("endpointDescription", "")
                if ep_desc:
                    paras.append(_make_para(f"    Endpoint: {ep_desc}", "list_bullet"))
                    si["list_bullet"] = si.get("list_bullet", 0) + 1

        return FormattedPage(page_number=2, width=612.0, height=792.0, paragraphs=paras)

    def _build_eligibility_page(self, study: dict, si: dict) -> FormattedPage | None:
        criteria = study.get("studyEligibilityCriteria", [])
        if not criteria:
            return None

        paras: list[FormattedParagraph] = []
        paras.append(_make_para("Eligibility Criteria", "heading2", bold=True, size=16.0))
        si["heading2"] = si.get("heading2", 0) + 1

        inclusion = [c for c in criteria if c.get("criteriaType") == "Inclusion"]
        exclusion = [c for c in criteria if c.get("criteriaType") == "Exclusion"]

        if inclusion:
            paras.append(_make_para("Inclusion Criteria", "heading3", bold=True, size=13.0))
            si["heading3"] = si.get("heading3", 0) + 1
            for i, c in enumerate(inclusion, 1):
                paras.append(_make_para(f"  {i}. {c.get('criteriaText', '')}", "list_number"))
                si["list_number"] = si.get("list_number", 0) + 1

        if exclusion:
            paras.append(_make_para("Exclusion Criteria", "heading3", bold=True, size=13.0))
            si["heading3"] = si.get("heading3", 0) + 1
            for i, c in enumerate(exclusion, 1):
                paras.append(_make_para(f"  {i}. {c.get('criteriaText', '')}", "list_number"))
                si["list_number"] = si.get("list_number", 0) + 1

        return FormattedPage(page_number=3, width=612.0, height=792.0, paragraphs=paras)

    def _build_soa_page(self, design: dict, si: dict) -> FormattedPage | None:
        """Reconstruct Schedule of Activities table from USDM schedule timelines."""
        encounters = design.get("encounters", [])
        activities = design.get("activities", [])
        timelines = design.get("scheduleTimelines", [])
        if not encounters or not activities or not timelines:
            return None

        # Build encounter order (by timing value)
        timings = {t["id"]: t for t in design.get("timings", [])}
        enc_order = sorted(encounters, key=lambda e: timings.get(
            e.get("encounterScheduledAtTimingId", ""), {}
        ).get("timingValue", 0))

        # Build activity → encounters map from schedule instances
        # activity_id → set of encounter_ids
        act_enc_map: dict[str, set[str]] = {a["id"]: set() for a in activities}
        for timeline in timelines:
            for instance in timeline.get("scheduledInstances", []):
                enc_id = instance.get("encounterId", "")
                for act_id in instance.get("activityIds", []):
                    if act_id in act_enc_map:
                        act_enc_map[act_id].add(enc_id)

        # Filter activities that have at least one scheduled instance
        scheduled_activities = [a for a in activities if act_enc_map.get(a["id"])]

        num_rows = len(scheduled_activities) + 1  # +1 for header
        num_cols = len(enc_order) + 1  # +1 for procedure name column

        # Build header row
        header = [FormattedTableCell(text="Procedure", row=0, col=0, is_header=True, bold=True)]
        for ci, enc in enumerate(enc_order, 1):
            header.append(FormattedTableCell(
                text=enc.get("encounterName", ""), row=0, col=ci, is_header=True, bold=True
            ))

        rows = [header]

        # Build data rows
        for ri, act in enumerate(scheduled_activities, 1):
            row = [FormattedTableCell(
                text=act.get("activityName", ""), row=ri, col=0, bold=True
            )]
            for ci, enc in enumerate(enc_order, 1):
                mark = "X" if enc["id"] in act_enc_map.get(act["id"], set()) else ""
                row.append(FormattedTableCell(text=mark, row=ri, col=ci))
            rows.append(row)

        table = FormattedTable(rows=rows, num_rows=num_rows, num_cols=num_cols)

        paras = [_make_para("Schedule of Activities", "heading2", bold=True, size=16.0)]
        si["heading2"] = si.get("heading2", 0) + 1

        return FormattedPage(
            page_number=4, width=612.0, height=792.0, paragraphs=paras, tables=[table]
        )


# Module-level singletons for registry
DETECTOR = USDMDetector()
PARSER = USDMDocumentParser()
