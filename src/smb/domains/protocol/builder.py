"""
Protocol Domain Builder — converts SoA extraction to structured model.

Takes ExtractionInput (tables, cells, procedures, visits, footnotes)
and produces entities + relationships for the protocol knowledge graph.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.smb.core.entity import ConfidenceLevel, Entity, ProvenanceInfo
from src.smb.core.model import StructuredModel
from src.smb.core.relationship import Relationship, RelationshipBuilder
from src.smb.api.models import (
    ExtractionInput,
    TableInput,
    ExtractedCellInput,
)

logger = logging.getLogger(__name__)

# Marker patterns for detecting firm visits
_MARKER_PATTERNS = {"X", "x", "Y", "YES", "✓", "✔", "●"}

# Footnote-embedded marker regex (Xr, Xm, Xf)
_EMBEDDED_MARKER_RE = re.compile(
    r'^[X✓✔√Yy][a-g,\d\s\^]*$', re.IGNORECASE
)

# Span/continuous patterns
_SPAN_RE = re.compile(
    r'^[\-<>─═]{3,}|[\-<>─═]{3,}$|[\-]{2,}.*(?:Day|Week|Month).*[\-]{2,}',
    re.IGNORECASE,
)

# Frequency word detection
_FREQ_RE = re.compile(r'\b(Daily|Weekly|Monthly|Continuous)\b', re.IGNORECASE)

# Day range extraction
_DAY_RANGE_RE = re.compile(
    r'Day\s+(\d+)\s+(?:through|to|thru|[-–—])\s+Day\s+(\d+)', re.IGNORECASE
)

# Conditional text patterns
_CONDITIONAL_RE = re.compile(
    r'as clinically indicated|if (?:clinically )?(?:appropriate|indicated|needed)|'
    r'as needed|per investigator|at discretion|\bprn\b|may be performed',
    re.IGNORECASE,
)


class ProtocolBuilder:
    """Builds a StructuredModel for a clinical protocol from extraction data."""

    def build(self, extraction: ExtractionInput) -> StructuredModel:
        """Build the complete protocol model from extraction input."""
        model = StructuredModel(
            document_id=extraction.document_id,
            domain="protocol",
            metadata={
                "document_name": extraction.document_name,
                **extraction.metadata,
            },
        )

        # Create Document entity
        doc_entity = self._create_document_entity(extraction)
        model.entities.append(doc_entity)

        # Process each table
        for table in extraction.tables:
            self._process_table(model, table, doc_entity.id, extraction)

        logger.info(
            f"Protocol model built: {model.summary()}"
        )
        return model

    def _create_document_entity(self, extraction: ExtractionInput) -> Entity:
        """Create the top-level Document entity."""
        meta = extraction.metadata
        return Entity(
            entity_type="Document",
            name=extraction.document_name or extraction.document_id,
            properties={
                "protocol_number": meta.get("protocol_number", ""),
                "sponsor": meta.get("sponsor", ""),
                "phase": meta.get("phase", ""),
                "therapeutic_area": meta.get("therapeutic_area", ""),
                "indication": meta.get("indication", ""),
                "title": meta.get("title", extraction.document_name),
            },
            provenance=ProvenanceInfo(
                source_type="document",
                extraction_method="metadata",
            ),
        )

    def _process_table(
        self,
        model: StructuredModel,
        table: TableInput,
        doc_entity_id: str,
        extraction: ExtractionInput,
    ) -> None:
        """Process one SoA table into entities and relationships."""

        # 1. Create Visit entities from column headers
        visit_entities: dict[int, Entity] = {}
        for visit in table.visits:
            entity = Entity(
                entity_type="Visit",
                name=visit.visit_name,
                properties={
                    "visit_label": visit.visit_name,
                    "col_index": visit.col_index,
                    "day_number": visit.target_day,
                    "window_minus": visit.window_minus,
                    "window_plus": visit.window_plus,
                    "window_unit": visit.window_unit,
                    "is_unscheduled": visit.is_unscheduled,
                    "cycle": visit.cycle,
                },
                provenance=ProvenanceInfo(
                    source_type="table_cell",
                    table_name=table.title,
                    col_index=visit.col_index,
                    raw_text=visit.visit_name,
                    extraction_method="vlm",
                ),
            )
            entity.id = entity.deterministic_id(extraction.document_id)
            visit_entities[visit.col_index] = entity
            model.entities.append(entity)

        # 2. Create Procedure entities
        proc_entities: dict[str, Entity] = {}
        for proc in table.procedures:
            entity = Entity(
                entity_type="Procedure",
                name=proc.canonical_name,
                properties={
                    "raw_name": proc.raw_name,
                    "canonical_name": proc.canonical_name,
                    "cpt_code": proc.code,
                    "code_system": proc.code_system,
                    "category": proc.category,
                    "cost_tier": proc.cost_tier,
                },
                provenance=ProvenanceInfo(
                    source_type="table_cell",
                    table_name=table.title,
                    raw_text=proc.raw_name,
                    extraction_method="vlm",
                ),
            )
            entity.id = entity.deterministic_id(extraction.document_id)
            proc_entities[proc.raw_name.lower()] = entity
            model.entities.append(entity)

        # 3. Create Footnote entities
        footnote_entities: dict[str, Entity] = {}
        for fn in table.footnotes:
            entity = Entity(
                entity_type="Footnote",
                name=f"Footnote {fn.marker}",
                properties={
                    "footnote_marker": fn.marker,
                    "footnote_text": fn.text,
                    "classification": fn.footnote_type,
                },
                provenance=ProvenanceInfo(
                    source_type="footnote",
                    table_name=table.title,
                    raw_text=fn.text,
                    extraction_method="text",
                ),
            )
            entity.id = entity.deterministic_id(extraction.document_id)
            footnote_entities[fn.marker] = entity
            model.entities.append(entity)

        # 4. Build footnote lookup: (row, col) → list of footnote markers
        footnote_cell_map: dict[tuple[int, int], list[str]] = {}
        for fn in table.footnotes:
            for ref in fn.applies_to:
                key = (ref.get("row", -1), ref.get("col", -1))
                footnote_cell_map.setdefault(key, []).append(fn.marker)

        # 5. Build row_header → procedure entity map
        row_proc_map: dict[int, Entity] = {}
        for cell in table.cells:
            if cell.col == 0 and cell.row_header:
                proc_key = cell.row_header.lower()
                if proc_key in proc_entities:
                    row_proc_map[cell.row] = proc_entities[proc_key]

        # 6. Create ScheduleEntry for each non-empty data cell
        for cell in table.cells:
            if cell.col == 0:
                continue  # Skip row header column

            # Determine mark type
            mark_info = self._classify_cell(cell)
            if mark_info["mark_type"] == "empty":
                continue

            # Find corresponding visit and procedure
            visit = visit_entities.get(cell.col)
            proc = row_proc_map.get(cell.row)
            if not visit or not proc:
                continue

            # Get footnote markers for this cell
            cell_fn_markers = footnote_cell_map.get((cell.row, cell.col), [])
            cell_fn_markers.extend(cell.footnote_markers)
            cell_fn_markers = list(set(cell_fn_markers))

            # Determine if conditional based on footnotes
            fn_types = []
            for marker in cell_fn_markers:
                fn_entity = footnote_entities.get(marker)
                if fn_entity:
                    fn_types.append(fn_entity.get_property("classification", ""))

            if "CONDITIONAL" in fn_types:
                mark_info["mark_type"] = "conditional"
            if "EXCEPTION" in fn_types:
                mark_info["mark_type"] = "excluded"

            # Create ScheduleEntry entity
            entry_name = f"{proc.name} @ {visit.name}"
            entry = Entity(
                entity_type="ScheduleEntry",
                name=entry_name,
                properties={
                    "visit_entity_id": visit.id,
                    "procedure_entity_id": proc.id,
                    "mark_type": mark_info["mark_type"],
                    "raw_mark": cell.raw_value,
                    "occurrence_count": mark_info.get("occurrences", 1),
                    "footnote_markers": cell_fn_markers,
                    "is_span": mark_info.get("is_span", False),
                    "span_frequency": mark_info.get("frequency"),
                    "span_start_day": mark_info.get("start_day"),
                    "span_end_day": mark_info.get("end_day"),
                    "total_occurrences": mark_info.get("occurrences", 1),
                    "conditions": [],
                    "inference_trail": [],
                    "cost_multiplier": 1.0,
                    "subset_fraction": 1.0,
                },
                confidence=(
                    ConfidenceLevel.HIGH if cell.confidence >= 0.9
                    else ConfidenceLevel.MEDIUM if cell.confidence >= 0.75
                    else ConfidenceLevel.LOW
                ),
                provenance=ProvenanceInfo(
                    source_type="table_cell",
                    table_name=table.title,
                    row_index=cell.row,
                    col_index=cell.col,
                    raw_text=cell.raw_value,
                    extraction_method="vlm",
                ),
            )
            entry.id = entry.deterministic_id(extraction.document_id)
            model.entities.append(entry)

            # Create relationships
            model.relationships.append(
                RelationshipBuilder("HAS_SCHEDULE_ENTRY")
                .from_entity(visit.id)
                .to_entity(entry.id)
                .with_provenance("table_cell")
                .build()
            )
            model.relationships.append(
                RelationshipBuilder("FOR_PROCEDURE")
                .from_entity(entry.id)
                .to_entity(proc.id)
                .with_provenance("table_cell")
                .build()
            )

            # Footnote relationships
            for marker in cell_fn_markers:
                fn_entity = footnote_entities.get(marker)
                if fn_entity:
                    model.relationships.append(
                        RelationshipBuilder("MODIFIED_BY")
                        .from_entity(entry.id)
                        .to_entity(fn_entity.id)
                        .with_property("modification_type", fn_entity.get_property("classification", ""))
                        .with_provenance("footnote")
                        .build()
                    )

    def _classify_cell(self, cell: ExtractedCellInput) -> dict[str, Any]:
        """Classify a cell value into a mark type."""
        val = cell.raw_value.strip()
        if not val:
            return {"mark_type": "empty"}

        # Strip superscript Unicode
        val_clean = re.sub(r'[²³⁴⁵⁶⁷⁸⁹¹⁰⚡\u26A1]+$', '', val).strip()
        val_upper = val_clean.upper()

        # Check for span/continuous
        if _SPAN_RE.search(val) or any(p in val for p in ['←→', '↔', '──']):
            result: dict[str, Any] = {"mark_type": "span", "is_span": True}
            # Parse frequency/duration
            freq_match = _FREQ_RE.search(val)
            day_match = _DAY_RANGE_RE.search(val)
            if freq_match:
                result["frequency"] = freq_match.group(1).lower()
            if day_match:
                start = int(day_match.group(1))
                end = int(day_match.group(2))
                total_days = end - start + 1
                result["start_day"] = start
                result["end_day"] = end
                freq = result.get("frequency", "daily")
                if freq == "weekly":
                    result["occurrences"] = max(1, total_days // 7)
                elif freq == "monthly":
                    result["occurrences"] = max(1, total_days // 30)
                else:
                    result["occurrences"] = total_days
            elif freq_match:
                result["occurrences"] = 1  # Unknown duration
            return result

        # Check for conditional text
        if _CONDITIONAL_RE.search(val):
            return {"mark_type": "conditional", "occurrences": 1}

        # Check for standard markers
        if val_upper in _MARKER_PATTERNS or (len(val_clean) <= 2 and val_upper in _MARKER_PATTERNS):
            return {"mark_type": "firm", "occurrences": 1}

        # Check for footnote-embedded markers (Xr, Xm)
        if _EMBEDDED_MARKER_RE.match(val_clean):
            return {"mark_type": "firm", "occurrences": 1}

        # Check for text indicators
        text_indicators = ["required", "perform", "assess", "collect", "administer"]
        if any(ind in val.lower() for ind in text_indicators):
            return {"mark_type": "firm", "occurrences": 1}

        # Non-empty but unrecognized — likely metadata
        return {"mark_type": "empty"}
