"""
Protocol — first-class data object representing a parsed clinical trial protocol.

Composes sections, SoA tables, procedures, footnotes, and metadata into a single
navigable structure. Designed to map cleanly to Knowledge Elements in a Neo4j graph.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Knowledge Element types
# ---------------------------------------------------------------------------

class KEType(str, Enum):
    """Knowledge Element types for Neo4j persistence."""
    PROTOCOL = "PROTOCOL"
    SECTION = "SECTION"
    SOA_TABLE = "SOA_TABLE"
    PROCEDURE = "PROCEDURE"
    FOOTNOTE = "FOOTNOTE"
    VISIT_WINDOW = "VISIT_WINDOW"
    INCLUSION_CRITERIA = "INCLUSION_CRITERIA"
    EXCLUSION_CRITERIA = "EXCLUSION_CRITERIA"
    OBJECTIVE = "OBJECTIVE"
    ENDPOINT = "ENDPOINT"
    STUDY_DESIGN = "STUDY_DESIGN"
    STATISTICAL = "STATISTICAL"


class KEStatus(str, Enum):
    DRAFT = "DRAFT"
    VERIFIED = "VERIFIED"
    LOCKED = "LOCKED"


# ---------------------------------------------------------------------------
# Knowledge Element graph primitives
# ---------------------------------------------------------------------------

class KERelationship(BaseModel):
    """A typed, directed relationship between two knowledge elements."""
    rel_type: str  # HAS_SECTION, CONTAINS, INFORMS, CONSTRAINS, etc.
    target_ke_id: str
    properties: dict[str, Any] = Field(default_factory=dict)


class KnowledgeElement(BaseModel):
    """A single knowledge element — the atomic unit of the protocol graph."""
    ke_id: str = ""  # Generated: {protocol_id}:{ke_type}:{identifier}
    ke_type: KEType
    title: str
    content: str = ""  # HTML or plain text content
    source_pages: list[int] = Field(default_factory=list)
    status: KEStatus = KEStatus.DRAFT
    version: str = "1.0"
    metadata: dict[str, Any] = Field(default_factory=dict)
    children: list[str] = Field(default_factory=list)  # Child KE IDs
    relationships: list[KERelationship] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Protocol metadata
# ---------------------------------------------------------------------------

class ProtocolMetadata(BaseModel):
    """Protocol-level metadata extracted from cover page and synopsis."""
    title: str = ""
    short_title: str = ""
    protocol_number: str = ""
    nct_number: str = ""
    sponsor: str = ""
    phase: str = ""
    therapeutic_area: str = ""
    indication: str = ""
    study_type: str = ""  # interventional, observational
    arms: list[str] = Field(default_factory=list)
    amendment_number: str = ""
    amendment_date: str = ""
    version: str = ""


# ---------------------------------------------------------------------------
# Section tree
# ---------------------------------------------------------------------------

class SectionNode(BaseModel):
    """A section in the protocol hierarchy — maps to a KE."""
    number: str
    title: str
    page: int
    end_page: int | None = None
    level: int = 1
    ke_type: KEType = KEType.SECTION  # Can be overridden for special sections
    content_html: str = ""  # Populated on demand via get_section_formatted
    children: list[SectionNode] = Field(default_factory=list)
    quality_score: float | None = None


# ---------------------------------------------------------------------------
# Protocol — top-level aggregate
# ---------------------------------------------------------------------------

class Protocol(BaseModel):
    """The canonical protocol data object. Everything downstream consumes this."""
    protocol_id: str  # e.g., "pfizer_bnt162" or document hash
    document_name: str
    document_hash: str = ""
    total_pages: int = 0
    metadata: ProtocolMetadata = Field(default_factory=ProtocolMetadata)
    sections: list[SectionNode] = Field(default_factory=list)
    tables: list[Any] = Field(default_factory=list)  # ExtractedTable from schema.py
    procedures: list[Any] = Field(default_factory=list)  # NormalizedProcedure
    budget_lines: list[Any] = Field(default_factory=list)  # BudgetLine data
    quality_summary: dict[str, Any] = Field(default_factory=dict)
    knowledge_elements: list[KnowledgeElement] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    pipeline_version: str = "0.1.0"

    # ------------------------------------------------------------------
    # KE graph generation
    # ------------------------------------------------------------------

    def to_ke_graph(self) -> list[KnowledgeElement]:
        """Convert the protocol to a flat list of KEs for Neo4j persistence."""
        kes: list[KnowledgeElement] = []

        # Protocol root KE
        root = KnowledgeElement(
            ke_id=f"{self.protocol_id}:PROTOCOL:root",
            ke_type=KEType.PROTOCOL,
            title=self.metadata.title or self.document_name,
            metadata=self.metadata.model_dump(),
            status=KEStatus.DRAFT,
        )
        kes.append(root)

        # Section KEs
        for section in self._flatten_sections(self.sections):
            end = section.end_page or section.page
            ke = KnowledgeElement(
                ke_id=f"{self.protocol_id}:SECTION:{section.number}",
                ke_type=section.ke_type,
                title=f"{section.number} {section.title}",
                content=section.content_html,
                source_pages=list(range(section.page, end + 1)),
                metadata={"level": section.level},
            )
            ke.relationships.append(
                KERelationship(
                    rel_type="BELONGS_TO",
                    target_ke_id=root.ke_id,
                )
            )
            kes.append(ke)

        return kes

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _flatten_sections(
        self, sections: list[SectionNode]
    ) -> list[SectionNode]:
        """Recursively flatten the section tree into a list."""
        flat: list[SectionNode] = []
        for s in sections:
            flat.append(s)
            flat.extend(self._flatten_sections(s.children))
        return flat
