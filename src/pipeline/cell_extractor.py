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
from src.pipeline.grid_anchor import GridSkeleton

logger = logging.getLogger(__name__)

# Anchored prompt: VLM fills values against a deterministic grid skeleton.
# Row indices come from PyMuPDF, not VLM inference — eliminates structural
# non-determinism where the same document produces different row mappings.
EXTRACTION_PROMPT_ANCHORED = """You are analyzing a clinical trial protocol table image.

{page_break_markers}{grid_anchor}

INSTRUCTIONS:
For EACH row listed above and EACH column, report the cell value. Use the EXACT
row indices provided — do NOT renumber or skip rows.

Return a JSON array where each element is:
{{
  "row": <row index from the table above — MUST match exactly>,
  "col": <0-based column index>,
  "raw_value": "<exact text in the cell, including any superscript markers>",
  "data_type": "MARKER" | "TEXT" | "NUMERIC" | "EMPTY" | "CONDITIONAL",
  "footnote_markers": ["a", "b"],
  "row_header": "<procedure name from the table above>",
  "col_header": "<the visit/column label>"
}}

Rules:
- MARKER = cells containing X, checkmarks, or similar marks
- CONDITIONAL = X with a superscript footnote letter (e.g., Xᵃ)
- EMPTY = cells with no content — report these explicitly
- TEXT = text content (procedure names, descriptions, volume amounts)
- NUMERIC = standalone numbers
- Use the row indices EXACTLY as listed — these are deterministic anchors
- Be precise — do not invent values not visible in the image

Return ONLY the JSON array."""

# Fallback prompt when no grid anchor is available
EXTRACTION_PROMPT_V1 = """You are analyzing a clinical trial protocol table image.
{page_break_markers}The table has the following structure:
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
{page_break_markers}Table structure: {columns} columns.
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

# Prompt for text-layout pages (>500 chars, no detected table grid lines)
EXTRACTION_PROMPT_TEXT_LAYOUT = """You are analyzing a clinical trial \
Schedule of Activities page.
{page_break_markers}
IMPORTANT: This page presents the SoA as TEXT WITHOUT VISIBLE GRID LINES.
The table structure is defined by HORIZONTAL ALIGNMENT -- text at the same
X-position belongs to the same column.

- The LEFTMOST column contains procedure names (assessments, tests,
  evaluations)
- SUBSEQUENT columns represent study visits or time points
- An "X" at a column position means that procedure is performed at that
  visit
- EMPTY positions (no text at that column) mean the procedure is NOT
  performed

Extract EVERY cell including empty ones. Pay close attention to:
1. Horizontal alignment -- text at similar X-positions = same column
2. "X" marks may be aligned with visit headers above
3. Procedure names in the first column may wrap to multiple lines
4. Footnote markers (a, b, c) may appear as superscripts

{columns}
Focus: rows {row_range}, section "{row_group}"

