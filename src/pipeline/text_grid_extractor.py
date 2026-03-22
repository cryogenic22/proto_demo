"""
Text Grid Extractor -- deterministic cell extraction from PDF text positions.

Fallback for text-layout tables where find_tables() returns nothing.
Uses PyMuPDF span (x,y) coordinates to reconstruct the table grid.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict

import fitz

from src.models.schema import CellDataType, ExtractedCell

logger = logging.getLogger(__name__)


def extract_cells_from_text_layout(
    pdf_bytes: bytes,
    pages: list[int],
    min_columns: int = 3,
) -> list[ExtractedCell]:
    """Extract table cells from text positions when find_tables() fails.

    Strategy:
    1. Extract all text spans with (x, y) coordinates
    2. Identify column positions from the row with the most items
    3. Identify X-mark columns vs text columns
    4. Map each span to its (row, col) position
    5. Classify cells by content type
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    all_spans: list[dict] = []
    for pg in pages:
        if pg >= doc.page_count:
            continue
        page = doc[pg]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    if not text:
                        continue
                    # Skip headers/footers
                    if any(kw in text for kw in
                           ["CONFIDENTIAL", "Protocol Number", "Page "]):
                        continue
                    all_spans.append({
                        "text": text,
                        "x": round(span["origin"][0], 1),
                        "y": round(span["origin"][1], 1),
                        "page": pg,
                        "bold": "Bold" in span.get("font", "")
                                or bool(span["flags"] & 16),
                        "size": span["size"],
                    })

    doc.close()

    if len(all_spans) < 10:
        return []

    # Step 1: Cluster Y-coordinates into rows (within 4pt = same row)
    all_spans.sort(key=lambda s: (s["page"], s["y"], s["x"]))
    rows: list[list[dict]] = []
    current_row = [all_spans[0]]
    current_y = all_spans[0]["y"]
    current_page = all_spans[0]["page"]

    for s in all_spans[1:]:
        if s["page"] != current_page or abs(s["y"] - current_y) > 4:
            if current_row:
                rows.append(current_row)
            current_row = [s]
            current_y = s["y"]
            current_page = s["page"]
        else:
            current_row.append(s)
    if current_row:
        rows.append(current_row)

    # Step 2: Find column positions from the widest row
    best_row = max(rows, key=lambda r: len(set(round(s["x"]) for s in r)))
    col_positions = sorted(set(round(s["x"]) for s in best_row))

    if len(col_positions) < min_columns:
        return []  # Not a table

    # Step 3: Map each row's spans to column positions
    def find_col(x: float) -> int:
        best_col = 0
        best_dist = abs(x - col_positions[0])
        for i, cx in enumerate(col_positions):
            dist = abs(x - cx)
            if dist < best_dist:
                best_dist = dist
                best_col = i
        return best_col if best_dist < 30 else -1  # 30pt tolerance

    cells: list[ExtractedCell] = []
    for row_idx, row_spans in enumerate(rows):
        row_texts: dict[int, str] = defaultdict(str)
        for s in row_spans:
            col = find_col(s["x"])
            if col >= 0:
                row_texts[col] = (row_texts[col] + " " + s["text"]).strip()

        row_header = row_texts.get(0, "")

        for col_idx in range(len(col_positions)):
            value = row_texts.get(col_idx, "")

            # Classify
            if not value:
                data_type = CellDataType.EMPTY
            elif value.strip() in ("X", "x", "\u2713", "\u2714", "\u2611"):
                data_type = CellDataType.MARKER
            elif re.match(r'^[\d.]+$', value.strip()):
                data_type = CellDataType.NUMERIC
            else:
                data_type = CellDataType.TEXT

            cells.append(ExtractedCell(
                row=row_idx,
                col=col_idx,
                raw_value=value,
                data_type=data_type,
                row_header=row_header,
                col_header="",  # Would need header row detection
                confidence=0.85,  # Lower confidence than VLM
            ))

    logger.info(
        f"Text-grid extraction: {len(cells)} cells from {len(rows)} rows "
        f"x {len(col_positions)} cols across {len(pages)} pages"
    )
    return cells
