"""
HTML Renderer — converts FormattedDocument IR to styled HTML5.

Produces semantic HTML with inline styles, suitable for CKEditor or any
rich-text editor. Supports bold/italic/underline, super/subscript, colors,
font sizes, tables with thead/tbody, and embedded base64 images.
"""

from __future__ import annotations

import html as html_module

from src.formatter.extractor import (
    FormattedDocument,
    FormattedPage,
    FormattedParagraph,
    FormattedSpan,
    FormattedTable,
    FormattedTableCell,
)


class HTMLRenderer:
    """Renders a FormattedDocument to styled HTML5.

    Usage::

        renderer = HTMLRenderer()
        html_str = renderer.render(doc)
    """

    def __init__(
        self,
        include_wrapper: bool = True,
        default_font: str = "Arial",
        default_size: float = 11.0,
    ):
        """Initialise the renderer.

        Args:
            include_wrapper: Whether to wrap output in a styled ``<div>``.
            default_font: Fallback font family when none is specified.
            default_size: Fallback font size (pt) when none is specified.
        """
        self._include_wrapper = include_wrapper
        self._default_font = default_font
        self._default_size = default_size

    def render(self, doc: FormattedDocument) -> str:
        """Render a FormattedDocument to an HTML string.

        Args:
            doc: A FormattedDocument IR instance.

        Returns:
            An HTML string with inline styles.
        """
        if not doc.pages:
            return ""

        parts: list[str] = []

        if self._include_wrapper:
            # Detect dominant font from inventory
            body_font = self._dominant_font(doc)
            body_size = self._default_size
            parts.append(
                f'<div style="'
                f"font-family:'{body_font}',sans-serif;"
                f"font-size:{body_size:.1f}pt;"
                f"color:#000000;"
                f"line-height:1.4;"
                f'">'
            )

        for page_idx, page in enumerate(doc.pages):
            parts.append(self._render_page(page))
            # Page break between pages (not after the last)
            if page_idx < len(doc.pages) - 1:
                parts.append('<hr style="page-break-after:always;border:none;">')

        if self._include_wrapper:
            parts.append("</div>")

        return "\n".join(parts)

    def render_with_profile(
        self,
        doc: FormattedDocument,
        profile: dict,
    ) -> str:
        """Render using a TemplateStyleProfile dictionary for style overrides.

        This method re-implements the logic previously in
        ``template_generator.py._render_with_profile`` as a proper renderer.

        Args:
            doc: The FormattedDocument to render.
            profile: A style profile dict (from TemplateStyleProfile.to_dict()).

        Returns:
            An HTML string with profile-derived styles.
        """
        body_font = profile.get("body_font", self._default_font)
        body_size = profile.get("body_size", self._default_size)
        primary_color = profile.get("primary_color", "#000000")
        line_spacing = profile.get("line_spacing", 1.15)
        margin_top = profile.get("margin_top", 72)
        margin_right = profile.get("margin_right", 72)
        margin_bottom = profile.get("margin_bottom", 72)
        margin_left = profile.get("margin_left", 72)
        paragraph_spacing = profile.get("paragraph_spacing", 6)
        list_indent_px = profile.get("list_indent_px", 24)

        parts: list[str] = [
            f'<div style="'
            f"font-family:'{body_font}',sans-serif;"
            f"font-size:{body_size:.1f}pt;"
            f"color:{primary_color};"
            f"line-height:{line_spacing};"
            f"margin:{margin_top:.0f}px {margin_right:.0f}px "
            f"{margin_bottom:.0f}px {margin_left:.0f}px;"
            f'">'
        ]

        heading_fonts = profile.get("heading_fonts", {})
        heading_sizes = profile.get("heading_sizes", {})
        heading_colors = profile.get("heading_colors", {})
        heading_bold = profile.get("heading_bold", {})

        for page in doc.pages:
            for para in page.paragraphs:
                if para.style == "image":
                    parts.append(self._render_image_para(para))
                    continue

                text = self._render_spans_html(para)
                if not text.strip():
                    continue

                style = para.style
                tag = self._tag_for_style(style)

                # Build inline CSS
                css_parts: list[str] = []
                if style.startswith("heading"):
                    font = heading_fonts.get(style, body_font)
                    size = heading_sizes.get(style, body_size + 4)
                    color = heading_colors.get(style, primary_color)
                    bold = heading_bold.get(style, True)
                    css_parts.append(f"font-family:'{font}',sans-serif")
                    css_parts.append(f"font-size:{size:.1f}pt")
                    css_parts.append(f"color:{color}")
                    if bold:
                        css_parts.append("font-weight:bold")

                css_parts.append(f"margin-bottom:{paragraph_spacing:.0f}px")
                if para.alignment and para.alignment != "left":
                    css_parts.append(f"text-align:{para.alignment}")
                if para.indent_level:
                    css_parts.append(f"margin-left:{para.indent_level * list_indent_px}px")

                style_attr = f' style="{";".join(css_parts)};"' if css_parts else ""
                parts.append(f"<{tag}{style_attr}>{text}</{tag}>")

            # Tables
            for table in page.tables:
                parts.append(self._render_table(table))

        parts.append("</div>")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Page-level rendering
    # ------------------------------------------------------------------

    def _render_page(self, page: FormattedPage) -> str:
        """Render a single page to HTML."""
        parts: list[str] = []

        for para in page.paragraphs:
            parts.append(self._render_paragraph(para))

        for table in page.tables:
            parts.append(self._render_table(table))

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Paragraph rendering
    # ------------------------------------------------------------------

    def _render_paragraph(self, para: FormattedParagraph) -> str:
        """Render a paragraph as an HTML element."""
        style = para.style

        # Image paragraphs
        if style == "image":
            return self._render_image_para(para)

        # Page break
        if style == "page_break":
            return '<hr style="page-break-after:always;border:none;">'

        tag = self._tag_for_style(style)
        inline_html = self._render_spans_html(para)

        if not inline_html.strip():
            return ""

        # Build inline style
        css = self._css_for_paragraph(para)
        style_attr = f' style="{css}"' if css else ""

        # Wrap list items in their list container tag
        # (For simplicity, each list item is self-contained; a smarter grouper
        # could batch consecutive items into <ul>/<ol> wrappers.)
        return f"<{tag}{style_attr}>{inline_html}</{tag}>"

    def _render_spans_html(self, para: FormattedParagraph) -> str:
        """Render the inline spans of a paragraph as formatted HTML."""
        parts: list[str] = []
        for line in para.lines:
            for span in line.spans:
                parts.append(self._render_span(span))
        return "".join(parts)

    def _render_span(self, span: FormattedSpan) -> str:
        """Render a single span as HTML with inline formatting."""
        text = html_module.escape(span.text)

        if not text.strip():
            return text

        # Inline tags
        if span.bold:
            text = f"<strong>{text}</strong>"
        if span.italic:
            text = f"<em>{text}</em>"
        if span.underline:
            text = f"<u>{text}</u>"
        if span.superscript:
            text = f"<sup>{text}</sup>"
        elif span.subscript:
            text = f"<sub>{text}</sub>"
        if span.strikethrough:
            text = f"<s>{text}</s>"

        # Inline style for color and font overrides
        css_parts: list[str] = []
        r, g, b = span.color_rgb
        if r > 20 or g > 20 or b > 20:
            css_parts.append(f"color:#{r:02X}{g:02X}{b:02X}")

        if span.font:
            family = span.font_family
            if family and family.lower() != self._default_font.lower():
                css_parts.append(f"font-family:'{family}',sans-serif")

        if span.size and abs(span.size - self._default_size) > 0.5:
            css_parts.append(f"font-size:{span.size:.1f}pt")

        if css_parts:
            style_str = ";".join(css_parts)
            text = f'<span style="{style_str}">{text}</span>'

        return text

    # ------------------------------------------------------------------
    # Table rendering
    # ------------------------------------------------------------------

    def _render_table(self, table: FormattedTable) -> str:
        """Render a table as HTML with thead/tbody."""
        if table.is_empty or not table.rows:
            return ""

        parts: list[str] = [
            '<table style="border-collapse:collapse;width:100%;">'
        ]

        for r_idx, row in enumerate(table.rows):
            # Detect header row
            is_header_row = r_idx == 0 and any(c.is_header for c in row)

            if is_header_row:
                parts.append("<thead>")
            elif r_idx == 1 or (r_idx == 0 and not is_header_row):
                if r_idx == 1:
                    pass  # thead was already closed
                if r_idx == 0:
                    parts.append("<tbody>")

            parts.append("<tr>")
            for cell in row:
                tag = "th" if cell.is_header else "td"
                css = self._css_for_cell(cell)
                style_attr = f' style="{css}"' if css else ""

                attrs = style_attr
                if cell.colspan > 1:
                    attrs += f' colspan="{cell.colspan}"'
                if cell.rowspan > 1:
                    attrs += f' rowspan="{cell.rowspan}"'

                text = html_module.escape(cell.text or "")
                parts.append(f"<{tag}{attrs}>{text}</{tag}>")

            parts.append("</tr>")

            if is_header_row:
                parts.append("</thead>")
                parts.append("<tbody>")

        # Close tbody if we opened it
        if table.rows:
            parts.append("</tbody>")

        parts.append("</table>")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Image rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _render_image_para(para: FormattedParagraph) -> str:
        """Render an image paragraph as an <img> tag."""
        if not para.lines or not para.lines[0].spans:
            return ""

        span = para.lines[0].spans[0]
        src = span.text
        if not src:
            return ""

        width = span.x1
        height = span.y1

        style_parts: list[str] = ["max-width:100%"]
        if width > 0:
            style_parts.append(f"width:{width:.0f}px")
        if height > 0:
            style_parts.append(f"height:{height:.0f}px")

        style_str = ";".join(style_parts)
        return f'<img src="{src}" style="{style_str}" alt="" />'

    # ------------------------------------------------------------------
    # CSS helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tag_for_style(style: str) -> str:
        """Map a paragraph style to an HTML tag."""
        tag_map = {
            "heading1": "h1",
            "heading2": "h2",
            "heading3": "h3",
            "heading4": "h4",
            "heading5": "h5",
            "heading6": "h6",
            "list_bullet": "li",
            "list_number": "li",
        }
        return tag_map.get(style, "p")

    @staticmethod
    def _css_for_paragraph(para: FormattedParagraph) -> str:
        """Build inline CSS for a paragraph."""
        parts: list[str] = []

        if para.alignment and para.alignment != "left":
            parts.append(f"text-align:{para.alignment}")

        if para.indent_level > 0:
            parts.append(f"margin-left:{para.indent_level * 24}px")

        if para.spacing_before > 0:
            pts = min(para.spacing_before, 36)
            parts.append(f"margin-top:{pts:.0f}pt")

        if para.spacing_after > 0:
            pts = min(para.spacing_after, 36)
            parts.append(f"margin-bottom:{pts:.0f}pt")

        return ";".join(parts)

    @staticmethod
    def _css_for_cell(cell: FormattedTableCell) -> str:
        """Build inline CSS for a table cell."""
        parts: list[str] = [
            "border:1px solid #ccc",
            "padding:6px 8px",
        ]
        if cell.is_header:
            parts.extend([
                "background:#1565C0",
                "color:#fff",
                "font-weight:bold",
            ])
        elif cell.bold:
            parts.append("font-weight:bold")
        return ";".join(parts)

    def _dominant_font(self, doc: FormattedDocument) -> str:
        """Return the most-used font in the document."""
        if not doc.font_inventory:
            return self._default_font
        return max(doc.font_inventory, key=doc.font_inventory.get)  # type: ignore[arg-type]
