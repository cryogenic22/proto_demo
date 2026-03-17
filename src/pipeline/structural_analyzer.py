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
    ColumnHeader,
    MergedRegion,
    PageImage,
    PipelineConfig,
    RowGroup,
    TableRegion,
    TableSchema,
)

logger = logging.getLogger(__name__)

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

        return self._parse_schema(raw, region.table_id)

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
                    col_index=h.get("col_index", i),
                    text=str(h.get("text", "")),
                    span=int(h.get("span", 1)),
                    level=int(h.get("level", 0)),
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
                    start_row=int(g.get("start_row", 0)),
                    end_row=int(g.get("end_row", 0)),
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
                    start_row=int(m.get("start_row", 0)),
                    end_row=int(m.get("end_row", 0)),
                    start_col=int(m.get("start_col", 0)),
                    end_col=int(m.get("end_col", 0)),
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

        return TableSchema(
            table_id=table_id,
            column_headers=column_headers,
            row_groups=row_groups,
            merged_regions=merged_regions,
            footnote_markers=footnote_markers,
            num_rows=int(raw.get("num_rows", 0)),
            num_cols=int(raw.get("num_cols", 0)),
        )
