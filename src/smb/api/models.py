"""
SMB API models — standard input/output contracts.

ExtractionInput is the universal format that adapters produce.
BuildResult is what the engine returns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from src.smb.core.model import StructuredModel


class ExtractedCellInput(BaseModel):
    """One cell from an extraction grid."""
    row: int
    col: int
    raw_value: str = ""
    data_type: str = "TEXT"  # MARKER, TEXT, NUMERIC, EMPTY, CONDITIONAL
    confidence: float = 1.0
    row_header: str = ""  # Procedure name
    col_header: str = ""  # Visit name
    footnote_markers: list[str] = Field(default_factory=list)
    resolved_footnotes: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] | None = None


class FootnoteInput(BaseModel):
    """A resolved footnote from extraction."""
    marker: str
    text: str
    footnote_type: str = "CLARIFICATION"
    applies_to: list[dict[str, int]] = Field(default_factory=list)  # [{row, col}]


class ProcedureInput(BaseModel):
    """A normalized procedure from extraction."""
    raw_name: str
    canonical_name: str
    code: str | None = None
    code_system: str | None = None
    category: str = "Unknown"
    cost_tier: str = "LOW"


class VisitInput(BaseModel):
    """A parsed visit/column header from extraction."""
    visit_name: str
    col_index: int
    target_day: int | None = None
    window_minus: int = 0
    window_plus: int = 0
    window_unit: str = "DAYS"
    relative_to: str = "randomization"
    is_unscheduled: bool = False
    cycle: int | None = None
    visit_path: list[str] = Field(
        default_factory=list,
        description="Hierarchical path from TreeThinker header tree, "
        "e.g., ['Treatment Period', 'Cycle 1', 'Day 1']",
    )


class TableInput(BaseModel):
    """One extracted table (typically a Schedule of Activities)."""
    table_id: str
    table_type: str = "SOA"
    title: str = ""
    source_pages: list[int] = Field(default_factory=list)
    cells: list[ExtractedCellInput] = Field(default_factory=list)
    footnotes: list[FootnoteInput] = Field(default_factory=list)
    procedures: list[ProcedureInput] = Field(default_factory=list)
    visits: list[VisitInput] = Field(default_factory=list)
    overall_confidence: float = 0.0


class ExtractionInput(BaseModel):
    """Standard input format for the SMB engine.

    Adapters convert pipeline-specific output into this format.
    The engine processes this regardless of extraction source.
    """
    document_id: str
    document_name: str = ""
    domain: str = "protocol"
    tables: list[TableInput] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    domain_config: dict[str, Any] = Field(default_factory=dict)


class BuildResult(BaseModel):
    """Result of an SMB engine build."""
    model: StructuredModel
    build_time_seconds: float = 0.0
    inference_rules_fired: list[str] = Field(default_factory=list)
    validation_passed: bool = True
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
