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

{
  "table_id": "<keep the provided table_id>",
  "column_headers": [
    {
      "col_index": <0-based index>,
      "text": "<header text>",
      "span": <number of columns this header spans, default 1>,
      "level": <header tier, 0=top-level, 1=sub-header>,
      "parent_col": <parent header col_index if nested, or null>
    }
  ],
  "row_groups": [
    {
      "name": "<group name, e.g. 'Safety Assessments'>",
      "start_row": <0-based row index>,
      "end_row": <0-based row index>,
      "category": "<category like Safety, Efficacy, PK, General>"
    }
  ],
  "merged_regions": [
    {
      "start_row": <int>, "end_row": <int>,
      "start_col": <int>, "end_col": <int>,
      "value": "<text in merged cell>"
    }
  ],
  "footnote_markers": ["a", "b", "c", "*", "†"],
  "num_rows": <total data rows excluding headers>,
  "num_cols": <total columns>
}

Focus on:
- Multi-tier headers (e.g., "Treatment Period" spanning sub-columns)
- Row groupings with section headers
- Merged cells spanning multiple rows or columns
- All footnote symbols used in the table (superscripts, *, †, ‡, etc.)

TABLE_ID: {table_id}

Return ONLY valid JSON."""


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
        # Collect page images for this table
        table_page_images = self._get_table_images(region, pages)

        if not table_page_images:
            raise ValueError(f"No page images found for table {region.table_id}")

        prompt = SCHEMA_PROMPT.format(table_id=region.table_id)

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

        return self._parse_schema(raw, region.table_id)

    def _get_table_images(
        self, region: TableRegion, pages: list[PageImage]
    ) -> list[bytes]:
        """Get the image bytes for all pages containing this table."""
        page_map = {p.page_number: p for p in pages}
        images = []
        for page_num in region.pages:
            if page_num in page_map:
                images.append(page_map[page_num].image_bytes)
        return images

    def _parse_schema(self, raw: dict[str, Any], table_id: str) -> TableSchema:
        """Parse raw LLM response into TableSchema."""
        column_headers = [
            ColumnHeader(
                col_index=h.get("col_index", i),
                text=h.get("text", ""),
                span=h.get("span", 1),
                level=h.get("level", 0),
                parent_col=h.get("parent_col"),
            )
            for i, h in enumerate(raw.get("column_headers", []))
        ]

        row_groups = [
            RowGroup(
                name=g.get("name", ""),
                start_row=g.get("start_row", 0),
                end_row=g.get("end_row", 0),
                category=g.get("category", ""),
            )
            for g in raw.get("row_groups", [])
        ]

        merged_regions = [
            MergedRegion(
                start_row=m.get("start_row", 0),
                end_row=m.get("end_row", 0),
                start_col=m.get("start_col", 0),
                end_col=m.get("end_col", 0),
                value=m.get("value", ""),
            )
            for m in raw.get("merged_regions", [])
        ]

        return TableSchema(
            table_id=table_id,
            column_headers=column_headers,
            row_groups=row_groups,
            merged_regions=merged_regions,
            footnote_markers=raw.get("footnote_markers", []),
            num_rows=raw.get("num_rows", 0),
            num_cols=raw.get("num_cols", 0),
        )
