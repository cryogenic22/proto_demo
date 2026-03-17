# Protocol Table Extraction Pipeline — Specification

## 1. Problem Statement

Clinical trial protocol documents (PDFs) contain complex tables — primarily
Schedule of Activities (SoA) tables — that must be digitized into structured,
machine-readable data for downstream site budgeting. Current approaches suffer
from structural information loss during extraction, hallucinated values, and
inability to handle footnotes, merged cells, and multi-page tables.

## 2. Goals

- **Input**: A clinical trial protocol PDF document.
- **Output**: Structured JSON containing every table in the document, with:
  - Cell-level values with row/column coordinates
  - Resolved footnotes anchored to specific cells
  - Procedures normalized to canonical codes
  - Visit windows with temporal logic
  - Per-cell confidence scores
  - Source provenance (page number, bounding box)

## 3. Pipeline Architecture

```
PDF Upload
    │
    ▼
┌─────────────────────┐
│  1. PDF Ingestion    │  PDF → high-res page images
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  2. Table Detection  │  Identify table regions per page
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  3. Table Stitcher   │  Merge multi-page tables into logical units
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  4. Structural       │  Pass 1: Extract table schema (headers,
│     Analyzer         │  row groups, merged cells, footnote markers)
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  5. Cell Extractor   │  Pass 2: High-res per-chunk value extraction
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  6. Footnote         │  Anchor footnote markers to cell-level
│     Resolver         │  metadata
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  7. Procedure        │  Map free-text procedure names to
│     Normalizer       │  canonical codes (CPT/SNOMED)
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  8. Temporal         │  Extract visit windows and conditional
│     Extractor        │  logic
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  9. Challenger       │  Adversarial validation agent that
│     Agent            │  hunts for errors
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 10. Reconciler       │  Multi-pass consistency check,
│                      │  confidence scoring
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 11. Orchestrator     │  Coordinates all stages, handles
│                      │  errors, produces final output
└─────────────────────┘
```

## 4. Data Models

### 4.1 BoundingBox
```
{
  page: int,
  x0: float, y0: float,
  x1: float, y1: float
}
```

### 4.2 PageImage
```
{
  page_number: int,
  image: bytes (PNG),
  width: int,
  height: int,
  dpi: int
}
```

### 4.3 TableRegion
```
{
  table_id: str,
  pages: list[int],
  bounding_boxes: list[BoundingBox],
  table_type: enum(SOA, DEMOGRAPHICS, LAB_PARAMS, DOSING, OTHER),
  title: str | None
}
```

### 4.4 TableSchema
```
{
  table_id: str,
  column_headers: list[ColumnHeader],
  row_groups: list[RowGroup],
  merged_regions: list[MergedRegion],
  footnote_markers: list[str],
  num_rows: int,
  num_cols: int
}
```

### 4.5 ExtractedCell
```
{
  row: int,
  col: int,
  raw_value: str,
  normalized_value: str | None,
  data_type: enum(MARKER, TEXT, NUMERIC, EMPTY, CONDITIONAL),
  footnote_markers: list[str],
  resolved_footnotes: list[str],
  confidence: float (0.0 - 1.0),
  source: BoundingBox
}
```

### 4.6 ResolvedFootnote
```
{
  marker: str,
  text: str,
  applies_to: list[CellRef],
  footnote_type: enum(CONDITIONAL, CLARIFICATION, EXCEPTION, REFERENCE)
}
```

### 4.7 NormalizedProcedure
```
{
  raw_name: str,
  canonical_name: str,
  code: str | None (CPT or SNOMED),
  category: str,
  estimated_cost_tier: enum(LOW, MEDIUM, HIGH, VERY_HIGH)
}
```

### 4.8 VisitWindow
```
{
  visit_name: str,
  target_day: int | None,
  window_minus: int,
  window_plus: int,
  window_unit: enum(DAYS, WEEKS, MONTHS),
  relative_to: str,
  is_unscheduled: bool
}
```

### 4.9 ExtractedTable (final output per table)
```
{
  table_id: str,
  table_type: str,
  title: str,
  source_pages: list[int],
  schema: TableSchema,
  cells: list[ExtractedCell],
  footnotes: list[ResolvedFootnote],
  procedures: list[NormalizedProcedure],
  visit_windows: list[VisitWindow],
  overall_confidence: float,
  flagged_cells: list[CellRef],
  extraction_metadata: {
    passes_run: int,
    challenger_issues_found: int,
    reconciliation_conflicts: int,
    timestamp: datetime
  }
}
```

### 4.10 PipelineOutput (final output)
```
{
  document_name: str,
  document_hash: str,
  total_pages: int,
  tables: list[ExtractedTable],
  processing_time_seconds: float,
  pipeline_version: str
}
```

## 5. Module Specifications

### 5.1 PDF Ingestion
- **Input**: PDF file path or bytes
- **Output**: list[PageImage]
- **Requirements**:
  - Render at 300 DPI minimum
  - Handle both native digital PDFs and scanned documents
  - Preserve page ordering
  - Support documents up to 500 pages

