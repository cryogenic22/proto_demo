"""
Protocol IR Schema — detector + parser for ProtoExtract Protocol JSON.

Detects JSON matching the Protocol Pydantic model (protocol_id, metadata,
sections, tables, procedures) and converts it to a FormattedDocument for
the formatter pipeline.
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

_SCHEMA_ID = "protocol_ir"


class ProtocolIRDetector(JsonSchemaDetector):
    """Detects Protocol JSON by checking for protocol_id + sections/tables."""

    def schema_id(self) -> str:
        return _SCHEMA_ID

    def detect(self, data: dict) -> bool:
        return (
            "protocol_id" in data
            and isinstance(data.get("metadata"), dict)
            and ("sections" in data or "tables" in data)
        )

    def priority(self) -> int:
        return 20  # After USDM (10), before fallbacks


class ProtocolIRParser(JsonSchemaParser):
    """Converts Protocol JSON to a FormattedDocument.

    Maps:
    - metadata → title page (heading + key-value pairs)
    - sections → heading paragraphs with content
    - tables → FormattedTable objects
    """

    def schema_id(self) -> str:
        return _SCHEMA_ID

    def to_formatted_document(self, data: dict, filename: str = "") -> FormattedDocument:
        pages: list[FormattedPage] = []
        paragraphs: list[FormattedParagraph] = []
        tables: list[FormattedTable] = []
        font_inv: dict[str, int] = {}
        style_inv: dict[str, int] = {}

        # -- Title page from metadata --
        meta = data.get("metadata", {})
        title = meta.get("title", data.get("document_name", "Untitled Protocol"))
        paragraphs.append(self._make_paragraph(title, "heading1", bold=True, size=18.0))
        style_inv["heading1"] = style_inv.get("heading1", 0) + 1

        # Key metadata fields as body text
        for key in ("sponsor", "phase", "therapeutic_area", "indication",
                     "protocol_number", "nct_number", "study_type"):
            val = meta.get(key, "")
            if val:
                paragraphs.append(self._make_paragraph(
                    f"{key.replace('_', ' ').title()}: {val}", "body", size=11.0
                ))
                style_inv["body"] = style_inv.get("body", 0) + 1

        # Arms
        for arm in meta.get("arms", []):
            paragraphs.append(self._make_paragraph(f"  - {arm}", "list_bullet", size=11.0))
            style_inv["list_bullet"] = style_inv.get("list_bullet", 0) + 1

        pages.append(FormattedPage(
            page_number=0, width=612.0, height=792.0, paragraphs=paragraphs,
        ))

        # -- Sections as pages --
        for section in data.get("sections", []):
            page_paras, page_tables = self._render_section(section, style_inv)
            if page_paras or page_tables:
                pages.append(FormattedPage(
                    page_number=len(pages), width=612.0, height=792.0,
                    paragraphs=page_paras, tables=page_tables,
                ))

        # -- Tables (SoA etc.) as separate pages --
        for tbl_data in data.get("tables", []):
            ft = self._render_table(tbl_data)
            if ft:
                pages.append(FormattedPage(
                    page_number=len(pages), width=612.0, height=792.0,
                    paragraphs=[self._make_paragraph(
                        tbl_data.get("title", "Table"), "heading2", bold=True, size=14.0
                    )],
                    tables=[ft],
                ))
                style_inv["heading2"] = style_inv.get("heading2", 0) + 1

        font_inv["Arial"] = sum(
            sum(len(s.text) for ln in p.lines for s in ln.spans)
            for pg in pages for p in pg.paragraphs
        )

        return FormattedDocument(
            filename=filename or data.get("document_name", ""),
            pages=pages,
            font_inventory=font_inv,
            color_inventory={"#000000": 1},
            style_inventory=style_inv,
        )

    def to_protocol(self, data: dict, filename: str = ""):
        """Protocol IR data is already a Protocol — validate and return."""
        from src.models.protocol import Protocol
        return Protocol.model_validate(data)

    # -- Helpers --

    def _render_section(
        self, section: dict, style_inv: dict
    ) -> tuple[list[FormattedParagraph], list[FormattedTable]]:
        paras: list[FormattedParagraph] = []
        tables: list[FormattedTable] = []
        level = min(section.get("level", 1), 6)
        style = f"heading{level}"

        number = section.get("number", "")
        title = section.get("title", "")
        heading_text = f"{number} {title}".strip()
        paras.append(self._make_paragraph(heading_text, style, bold=True,
                                           size=max(16.0 - level * 1.5, 10.0)))
        style_inv[style] = style_inv.get(style, 0) + 1

        content = section.get("content_html", "")
        if content:
            # Strip HTML tags for plain text rendering
            import re
            plain = re.sub(r"<[^>]+>", "", content).strip()
            if plain:
                paras.append(self._make_paragraph(plain, "body", size=11.0))
                style_inv["body"] = style_inv.get("body", 0) + 1

        for child in section.get("children", []):
            child_paras, child_tables = self._render_section(child, style_inv)
            paras.extend(child_paras)
            tables.extend(child_tables)

        return paras, tables

    def _render_table(self, tbl: dict) -> FormattedTable | None:
        cells = tbl.get("cells", [])
        if not cells:
            return None
        max_row = max(c.get("row", 0) for c in cells) + 1
        max_col = max(c.get("col", 0) for c in cells) + 1

        grid: list[list[FormattedTableCell]] = [
            [FormattedTableCell(text="", row=r, col=c) for c in range(max_col)]
            for r in range(max_row)
        ]
        for cell in cells:
            r, c = cell.get("row", 0), cell.get("col", 0)
            if 0 <= r < max_row and 0 <= c < max_col:
                grid[r][c] = FormattedTableCell(
                    text=cell.get("raw_value", cell.get("text", "")),
                    row=r, col=c,
                    is_header=(r == 0),
                    bold=(r == 0),
                )
        return FormattedTable(rows=grid, num_rows=max_row, num_cols=max_col)

    @staticmethod
    def _make_paragraph(
        text: str, style: str, bold: bool = False, size: float = 11.0
    ) -> FormattedParagraph:
        span = FormattedSpan(
            text=text, x0=0, y0=0, x1=0, y1=0,
            font="Arial", size=size, color=0, bold=bold,
        )
        line = FormattedLine(spans=[span], y_center=0.0, indent=0.0)
        return FormattedParagraph(lines=[line], style=style)


# Module-level singletons for registry
DETECTOR = ProtocolIRDetector()
PARSER = ProtocolIRParser()
