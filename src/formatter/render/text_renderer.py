"""
Text Renderer — converts FormattedDocument IR to plain text.

Strips all formatting, preserves paragraph structure with double newlines,
renders tables as tab-separated columns, and uses simple markers for
headings, lists, and images.
"""

from __future__ import annotations

from src.formatter.extractor import (
    FormattedDocument,
    FormattedPage,
    FormattedParagraph,
    FormattedTable,
)


class TextRenderer:
    """Renders a FormattedDocument to a plain-text string."""

    def render(self, doc: FormattedDocument) -> str:
        """Render the full document as plain text.

        Args:
            doc: A FormattedDocument IR instance.

        Returns:
            A plain-text string with paragraph breaks preserved.
        """
        if not doc.pages:
            return ""

        parts: list[str] = []

        for page_idx, page in enumerate(doc.pages):
            page_text = self._render_page(page)
            if page_text:
                parts.append(page_text)

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _render_page(self, page: FormattedPage) -> str:
        """Render a single page to plain text."""
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
        """Render a paragraph as plain text."""
        text = self._extract_text(para)
        if not text.strip():
            return None

        style = para.style

        # Images → placeholder
        if style == "image":
            return "[Image]"

        # Headings → UPPERCASE
        if style.startswith("heading"):
            return text.upper()

        # Bullet list
        if style == "list_bullet":
            indent = "  " * para.indent_level
            return f"{indent}- {text}"

        # Numbered list
        if style == "list_number":
            indent = "  " * para.indent_level
            return f"{indent}{text}"

        # Body text — preserve indent
        if para.indent_level > 0:
            indent = "  " * para.indent_level
            return f"{indent}{text}"

        return text

    def _render_table(self, table: FormattedTable) -> str:
        """Render a table as tab-separated columns."""
        if table.is_empty or not table.rows:
            return ""

        lines: list[str] = []
        for row in table.rows:
            cells = [cell.text or "" for cell in row]
            lines.append("\t".join(cells))

        return "\n".join(lines)

    @staticmethod
    def _extract_text(para: FormattedParagraph) -> str:
        """Extract raw text from a paragraph, stripping all formatting."""
        parts: list[str] = []
        for line in para.lines:
            for span in line.spans:
                parts.append(span.text)
        return "".join(parts)
