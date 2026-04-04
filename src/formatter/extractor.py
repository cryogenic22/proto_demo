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

        # Collect table bounding boxes per page for deduplication (Issue 3)
        page_table_bboxes: dict[int, list[tuple[float, float, float, float]]] = {}

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

            # Extract tables first so we know their bounding boxes
            table_bboxes: list[tuple[float, float, float, float]] = []
            fmt_page.tables = self._extract_tables(page, _out_bboxes=table_bboxes)
            page_table_bboxes[page_idx] = table_bboxes

            # Extract spans with formatting
            lines = self._extract_lines(blocks, font_counts, color_counts)

            # Filter out lines that overlap with table bounding boxes (Issue 3)
            if table_bboxes:
                lines = self._filter_table_overlapping_lines(lines, table_bboxes)

            # Group lines into paragraphs
            fmt_page.paragraphs = self._group_paragraphs(lines, fmt_page)

            # Extract images
            self._extract_images(page, fmt_page)

            pages.append(fmt_page)

        doc.close()

        # Detect and mark headers/footers (Issue 4)
        self._mark_headers_footers(pages)

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
        """Extract formatted lines from PyMuPDF blocks.

        Subscript detection uses a two-pass approach:
        1. First pass: collect all spans for a line, compute dominant font size
        2. Second pass: mark subscript only if span is < 80% of dominant size
           AND positioned below the line's baseline (higher y1 value)
        """
        lines: list[FormattedLine] = []

        for block in blocks:
            if block.get("type") != 0:
                continue

            for line_data in block.get("lines", []):
                raw_spans = line_data.get("spans", [])
                if not raw_spans:
                    continue

                # --- First pass: collect span data + compute line metrics ---
                span_entries: list[dict] = []
                for span in raw_spans:
                    text = span.get("text", "")
                    if not text:
                        continue
                    span_entries.append(span)

                if not span_entries:
                    continue

                # Dominant font size = the most common (mode) size on this line,
                # weighted by text length.  Falls back to max size.
                size_weight: dict[float, int] = {}
                for sp in span_entries:
                    sz = round(sp.get("size", 10.0), 1)
                    size_weight[sz] = size_weight.get(sz, 0) + len(sp.get("text", ""))
                dominant_size = max(size_weight, key=size_weight.get)  # type: ignore[arg-type]

                # Baseline: the maximum y1 (bottom) among spans at the dominant size
                dominant_y1_values = [
                    sp.get("bbox", sp.get("origin", [0, 0, 0, 0]))[3]
                    for sp in span_entries
                    if len(sp.get("bbox", sp.get("origin", [0, 0, 0, 0]))) >= 4
                    and abs(sp.get("size", 10.0) - dominant_size) < 0.5
                ]
                line_baseline = max(dominant_y1_values) if dominant_y1_values else 0

                # --- Second pass: build FormattedLine with corrected subscript ---
                fmt_line = FormattedLine()
                prev_span_end_x = None

                for span in span_entries:
                    text = span.get("text", "")
                    flags = span.get("flags", 0)
                    font_name = span.get("font", "")
                    font_size = span.get("size", 10.0)
                    color = span.get("color", 0)

                    is_bold = bool(flags & 16) or "Bold" in font_name
                    is_italic = bool(flags & 2) or "Italic" in font_name
                    is_superscript = bool(flags & 1)
                    is_underline = bool(flags & 4)

                    bbox = span.get("bbox", span.get("origin", [0, 0, 0, 0]))
                    if len(bbox) == 2:
                        bbox = [bbox[0], bbox[1], bbox[0] + len(text) * font_size * 0.5, bbox[1] + font_size]

                    # Subscript detection (improved):
                    # A span is subscript only if:
                    #  1. NOT already flagged as superscript
                    #  2. Significantly smaller than the dominant size (< 80%)
                    #  3. Positioned below the line baseline (y1 extends lower)
                    #     OR its top (y0) is below the midpoint of dominant spans
                    # This prevents header/footer text (uniformly small) from
                    # being falsely marked as subscript.
                    is_subscript = False
                    if (not is_superscript
                            and font_size <= dominant_size * 0.82
                            and dominant_size > 0):
                        # Check vertical position: subscript sits lower
                        span_y1 = bbox[3] if len(bbox) >= 4 else 0
                        span_y0 = bbox[1] if len(bbox) >= 2 else 0
                        # Subscript baseline extends beyond the dominant baseline,
                        # or its top is near/below the dominant baseline
                        if line_baseline > 0:
                            baseline_offset = span_y1 - line_baseline
                            top_below_baseline = span_y0 >= line_baseline - (dominant_size * 0.2)
                            if baseline_offset > -0.5 or top_below_baseline:
                                is_subscript = True

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
        """Group lines into paragraphs based on Y-gap, x-position, and formatting.

        Two consecutive lines are joined into one paragraph when:
        - Y-gap is small (< 1.5x font size) — they're visually close
        - X-positions are similar (within margin tolerance) — same column
        - Neither line looks like a heading (short bold text)
        - They share similar font size (within 1pt)
        """
        if not lines:
            return []

        paragraphs: list[FormattedParagraph] = []
        current = FormattedParagraph(lines=[lines[0]])

        for i in range(1, len(lines)):
            prev_line = lines[i - 1]
            curr_line = lines[i]

            # Compute Y gap
            y_gap = curr_line.y_center - prev_line.y_center
            prev_size = max(s.size for s in prev_line.spans) if prev_line.spans else 12.0
            curr_size = max(s.size for s in curr_line.spans) if curr_line.spans else 12.0

            # --- Signals for paragraph break ---

            # 1. Large vertical gap
            gap_break = y_gap > prev_size * 1.5

            # 2. Significant indent change (new indented block or de-indent)
            indent_tolerance = 18.0  # ~0.25 inch
            indent_diff = abs(curr_line.indent - prev_line.indent)
            # A first-line indent (small rightward shift) is normal continuation
            first_line_indent = (
                curr_line.indent > prev_line.indent
                and indent_diff < 36.0  # < 0.5 inch is first-line indent
                and indent_diff > indent_tolerance
            )
            major_indent_change = indent_diff > indent_tolerance and not first_line_indent

            # 3. Font size mismatch — different visual hierarchy
            size_mismatch = abs(prev_size - curr_size) > 1.0

            # 4. Both lines are short + bold → likely separate headings
            prev_bold = all(s.bold for s in prev_line.spans if s.text.strip())
            curr_bold = all(s.bold for s in curr_line.spans if s.text.strip())
            prev_short = len(prev_line.text.split()) <= 10
            curr_short = len(curr_line.text.split()) <= 10
            heading_break = prev_bold and curr_bold and prev_short and curr_short and size_mismatch

            # Determine break
            is_new_para = gap_break or heading_break
            # Size mismatch + indent change together are strong signals
            if size_mismatch and major_indent_change:
                is_new_para = True

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

    # ── Issue 3: Table/paragraph deduplication ─────────────────────────

    @staticmethod
    def _rects_overlap(
        r1: tuple[float, float, float, float],
        r2: tuple[float, float, float, float],
        tolerance: float = 2.0,
    ) -> bool:
        """Check if two rectangles (x0, y0, x1, y1) overlap."""
        x0a, y0a, x1a, y1a = r1
        x0b, y0b, x1b, y1b = r2
        return (
            x0a < x1b + tolerance
            and x1a > x0b - tolerance
            and y0a < y1b + tolerance
            and y1a > y0b - tolerance
        )

    def _filter_table_overlapping_lines(
        self,
        lines: list[FormattedLine],
        table_bboxes: list[tuple[float, float, float, float]],
    ) -> list[FormattedLine]:
        """Remove lines whose bounding box overlaps with any table region.

        This prevents table content from being duplicated as paragraphs.
        """
        if not table_bboxes:
            return lines

        filtered: list[FormattedLine] = []
        for line in lines:
            if not line.spans:
                filtered.append(line)
                continue

            # Compute the line's bounding box from its spans
            line_x0 = min(s.x0 for s in line.spans)
            line_y0 = min(s.y0 for s in line.spans)
            line_x1 = max(s.x1 for s in line.spans)
            line_y1 = max(s.y1 for s in line.spans)
            line_bbox = (line_x0, line_y0, line_x1, line_y1)

            overlaps = any(
                self._rects_overlap(line_bbox, tb)
                for tb in table_bboxes
            )
            if not overlaps:
                filtered.append(line)

        removed = len(lines) - len(filtered)
        if removed > 0:
            logger.debug("Filtered %d lines overlapping with tables", removed)
        return filtered

    # ── Issue 4: Header/footer detection & marking ───────────────────

    # Pattern to strip page numbers from header/footer text for fingerprinting
    _PAGE_NUM_RE = re.compile(r"\bpage\s*\d+\b", re.IGNORECASE)

    def _normalize_hf_text(self, text: str) -> str:
        """Normalize header/footer text for comparison.

        Strips page numbers (e.g., 'Page 3') so that footers varying only
        by page number are still detected as repeating.
        """
        fp = text.strip().lower()
        fp = self._PAGE_NUM_RE.sub("", fp)
        # Collapse whitespace
        fp = re.sub(r"\s+", " ", fp).strip()
        return fp

    def _mark_headers_footers(self, pages: list[FormattedPage]) -> None:
        """Detect repeating headers/footers and mark their paragraphs.

        Text appearing in the top ~50pt or bottom ~50pt of a page that
        repeats (same or very similar text) across 3+ pages is marked
        with style 'header' or 'footer'.  Page numbers are normalized
        out before comparison so 'Page 1' / 'Page 2' still match.
        """
        if len(pages) < 3:
            return

        header_zone = 50.0  # points from top
        footer_zone = 50.0  # points from bottom

        # Collect text fingerprints from header/footer zones per page
        header_texts: dict[str, int] = {}  # normalized text -> page count
        footer_texts: dict[str, int] = {}

        for page in pages:
            page_header_seen: set[str] = set()
            page_footer_seen: set[str] = set()
            for para in page.paragraphs:
                if not para.lines or not para.lines[0].spans:
                    continue
                # Use the y-position of the first span to determine zone
                first_y = para.lines[0].spans[0].y0
                last_y = para.lines[-1].spans[-1].y1 if para.lines[-1].spans else first_y
                text_fp = self._normalize_hf_text(para.text)
                if not text_fp:
                    continue

                if first_y < page.margin_top + header_zone and first_y < 80:
                    if text_fp not in page_header_seen:
                        page_header_seen.add(text_fp)
                        header_texts[text_fp] = header_texts.get(text_fp, 0) + 1
                elif last_y > page.height - footer_zone and last_y > page.height - 80:
                    if text_fp not in page_footer_seen:
                        page_footer_seen.add(text_fp)
                        footer_texts[text_fp] = footer_texts.get(text_fp, 0) + 1

        # Texts appearing on 3+ pages are headers/footers
        min_repeat = min(3, len(pages))
        header_fps = {t for t, c in header_texts.items() if c >= min_repeat}
        footer_fps = {t for t, c in footer_texts.items() if c >= min_repeat}

        if not header_fps and not footer_fps:
            return

        # Second pass: mark matching paragraphs
        marked = 0
        for page in pages:
            for para in page.paragraphs:
                if not para.lines or not para.lines[0].spans:
                    continue
                first_y = para.lines[0].spans[0].y0
                last_y = para.lines[-1].spans[-1].y1 if para.lines[-1].spans else first_y
                text_fp = self._normalize_hf_text(para.text)
                if not text_fp:
                    continue

                if text_fp in header_fps and first_y < page.margin_top + header_zone and first_y < 80:
                    para.style = "header"
                    marked += 1
                elif text_fp in footer_fps and last_y > page.height - footer_zone and last_y > page.height - 80:
                    para.style = "footer"
                    marked += 1

        if marked:
            logger.debug("Marked %d paragraphs as headers/footers", marked)

    # Heuristic for detecting tabular content inside a single cell.
    # Matches lines that have 2+ columns separated by 2+ spaces or tab chars.
    _TABULAR_LINE_RE = re.compile(r"\S.*(?:\t|  {2,})\S")

    def _extract_tables(
        self, page: Any, _out_bboxes: list | None = None,
    ) -> list[FormattedTable]:
        """Extract tables from a PDF page using PyMuPDF's find_tables().

        Also detects cells that contain nested/sub-table content (multiple
        aligned columns of data).  PyMuPDF flattens nested tables, so the
        inner content is preserved as text with a ``[nested table]`` marker
        prepended to flag downstream consumers.

        If *_out_bboxes* is provided (a list), the bounding boxes of all
        detected tables are appended to it for use in deduplication.
        """
        tables: list[FormattedTable] = []
        try:
            found = page.find_tables()
            if not found.tables:
                return []

            for tab in found.tables:
                # Collect bbox for dedup if caller requested
                if _out_bboxes is not None and hasattr(tab, "bbox"):
                    _out_bboxes.append(tuple(tab.bbox))
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
