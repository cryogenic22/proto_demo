"""
Grid Anchor — deterministic row extraction using PyMuPDF.

Solves the structural non-determinism problem: the VLM infers row/col
indices visually, producing different mappings across runs. This module
extracts procedure names and their Y-coordinates deterministically from
the PDF text layer, building a "grid skeleton" that anchors row indices.

The VLM then fills in cell values against this fixed skeleton instead
of inferring row numbers from scratch.

Strategy:
  1. Use PyMuPDF find_tables() to locate actual table boundaries on each page
  2. Extract table cells from the detected table structure
  3. The first column cells are procedure names → anchored row indices
  4. Remaining column headers form the visit structure
  5. Feed this skeleton to the VLM prompt as a deterministic anchor
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import fitz

logger = logging.getLogger(__name__)


@dataclass
class AnchoredRow:
    """A deterministically identified table row."""
    row_index: int
    procedure_name: str
    y_position: float          # Y-coordinate on page (for ordering)
    page_number: int           # 1-indexed page number
    is_header: bool = False


@dataclass
class GridSkeleton:
    """Complete deterministic grid structure for a table."""
    table_id: str
    rows: list[AnchoredRow]
    column_headers: list[str] = field(default_factory=list)
    num_rows: int = 0
    num_cols: int = 0

    def to_prompt_anchor(self) -> str:
        """Format the skeleton as a VLM prompt anchor."""
        lines = []
        lines.append("TABLE STRUCTURE (deterministic — DO NOT change row indices):")
        lines.append(f"Total rows: {self.num_rows}, Total columns: {self.num_cols}")
        if self.column_headers:
            cols_display = [f"col {i}: {h}" for i, h in enumerate(self.column_headers)]
            lines.append(f"Columns: {'; '.join(cols_display)}")
        lines.append("")
        lines.append("ROW INDEX | PROCEDURE NAME")
        lines.append("-" * 60)
        for row in self.rows:
            if row.is_header:
                continue
            lines.append(f"  {row.row_index:>3}      | {row.procedure_name}")
        return "\n".join(lines)


class GridAnchor:
    """Extract deterministic grid structure from PDF table pages."""

    def extract_skeleton(
        self,
        pdf_bytes: bytes,
        table_pages: list[int],
        table_id: str = "",
    ) -> GridSkeleton:
        """
        Extract a grid skeleton from the specified table pages.

        Uses PyMuPDF's built-in table detection to find actual table
        boundaries, then extracts procedure names from the first column.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        all_rows: list[AnchoredRow] = []
        all_col_headers: list[str] = []
        global_row_index = 0

        for page_num in table_pages:
            if page_num < 1 or page_num > doc.page_count:
                continue

            page = doc[page_num - 1]

            # Use PyMuPDF's table finder to locate table boundaries
            tables = page.find_tables()

            if not tables.tables:
                # Fallback: use text-based extraction with heuristics
                rows_from_page = self._extract_from_text(page, page_num)
                for row in rows_from_page:
                    row.row_index = global_row_index
                    all_rows.append(row)
                    global_row_index += 1
                continue

            # Process each detected table on the page
            for table in tables.tables:
                extracted = table.extract()
                if not extracted or len(extracted) < 2:
                    continue

                # First row is typically the column header
                header_row = extracted[0]
                if not all_col_headers and header_row:
                    all_col_headers = [
                        str(cell or "").strip() for cell in header_row
                    ]

                # Remaining rows are data rows
                for row_data in extracted[1:]:
                    if not row_data:
                        continue

                    # First cell is the procedure name
                    proc_name = str(row_data[0] or "").strip()
                    if not proc_name:
                        continue

                    # Skip rows that are just page headers/footers
                    if self._is_noise(proc_name):
                        continue

                    # Get Y-position from the table cell bounding box
                    y_pos = table.bbox[1]  # Top of table as approximation

                    all_rows.append(AnchoredRow(
                        row_index=global_row_index,
                        procedure_name=proc_name,
                        y_position=y_pos,
                        page_number=page_num,
                    ))
                    global_row_index += 1

        doc.close()

        # Deduplicate rows from multi-page continuation
        all_rows = self._deduplicate_rows(all_rows)

        # Clean up column headers — remove empty and duplicate entries
        if all_col_headers:
            all_col_headers = [h for h in all_col_headers if h]

        skeleton = GridSkeleton(
            table_id=table_id,
            rows=all_rows,
            column_headers=all_col_headers,
            num_rows=len(all_rows),
            num_cols=len(all_col_headers) if all_col_headers else 0,
        )

        logger.info(
            f"Grid anchor for {table_id}: {skeleton.num_rows} rows, "
            f"{skeleton.num_cols} cols from {len(table_pages)} pages"
        )

        return skeleton

    def _extract_from_text(
        self, page: fitz.Page, page_num: int
    ) -> list[AnchoredRow]:
        """Fallback: extract procedure names from text when table detection fails."""
        rows = []
        page_width = page.rect.width
        proc_x_threshold = page_width * 0.35

        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                x = spans[0]["origin"][0]
                y = spans[0]["origin"][1]
                font_size = max(s["size"] for s in spans)

                # Only consider text in the procedure column region
                if x > proc_x_threshold:
                    continue
                # Skip small text (footnotes)
                if font_size < 8:
                    continue
                if not text or len(text) < 3:
                    continue
                if self._is_noise(text):
                    continue

                rows.append(AnchoredRow(
                    row_index=0,  # Will be reassigned
                    procedure_name=text,
                    y_position=y,
                    page_number=page_num,
                ))

        return rows

    def _is_noise(self, text: str) -> bool:
        """Check if text is a page header, footer, or non-table content."""
        text_lower = text.lower().strip()

        # Common page headers/footers
        noise_patterns = [
            r"^page \d+",
            r"^confidential",
            r"^protocol [a-z0-9]",
            r"^pf-\d+",
            r"^final protocol",
            r"^table \d+",
            r"^continued",
            r"^abbreviation",
            r"^note:",
            r"^source:",
            r"^\d+\.\d+",  # Section numbers like "1.3.2"
        ]
        for pattern in noise_patterns:
            if re.match(pattern, text_lower):
                return True

        # Very long text is likely body paragraphs, not procedure names
        if len(text) > 120:
            return True

        # Body text heuristics: sentences with multiple clauses
        # Procedure names don't usually have these patterns
        body_signals = [
            " if a ", " and the ", " will be ", " in order to ",
            " has been ", " required at ", " that covid", " whether ",
            " according to ", " prior to ", " sufficient ",
            " originally ", " determine ", " eligible ",
            " including mis-c", " between visit", " after each ",
            " the participant ", " the investigator ",
            " the requirement ", " the site ",
            "refer to the", "provide an overview",
            "section of the protocol", "compliance with",
            "all other participant", "remaining visits",
            "no later than", "not already been",
        ]
        for signal in body_signals:
            if signal in text_lower:
                return True

        # Lines ending with common sentence-continuation patterns
        if text_lower.endswith((".", ",")):
            # Short lines ending with period are OK (e.g. "protocol.")
            # but longer lines are likely body text
            if len(text) > 80:
                return True

        # Fragments that are clearly mid-sentence from body text
        if text_lower.startswith(("to protocol", "participant.", "those listed")):
            return True

        # Sentence fragments: starts with lowercase letter
        if text and text[0].islower() and len(text) > 30:
            return True

        return False

    def _deduplicate_rows(self, rows: list[AnchoredRow]) -> list[AnchoredRow]:
        """Remove duplicate rows from multi-page table continuations."""
        seen: dict[str, AnchoredRow] = {}
        result = []

        for row in rows:
            name_key = row.procedure_name.lower().strip()[:60]
            if name_key in seen:
                continue
            seen[name_key] = row
            result.append(row)

        # Re-index
        for i, row in enumerate(result):
            row.row_index = i

        return result
