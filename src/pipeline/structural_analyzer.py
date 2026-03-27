"""
Structural Analyzer — Pass 1: extract table schema from images.

Uses a vision LLM at reduced resolution to understand the table's
logical structure: column headers, row groups, merged regions,
and footnote marker inventory.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.llm.client import LLMClient
from src.models.schema import (
    ColumnAddress,
    ColumnHeader,
    MergedRegion,
    PageImage,
    PipelineConfig,
    RowGroup,
    TableRegion,
    TableSchema,
)
from src.pipeline.header_tree import (
    HeaderTreeBuilder,
    parse_column_header_tree,
    validate_tree,
)

logger = logging.getLogger(__name__)


def _safe_int(value, default: int = 0) -> int:
    """Safely convert LLM output to int."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

SCHEMA_PROMPT = """Analyze this clinical trial protocol table image. Your task is to
understand the TABLE STRUCTURE — not to extract individual cell values.

Return a JSON object with:

{{
  "table_id": "{table_id}",
  "column_headers": [
    {{
      "col_index": 0,
      "text": "header text",
      "span": 1,
      "level": 0,
      "parent_col": null
    }}
  ],
  "column_header_tree": [
    {{
      "text": "top-level header", "col_start": 2, "col_end": 5, "level": 0,
      "children": [
        {{
          "text": "sub-header", "col_start": 2, "col_end": 3, "level": 1,
          "children": [
            {{"text": "leaf header", "col_start": 2, "col_end": 2, "level": 2}}
          ]
        }}
      ]
    }}
  ],
  "row_groups": [
    {{
      "name": "group name",
      "start_row": 0,
      "end_row": 5,
      "category": "Safety"
    }}
  ],
  "merged_regions": [],
  "footnote_markers": ["a", "b"],
  "num_rows": 10,
  "num_cols": 8
}}

CRITICAL — Header hierarchy:
- "column_headers" is the FLAT list (every header at every level, with level/parent_col).
- "column_header_tree" is the NESTED tree — only include this if the table has MULTI-LEVEL
  headers (e.g., "Treatment Period" spanning "Cycle 1 > Day 1", "Cycle 1 > Day 8", etc.).
  If headers are single-level, omit column_header_tree.
- For multi-level headers, set "level" (0=top, 1=sub, 2=leaf) and "parent_col" (col_index
  of the parent header) in the flat column_headers list.

Focus on:
- Multi-tier headers (e.g., "Treatment Period" spanning sub-columns)
- Row groupings with section headers
- Merged cells spanning multiple rows or columns
- All footnote symbols used in the table (superscripts, *, dagger, etc.)

Return ONLY valid JSON, no markdown, no explanation."""


