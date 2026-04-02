"""
Text Ingestor — converts plain text to FormattedDocument IR.

Detects basic structure: numbered sections become headings, bullet lines
become lists, and everything else becomes body paragraphs.
"""

from __future__ import annotations

import re

from src.formatter.extractor import (
    FormattedDocument,
    FormattedLine,
    FormattedPage,
    FormattedParagraph,
    FormattedSpan,
)

# Default styling constants
_DEFAULT_FONT = "Arial"
_DEFAULT_SIZE = 11.0
_PAGE_WIDTH = 612.0   # US Letter width in points
_PAGE_HEIGHT = 792.0  # US Letter height in points

# Patterns for structure detection
_HEADING_RE = re.compile(
    r"^(\d+(?:\.\d+)*)\.?\s+(.+)$"
)  # 1. Title  or  1.1 Sub-title  or  1 Title
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)$")
_NUMBERED_LIST_RE = re.compile(r"^\s*\d{1,3}[.)]\s+(.+)$")


class TextIngestor:
    """Converts plain text content into a FormattedDocument IR.

    Structure detection rules:
    - Double newline → paragraph break
    - Lines matching ``1.`` or ``1.1`` pattern → headings
    - Lines starting with ``-`` or ``*`` → bullet lists
    - Lines starting with ``1)`` or ``1.`` (short) → numbered lists
    - Everything else → body paragraphs
    """

    def ingest(self, content: str, filename: str = "") -> FormattedDocument:
        """Parse plain text and return a FormattedDocument.

        Args:
            content: The plain-text string to parse.
            filename: Optional source filename for metadata.

        Returns:
            A FormattedDocument with a single page of detected paragraphs.
        """
        if not content or not content.strip():
            return self._empty_doc(filename)

        paragraphs = self._parse_paragraphs(content)

        page = FormattedPage(
            page_number=0,
            width=_PAGE_WIDTH,
            height=_PAGE_HEIGHT,
            paragraphs=paragraphs,
        )

        return FormattedDocument(
            filename=filename,
            pages=[page],
            font_inventory={_DEFAULT_FONT: sum(
                len(s.text)
                for p in paragraphs
                for ln in p.lines
                for s in ln.spans
            )},
            color_inventory={"#000000": 1},
            style_inventory=self._count_styles(paragraphs),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _empty_doc(self, filename: str) -> FormattedDocument:
        """Return a minimal empty document."""
        return FormattedDocument(
            filename=filename,
            pages=[FormattedPage(
                page_number=0,
                width=_PAGE_WIDTH,
                height=_PAGE_HEIGHT,
            )],
        )

    def _parse_paragraphs(self, text: str) -> list[FormattedParagraph]:
        """Split text into paragraphs and classify each one."""
        # Normalise line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Split on double-newline (blank line) to get raw paragraph blocks
        raw_blocks = re.split(r"\n{2,}", text.strip())

        paragraphs: list[FormattedParagraph] = []
        for block in raw_blocks:
            block = block.strip()
            if not block:
                continue

            # Each block may contain multiple lines; process them individually
            lines = block.split("\n")
            for line_text in lines:
                line_text = line_text.rstrip()
                if not line_text:
                    continue

                para = self._classify_line(line_text)
                paragraphs.append(para)

        return paragraphs

    def _classify_line(self, text: str) -> FormattedParagraph:
        """Classify a single line of text and return a FormattedParagraph."""
        style = "body"
        indent_level = 0

        # Check for numbered heading (1. or 1.1 pattern followed by text)
        heading_match = _HEADING_RE.match(text)
        if heading_match:
            section_num = heading_match.group(1)
            depth = section_num.count(".")
            if depth == 0:
                style = "heading1"
            elif depth == 1:
                style = "heading2"
            elif depth == 2:
                style = "heading3"
            else:
                style = "heading4"

        # Check for bullet list
        elif _BULLET_RE.match(text):
            style = "list_bullet"
            # Detect indent from leading whitespace
            stripped = text.lstrip()
            indent_chars = len(text) - len(stripped)
            indent_level = indent_chars // 2
            # Strip the bullet marker so renderers can re-add their own
            text = _BULLET_RE.match(text).group(1)

        # Check for numbered list
        elif _NUMBERED_LIST_RE.match(text):
            style = "list_number"
            # Strip the number marker so renderers can re-add their own
            text = _NUMBERED_LIST_RE.match(text).group(1)

        span = FormattedSpan(
            text=text,
            x0=0.0,
            y0=0.0,
            x1=len(text) * _DEFAULT_SIZE * 0.5,
            y1=_DEFAULT_SIZE,
            font=_DEFAULT_FONT,
            size=_DEFAULT_SIZE,
            color=0,
            bold=style.startswith("heading"),
        )

        line = FormattedLine(
            spans=[span],
            y_center=0.0,
            indent=float(indent_level * 18),
        )

        return FormattedParagraph(
            lines=[line],
            style=style,
            indent_level=indent_level,
        )

    @staticmethod
    def _count_styles(paragraphs: list[FormattedParagraph]) -> dict[str, int]:
        """Build a style inventory from a list of paragraphs."""
        counts: dict[str, int] = {}
        for p in paragraphs:
            counts[p.style] = counts.get(p.style, 0) + 1
        return counts
