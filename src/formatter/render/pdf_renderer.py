"""
PDF Renderer — converts FormattedDocument IR to PDF bytes.

Uses reportlab to produce a styled PDF with paragraphs, inline formatting
(bold, italic, underline, super/subscript, colors), tables with header
styling, and embedded base64 images.
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any

from src.formatter.extractor import (
    FormattedDocument,
    FormattedLine,
    FormattedPage,
    FormattedParagraph,
    FormattedSpan,
    FormattedTable,
    FormattedTableCell,
)

logger = logging.getLogger(__name__)

try:
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import (
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False

# Default page dimensions (US Letter in points)
_DEFAULT_WIDTH = 612.0
_DEFAULT_HEIGHT = 792.0
_DEFAULT_MARGIN = 72.0


class PDFRenderer:
    """Renders a FormattedDocument to PDF bytes using reportlab.

    Usage::

        renderer = PDFRenderer()
        pdf_bytes = renderer.render(doc)
    """

    def __init__(
        self,
        default_font: str = "Helvetica",
        default_size: float = 11.0,
    ):
        """Initialise the renderer.

        Args:
            default_font: Fallback font family for body text.
            default_size: Fallback font size (pt).
        """
        self._default_font = default_font
        self._default_size = default_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, doc: FormattedDocument) -> bytes:
        """Render a FormattedDocument to PDF bytes.

        Args:
            doc: A FormattedDocument IR instance.

        Returns:
            PDF file content as bytes.

        Raises:
            ImportError: If reportlab is not installed.
        """
        if not _HAS_REPORTLAB:
            raise ImportError(
                "reportlab is required for PDF rendering. "
                "Install it with: pip install reportlab"
            )

        if not doc.pages:
            return self._empty_pdf()

        buffer = io.BytesIO()

        # Determine page size from the first page
        first_page = doc.pages[0]
        page_width = first_page.width if first_page.width > 0 else _DEFAULT_WIDTH
        page_height = first_page.height if first_page.height > 0 else _DEFAULT_HEIGHT

        template = SimpleDocTemplate(
            buffer,
            pagesize=(page_width, page_height),
            leftMargin=first_page.margin_left or _DEFAULT_MARGIN,
            rightMargin=first_page.margin_right or _DEFAULT_MARGIN,
            topMargin=first_page.margin_top or _DEFAULT_MARGIN,
            bottomMargin=first_page.margin_bottom or _DEFAULT_MARGIN,
        )

        story: list[Any] = []

        for page_idx, page in enumerate(doc.pages):
            if page_idx > 0:
                story.append(PageBreak())

            # Merge paragraphs and tables by y-position for correct ordering
            elements = self._build_page_elements(page)
            story.extend(elements)

        template.build(story)
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # Internal — page elements
    # ------------------------------------------------------------------

    def _build_page_elements(self, page: FormattedPage) -> list[Any]:
        """Build a list of reportlab flowables for a single page."""
        # Collect paragraphs with y-positions for interleaving with tables
        items: list[tuple[float, Any]] = []

        for para in page.paragraphs:
            y_pos = para.lines[0].y_center if para.lines else 0.0
            flowable = self._render_paragraph(para)
            if flowable is not None:
                items.append((y_pos, flowable))

        for table in page.tables:
            flowable = self._render_table(table)
            if flowable is not None:
                items.append((table.y_position, flowable))

        # Sort by vertical position (top to bottom)
        items.sort(key=lambda x: x[0])
        # Filter out None items (failed renders)
        return [item[1] for item in items if item[1] is not None]

    # ------------------------------------------------------------------
    # Internal — paragraphs
    # ------------------------------------------------------------------

    def _render_paragraph(self, para: FormattedParagraph) -> Any | None:
        """Convert a FormattedParagraph to a reportlab Paragraph flowable."""
        if not para.lines:
            return None

        # Handle embedded images
        if para.style == "image":
            return self._render_image(para)

        # Build inline HTML markup for reportlab's Paragraph
        markup = self._spans_to_markup(para)
        if not markup.strip():
            return Spacer(1, para.spacing_after or 6)

        style = self._paragraph_style(para)

        # Add spacing
        if para.spacing_before > 0:
            style.spaceBefore = para.spacing_before
        if para.spacing_after > 0:
            style.spaceAfter = para.spacing_after

        try:
            return Paragraph(markup, style)
        except Exception as exc:
            logger.debug("Failed to render paragraph with markup: %s", exc)
            # Fall back to plain text with all XML stripped
            plain = para.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            try:
                return Paragraph(plain, style)
            except Exception:
                # Last resort: skip this paragraph
                return Spacer(1, 6)

    def _spans_to_markup(self, para: FormattedParagraph) -> str:
        """Convert all spans in a paragraph to reportlab-compatible XML markup."""
        parts: list[str] = []

        # List prefixes
        if para.style == "list_bullet":
            parts.append("\u2022 ")
        elif para.style == "list_number":
            parts.append("1. ")

        for line_idx, line in enumerate(para.lines):
            if line_idx > 0:
                parts.append("<br/>")
            for span in line.spans:
                parts.append(self._span_to_markup(span))

        return "".join(parts)

    def _span_to_markup(self, span: FormattedSpan) -> str:
        """Convert a single FormattedSpan to reportlab inline XML."""
        text = span.text
        if not text:
            return ""

        # Escape XML special characters
        text = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        # Apply formatting wrappers (innermost first)
        if span.bold:
            text = f"<b>{text}</b>"
        if span.italic:
            text = f"<i>{text}</i>"
        if span.underline:
            text = f"<u>{text}</u>"
        if span.superscript:
            text = f"<super>{text}</super>"
        if span.subscript:
            text = f"<sub>{text}</sub>"

        # Color
        if span.color != 0:
            r, g, b = span.color_rgb
            hex_color = f"#{r:02X}{g:02X}{b:02X}"
            text = f'<font color="{hex_color}">{text}</font>'

        return text

    def _paragraph_style(self, para: FormattedParagraph) -> ParagraphStyle:
        """Create a ParagraphStyle for a given paragraph classification."""
        base = getSampleStyleSheet()["Normal"]

        style_map = {
            "heading1": ParagraphStyle(
                "heading1",
                parent=base,
                fontSize=16,
                leading=20,
                fontName="Helvetica-Bold",
                spaceAfter=8,
            ),
            "heading2": ParagraphStyle(
                "heading2",
                parent=base,
                fontSize=14,
                leading=18,
                fontName="Helvetica-Bold",
                spaceAfter=6,
            ),
            "heading3": ParagraphStyle(
                "heading3",
                parent=base,
                fontSize=12,
                leading=16,
                fontName="Helvetica-Bold",
                spaceAfter=4,
            ),
            "heading4": ParagraphStyle(
                "heading4",
                parent=base,
                fontSize=11,
                leading=14,
                fontName="Helvetica-Bold",
                spaceAfter=4,
            ),
            "list_bullet": ParagraphStyle(
                "list_bullet",
                parent=base,
                fontSize=self._default_size,
                leading=self._default_size + 3,
                leftIndent=18 * max(para.indent_level, 1),
            ),
            "list_number": ParagraphStyle(
                "list_number",
                parent=base,
                fontSize=self._default_size,
                leading=self._default_size + 3,
                leftIndent=18 * max(para.indent_level, 1),
            ),
        }

        style = style_map.get(para.style)
        if style is None:
            style = ParagraphStyle(
                "body",
                parent=base,
                fontSize=self._default_size,
                leading=self._default_size + 3,
                leftIndent=18 * para.indent_level,
            )

        # Alignment
        alignment_map = {"left": 0, "center": 1, "right": 2, "justify": 4}
        style.alignment = alignment_map.get(para.alignment, 0)

        return style

    # ------------------------------------------------------------------
    # Internal — tables
    # ------------------------------------------------------------------

    def _render_table(self, table: FormattedTable) -> Any | None:
        """Convert a FormattedTable to a reportlab Table flowable."""
        if table.is_empty or not table.rows:
            return None

        data: list[list[str]] = []
        for row in table.rows:
            row_data: list[str] = []
            for cell in row:
                cell_text = cell.text or ""
                if cell.bold:
                    cell_text = f"<b>{cell_text}</b>"
                row_data.append(cell_text)
            data.append(row_data)

        if not data:
            return None

        # Convert cell strings to Paragraph flowables for wrapping
        base_style = ParagraphStyle(
            "TableCell",
            fontSize=9,
            leading=11,
            fontName="Helvetica",
        )
        header_style = ParagraphStyle(
            "TableHeader",
            fontSize=9,
            leading=11,
            fontName="Helvetica-Bold",
        )

        para_data: list[list[Any]] = []
        for r_idx, row in enumerate(data):
            para_row: list[Any] = []
            for cell_text in row:
                s = header_style if r_idx == 0 else base_style
                try:
                    para_row.append(Paragraph(cell_text, s))
                except Exception:
                    para_row.append(Paragraph(cell_text.replace("<", "&lt;"), s))
            para_data.append(para_row)

        rl_table = Table(para_data, repeatRows=1)

        # Style the table
        style_commands: list[Any] = [
            ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.Color(0.9, 0.9, 0.9)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]

        rl_table.setStyle(TableStyle(style_commands))
        return rl_table

    # ------------------------------------------------------------------
    # Internal — images
    # ------------------------------------------------------------------

    def _render_image(self, para: FormattedParagraph) -> Any | None:
        """Convert an image paragraph (data URI) to a reportlab Image."""
        if not para.lines or not para.lines[0].spans:
            return None

        span = para.lines[0].spans[0]
        data_uri = span.text

        if not data_uri.startswith("data:image/"):
            return None

        try:
            # Parse data URI: data:image/png;base64,<data>
            header, b64_data = data_uri.split(",", 1)
            img_bytes = base64.b64decode(b64_data)
            img_buffer = io.BytesIO(img_bytes)

            # Use span bounding box for dimensions, constrained to reasonable size
            width = min(span.x1, 500)
            height = min(span.y1, 500)
            if width <= 0:
                width = 200
            if height <= 0:
                height = 200

            return Image(img_buffer, width=width, height=height)
        except Exception as exc:
            logger.debug("Failed to render embedded image: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internal — helpers
    # ------------------------------------------------------------------

    def _empty_pdf(self) -> bytes:
        """Return a minimal empty PDF document."""
        buffer = io.BytesIO()
        template = SimpleDocTemplate(buffer, pagesize=letter)
        template.build([Spacer(1, 1)])
        return buffer.getvalue()