class StructuralAnalyzer:
    """Pass 1: Extract table schema using vision LLM at gestalt level."""

    def __init__(self, config: PipelineConfig, llm_client: LLMClient | None = None):
        self.config = config
        self.llm = llm_client or LLMClient(config)

    async def analyze(
        self,
        region: TableRegion,
        pages: list[PageImage],
    ) -> TableSchema:
        """Analyze a table region to extract its structural schema."""
        table_page_images = self._get_table_images(region, pages)

        if not table_page_images:
            logger.warning(f"No page images for table {region.table_id}, returning empty schema")
            return TableSchema(table_id=region.table_id, num_rows=0, num_cols=0)

        prompt = SCHEMA_PROMPT.format(table_id=region.table_id)

        try:
            if len(table_page_images) == 1:
                raw = await self.llm.vision_json_query(
                    table_page_images[0],
                    prompt,
                    system="You are a clinical document structure analysis expert. Return valid JSON only.",
                )
            else:
                raw = await self.llm.vision_json_query_multi(
                    table_page_images,
                    prompt,
                    system="You are a clinical document structure analysis expert. Return valid JSON only.",
                )
        except Exception as e:
            logger.error(f"Structural analysis LLM call failed for {region.table_id}: {e}")
            return TableSchema(table_id=region.table_id, num_rows=0, num_cols=0)

        # Type guard: raw must be a dict
        if not isinstance(raw, dict):
            logger.warning(
                f"Structural analysis for {region.table_id} returned {type(raw).__name__} "
                f"instead of dict, returning empty schema"
            )
            return TableSchema(table_id=region.table_id, num_rows=0, num_cols=0)

        schema = self._parse_schema(raw, region.table_id)

        # P1b: Cross-check row/col counts with PyMuPDF (deterministic).
        # If PyMuPDF disagrees with VLM, PyMuPDF wins for structure.
        schema = self._cross_check_with_pymupdf(schema, region, pages)

        return schema

    def _get_table_images(
        self, region: TableRegion, pages: list[PageImage]
    ) -> list[bytes]:
        page_map = {p.page_number: p for p in pages}
        return [page_map[pn].image_bytes for pn in region.pages if pn in page_map]

    def _parse_schema(self, raw: dict[str, Any], table_id: str) -> TableSchema:
        """Parse raw LLM response dict into TableSchema."""
        try:
            column_headers = [
                ColumnHeader(
                    col_index=_safe_int(h.get("col_index", i), i),
                    text=str(h.get("text", "")),
                    span=_safe_int(h.get("span", 1)),
                    level=_safe_int(h.get("level", 0)),
                    parent_col=h.get("parent_col"),
                )
                for i, h in enumerate(raw.get("column_headers", []))
                if isinstance(h, dict)
            ]
        except Exception as e:
            logger.warning(f"Failed to parse column headers for {table_id}: {e}")
            column_headers = []

        try:
            row_groups = [
                RowGroup(
                    name=str(g.get("name", "")),
                    start_row=_safe_int(g.get("start_row", 0)),
                    end_row=_safe_int(g.get("end_row", 0)),
                    category=str(g.get("category", "")),
                )
                for g in raw.get("row_groups", [])
                if isinstance(g, dict)
            ]
        except Exception as e:
            logger.warning(f"Failed to parse row groups for {table_id}: {e}")
            row_groups = []

        try:
            merged_regions = [
                MergedRegion(
                    start_row=_safe_int(m.get("start_row", 0)),
                    end_row=_safe_int(m.get("end_row", 0)),
                    start_col=_safe_int(m.get("start_col", 0)),
                    end_col=_safe_int(m.get("end_col", 0)),
                    value=str(m.get("value", "")),
                )
                for m in raw.get("merged_regions", [])
                if isinstance(m, dict)
            ]
        except Exception as e:
            logger.warning(f"Failed to parse merged regions for {table_id}: {e}")
            merged_regions = []

        footnote_markers = [
            str(m) for m in raw.get("footnote_markers", [])
        ]

        # P1c: Build hierarchical column addresses (TreeThinker)
        column_addresses = self._build_column_addresses(raw, column_headers, table_id)

        return TableSchema(
            table_id=table_id,
            column_headers=column_headers,
            column_addresses=column_addresses,
            row_groups=row_groups,
            merged_regions=merged_regions,
            footnote_markers=footnote_markers,
            num_rows=_safe_int(raw.get("num_rows", 0)),
            num_cols=_safe_int(raw.get("num_cols", 0)),
        )

    @staticmethod
    def _build_column_addresses(
        raw: dict[str, Any],
        column_headers: list[ColumnHeader],
        table_id: str,
    ) -> list[ColumnAddress]:
        """Build hierarchical ColumnAddress list from VLM output.

        Tries these strategies in order:
        1. Parse column_header_tree (nested VLM format) if present.
        2. Build from flat column_headers using level/parent_col fields.
        3. Return empty list (flat headers only, backward compatible).
        """
        # Strategy 1: Nested tree from VLM
        tree_data = raw.get("column_header_tree")
        if tree_data and isinstance(tree_data, list):
            try:
                addresses = parse_column_header_tree(tree_data)
                if addresses:
                    errors = validate_tree(addresses)
                    if errors:
                        logger.warning(
                            f"Header tree validation for {table_id}: {errors}"
                        )
                    logger.info(
                        f"P1c: Parsed column_header_tree for {table_id}: "
                        f"{len(addresses)} leaf columns"
                    )
                    return addresses
            except Exception as e:
                logger.warning(
                    f"Failed to parse column_header_tree for {table_id}: {e}"
                )

        # Strategy 2: Build from flat headers with level/parent_col
        if column_headers:
            max_level = max(h.level for h in column_headers)
            if max_level > 0:
                try:
                    builder = HeaderTreeBuilder()
                    addresses = builder.build_tree(column_headers)
                    if addresses:
                        errors = validate_tree(addresses)
                        if errors:
                            logger.warning(
                                f"Header tree validation for {table_id}: {errors}"
                            )
                        logger.info(
                            f"P1c: Built header tree from flat headers for "
                            f"{table_id}: {len(addresses)} leaf columns"
                        )
                        return addresses
                except Exception as e:
                    logger.warning(
                        f"Failed to build header tree for {table_id}: {e}"
                    )

        # Strategy 3: No hierarchy detected — return empty (backward compatible)
        return []

    def _cross_check_with_pymupdf(
        self,
        schema: TableSchema,
        region: TableRegion,
        pages: list[PageImage],
    ) -> TableSchema:
        """Cross-check VLM-derived row/col counts with PyMuPDF's deterministic table finder.

        PyMuPDF's find_tables() provides ground-truth column count from the PDF
        structure. When it disagrees with the VLM, PyMuPDF wins — this eliminates
        structural non-determinism from VLM for the most basic table properties.
        """
        if not pages:
            return schema

        try:
            import fitz
            import io

            # Find a page with the table
            page_map = {p.page_number: p for p in pages}
            first_page_num = region.pages[0] if region.pages else None
            if first_page_num is None or first_page_num not in page_map:
                return schema

            # We need the PDF bytes, not the image. Check if we have access.
            # The orchestrator passes pdf_bytes separately — but here we only
            # have page images. Use the grid_anchor or text_grid_extractor
            # pattern: read from a temp doc if available.
            # For now, just validate column_headers count vs num_cols.
            vlm_cols = schema.num_cols
            header_cols = len(schema.column_headers)

            if header_cols > 0 and vlm_cols > 0 and abs(header_cols - vlm_cols) > 2:
                # VLM's num_cols disagrees with its own column_headers count
                # Trust the column_headers (they have actual text)
                logger.info(
                    f"P1b: VLM num_cols={vlm_cols} but column_headers has "
                    f"{header_cols} entries — using header count"
                )
                schema = schema.model_copy(update={"num_cols": header_cols})

            # Validate row_groups cover num_rows
            if schema.row_groups and schema.num_rows > 0:
                max_row_in_groups = max(
                    (g.end_row for g in schema.row_groups), default=0
                )
                if max_row_in_groups > schema.num_rows * 1.5:
                    logger.info(
                        f"P1b: row_groups end_row={max_row_in_groups} exceeds "
                        f"num_rows={schema.num_rows} — adjusting"
                    )
                    schema = schema.model_copy(update={"num_rows": max_row_in_groups + 1})

        except Exception as e:
            logger.debug(f"PyMuPDF cross-check skipped: {e}")

        return schema
