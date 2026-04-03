"""
Formatting Extractor — extracts rich formatting metadata from PDF documents.

Produces a FormattedDocument with every span's position, font, size, color,
bold/italic/underline/superscript flags, and paragraph structure. This is
the "ground truth" for formatting fidelity checks.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import fitz

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FormattedSpan:
    """A single text span with full formatting metadata."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    font: str = ""
    size: float = 10.0
    color: int = 0          # RGB packed as integer
    bold: bool = False
    italic: bool = False
    underline: bool = False
    superscript: bool = False
    subscript: bool = False
    strikethrough: bool = False
    flags: int = 0
    formula: Any = None     # FormattedFormula if this span is a formula

    @property
    def color_rgb(self) -> tuple[int, int, int]:
        r = (self.color >> 16) & 0xFF
        g = (self.color >> 8) & 0xFF
        b = self.color & 0xFF
        return (r, g, b)

    @property
    def font_family(self) -> str:
        """Extract base font family from PDF font name."""
        name = self.font
        for suffix in ["-Bold", "-Italic", "-BoldItalic", "MT", "PS",
                       ",Bold", ",Italic", ",BoldItalic", "-Regular"]:
            name = name.replace(suffix, "")
        return name.strip()


@dataclass
class FormattedLine:
    """A line of text with spans preserving formatting."""
    spans: list[FormattedSpan] = field(default_factory=list)
    y_center: float = 0.0
    indent: float = 0.0

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass
class FormattedParagraph:
    """A paragraph with lines and formatting metadata."""
    lines: list[FormattedLine] = field(default_factory=list)
    style: str = "body"       # body, heading1-6, list_item, table_cell
    indent_level: int = 0
    alignment: str = "left"   # left, center, right, justify
    spacing_before: float = 0.0
    spacing_after: float = 0.0

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines)

    @property
    def is_bold(self) -> bool:
        spans = [s for line in self.lines for s in line.spans if s.text.strip()]
        return bool(spans) and all(s.bold for s in spans)

    @property
    def font_size(self) -> float:
        sizes = [s.size for line in self.lines for s in line.spans if s.text.strip()]
        return max(sizes) if sizes else 10.0


@dataclass
class FormattedTableCell:
    """A cell in a formatted table."""
    text: str = ""
    row: int = 0
    col: int = 0
    rowspan: int = 1
    colspan: int = 1
    bold: bool = False
    is_header: bool = False


@dataclass
class FormattedTable:
    """A table extracted from the document."""
    rows: list[list[FormattedTableCell]] = field(default_factory=list)
    num_rows: int = 0
    num_cols: int = 0
    y_position: float = 0.0  # Y coordinate on page for ordering with paragraphs

    @property
    def is_empty(self) -> bool:
        return self.num_rows == 0


@dataclass
class FormattedPage:
    """A page with paragraphs, tables, and layout info."""
    page_number: int
    width: float
    height: float
    paragraphs: list[FormattedParagraph] = field(default_factory=list)
    tables: list[FormattedTable] = field(default_factory=list)
    margin_left: float = 72.0
    margin_right: float = 72.0
    margin_top: float = 72.0
    margin_bottom: float = 72.0


