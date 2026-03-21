"""
Cell Extractor — Pass 2: high-resolution per-chunk cell value extraction.

Decomposes the table into semantic chunks using the schema from Pass 1,
then extracts each chunk at full resolution with overlapping boundary rows.
Runs extraction twice with different prompts for consistency checking.
"""

from __future__ import annotations

import logging
from typing import Any

from src.llm.client import LLMClient
from src.models.schema import (
    CellDataType,
    ExtractedCell,
    PageImage,
    PipelineConfig,
    TableRegion,
    TableSchema,
)

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT_V1 = """You are analyzing a clinical trial protocol table image.
The table has the following structure:
- Columns: {columns}
- This section covers rows: {row_range}
- Row group: {row_group}

Extract EVERY cell value in this table section. Return a JSON array where each element is:
{{
  "row": <0-based row index within the full table>,
  "col": <0-based column index>,
  "raw_value": "<exact text in the cell, including any superscript markers>",
  "data_type": "MARKER" | "TEXT" | "NUMERIC" | "EMPTY" | "CONDITIONAL",
  "footnote_markers": ["a", "b"] (list of superscript symbols found in this cell),
  "row_header": "<the procedure/row label for this row>",
  "col_header": "<the visit/column label for this column>"
}}

Rules:
- MARKER = cells containing X, ✓, ✗, or similar check/cross marks
- TEXT = cells with text content (procedure names, descriptions)
- NUMERIC = cells with numbers
- EMPTY = cells with no content
- CONDITIONAL = cells with markers that have footnotes modifying their meaning
- Capture ALL superscript symbols as footnote_markers
- Be precise — do not invent values not visible in the image

Return ONLY the JSON array."""

EXTRACTION_PROMPT_V2 = """Look at this clinical trial protocol table image carefully.
Table structure: {columns} columns.
Focus area: rows {row_range}, section "{row_group}".

List every single cell in this table section as a JSON array. Each cell:
{{
  "row": <row number, 0-based in full table>,
  "col": <column number, 0-based>,
  "raw_value": "<verbatim cell text including superscripts>",
  "data_type": one of "MARKER", "TEXT", "NUMERIC", "EMPTY", "CONDITIONAL",
  "footnote_markers": [<list of superscript symbols if any>],
  "row_header": "<row label>",
  "col_header": "<column label>"
}}

Important:
- Report empty cells explicitly as EMPTY with raw_value ""
- Include superscript letters/symbols in footnote_markers
- MARKER means X or check marks
- CONDITIONAL means the cell's meaning depends on a footnote
- Do NOT guess or hallucinate values — only report what you can see

Return ONLY valid JSON array."""


class CellExtractor:
    """Pass 2: Extract cell values from table chunks at full resolution."""

    def __init__(self, config: PipelineConfig, llm_client: LLMClient | None = None):
        self.config = config
        self.llm = llm_client or LLMClient(config)

    async def extract(
        self,
        region: TableRegion,
        schema: TableSchema,
        pages: list[PageImage],
        pass_number: int = 1,
    ) -> list[ExtractedCell]:
        """
        Extract all cell values from a table.

        Args:
            region: The table region to extract from.
            schema: Structural schema from Pass 1.
            pages: All page images.
            pass_number: 1 or 2 — determines which prompt variant to use.

        Returns:
            List of ExtractedCell objects.
        """
        table_images = self._get_table_images(region, pages)
        if not table_images:
            return []

        prompt_template = EXTRACTION_PROMPT_V1 if pass_number == 1 else EXTRACTION_PROMPT_V2

        # Build column description from schema
        col_desc = ", ".join(
            f"{h.text} (col {h.col_index})"
            for h in schema.column_headers
        ) or f"{schema.num_cols} columns"

        # If we have row groups, extract per group in parallel
        if schema.row_groups:
            import asyncio
            semaphore = asyncio.Semaphore(self.config.max_concurrent_llm_calls)

            async def extract_group(group):
                async with semaphore:
                    prompt = prompt_template.format(
                        columns=col_desc,
                        row_range=f"{group.start_row}-{group.end_row}",
                        row_group=group.name,
                    )
                    return await self._extract_chunk(table_images, prompt)

            results = await asyncio.gather(
                *(extract_group(g) for g in schema.row_groups),
                return_exceptions=True,
            )
            all_cells: list[ExtractedCell] = []
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    logger.error(f"Row group extraction failed: {res}")
                else:
                    all_cells.extend(res)
            return all_cells
        else:
            # Single extraction for entire table
            prompt = prompt_template.format(
                columns=col_desc,
                row_range=f"0-{schema.num_rows - 1}",
                row_group="Full table",
            )
            return await self._extract_chunk(table_images, prompt)

    async def _extract_chunk(
        self, images: list[bytes], prompt: str
    ) -> list[ExtractedCell]:
        """Extract cells from a table chunk."""
        try:
            if len(images) == 1:
                raw = await self.llm.vision_json_query(
                    images[0], prompt,
                    system="You are a precise clinical document data extractor. Return valid JSON only.",
                    max_tokens=8192,
                )
            else:
                raw = await self.llm.vision_json_query_multi(
                    images, prompt,
                    system="You are a precise clinical document data extractor. Return valid JSON only.",
                    max_tokens=8192,
                )

            if not isinstance(raw, list):
                logger.warning("Cell extraction did not return a list")
                return []

            return [self._parse_cell(item) for item in raw]

        except Exception as e:
            logger.error(f"Cell extraction failed: {e}")
            return []

    def _parse_cell(self, raw: dict[str, Any]) -> ExtractedCell:
        """Parse a raw cell dict into an ExtractedCell."""
        raw_type = raw.get("data_type", "TEXT")
        try:
            data_type = CellDataType(raw_type)
        except ValueError:
            data_type = CellDataType.TEXT

        return ExtractedCell(
            row=_safe_int(raw.get("row", 0)),
            col=_safe_int(raw.get("col", 0)),
            raw_value=str(raw.get("raw_value", "")),
            data_type=data_type,
            footnote_markers=raw.get("footnote_markers", []) or [],
            row_header=str(raw.get("row_header", "")),
            col_header=str(raw.get("col_header", "")),
            confidence=1.0,
        )

    @staticmethod
    def _get_table_images(
        region: TableRegion, pages: list[PageImage]
    ) -> list[bytes]:
        page_map = {p.page_number: p for p in pages}
        return [
            page_map[pn].image_bytes
            for pn in region.pages
            if pn in page_map
        ]


def _safe_int(value, default: int = 0) -> int:
    """Safely convert LLM output to int — handles float, str, None."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
