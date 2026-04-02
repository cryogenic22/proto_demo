"""
Markdown Renderer — converts FormattedDocument IR to a Markdown string.

Produces CommonMark-compatible output with extensions for superscript (^text^)
and subscript (~text~).
"""

from __future__ import annotations

from src.formatter.extractor import (
    FormattedDocument,
    FormattedPage,
    FormattedParagraph,
    FormattedSpan,
    FormattedTable,
)


class MarkdownRenderer:
    """Renders a FormattedDocument to a Markdown string."""

    def render(self, doc: FormattedDocument) -> str:
        """Render the full document as Markdown.

        Args:
            doc: A FormattedDocument IR instance.

        Returns:
            A Markdown-formatted string.
        """
        if not doc.pages:
            return ""

        parts: list[str] = []

        for page_idx, page in enumerate(doc.pages):
            page_md = self._render_page(page)
            if page_md:
                parts.append(page_md)
            # Page break between pages (not after the last)
            if page_idx < len(doc.pages) - 1:
                parts.append("---")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _render_page(self, page: FormattedPage) -> str:
        """Render a single page to Markdown."""
        sections: list[str] = []

        for para in page.paragraphs:
            rendered = self._render_paragraph(para)
            if rendered is not None:
                sections.append(rendered)

        for table in page.tables:
            rendered = self._render_table(table)
            if rendered:
                sections.append(rendered)

        return "\n\n".join(sections)

    def _render_paragraph(self, para: FormattedParagraph) -> str | None:
        """Render a paragraph as Markdown."""
        style = para.style

        # Images
        if style == "image":
            src = self._extract_raw_text(para)
            if src.startswith("data:"):
                return f"![](data_uri)"
            return f"![]({src})"

        # Page break
        if style == "page_break":
            return "---"

        # Build inline text with formatting
        inline = self._render_inline(para)
        if not inline.strip():
            return None

        # Headings
        if style.startswith("heading"):
            level_char = style[-1]
            level = int(level_char) if level_char.isdigit() else 3
            prefix = "#" * level
            return f"{prefix} {inline}"

        # Bullet list
        if style == "list_bullet":
            indent = "  " * para.indent_level
            return f"{indent}- {inline}"

        # Numbered list
        if style == "list_number":
            indent = "  " * para.indent_level
            return f"{indent}1. {inline}"

        # Blockquote (indent_level > 0 on body text)
        if para.indent_level > 0 and style == "body":
            prefix = "> " * para.indent_level
            return f"{prefix}{inline}"

        return inline

    def _render_inline(self, para: FormattedParagraph) -> str:
        """Render the inline content of a paragraph with Markdown formatting."""
        parts: list[str] = []
        for line in para.lines:
            for span in line.spans:
                text = span.text
                if not text:
                    continue
                text = self._format_span(span)
                parts.append(text)
        return "".join(parts)

    @staticmethod
    def _format_span(span: FormattedSpan) -> str:
        """Apply Markdown formatting to a single span's text."""
        text = span.text

        # Don't format whitespace-only spans
        if not text.strip():
            return text

        # Superscript / subscript (extended markdown)
        if span.superscript:
            text = f"^{text}^"
        elif span.subscript:
            text = f"~{text}~"

        # Code / monospace
        font = span.font.lower() if span.font else ""
        if "courier" in font or "mono" in font or "consol" in font:
            text = f"`{text}`"
        # Bold + italic
        elif span.bold and span.italic:
            text = f"***{text}***"
        elif span.bold:
            text = f"**{text}**"
        elif span.italic:
            text = f"*{text}*"

        # Underline — no standard Markdown; use HTML
        if span.underline:
            text = f"<u>{text}</u>"

        # Strikethrough
        if span.strikethrough:
            text = f"~~{text}~~"

        return text

    def _render_table(self, table: FormattedTable) -> str:
        """Render a table as a Markdown pipe table."""
        if table.is_empty or not table.rows:
            return ""

        lines: list[str] = []

        # Determine column widths for alignment (min 3 for separator)
        num_cols = table.num_cols or (max(len(r) for r in table.rows) if table.rows else 0)
        if num_cols == 0:
            return ""

        for r_idx, row in enumerate(table.rows):
            cells: list[str] = []
            for c_idx in range(num_cols):
                if c_idx < len(row):
                    text = row[c_idx].text or ""
                    # Escape pipes in cell text
                    text = text.replace("|", "\\|")
                else:
                    text = ""
                cells.append(f" {text} ")

            lines.append("|" + "|".join(cells) + "|")

            # After the first row (header), add separator
            if r_idx == 0:
                sep_cells = [" --- " for _ in range(num_cols)]
                lines.append("|" + "|".join(sep_cells) + "|")

        return "\n".join(lines)

    @staticmethod
    def _extract_raw_text(para: FormattedParagraph) -> str:
        """Extract raw text from a paragraph without formatting."""
        parts: list[str] = []
        for line in para.lines:
            for span in line.spans:
                parts.append(span.text)
        return "".join(parts)