@dataclass
class FormattedDocument:
    """Complete document with formatting metadata."""
    filename: str = ""
    pages: list[FormattedPage] = field(default_factory=list)
    font_inventory: dict[str, int] = field(default_factory=dict)  # font → count
    color_inventory: dict[str, int] = field(default_factory=dict)  # hex color → count
    style_inventory: dict[str, int] = field(default_factory=dict)  # style → count

    @property
    def total_spans(self) -> int:
        return sum(
            len(s.text)
            for page in self.pages
            for para in page.paragraphs
            for line in para.lines
            for s in line.spans
        )

    @property
    def total_paragraphs(self) -> int:
        return sum(len(p.paragraphs) for p in self.pages)


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class FormattingExtractor:
    """Extracts rich formatting metadata from PDF documents."""

    def extract(self, pdf_bytes: bytes, filename: str = "") -> FormattedDocument:
        """Extract formatting from a PDF document."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages: list[FormattedPage] = []
        font_counts: dict[str, int] = {}
        color_counts: dict[str, int] = {}

        for page_idx in range(doc.page_count):
            page = doc[page_idx]
            rect = page.rect
            fmt_page = FormattedPage(
                page_number=page_idx,
                width=rect.width,
                height=rect.height,
            )

            # Detect margins from text block positions
            blocks = page.get_text("dict")["blocks"]
            self._detect_margins(fmt_page, blocks)

            # Extract spans with formatting
            lines = self._extract_lines(blocks, font_counts, color_counts)

            # Group lines into paragraphs
            fmt_page.paragraphs = self._group_paragraphs(lines, fmt_page)

            # Extract tables
            fmt_page.tables = self._extract_tables(page)

            # Extract images
            self._extract_images(page, fmt_page)

            pages.append(fmt_page)

        doc.close()

        # Build style inventory
        style_counts: dict[str, int] = {}
        for p in pages:
            for para in p.paragraphs:
                style_counts[para.style] = style_counts.get(para.style, 0) + 1

        return FormattedDocument(
            filename=filename,
            pages=pages,
            font_inventory=font_counts,
            color_inventory=color_counts,
            style_inventory=style_counts,
        )

    def _detect_margins(self, page: FormattedPage, blocks: list[dict]) -> None:
        """Detect page margins from text block positions."""
        x_positions = []
        x_ends = []
        y_positions = []
        y_ends = []

        for b in blocks:
            if b.get("type") != 0:  # text blocks only
                continue
            bbox = b["bbox"]
            x_positions.append(bbox[0])
            x_ends.append(bbox[2])
            y_positions.append(bbox[1])
            y_ends.append(bbox[3])

        if x_positions:
            page.margin_left = min(x_positions)
            page.margin_right = page.width - max(x_ends)
        if y_positions:
            page.margin_top = min(y_positions)
            page.margin_bottom = page.height - max(y_ends)

    def _extract_lines(
        self, blocks: list[dict],
        font_counts: dict[str, int],
        color_counts: dict[str, int],
    ) -> list[FormattedLine]:
        """Extract formatted lines from PyMuPDF blocks."""
        lines: list[FormattedLine] = []

        for block in blocks:
            if block.get("type") != 0:
                continue

            for line_data in block.get("lines", []):
                fmt_line = FormattedLine()
                spans = line_data.get("spans", [])

                prev_span_end_x = None

                for i, span in enumerate(spans):
                    text = span.get("text", "")
                    if not text:
                        continue

                    flags = span.get("flags", 0)
                    font_name = span.get("font", "")
                    font_size = span.get("size", 10.0)
                    color = span.get("color", 0)

                    is_bold = bool(flags & 16) or "Bold" in font_name
                    is_italic = bool(flags & 2) or "Italic" in font_name
                    is_superscript = bool(flags & 1)
                    is_underline = bool(flags & 4)

                    # Subscript: small font, not flagged as superscript
                    is_subscript = False
                    if not is_superscript and font_size < 7.5:
                        is_subscript = True

                    bbox = span.get("bbox", span.get("origin", [0, 0, 0, 0]))
                    if len(bbox) == 2:
                        bbox = [bbox[0], bbox[1], bbox[0] + len(text) * font_size * 0.5, bbox[1] + font_size]

                    # Space injection for run-on words
                    if prev_span_end_x is not None and fmt_line.spans:
                        gap = bbox[0] - prev_span_end_x
                        char_width = font_size * 0.25
                        prev_text = fmt_line.spans[-1].text
                        if (gap > char_width
                                and prev_text and prev_text[-1].isalpha()
                                and text and text[0].isalpha()):
                            # Insert space to fix run-on word
                            fmt_line.spans[-1] = FormattedSpan(
                                text=prev_text + " ",
                                x0=fmt_line.spans[-1].x0,
                                y0=fmt_line.spans[-1].y0,
                                x1=fmt_line.spans[-1].x1,
                                y1=fmt_line.spans[-1].y1,
                                font=fmt_line.spans[-1].font,
                                size=fmt_line.spans[-1].size,
                                color=fmt_line.spans[-1].color,
                                bold=fmt_line.spans[-1].bold,
                                italic=fmt_line.spans[-1].italic,
                                underline=fmt_line.spans[-1].underline,
                                superscript=fmt_line.spans[-1].superscript,
                                subscript=fmt_line.spans[-1].subscript,
                                flags=fmt_line.spans[-1].flags,
                            )

                    prev_span_end_x = bbox[2]

                    fmt_span = FormattedSpan(
                        text=text,
                        x0=bbox[0], y0=bbox[1],
                        x1=bbox[2], y1=bbox[3],
                        font=font_name,
                        size=font_size,
                        color=color,
                        bold=is_bold,
                        italic=is_italic,
                        underline=is_underline,
                        superscript=is_superscript,
                        subscript=is_subscript,
                        flags=flags,
                    )
                    fmt_line.spans.append(fmt_span)

                    # Track inventories
                    base_font = fmt_span.font_family
                    font_counts[base_font] = font_counts.get(base_font, 0) + 1
                    hex_color = f"#{color:06X}"
                    color_counts[hex_color] = color_counts.get(hex_color, 0) + 1

                if fmt_line.spans:
                    fmt_line.y_center = sum(s.y0 for s in fmt_line.spans) / len(fmt_line.spans)
                    fmt_line.indent = fmt_line.spans[0].x0
                    lines.append(fmt_line)

        return lines

    def _group_paragraphs(
        self, lines: list[FormattedLine], page: FormattedPage,
    ) -> list[FormattedParagraph]:
        """Group lines into paragraphs based on Y-gap analysis."""
        if not lines:
            return []

        paragraphs: list[FormattedParagraph] = []
        current = FormattedParagraph(lines=[lines[0]])

        for i in range(1, len(lines)):
            prev_line = lines[i - 1]
            curr_line = lines[i]

            # Compute Y gap
            y_gap = curr_line.y_center - prev_line.y_center
            line_height = max(s.size for s in prev_line.spans) if prev_line.spans else 12.0

            # New paragraph if gap > 1.5x line height or significant indent change
            is_new_para = y_gap > line_height * 1.5

            if is_new_para:
                # Classify the completed paragraph
                self._classify_paragraph(current, page)
                paragraphs.append(current)
                current = FormattedParagraph(
                    lines=[curr_line],
                    spacing_before=y_gap,
                )
            else:
                current.lines.append(curr_line)

        # Don't forget the last paragraph
        if current.lines:
            self._classify_paragraph(current, page)
            paragraphs.append(current)

        return paragraphs

    def _classify_paragraph(self, para: FormattedParagraph, page: FormattedPage) -> None:
        """Classify paragraph style using multi-signal scoring.

        Heading detection uses a scoring model with signals:
        - Font size (larger = more likely heading)
        - Bold (strong signal)
        - Short text (headings are typically < 15 words)
        - Starts with section number (1., 1.1, etc.)
        - Followed by spacing gap (structural signal)
        - ALL CAPS (common heading convention)
        """
        if not para.lines or not para.lines[0].spans:
            return

        font_size = para.font_size
        is_bold = para.is_bold
        text = para.text.strip()
        word_count = len(text.split())

        # ── Heading scoring model ──────────────────────────────────
        heading_score = 0.0

        # Signal 1: Font size (larger = more likely heading)
        if font_size >= 16:
            heading_score += 3.0
        elif font_size >= 14:
            heading_score += 2.0
        elif font_size >= 12:
            heading_score += 1.0

        # Signal 2: Bold text
        if is_bold:
            heading_score += 2.0

        # Signal 3: Short text (< 15 words)
        if word_count <= 15:
            heading_score += 1.5
        elif word_count <= 8:
            heading_score += 2.0

        # Signal 4: Section numbering pattern
        section_match = re.match(r"^(\d+(?:\.\d+)*)[.)]?\s+", text)
        if section_match:
            heading_score += 2.5
            # Determine depth from numbering
            section_num = section_match.group(1)
            depth = section_num.count(".")
        else:
            depth = -1

        # Signal 5: ALL CAPS (common in legal/clinical docs)
        alpha_chars = [c for c in text if c.isalpha()]
        if alpha_chars and len(alpha_chars) > 3:
            upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if upper_ratio > 0.8:
                heading_score += 1.0

        # Signal 6: Large spacing before (structural gap)
        if para.spacing_before > 15:
            heading_score += 0.5

        # Classify based on score
        if heading_score >= 5.0:
            # Determine level from depth or font size
            if depth == 0 or font_size >= 16:
                para.style = "heading1"
            elif depth == 1 or font_size >= 14:
                para.style = "heading2"
            elif depth >= 2 or font_size >= 12:
                para.style = "heading3"
            else:
                para.style = "heading4"
        elif heading_score >= 3.5 and is_bold and word_count <= 15:
            para.style = "heading4"

        # ── List detection (overrides heading if matched) ──────────
        if re.match(r"^\s*[\u2022\u2023\u25CF\u25CB\u2013\u2014\u2015•●○–—\-]\s", text):
            para.style = "list_bullet"
        elif re.match(r"^\s*\d{1,3}[.)]\s", text) and not section_match:
            # Numbered list (but NOT section headings like "1. DEFINITIONS")
            para.style = "list_number"

        # Indent level
        if para.lines:
            indent = para.lines[0].indent - page.margin_left
            para.indent_level = max(0, int(indent / 18))  # 18pt per indent level

        # Alignment detection
        if para.lines:
            line_widths = [
                (l.spans[-1].x1 - l.spans[0].x0) if l.spans else 0
                for l in para.lines
            ]
            content_width = page.width - page.margin_left - page.margin_right
            if line_widths:
                avg_width = sum(line_widths) / len(line_widths)
                first_indent = para.lines[0].indent
                center_of_content = page.margin_left + content_width / 2
                center_of_para = first_indent + avg_width / 2

                if abs(center_of_para - center_of_content) < 20 and avg_width < content_width * 0.8:
                    para.alignment = "center"

    # Heuristic for detecting tabular content inside a single cell.
    # Matches lines that have 2+ columns separated by 2+ spaces or tab chars.
    _TABULAR_LINE_RE = re.compile(r"\S.*(?:\t|  {2,})\S")

    def _extract_tables(self, page: Any) -> list[FormattedTable]:
        """Extract tables from a PDF page using PyMuPDF's find_tables().

        Also detects cells that contain nested/sub-table content (multiple
        aligned columns of data).  PyMuPDF flattens nested tables, so the
        inner content is preserved as text with a ``[nested table]`` marker
        prepended to flag downstream consumers.
        """
        tables: list[FormattedTable] = []
        try:
            found = page.find_tables()
            if not found.tables:
                return []

            for tab in found.tables:
                extracted = tab.extract()
                if not extracted or len(extracted) < 1:
                    continue

                num_rows = len(extracted)
                num_cols = len(extracted[0]) if extracted[0] else 0

                fmt_rows: list[list[FormattedTableCell]] = []
                for r_idx, row in enumerate(extracted):
                    fmt_row: list[FormattedTableCell] = []
                    for c_idx, cell_val in enumerate(row):
                        text = str(cell_val).strip() if cell_val else ""
                        is_header = r_idx == 0
                        # Detect bold in header rows
                        is_bold = is_header

                        # --- Nested table detection -----------------------
                        # If the cell text looks like it contains structured
                        # tabular data (multiple lines with aligned columns),
                        # flag it so downstream consumers can handle it.
                        if text and self._cell_looks_tabular(text):
                            text = f"[nested table] {text}"
                            logger.debug(
                                "Nested table content detected in cell "
                                "(%d, %d): %s...",
                                r_idx, c_idx, text[:80],
                            )

                        fmt_row.append(FormattedTableCell(
                            text=text,
                            row=r_idx,
                            col=c_idx,
                            bold=is_bold,
                            is_header=is_header,
                        ))
                    fmt_rows.append(fmt_row)

                tables.append(FormattedTable(
                    rows=fmt_rows,
                    num_rows=num_rows,
                    num_cols=num_cols,
                    y_position=tab.bbox[1] if hasattr(tab, 'bbox') else 0.0,
                ))

        except Exception as e:
            logger.debug(f"Table extraction failed on page: {e}")

        return tables

    def _cell_looks_tabular(self, text: str) -> bool:
        """Return True if *text* contains content that looks like a nested table.

        Heuristic: the cell has 3+ lines and at least half of them contain
        two or more whitespace-separated columns (tab or 2+ consecutive
        spaces between non-whitespace segments).
        """
        lines = [ln for ln in text.split("\n") if ln.strip()]
        if len(lines) < 3:
            return False

        tabular_lines = sum(
            1 for ln in lines if self._TABULAR_LINE_RE.search(ln)
        )
        return tabular_lines >= len(lines) * 0.5

    def _extract_images(self, page: Any, fmt_page: FormattedPage) -> None:
        """Extract images from a PDF page and store metadata."""
        try:
            image_list = page.get_images(full=True)
            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                try:
                    base_image = page.parent.extract_image(xref)
                    if base_image and base_image.get("image"):
                        # Store as a paragraph with image marker
                        # (actual image embedding handled by renderer)
                        img_data = base_image["image"]
                        img_ext = base_image.get("ext", "png")
                        width = base_image.get("width", 0)
                        height = base_image.get("height", 0)

                        import base64
                        b64 = base64.b64encode(img_data).decode("ascii")
                        data_uri = f"data:image/{img_ext};base64,{b64}"

                        # Create a paragraph with the image data
                        img_para = FormattedParagraph(
                            style="image",
                            lines=[FormattedLine(spans=[FormattedSpan(
                                text=data_uri,
                                x0=0, y0=0, x1=float(width), y1=float(height),
                                font="", size=0,
                            )])],
                        )
                        fmt_page.paragraphs.append(img_para)
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Image extraction failed: {e}")
