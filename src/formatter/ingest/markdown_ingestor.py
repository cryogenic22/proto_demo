"""
Markdown Ingestor — converts a Markdown string to FormattedDocument IR.

Uses regex-based parsing (no external dependency). Handles headings, bold,
italic, code, bullet lists, numbered lists, tables, images, blockquotes,
and horizontal rules.
"""

from __future__ import annotations

import re

from src.formatter.extractor import (
    FormattedDocument,
    FormattedLine,
    FormattedPage,
    FormattedParagraph,
    FormattedSpan,
    FormattedTable,
    FormattedTableCell,
)

_PAGE_WIDTH = 612.0
_PAGE_HEIGHT = 792.0
_DEFAULT_FONT = "Arial"
_DEFAULT_SIZE = 11.0

# Heading sizes (points) by level 1-6
_HEADING_SIZES = {1: 24.0, 2: 20.0, 3: 16.0, 4: 14.0, 5: 12.0, 6: 11.0}


class MarkdownIngestor:
    """Converts a Markdown string into a FormattedDocument IR.

    Usage::

        ingestor = MarkdownIngestor()
        doc = ingestor.ingest("# Title\\n\\nSome **bold** text.")
    """

    def ingest(self, content: str, filename: str = "") -> FormattedDocument:
        """Parse Markdown content and return a FormattedDocument.

        Args:
            content: The Markdown string to parse.
            filename: Optional source filename for metadata.

        Returns:
            A FormattedDocument with a single page of parsed elements.
        """
        if not content or not content.strip():
            return self._empty_doc(filename)

        content = content.replace("\r\n", "\n").replace("\r", "\n")

        paragraphs: list[FormattedParagraph] = []
        tables: list[FormattedTable] = []

        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            # Blank line — skip
            if not line.strip():
                i += 1
                continue

            # Horizontal rule
            if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
                paragraphs.append(FormattedParagraph(
                    lines=[FormattedLine(spans=[FormattedSpan(
                        text="---", x0=0, y0=0, x1=0, y1=0,
                        font=_DEFAULT_FONT, size=_DEFAULT_SIZE,
                    )])],
                    style="page_break",
                ))
                i += 1
                continue

            # Heading (ATX style: # Heading)
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2).strip()
                spans = self._parse_inline(text)
                # Mark all spans as bold for headings
                for s in spans:
                    s.bold = True
                    s.size = _HEADING_SIZES.get(level, _DEFAULT_SIZE)
                paragraphs.append(FormattedParagraph(
                    lines=[FormattedLine(spans=spans)],
                    style=f"heading{level}",
                ))
                i += 1
                continue

            # Table — sequence of lines with | delimiters
            if "|" in line and i + 1 < len(lines):
                table_lines: list[str] = []
                j = i
                while j < len(lines) and "|" in lines[j]:
                    table_lines.append(lines[j])
                    j += 1
                if len(table_lines) >= 2:
                    table = self._parse_table(table_lines)
                    if table:
                        tables.append(table)
                        i = j
                        continue

            # Blockquote
            bq_match = re.match(r"^>\s?(.*)", line)
            if bq_match:
                text = bq_match.group(1)
                spans = self._parse_inline(text)
                paragraphs.append(FormattedParagraph(
                    lines=[FormattedLine(spans=spans)],
                    style="body",
                    indent_level=1,
                ))
                i += 1
                continue

            # Unordered list
            ul_match = re.match(r"^(\s*)[*\-+]\s+(.+)$", line)
            if ul_match:
                indent = len(ul_match.group(1)) // 2
                text = ul_match.group(2)
                spans = self._parse_inline(text)
                paragraphs.append(FormattedParagraph(
                    lines=[FormattedLine(spans=spans)],
                    style="list_bullet",
                    indent_level=indent,
                ))
                i += 1
                continue

            # Ordered list
            ol_match = re.match(r"^(\s*)\d+[.)]\s+(.+)$", line)
            if ol_match:
                indent = len(ol_match.group(1)) // 2
                text = ol_match.group(2)
                spans = self._parse_inline(text)
                paragraphs.append(FormattedParagraph(
                    lines=[FormattedLine(spans=spans)],
                    style="list_number",
                    indent_level=indent,
                ))
                i += 1
                continue

            # Image (standalone line)
            img_match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", line)
            if img_match:
                alt_text = img_match.group(1)
                src = img_match.group(2)
                paragraphs.append(FormattedParagraph(
                    style="image",
                    lines=[FormattedLine(spans=[FormattedSpan(
                        text=src, x0=0, y0=0, x1=0, y1=0,
                        font="", size=0,
                    )])],
                ))
                i += 1
                continue

            # Regular paragraph — collect contiguous non-blank, non-special lines
            para_lines: list[str] = []
            while i < len(lines) and lines[i].strip():
                # Stop if the next line is a heading, list, table, blockquote, etc.
                next_line = lines[i]
                if (re.match(r"^#{1,6}\s+", next_line)
                        or re.match(r"^\s*[*\-+]\s+", next_line)
                        or re.match(r"^\s*\d+[.)]\s+", next_line)
                        or re.match(r"^>\s?", next_line)
                        or re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", next_line)
                        or re.match(r"^!\[", next_line)):
                    if para_lines:  # flush what we have
                        break
                    else:
                        break  # let the main loop handle it
                para_lines.append(next_line)
                i += 1

            if para_lines:
                full_text = " ".join(para_lines)
                spans = self._parse_inline(full_text)
                paragraphs.append(FormattedParagraph(
                    lines=[FormattedLine(spans=spans)],
                    style="body",
                ))
                continue

            # Fallback: advance to avoid infinite loop
            i += 1

        page = FormattedPage(
            page_number=0,
            width=_PAGE_WIDTH,
            height=_PAGE_HEIGHT,
            paragraphs=paragraphs,
            tables=tables,
        )

        # Build inventories
        font_inv, color_inv, style_inv = self._build_inventories(paragraphs)

        return FormattedDocument(
            filename=filename,
            pages=[page],
            font_inventory=font_inv,
            color_inventory=color_inv,
            style_inventory=style_inv,
        )

    # ------------------------------------------------------------------
    # Inline parsing
    # ------------------------------------------------------------------

    def _parse_inline(self, text: str) -> list[FormattedSpan]:
        """Parse inline Markdown formatting and return a list of FormattedSpans.

        Handles: **bold**, *italic*, ***bold+italic***, `code`,
        ~~strikethrough~~, and ![alt](url) images inline.
        """
        if not text:
            return [self._plain_span("")]

        spans: list[FormattedSpan] = []
        # Regex to find inline patterns
        # Order matters: bold+italic first, then bold, then italic, then code, then strikethrough
        pattern = re.compile(
            r"(\*\*\*(.+?)\*\*\*)"       # ***bold italic***
            r"|(\*\*(.+?)\*\*)"           # **bold**
            r"|(__(.+?)__)"               # __bold__
            r"|(\*(.+?)\*)"              # *italic*
            r"|(_(.+?)_)"               # _italic_
            r"|(`(.+?)`)"               # `code`
            r"|(~~(.+?)~~)"             # ~~strikethrough~~
            r"|(\!\[([^\]]*)\]\(([^)]+)\))"  # ![alt](url)
        )

        last_end = 0
        for m in pattern.finditer(text):
            # Add any text before this match as a plain span
            if m.start() > last_end:
                plain = text[last_end:m.start()]
                if plain:
                    spans.append(self._plain_span(plain))

            if m.group(2) is not None:
                # ***bold italic***
                spans.append(self._styled_span(m.group(2), bold=True, italic=True))
            elif m.group(4) is not None:
                # **bold**
                spans.append(self._styled_span(m.group(4), bold=True))
            elif m.group(6) is not None:
                # __bold__
                spans.append(self._styled_span(m.group(6), bold=True))
            elif m.group(8) is not None:
                # *italic*
                spans.append(self._styled_span(m.group(8), italic=True))
            elif m.group(10) is not None:
                # _italic_
                spans.append(self._styled_span(m.group(10), italic=True))
            elif m.group(12) is not None:
                # `code`
                spans.append(self._styled_span(m.group(12), font="Courier New"))
            elif m.group(14) is not None:
                # ~~strikethrough~~ (store as plain — IR has strikethrough field)
                s = self._plain_span(m.group(14))
                s.strikethrough = True
                spans.append(s)
            elif m.group(16) is not None:
                # ![alt](url) — inline image, emit as plain text placeholder
                alt = m.group(17)
                spans.append(self._plain_span(f"[{alt}]" if alt else "[Image]"))

            last_end = m.end()

        # Remaining text after the last match
        if last_end < len(text):
            remaining = text[last_end:]
            if remaining:
                spans.append(self._plain_span(remaining))

        if not spans:
            spans.append(self._plain_span(text))

        return spans

    # ------------------------------------------------------------------
    # Table parsing
    # ------------------------------------------------------------------

    def _parse_table(self, lines: list[str]) -> FormattedTable | None:
        """Parse a Markdown table from a list of lines.

        Expected format:
            | Header 1 | Header 2 |
            |----------|----------|
            | Cell 1   | Cell 2   |
        """
        if len(lines) < 2:
            return None

        # Filter out separator rows (|---|---|)
        data_rows: list[list[str]] = []
        for line in lines:
            stripped = line.strip()
            # Skip separator lines
            if re.match(r"^\|?[\s\-:|]+\|?$", stripped):
                continue
            # Parse cells
            cells = self._split_table_row(stripped)
            if cells:
                data_rows.append(cells)

        if not data_rows:
            return None

        num_rows = len(data_rows)
        num_cols = max(len(r) for r in data_rows)

        fmt_rows: list[list[FormattedTableCell]] = []
        for r_idx, row in enumerate(data_rows):
            fmt_row: list[FormattedTableCell] = []
            for c_idx in range(num_cols):
                text = row[c_idx].strip() if c_idx < len(row) else ""
                is_header = r_idx == 0
                fmt_row.append(FormattedTableCell(
                    text=text,
                    row=r_idx,
                    col=c_idx,
                    bold=is_header,
                    is_header=is_header,
                ))
            fmt_rows.append(fmt_row)

        return FormattedTable(
            rows=fmt_rows,
            num_rows=num_rows,
            num_cols=num_cols,
        )

    @staticmethod
    def _split_table_row(line: str) -> list[str]:
        """Split a Markdown table row into cells."""
        # Remove leading/trailing pipes
        stripped = line.strip()
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|"):
            stripped = stripped[:-1]
        if not stripped:
            return []
        return [cell.strip() for cell in stripped.split("|")]

    # ------------------------------------------------------------------
    # Span helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _plain_span(text: str) -> FormattedSpan:
        return FormattedSpan(
            text=text,
            x0=0, y0=0, x1=0, y1=0,
            font=_DEFAULT_FONT,
            size=_DEFAULT_SIZE,
        )

    @staticmethod
    def _styled_span(
        text: str,
        bold: bool = False,
        italic: bool = False,
        font: str = _DEFAULT_FONT,
    ) -> FormattedSpan:
        return FormattedSpan(
            text=text,
            x0=0, y0=0, x1=0, y1=0,
            font=font,
            size=_DEFAULT_SIZE,
            bold=bold,
            italic=italic,
        )

    # ------------------------------------------------------------------
    # Inventories
    # ------------------------------------------------------------------

    @staticmethod
    def _build_inventories(
        paragraphs: list[FormattedParagraph],
    ) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
        font_inv: dict[str, int] = {}
        color_inv: dict[str, int] = {}
        style_inv: dict[str, int] = {}
        for para in paragraphs:
            style_inv[para.style] = style_inv.get(para.style, 0) + 1
            for line in para.lines:
                for span in line.spans:
                    f = span.font or _DEFAULT_FONT
                    font_inv[f] = font_inv.get(f, 0) + 1
                    hex_c = f"#{span.color:06X}"
                    color_inv[hex_c] = color_inv.get(hex_c, 0) + 1
        return font_inv, color_inv, style_inv

    @staticmethod
    def _empty_doc(filename: str) -> FormattedDocument:
        return FormattedDocument(
            filename=filename,
            pages=[FormattedPage(
                page_number=0,
                width=_PAGE_WIDTH,
                height=_PAGE_HEIGHT,
            )],
        )
