"""
FormattedDocument IR Schema — detector + parser for JSONRenderer round-trip.

Detects JSON matching the JSONRenderer output format (filename, pages, metadata)
and deserialises it back into a FormattedDocument. This enables round-tripping:
doc → JSONRenderer → JSON string → FormattedDocIRParser → doc.
"""

from __future__ import annotations

from src.formatter.extractor import (
    FormattedDocument,
    FormattedLine,
    FormattedPage,
    FormattedParagraph,
    FormattedSpan,
    FormattedTable,
    FormattedTableCell,
)
from src.formatter.ingest.json_ingestor import JsonSchemaDetector, JsonSchemaParser

_SCHEMA_ID = "formatted_doc_ir"


class FormattedDocIRDetector(JsonSchemaDetector):
    """Detects JSONRenderer output by checking for pages + total_pages + filename."""

    def schema_id(self) -> str:
        return _SCHEMA_ID

    def detect(self, data: dict) -> bool:
        return (
            "pages" in data
            and "total_pages" in data
            and isinstance(data.get("pages"), list)
        )

    def priority(self) -> int:
        return 15  # After USDM (10), before Protocol IR (20)


class FormattedDocIRParser(JsonSchemaParser):
    """Deserialises JSONRenderer output back into a FormattedDocument."""

    def schema_id(self) -> str:
        return _SCHEMA_ID

    def to_formatted_document(self, data: dict, filename: str = "") -> FormattedDocument:
        pages = [self._parse_page(p) for p in data.get("pages", [])]

        meta = data.get("metadata", {})
        return FormattedDocument(
            filename=filename or data.get("filename", ""),
            pages=pages,
            font_inventory=meta.get("font_inventory", {}),
            color_inventory=meta.get("color_inventory", {}),
            style_inventory=meta.get("style_inventory", {}),
        )

    # -- Deserialisers --

    def _parse_page(self, p: dict) -> FormattedPage:
        margins = p.get("margins", {})
        return FormattedPage(
            page_number=p.get("page_number", 0),
            width=p.get("width", 612.0),
            height=p.get("height", 792.0),
            paragraphs=[self._parse_paragraph(pr) for pr in p.get("paragraphs", [])],
            tables=[self._parse_table(t) for t in p.get("tables", [])],
            margin_left=margins.get("left", 72.0),
            margin_right=margins.get("right", 72.0),
            margin_top=margins.get("top", 72.0),
            margin_bottom=margins.get("bottom", 72.0),
        )

    def _parse_paragraph(self, pr: dict) -> FormattedParagraph:
        return FormattedParagraph(
            lines=[self._parse_line(ln) for ln in pr.get("lines", [])],
            style=pr.get("style", "body"),
            indent_level=pr.get("indent_level", 0),
            alignment=pr.get("alignment", "left"),
            spacing_before=pr.get("spacing_before", 0.0),
            spacing_after=pr.get("spacing_after", 0.0),
        )

    def _parse_line(self, ln: dict) -> FormattedLine:
        return FormattedLine(
            spans=[self._parse_span(s) for s in ln.get("spans", [])],
            y_center=ln.get("y_center", 0.0),
            indent=ln.get("indent", 0.0),
        )

    @staticmethod
    def _parse_span(s: dict) -> FormattedSpan:
        # Parse color from hex string
        color_str = s.get("color", "#000000")
        if isinstance(color_str, str) and color_str.startswith("#"):
            color = int(color_str[1:], 16)
        elif isinstance(color_str, int):
            color = color_str
        else:
            color = 0

        # Parse bbox if present
        bbox = s.get("bbox", [0, 0, 0, 0])
        x0, y0, x1, y1 = (bbox + [0, 0, 0, 0])[:4]

        return FormattedSpan(
            text=s.get("text", ""),
            x0=x0, y0=y0, x1=x1, y1=y1,
            font=s.get("font", ""),
            size=s.get("size", 10.0),
            color=color,
            bold=s.get("bold", False),
            italic=s.get("italic", False),
            underline=s.get("underline", False),
            superscript=s.get("superscript", False),
            subscript=s.get("subscript", False),
            strikethrough=s.get("strikethrough", False),
        )

    @staticmethod
    def _parse_table(t: dict) -> FormattedTable:
        rows = []
        for row_data in t.get("rows", []):
            row = [
                FormattedTableCell(
                    text=c.get("text", ""),
                    row=c.get("row", 0),
                    col=c.get("col", 0),
                    rowspan=c.get("rowspan", 1),
                    colspan=c.get("colspan", 1),
                    bold=c.get("bold", False),
                    is_header=c.get("is_header", False),
                )
                for c in row_data
            ]
            rows.append(row)
        return FormattedTable(
            rows=rows,
            num_rows=t.get("num_rows", len(rows)),
            num_cols=t.get("num_cols", len(rows[0]) if rows else 0),
        )


# Module-level singletons for registry
DETECTOR = FormattedDocIRDetector()
PARSER = FormattedDocIRParser()
