"""
Core data models for the Protocol Table Extraction Pipeline.

All models are Pydantic v2 BaseModels with strict validation.
These define the contract between every pipeline stage.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TableType(str, Enum):
    SOA = "SOA"
    DEMOGRAPHICS = "DEMOGRAPHICS"
    LAB_PARAMS = "LAB_PARAMS"
    DOSING = "DOSING"
    INCLUSION_EXCLUSION = "INCLUSION_EXCLUSION"
    OTHER = "OTHER"


class CellDataType(str, Enum):
    MARKER = "MARKER"          # X, ✓, check marks
    TEXT = "TEXT"
    NUMERIC = "NUMERIC"
    EMPTY = "EMPTY"
    CONDITIONAL = "CONDITIONAL"  # value depends on footnote


class FootnoteType(str, Enum):
    CONDITIONAL = "CONDITIONAL"      # modifies when/if procedure is done
    CLARIFICATION = "CLARIFICATION"  # adds detail
    EXCEPTION = "EXCEPTION"          # excludes certain cases
    REFERENCE = "REFERENCE"          # points to another section


class CostTier(str, Enum):
    LOW = "LOW"            # vitals, weight, basic labs
    MEDIUM = "MEDIUM"      # ECG, standard bloodwork
    HIGH = "HIGH"          # MRI, CT, specialized labs
    VERY_HIGH = "VERY_HIGH"  # PET, biopsy, genetic testing


class WindowUnit(str, Enum):
    DAYS = "DAYS"
    WEEKS = "WEEKS"
    MONTHS = "MONTHS"


class ChallengeType(str, Enum):
    MISSING_VALUE = "MISSING_VALUE"
    HALLUCINATED_VALUE = "HALLUCINATED_VALUE"
    STRUCTURAL_MISMATCH = "STRUCTURAL_MISMATCH"
    FOOTNOTE_UNRESOLVED = "FOOTNOTE_UNRESOLVED"
    IMPLAUSIBLE_VALUE = "IMPLAUSIBLE_VALUE"


class ReviewType(str, Enum):
    """Triage category for human review queue."""
    LOCAL_RESOLUTION = "LOCAL_RESOLUTION"      # Type 1: human can see answer
    STRUCTURAL_INTERPRETATION = "STRUCTURAL_INTERPRETATION"  # Type 2: needs steer
    SYSTEMATIC_PATTERN = "SYSTEMATIC_PATTERN"  # Type 3: pipeline update needed


# ---------------------------------------------------------------------------
# Core geometry
# ---------------------------------------------------------------------------

class BoundingBox(BaseModel):
    page: int = Field(..., ge=0, description="0-indexed page number")
    x0: float = Field(..., ge=0)
    y0: float = Field(..., ge=0)
    x1: float = Field(..., ge=0)
    y1: float = Field(..., ge=0)

    @field_validator("x1")
    @classmethod
    def x1_gt_x0(cls, v: float, info: Any) -> float:
        if "x0" in info.data and v <= info.data["x0"]:
            raise ValueError("x1 must be greater than x0")
        return v

    @field_validator("y1")
    @classmethod
    def y1_gt_y0(cls, v: float, info: Any) -> float:
        if "y0" in info.data and v <= info.data["y0"]:
            raise ValueError("y1 must be greater than y0")
        return v

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        return self.width * self.height


# ---------------------------------------------------------------------------
# Page-level models
# ---------------------------------------------------------------------------

class PageImage(BaseModel):
    page_number: int = Field(..., ge=0)
    image_bytes: bytes
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    dpi: int = Field(default=300, gt=0)

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Table structure models
# ---------------------------------------------------------------------------

class ColumnHeader(BaseModel):
    col_index: int = Field(..., ge=0)
    text: str
    span: int = Field(default=1, ge=1, description="Number of columns this header spans")
    level: int = Field(default=0, ge=0, description="Header tier, 0 = top-level")
    parent_col: int | None = Field(default=None, description="Parent header column index if nested")


class RowGroup(BaseModel):
    name: str
    start_row: int = Field(..., ge=0)
    end_row: int = Field(..., ge=0)
    category: str = Field(default="", description="e.g., Safety, Efficacy, PK")


class MergedRegion(BaseModel):
    start_row: int = Field(..., ge=0)
    end_row: int = Field(..., ge=0)
    start_col: int = Field(..., ge=0)
    end_col: int = Field(..., ge=0)
    value: str = ""


class CellRef(BaseModel):
    """Reference to a specific cell. Hashable so it can be used as dict key."""
    model_config = {"frozen": True}

    row: int = Field(..., ge=0)
    col: int = Field(..., ge=0)

    def __hash__(self) -> int:
        return hash((self.row, self.col))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CellRef):
            return self.row == other.row and self.col == other.col
        return NotImplemented


class TableRegion(BaseModel):
    table_id: str
    pages: list[int] = Field(..., min_length=1)
    bounding_boxes: list[BoundingBox] = Field(..., min_length=1)
    table_type: TableType = TableType.OTHER
    title: str | None = None
    continuation_markers: list[str] = Field(default_factory=list)


class TableSchema(BaseModel):
    table_id: str
    column_headers: list[ColumnHeader] = Field(default_factory=list)
    row_groups: list[RowGroup] = Field(default_factory=list)
    merged_regions: list[MergedRegion] = Field(default_factory=list)
    footnote_markers: list[str] = Field(default_factory=list)
    num_rows: int = Field(..., ge=0)
    num_cols: int = Field(..., ge=0)


# ---------------------------------------------------------------------------
# Extraction models
# ---------------------------------------------------------------------------

class ExtractedCell(BaseModel):
    row: int = Field(..., ge=0)
    col: int = Field(..., ge=0)
    raw_value: str = ""
    normalized_value: str | None = None
    data_type: CellDataType = CellDataType.TEXT
    footnote_markers: list[str] = Field(default_factory=list)
    resolved_footnotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: BoundingBox | None = None
    row_header: str = Field(default="", description="Procedure/row label for this cell")
    col_header: str = Field(default="", description="Visit/column label for this cell")


class ResolvedFootnote(BaseModel):
    marker: str
    text: str
    applies_to: list[CellRef] = Field(default_factory=list)
    footnote_type: FootnoteType = FootnoteType.CLARIFICATION


class NormalizedProcedure(BaseModel):
    raw_name: str
    canonical_name: str
    code: str | None = None
    code_system: str | None = Field(default=None, description="CPT, SNOMED, LOINC, etc.")
    category: str = ""
    estimated_cost_tier: CostTier = CostTier.LOW


class VisitWindow(BaseModel):
    visit_name: str
    col_index: int = Field(..., ge=0)
    target_day: int | None = None
    window_minus: int = Field(default=0, ge=0)
    window_plus: int = Field(default=0, ge=0)
    window_unit: WindowUnit = WindowUnit.DAYS
    relative_to: str = Field(default="randomization", description="Anchor event")
    is_unscheduled: bool = False
    cycle: int | None = Field(default=None, description="Cycle number for oncology protocols")


# ---------------------------------------------------------------------------
# Validation / challenge models
# ---------------------------------------------------------------------------

class ChallengeIssue(BaseModel):
    cell_ref: CellRef | None = None
    challenge_type: ChallengeType
    description: str
    extracted_value: str = ""
    suggested_value: str | None = None
    severity: float = Field(default=0.5, ge=0.0, le=1.0, description="0=minor, 1=critical")


class ReviewItem(BaseModel):
    cell_ref: CellRef
    review_type: ReviewType
    reason: str
    extracted_value: str
    source_page: int
    cost_tier: CostTier = CostTier.LOW


# ---------------------------------------------------------------------------
# Composite output models
# ---------------------------------------------------------------------------

class ExtractionMetadata(BaseModel):
    passes_run: int = 1
    challenger_issues_found: int = 0
    reconciliation_conflicts: int = 0
    processing_time_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_used: str = ""


class ExtractedTable(BaseModel):
    table_id: str
    table_type: TableType
    title: str = ""
    source_pages: list[int] = Field(default_factory=list)
    schema_info: TableSchema  # renamed to avoid shadowing BaseModel.schema
    cells: list[ExtractedCell] = Field(default_factory=list)
    footnotes: list[ResolvedFootnote] = Field(default_factory=list)
    procedures: list[NormalizedProcedure] = Field(default_factory=list)
    visit_windows: list[VisitWindow] = Field(default_factory=list)
    overall_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    flagged_cells: list[CellRef] = Field(default_factory=list)
    review_items: list[ReviewItem] = Field(default_factory=list)
    extraction_metadata: ExtractionMetadata = Field(default_factory=ExtractionMetadata)


class PipelineOutput(BaseModel):
    document_name: str
    document_hash: str = ""
    total_pages: int = Field(..., ge=0)
    tables: list[ExtractedTable] = Field(default_factory=list)
    processing_time_seconds: float = 0.0
    pipeline_version: str = "0.1.0"
    warnings: list[str] = Field(default_factory=list)

    @staticmethod
    def compute_hash(pdf_bytes: bytes) -> str:
        return hashlib.sha256(pdf_bytes).hexdigest()


# ---------------------------------------------------------------------------
# Pipeline configuration
# ---------------------------------------------------------------------------

class PipelineConfig(BaseModel):
    render_dpi: int = Field(default=150, ge=72, le=600)
    llm_provider: str = Field(default="anthropic", description="LLM provider: 'anthropic', 'openai', or 'azure'")
    llm_model: str = Field(default="", description="Model name. Leave empty for provider default.")
    vision_model: str = Field(default="", description="Vision model. Leave empty for provider default.")
    confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    high_cost_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    max_extraction_passes: int = Field(default=2, ge=1, le=5)
    enable_challenger: bool = True
    enable_round_trip_test: bool = False
    max_concurrent_llm_calls: int = Field(default=10, ge=1)
    openai_batch_mode: bool = Field(default=False, description="Use OpenAI Batch API for async processing (cheaper, slower)")
    soa_only: bool = Field(default=True, description="Only extract Schedule of Activities tables")
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = Field(default="", description="Azure OpenAI endpoint URL (e.g., https://myinstance.openai.azure.com)")
    azure_openai_api_version: str = Field(default="2024-12-01-preview", description="Azure OpenAI API version")
    azure_openai_deployment: str = Field(default="", description="Azure OpenAI deployment name (overrides llm_model)")

    @property
    def resolved_llm_model(self) -> str:
        if self.llm_model:
            return self.llm_model
        if self.llm_provider == "azure":
            return self.azure_openai_deployment or "gpt-4o"
        if self.llm_provider == "openai":
            return "gpt-4.1"
        return "claude-sonnet-4-6"

    @property
    def resolved_vision_model(self) -> str:
        if self.vision_model:
            return self.vision_model
        if self.llm_provider == "azure":
            return self.azure_openai_deployment or "gpt-4o"
        if self.llm_provider == "openai":
            return "gpt-4.1"
        return "claude-sonnet-4-6"
