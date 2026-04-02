"""
DOCX Renderer — converts FormattedDocument IR to a styled Word document.

Preserves: fonts, sizes, colors, bold/italic/underline, super/subscript,
paragraph spacing, alignment, heading levels, lists, table structure,
and page margins.

Usage:
    from src.formatter.docx_renderer import DOCXRenderer
    renderer = DOCXRenderer()
    docx_bytes = renderer.render(formatted_document)
    # or render from PDF directly:
    docx_bytes = renderer.render_from_pdf(pdf_bytes)
"""

from __future__ import annotations

import io
import logging
from typing import Any

from src.formatter.extractor import (
    FormattedDocument,
    FormattedPage,
    FormattedParagraph,
    FormattedSpan,
    FormattingExtractor,
)

logger = logging.getLogger(__name__)


class DOCXRenderer:
    """Renders a FormattedDocument to DOCX with full formatting preservation."""

    def __init__(self):
        self.extractor = FormattingExtractor()

    def render(self, doc: FormattedDocument) -> bytes:
        """Render a FormattedDocument to DOCX bytes."""
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches, Cm, Emu
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn

        word_doc = Document()

        # Set page margins from first page
        if doc.pages:
            p0 = doc.pages[0]
            for section in word_doc.sections:
                # Convert PDF points to EMU (1 pt = 12700 EMU)
                section.left_margin = Emu(int(p0.margin_left * 12700))
                section.right_margin = Emu(int(p0.margin_right * 12700))
                section.top_margin = Emu(int(p0.margin_top * 12700))
                section.bottom_margin = Emu(int(p0.margin_bottom * 12700))
                # Set page size
                section.page_width = Emu(int(p0.width * 12700))
                section.page_height = Emu(int(p0.height * 12700))

        for page in doc.pages:
            for para in page.paragraphs:
                self._add_paragraph(word_doc, para)

        # Write to bytes
        buf = io.BytesIO()
        word_doc.save(buf)
        return buf.getvalue()

    def render_from_pdf(self, pdf_bytes: bytes, filename: str = "") -> bytes:
        """Extract formatting from PDF and render to DOCX."""
        doc = self.extractor.extract(pdf_bytes, filename)
        return self.render(doc)

    def render_with_profile(
        self, doc: FormattedDocument, profile: dict[str, Any] | None = None,
    ) -> bytes:
        """Render with an optional style profile override.

        If a profile is provided (from TemplateConformer), use template
        fonts/sizes instead of source document formatting.
        """
        from docx import Document
        from docx.shared import Pt, RGBColor, Emu
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        word_doc = Document()

        # Set page margins
        if doc.pages:
            p0 = doc.pages[0]
            if profile:
                ml = profile.get("margin_left", p0.margin_left)
                mr = profile.get("margin_right", p0.margin_right)
                mt = profile.get("margin_top", p0.margin_top)
                mb = profile.get("margin_bottom", p0.margin_bottom)
            else:
                ml, mr, mt, mb = p0.margin_left, p0.margin_right, p0.margin_top, p0.margin_bottom

            for section in word_doc.sections:
                section.left_margin = Emu(int(ml * 12700))
                section.right_margin = Emu(int(mr * 12700))
                section.top_margin = Emu(int(mt * 12700))
                section.bottom_margin = Emu(int(mb * 12700))
                section.page_width = Emu(int(p0.width * 12700))
                section.page_height = Emu(int(p0.height * 12700))

        for page in doc.pages:
            for para in page.paragraphs:
                self._add_paragraph(word_doc, para, profile)

        buf = io.BytesIO()
        word_doc.save(buf)
        return buf.getvalue()

    def _add_paragraph(
        self,
        word_doc: Any,
        para: FormattedParagraph,
        profile: dict[str, Any] | None = None,
    ) -> None:
        """Add a formatted paragraph to the Word document."""
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        # Determine style
        style_name = None
        if para.style.startswith("heading"):
            level = para.style[-1] if para.style[-1].isdigit() else "3"
            style_name = f"Heading {level}"
        elif para.style == "list_bullet":
            style_name = "List Bullet"
        elif para.style == "list_number":
            style_name = "List Number"

        try:
            wp = word_doc.add_paragraph(style=style_name)
        except KeyError:
            wp = word_doc.add_paragraph()

        # Set alignment
        align_map = {
            "left": WD_ALIGN_PARAGRAPH.LEFT,
            "center": WD_ALIGN_PARAGRAPH.CENTER,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
            "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
        }
        wp.alignment = align_map.get(para.alignment, WD_ALIGN_PARAGRAPH.LEFT)

        # Set spacing
        pf = wp.paragraph_format
        if para.spacing_before > 0:
            pf.space_before = Pt(min(para.spacing_before, 36))
        if para.spacing_after > 0:
            pf.space_after = Pt(min(para.spacing_after, 36))

        # Set indent
        if para.indent_level > 0 and not style_name:
            pf.left_indent = Pt(para.indent_level * 18)

        # Add runs with formatting
        for line in para.lines:
            for span in line.spans:
                if not span.text:
                    continue

                run = wp.add_run(span.text)

                # Font name
                font_name = span.font_family
                if profile and not para.style.startswith("heading"):
                    font_name = profile.get("body_font", font_name)
                elif profile and para.style.startswith("heading"):
                    heading_fonts = profile.get("heading_fonts", {})
                    font_name = heading_fonts.get(para.style, font_name)

                run.font.name = font_name

                # Font size
                size = span.size
                if profile and not para.style.startswith("heading"):
                    size = profile.get("body_size", size)
                elif profile and para.style.startswith("heading"):
                    heading_sizes = profile.get("heading_sizes", {})
                    size = heading_sizes.get(para.style, size)

                run.font.size = Pt(size)

                # Bold / Italic
                run.font.bold = span.bold
                run.font.italic = span.italic

                # Underline
                if span.underline:
                    run.font.underline = True

                # Superscript / Subscript
                if span.superscript:
                    run.font.superscript = True
                elif span.subscript:
                    run.font.subscript = True

                # Color
                r, g, b = span.color_rgb
                if r > 30 or g > 30 or b > 30:  # Skip near-black
                    run.font.color.rgb = RGBColor(r, g, b)