Return JSON array of cells as before.
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
        grid_skeleton: GridSkeleton | None = None,
        is_text_layout: bool = False,
    ) -> list[ExtractedCell]:
        """
        Extract all cell values from a table.

        Args:
            region: The table region to extract from.
            schema: Structural schema from Pass 1.
            pages: All page images.
            pass_number: 1 or 2 — determines which prompt variant to use.
            grid_skeleton: Deterministic row anchors from PyMuPDF.
                When provided, row indices are locked to the skeleton
                instead of being inferred by the VLM.
            is_text_layout: True if the table uses text-layout (no grid
                lines). Uses the specialized text-layout prompt.

        Returns:
            List of ExtractedCell objects.
        """
        table_images = self._get_table_images(region, pages)
        if not table_images:
            return []

        num_pages = len(table_images)

        # Build page break marker text for multi-page prompts
        page_break_text = self._build_page_break_markers(
            num_pages, region, grid_skeleton
        )

        # For tables >5 pages, switch to per-page extraction with column
        # headers repeated in each prompt for better accuracy.
        if num_pages > 5:
            return await self._extract_per_page(
                table_images, region, schema, grid_skeleton, pass_number
            )

        # Use anchored extraction when grid skeleton is available
        if grid_skeleton and grid_skeleton.rows:
            logger.info(
                f"Using grid-anchored extraction: {grid_skeleton.num_rows} rows, "
                f"{grid_skeleton.num_cols} cols"
            )
            anchor_text = grid_skeleton.to_prompt_anchor()
            prompt = EXTRACTION_PROMPT_ANCHORED.format(
                grid_anchor=anchor_text,
                page_break_markers=page_break_text,
            )
            return await self._extract_chunk(table_images, prompt)

        # Fallback: unanchored extraction (original behavior)
        # Use text-layout prompt when flagged
        if is_text_layout:
            logger.info("Detected text-layout table — using text-layout prompt")
            prompt_template = EXTRACTION_PROMPT_TEXT_LAYOUT
        else:
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
                        page_break_markers=page_break_text,
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
                page_break_markers=page_break_text,
            )
            return await self._extract_chunk(table_images, prompt)

    async def _extract_per_page(
        self,
        table_images: list[bytes],
        region: TableRegion,
        schema: TableSchema,
        grid_skeleton: GridSkeleton | None,
        pass_number: int,
    ) -> list[ExtractedCell]:
        """Per-page extraction for tables spanning >5 pages.

        Repeats column headers in each prompt so the VLM has full context
        without needing to reference earlier images.
        """
        import asyncio

        logger.info(
            f"Per-page extraction for {len(table_images)}-page table "
            f"(region {region.table_id})"
        )

        col_desc = ", ".join(
            f"{h.text} (col {h.col_index})"
            for h in schema.column_headers
        ) or f"{schema.num_cols} columns"

        # Build per-page row ranges from grid_skeleton when available
        page_row_ranges = self._get_per_page_row_ranges(region, grid_skeleton)

        semaphore = asyncio.Semaphore(self.config.max_concurrent_llm_calls)

        async def extract_single_page(page_idx: int, image: bytes) -> list[ExtractedCell]:
            async with semaphore:
                page_num = region.pages[page_idx] if page_idx < len(region.pages) else page_idx
                total = len(table_images)
                marker = f"--- PAGE {page_idx + 1} OF {total} ---\n"

                row_range_str = page_row_ranges.get(page_idx, "unknown")

                if grid_skeleton and grid_skeleton.rows:
                    # Filter skeleton rows for this page
                    page_rows = [
                        r for r in grid_skeleton.rows
                        if r.page_number == page_num or r.page_number == page_num + 1
                    ]
                    if page_rows:
                        anchor_lines = [
                            "TABLE STRUCTURE (deterministic — DO NOT change row indices):",
                            f"Total rows: {grid_skeleton.num_rows}, Total columns: {grid_skeleton.num_cols}",
                        ]
                        if grid_skeleton.column_headers:
                            cols_display = [
                                f"col {i}: {h}"
                                for i, h in enumerate(grid_skeleton.column_headers)
                            ]
                            anchor_lines.append(f"Columns: {'; '.join(cols_display)}")
                        anchor_lines.append("")
                        anchor_lines.append("ROW INDEX | PROCEDURE NAME")
                        anchor_lines.append("-" * 60)
                        for row in page_rows:
                            if not row.is_header:
                                anchor_lines.append(
                                    f"  {row.row_index:>3}      | {row.procedure_name}"
                                )
                        anchor_text = "\n".join(anchor_lines)
                        prompt = EXTRACTION_PROMPT_ANCHORED.format(
                            grid_anchor=anchor_text,
                            page_break_markers=marker,
                        )
                    else:
                        prompt_template = (
                            EXTRACTION_PROMPT_V1 if pass_number == 1
                            else EXTRACTION_PROMPT_V2
                        )
                        prompt = prompt_template.format(
                            columns=col_desc,
                            row_range=row_range_str,
                            row_group=f"Page {page_idx + 1} of {total}",
                            page_break_markers=marker,
                        )
                else:
                    prompt_template = (
                        EXTRACTION_PROMPT_V1 if pass_number == 1
                        else EXTRACTION_PROMPT_V2
                    )
                    prompt = prompt_template.format(
                        columns=col_desc,
                        row_range=row_range_str,
                        row_group=f"Page {page_idx + 1} of {total}",
                        page_break_markers=marker,
                    )

                return await self._extract_chunk([image], prompt)

        results = await asyncio.gather(
            *(extract_single_page(i, img) for i, img in enumerate(table_images)),
            return_exceptions=True,
        )

        # Apply cumulative row offset so page 2 rows don't restart at 0.
        # Pages are processed concurrently but assembled in order here.
        all_cells: list[ExtractedCell] = []
        cumulative_row_offset = 0
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(f"Per-page extraction failed on page {i}: {res}")
                continue

            page_cells: list[ExtractedCell] = res
            if not page_cells:
                continue

            if i > 0 and page_cells and not (grid_skeleton and grid_skeleton.rows):
                # Only apply offset when there's no grid skeleton
                # (grid skeleton already has correct absolute row indices)
                min_row_in_page = min(c.row for c in page_cells)
                if min_row_in_page < cumulative_row_offset:
                    # VLM restarted row numbering — apply offset
                    offset_cells = []
                    for cell in page_cells:
                        offset_cells.append(cell.model_copy(
                            update={"row": cell.row + cumulative_row_offset}
                        ))
                    page_cells = offset_cells

            all_cells.extend(page_cells)

            # Update offset for next page: next page starts after
            # the highest row seen so far
            if page_cells:
                max_row_this_page = max(c.row for c in page_cells)
                cumulative_row_offset = max_row_this_page + 1

        return all_cells

    @staticmethod
    def _build_page_break_markers(
        num_pages: int,
        region: TableRegion,
        grid_skeleton: GridSkeleton | None,
    ) -> str:
        """Build page break marker text for multi-page prompts.

        Produces lines like:
            --- PAGE 1 OF 3 (rows 0-12) ---
            --- PAGE 2 OF 3 (rows 13-25) ---
            --- PAGE 3 OF 3 (rows 26-38) ---

        Returns empty string for single-page tables.
        """
        if num_pages <= 1:
            return ""

        lines = ["The following images span multiple pages of the same table:\n"]

        # Build per-page row ranges from grid skeleton if available
        page_row_map: dict[int, tuple[int, int]] = {}
        if grid_skeleton and grid_skeleton.rows:
            for row in grid_skeleton.rows:
                pg = row.page_number
                if pg not in page_row_map:
                    page_row_map[pg] = (row.row_index, row.row_index)
                else:
                    lo, hi = page_row_map[pg]
                    page_row_map[pg] = (min(lo, row.row_index), max(hi, row.row_index))

        for i in range(num_pages):
            page_num = region.pages[i] if i < len(region.pages) else i
            row_info = ""
            if page_num in page_row_map:
                lo, hi = page_row_map[page_num]
                row_info = f" (rows {lo}-{hi})"
            elif (page_num + 1) in page_row_map:
                # grid_skeleton uses 1-indexed pages sometimes
                lo, hi = page_row_map[page_num + 1]
                row_info = f" (rows {lo}-{hi})"
            lines.append(f"  --- PAGE {i + 1} OF {num_pages}{row_info} ---")

        lines.append("")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _get_per_page_row_ranges(
        region: TableRegion,
        grid_skeleton: GridSkeleton | None,
    ) -> dict[int, str]:
        """Return mapping of page_index → row range string for per-page extraction."""
        result: dict[int, str] = {}
        if not grid_skeleton or not grid_skeleton.rows:
            return result

        page_rows: dict[int, list[int]] = {}
        for row in grid_skeleton.rows:
            pg = row.page_number
            page_rows.setdefault(pg, []).append(row.row_index)

        for i, page_num in enumerate(region.pages):
            # Try both 0-indexed and 1-indexed page numbers
            rows = page_rows.get(page_num, page_rows.get(page_num + 1, []))
            if rows:
                result[i] = f"{min(rows)}-{max(rows)}"
            else:
                result[i] = "unknown"

        return result

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

    @staticmethod
    def detect_text_layout(pdf_bytes: bytes, table_pages: list[int]) -> bool:
        """Detect if a table region uses text-layout (no grid lines).

        Heuristic: pages with >500 characters of text content but where
        PyMuPDF's find_tables() returns 0 tables are text-layout pages.
        Falls back to False if fitz is not available or detection fails.
        """
        try:
            import fitz
        except ImportError:
            return False

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_layout_pages = 0
            checked_pages = 0

            for pg in table_pages:
                if pg >= doc.page_count:
                    continue
                checked_pages += 1
                page = doc[pg]
                text = page.get_text("text")
                tables = page.find_tables()

                # Text-layout: lots of text but no detected table grid
                if len(text) > 500 and len(tables.tables) == 0:
                    text_layout_pages += 1

            doc.close()

            # If majority of pages are text-layout, flag the region
            return checked_pages > 0 and text_layout_pages > checked_pages / 2
        except Exception:
            return False


def _safe_int(value, default: int = 0) -> int:
    """Safely convert LLM output to int — handles float, str, None."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