### 5.2 Table Detection
- **Input**: list[PageImage]
- **Output**: list[TableRegion]
- **Requirements**:
  - Detect all table regions including partial tables (continuation pages)
  - Classify table type (SoA, demographics, lab params, dosing, other)
  - Detect table titles/captions
  - Handle tables embedded in text vs full-page tables

### 5.3 Table Stitcher
- **Input**: list[TableRegion]
- **Output**: list[TableRegion] (merged)
- **Requirements**:
  - Identify tables that span multiple pages via:
    - Matching row header text across pages
    - Detecting repeated column headers
    - Detecting "continued" / "cont'd" markers
  - Merge into single logical TableRegion with multiple bounding boxes
  - Handle column subsets across pages (visits 1-8 on page 1, 9-ET on page 2)

### 5.4 Structural Analyzer
- **Input**: TableRegion + page images
- **Output**: TableSchema
- **Requirements**:
  - Use vision LLM at reduced resolution for gestalt read
  - Identify multi-tier column headers (e.g., "Treatment Period" spanning sub-columns)
  - Detect merged cell regions
  - Identify row groupings (e.g., "Safety Assessments", "Efficacy", "PK")
  - Catalog all footnote marker symbols used

### 5.5 Cell Extractor
- **Input**: TableRegion + TableSchema + page images
- **Output**: list[ExtractedCell]
- **Requirements**:
  - Semantically decompose table into chunks using schema
  - Extract each chunk at full resolution
  - Include overlapping boundary rows between chunks
  - Run extraction twice with different prompts for consistency
  - Assign per-cell confidence based on extraction agreement

### 5.6 Footnote Resolver
- **Input**: list[ExtractedCell] + footnote text from page
- **Output**: list[ResolvedFootnote] + updated ExtractedCell list
- **Requirements**:
  - Match superscript markers in cells to footnote definitions
  - Classify footnote type (conditional, clarification, exception, reference)
  - Handle nested footnotes
  - Attach resolved footnote text as cell-level metadata

### 5.7 Procedure Normalizer
- **Input**: list[ExtractedCell] (procedure name cells)
- **Output**: list[NormalizedProcedure]
- **Requirements**:
  - Map free-text procedure names to canonical vocabulary
  - Use embedding similarity for fuzzy matching
  - Assign cost tier based on procedure type
  - Flag ambiguous mappings (confidence < threshold)

### 5.8 Temporal Extractor
- **Input**: TableSchema column headers
- **Output**: list[VisitWindow]
- **Requirements**:
  - Parse visit names to extract target day/week
  - Parse window notation (±N days/weeks)
  - Identify relative-to anchors
  - Handle cycle-based nomenclature (Cycle 1 Day 1, C2D1, etc.)
  - Handle unscheduled/early termination visits

### 5.9 Challenger Agent
- **Input**: ExtractedTable + source page images
- **Output**: list[ChallengeIssue]
- **Requirements**:
  - Compare extracted data against source images
  - Check structural consistency (cell count matches schema)
  - Check footnote coverage (all markers accounted for)
  - Check value plausibility (procedure names are real, frequencies are reasonable)
  - Output specific issues with reasoning

### 5.10 Reconciler
- **Input**: Multi-pass extraction results + ChallengeIssues
- **Output**: Final ExtractedTable with confidence scores
- **Requirements**:
  - Reconcile disagreements between extraction passes
  - Incorporate challenger findings
  - Compute final per-cell confidence
  - Flag cells below confidence threshold for human review
  - Apply cost-weighted thresholds (high-cost procedures = stricter threshold)

### 5.11 Orchestrator
- **Input**: PDF file
- **Output**: PipelineOutput
- **Requirements**:
  - Coordinate all pipeline stages sequentially
  - Handle errors gracefully (one failed table shouldn't block others)
  - Produce structured JSON output
  - Track processing time
  - Support configuration (DPI, confidence thresholds, model selection)

## 6. Configuration

```python
@dataclass
class PipelineConfig:
    render_dpi: int = 300
    llm_model: str = "claude-sonnet-4-6-20250514"
    confidence_threshold: float = 0.85
    high_cost_threshold: float = 0.95
    max_extraction_passes: int = 2
    enable_challenger: bool = True
    enable_round_trip_test: bool = False
    max_concurrent_llm_calls: int = 5
```

## 7. Error Handling

- Each pipeline stage wraps its work in try/except and produces a
  degraded output rather than failing completely.
- If table detection finds 0 tables, return empty output with a warning.
- If a single table extraction fails, skip it and continue with others.
- All errors are logged with stage name, table_id, and error details.

## 8. Testing Strategy

- **Unit tests**: Each module tested in isolation with fixtures
- **Integration tests**: End-to-end pipeline on synthetic table images
- **Golden set regression**: Run against curated protocol set, compare
  to ground truth at cell level
- **Metrics**: Precision, recall, F1 at cell level, stratified by
  difficulty tier
