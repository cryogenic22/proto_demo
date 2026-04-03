"""
JSON Renderer — converts FormattedDocument IR to structured JSON.

Produces a full serialisation of the IR including pages, paragraphs, spans,
tables, and metadata (font inventory, color inventory, style counts).
"""

from __future__ import annotations

import json

from src.formatter.extractor import (
    FormattedDocument,
    FormattedLine,
    FormattedPage,
    FormattedParagraph,
    FormattedSpan,
    FormattedTable,
    FormattedTableCell,
)


class JSONRenderer:
    """Renders a FormattedDocument to a structured JSON string."""

    def __init__(self, indent: int = 2, include_coordinates: bool = False):
        """Initialise the renderer.

        Args:
            indent: JSON indentation level (0 for compact).
            include_coordinates: Whether to include x0/y0/x1/y1 span coordinates.
        """
        self._indent = indent
        self._include_coords = include_coordinates

    def render(self, doc: FormattedDocument) -> str:
        """Render the full document as a JSON string.

        Args:
            doc: A FormattedDocument IR instance.

        Returns:
            A JSON string with full IR serialisation.
        """
        payload = self._serialise_document(doc)
        return json.dumps(payload, indent=self._indent if self._indent else None, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def _serialise_document(self, doc: FormattedDocument) -> dict:
        """Serialise a FormattedDocument to a dict."""
        return {
            "filename": doc.filename,
            "total_pages": len(doc.pages),
            "total_paragraphs": doc.total_paragraphs,
            "total_spans": doc.total_spans,
            "pages": [self._serialise_page(p) for p in doc.pages],
            "metadata": {
                "font_inventory": doc.font_inventory,
                "color_inventory": doc.color_inventory,
                "style_inventory": doc.style_inventory,
            },
        }

    def _serialise_page(self, page: FormattedPage) -> dict:
        """Serialise a FormattedPage."""
        return {
            "page_number": page.page_number,
            "width": page.width,
            "height": page.height,
            "margins": {
                "left": page.margin_left,
                "right": page.margin_right,
                "top": page.margin_top,
                "bottom": page.margin_bottom,
            },
            "paragraphs": [self._serialise_paragraph(p) for p in page.paragraphs],
            "tables": [self._serialise_table(t) for t in page.tables],
        }

    def _serialise_paragraph(self, para: FormattedParagraph) -> dict:
        """Serialise a FormattedParagraph."""
        result: dict = {
            "style": para.style,
            "text": para.text,
            "alignment": para.alignment,
            "indent_level": para.indent_level,
        }

        if para.spacing_before > 0:
            result["spacing_before"] = para.spacing_before
        if para.spacing_after > 0:
            result["spacing_after"] = para.spacing_after

        result["lines"] = [self._serialise_line(ln) for ln in para.lines]

        return result

    def _serialise_line(self, line: FormattedLine) -> dict:
        """Serialise a FormattedLine."""
        result: dict = {
            "text": line.text,
            "spans": [self._serialise_span(s) for s in line.spans],
        }
        if self._include_coords:
            result["y_center"] = line.y_center
            result["indent"] = line.indent
        return result

    def _serialise_span(self, span: FormattedSpan) -> dict:
        """Serialise a FormattedSpan."""
        result: dict = {
            "text": span.text,
            "font": span.font,
            "size": span.size,
            "color": f"#{span.color:06X}",
        }

        # Only include non-default formatting flags
        if span.bold:
            result["bold"] = True
        if span.italic:
            result["italic"] = True
        if span.underline:
            result["underline"] = True
        if span.superscript:
            result["superscript"] = True
        if span.subscript:
            result["subscript"] = True
        if span.strikethrough:
            result["strikethrough"] = True

        if self._include_coords:
            result["bbox"] = [span.x0, span.y0, span.x1, span.y1]

        # Include formula metadata if present
        if span.formula and hasattr(span.formula, 'latex'):
            result["formula"] = {
                "type": span.formula.formula_type.value if hasattr(span.formula.formula_type, 'value') else str(span.formula.formula_type),
                "latex": span.formula.latex or "",
                "html": span.formula.html or "",
                "complexity": span.formula.complexity.value if hasattr(span.formula.complexity, 'value') else str(span.formula.complexity),
                "source": span.formula.source.value if hasattr(span.formula.source, 'value') else str(span.formula.source),
            }

        return result

    def _serialise_table(self, table: FormattedTable) -> dict:
        """Serialise a FormattedTable."""
        return {
            "num_rows": table.num_rows,
            "num_cols": table.num_cols,
            "rows": [
                [self._serialise_cell(cell) for cell in row]
                for row in table.rows
            ],
        }

    @staticmethod
    def _serialise_cell(cell: FormattedTableCell) -> dict:
        """Serialise a FormattedTableCell."""
        result: dict = {
            "text": cell.text,
            "row": cell.row,
            "col": cell.col,
        }
        if cell.rowspan > 1:
            result["rowspan"] = cell.rowspan
        if cell.colspan > 1:
            result["colspan"] = cell.colspan
        if cell.bold:
            result["bold"] = True
        if cell.is_header:
            result["is_header"] = True
        return result
