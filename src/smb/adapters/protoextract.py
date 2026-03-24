"""
ProtoExtract Adapter — converts PipelineOutput/Protocol JSON to ExtractionInput.

This is the ONLY coupling point between ProtoExtract and the SMB.
"""

from __future__ import annotations

import logging
from typing import Any

from src.smb.api.models import (
    ExtractionInput,
    ExtractedCellInput,
    FootnoteInput,
    ProcedureInput,
    TableInput,
    VisitInput,
)

logger = logging.getLogger(__name__)


class ProtoExtractAdapter:
    """Converts ProtoExtract protocol data to SMB ExtractionInput."""

    def convert(self, protocol_data: dict[str, Any]) -> ExtractionInput:
        """Convert a stored protocol JSON dict to ExtractionInput."""
        tables = []
        for td in protocol_data.get("tables", []):
            tables.append(self._convert_table(td))

        # Extract metadata
        metadata = protocol_data.get("metadata", {})
        if isinstance(metadata, dict):
            meta = metadata
        else:
            meta = {}

        # Load domain config if available
        domain_config = self._load_domain_config(meta)

        return ExtractionInput(
            document_id=protocol_data.get("protocol_id", ""),
            document_name=protocol_data.get("document_name", ""),
            domain="protocol",
            tables=tables,
            metadata=meta,
            domain_config=domain_config,
        )

    def _convert_table(self, td: dict[str, Any]) -> TableInput:
        """Convert one ExtractedTable dict to TableInput."""
        cells = [
            ExtractedCellInput(
                row=c.get("row", 0),
                col=c.get("col", 0),
                raw_value=c.get("raw_value", ""),
                data_type=c.get("data_type", "TEXT"),
                confidence=c.get("confidence", 1.0),
                row_header=c.get("row_header", ""),
                col_header=c.get("col_header", ""),
                footnote_markers=c.get("footnote_markers", []),
                resolved_footnotes=c.get("resolved_footnotes", []),
                evidence=c.get("evidence"),
            )
            for c in td.get("cells", [])
        ]

        footnotes = [
            FootnoteInput(
                marker=fn.get("marker", ""),
                text=fn.get("text", ""),
                footnote_type=fn.get("footnote_type", "CLARIFICATION"),
                applies_to=[
                    {"row": ref.get("row", 0), "col": ref.get("col", 0)}
                    for ref in fn.get("applies_to", [])
                ],
            )
            for fn in td.get("footnotes", [])
        ]

        procedures = [
            ProcedureInput(
                raw_name=p.get("raw_name", ""),
                canonical_name=p.get("canonical_name", ""),
                code=p.get("code"),
                code_system=p.get("code_system"),
                category=p.get("category", "Unknown"),
                cost_tier=p.get("estimated_cost_tier", "LOW"),
            )
            for p in td.get("procedures", [])
        ]

        visits = [
            VisitInput(
                visit_name=vw.get("visit_name", ""),
                col_index=vw.get("col_index", 0),
                target_day=vw.get("target_day"),
                window_minus=vw.get("window_minus", 0),
                window_plus=vw.get("window_plus", 0),
                window_unit=vw.get("window_unit", "DAYS"),
                relative_to=vw.get("relative_to", "randomization"),
                is_unscheduled=vw.get("is_unscheduled", False),
                cycle=vw.get("cycle"),
            )
            for vw in td.get("visit_windows", [])
        ]

        return TableInput(
            table_id=td.get("table_id", ""),
            table_type=td.get("table_type", "SOA"),
            title=td.get("title", ""),
            source_pages=td.get("source_pages", []),
            cells=cells,
            footnotes=footnotes,
            procedures=procedures,
            visits=visits,
            overall_confidence=td.get("overall_confidence", 0.0),
        )

    def _load_domain_config(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Load domain YAML config based on protocol metadata."""
        try:
            from src.domain.config import load_domain_config
            ta = metadata.get("therapeutic_area", "")
            sponsor = metadata.get("sponsor", "")
            return load_domain_config(therapeutic_area=ta, sponsor=sponsor)
        except Exception:
            return {}
