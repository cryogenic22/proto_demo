"""
DigitizedDocument — the contract between Layer 1 (digitization) and Layer 2 (extraction).

Layer 1 (DocumentDigitizer) produces a DigitizedDocument containing:
- Full formatting IR (FormattedDocument — pages, paragraphs, spans, tables)
- Section tree (SectionNode hierarchy with ke_types)
- Table classifications (SOA / DEMOGRAPHICS / LAB_PARAMS / OTHER)
- Protocol metadata (title, sponsor, phase, indication)

Layer 2 extractors consume this to perform targeted extraction (SoA tables,
eligibility criteria, study design, etc.) without re-parsing the source PDF.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.formatter.extractor import FormattedDocument
from src.models.protocol import ProtocolMetadata, SectionNode


# ---------------------------------------------------------------------------
# Table classification
# ---------------------------------------------------------------------------

class TableType:
    """Well-known table type identifiers."""
    SOA = "SOA"
    DEMOGRAPHICS = "DEMOGRAPHICS"
    LAB_PARAMS = "LAB_PARAMS"
    DOSING = "DOSING"
    INCLUSION_EXCLUSION = "INCLUSION_EXCLUSION"
    ENDPOINTS = "ENDPOINTS"
    OTHER = "OTHER"


@dataclass
class TableClassification:
    """Classification of a single table detected in the document.

    References a specific FormattedTable via page_number + table_index
    (index within that page's tables list).
    """
    page_number: int
    table_index: int          # index into FormattedDocument.pages[page].tables
    table_type: str           # TableType constant
    confidence: float         # 0.0 - 1.0
    title: str = ""           # Detected table title (from preceding heading or caption)
    num_rows: int = 0
    num_cols: int = 0
    signals: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Digitized document
# ---------------------------------------------------------------------------

@dataclass
class DigitizedDocument:
    """Full digitization output — the bridge between Layer 1 and Layer 2.

    Contains everything needed for downstream extractors to operate
    without re-parsing the source PDF.
    """
    formatted: FormattedDocument
    sections: list[SectionNode] = field(default_factory=list)
    table_classifications: list[TableClassification] = field(default_factory=list)
    metadata: ProtocolMetadata = field(default_factory=ProtocolMetadata)
    source_hash: str = ""
    source_filename: str = ""

    # -- Convenience queries --

    def get_tables_by_type(self, table_type: str) -> list[TableClassification]:
        """Return all table classifications matching a given type."""
        return [tc for tc in self.table_classifications if tc.table_type == table_type]

    def get_soa_tables(self) -> list[TableClassification]:
        """Return all tables classified as Schedule of Activities."""
        return self.get_tables_by_type(TableType.SOA)

    def get_soa_pages(self) -> set[int]:
        """Return page numbers containing SoA tables."""
        return {tc.page_number for tc in self.get_soa_tables()}

    @property
    def total_pages(self) -> int:
        return len(self.formatted.pages)

    @property
    def total_tables(self) -> int:
        return len(self.table_classifications)

    def summary(self) -> dict[str, Any]:
        """Return a summary dict for logging/display."""
        type_counts: dict[str, int] = {}
        for tc in self.table_classifications:
            type_counts[tc.table_type] = type_counts.get(tc.table_type, 0) + 1
        return {
            "pages": self.total_pages,
            "paragraphs": self.formatted.total_paragraphs,
            "tables": self.total_tables,
            "table_types": type_counts,
            "sections": len(self.sections),
            "title": self.metadata.title[:80] if self.metadata.title else "",
            "source": self.source_filename,
        }
