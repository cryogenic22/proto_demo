"""
HTML Ingestor — converts an HTML string to FormattedDocument IR.

Uses Python's stdlib ``html.parser`` (no BeautifulSoup dependency).
Maps semantic HTML tags to the IR model: headings, bold, italic, underline,
superscript, subscript, lists, tables, and inline styles.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
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

_PAGE_WIDTH = 612.0
_PAGE_HEIGHT = 792.0
_DEFAULT_FONT = "Arial"
_DEFAULT_SIZE = 11.0

# Tags that produce block-level paragraph breaks
_BLOCK_TAGS = frozenset({
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "blockquote", "pre", "hr", "br",
    "table", "tr", "td", "th", "thead", "tbody", "tfoot",
    "ul", "ol", "dl", "dt", "dd", "figure", "figcaption",
    "section", "article", "header", "footer", "nav", "aside", "main",
})

# Tags whose content should be completely ignored
_IGNORE_TAGS = frozenset({"script", "style", "head", "meta", "link", "title"})


class _FormatState:
    """Tracks the current inline formatting context while walking the HTML."""

    __slots__ = ("bold", "italic", "underline", "superscript", "subscript",
                 "font", "size", "color")

    def __init__(self) -> None:
        self.bold: bool = False
        self.italic: bool = False
        self.underline: bool = False
        self.superscript: bool = False
        self.subscript: bool = False
        self.font: str = _DEFAULT_FONT
        self.size: float = _DEFAULT_SIZE
        self.color: int = 0  # packed RGB

    def copy(self) -> _FormatState:
        s = _FormatState()
        s.bold = self.bold
        s.italic = self.italic
        s.underline = self.underline
        s.superscript = self.superscript
        s.subscript = self.subscript
        s.font = self.font
        s.size = self.size
        s.color = self.color
        return s


class _HTMLWalker(HTMLParser):
    """Walk an HTML document and produce FormattedDocument IR elements."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)

        # Result containers
        self.paragraphs: list[FormattedParagraph] = []
        self.tables: list[FormattedTable] = []

        # State stacks
        self._fmt_stack: list[_FormatState] = [_FormatState()]
        self._current_spans: list[FormattedSpan] = []
        self._current_style: str = "body"
        self._current_alignment: str = "left"
        self._current_indent: int = 0

        # List context
        self._list_stack: list[str] = []  # "ul" or "ol"

        # Table context
        self._in_table: bool = False
        self._table_rows: list[list[FormattedTableCell]] = []
        self._current_row: list[FormattedTableCell] = []
        self._cell_text: str = ""
        self._cell_is_header: bool = False

        # Ignore depth counter (for script/style)
        self._ignore_depth: int = 0

    # -- formatting helpers ------------------------------------------------

    @property
    def _fmt(self) -> _FormatState:
        return self._fmt_stack[-1]

    def _push_fmt(self, **overrides: Any) -> None:
        new = self._fmt.copy()
        for k, v in overrides.items():
            setattr(new, k, v)
        self._fmt_stack.append(new)

    def _pop_fmt(self) -> None:
        if len(self._fmt_stack) > 1:
            self._fmt_stack.pop()

    # -- flush current paragraph -------------------------------------------

    def _flush_paragraph(self) -> None:
        """Commit accumulated spans as a paragraph."""
        if not self._current_spans:
            return

        line = FormattedLine(spans=list(self._current_spans))
        para = FormattedParagraph(
            lines=[line],
            style=self._current_style,
            alignment=self._current_alignment,
            indent_level=self._current_indent,
        )
        self.paragraphs.append(para)

        self._current_spans.clear()
        self._current_style = "body"
        self._current_alignment = "left"
        self._current_indent = 0

    # -- HTMLParser callbacks -----------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr_dict = {k: (v or "") for k, v in attrs}

        # Ignored tags
        if tag in _IGNORE_TAGS:
            self._ignore_depth += 1
            return
        if self._ignore_depth:
            return

        # Block-level elements: flush any pending inline content first
        if tag in _BLOCK_TAGS:
            self._flush_paragraph()

        # Headings
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = tag[1]
            self._current_style = f"heading{level}"
            self._push_fmt(bold=True)
            return

        # Paragraph / div
        if tag in ("p", "div"):
            style_attr = attr_dict.get("style", "")
            self._apply_block_style(style_attr)
            return

        # Lists
        if tag in ("ul", "ol"):
            self._list_stack.append(tag)
            return
        if tag == "li":
            if self._list_stack:
                list_type = self._list_stack[-1]
                self._current_style = (
                    "list_bullet" if list_type == "ul" else "list_number"
                )
            else:
                self._current_style = "list_bullet"
            self._current_indent = len(self._list_stack)
            return

        # Blockquote
        if tag == "blockquote":
            self._current_indent += 1
            return

        # Horizontal rule → page break style
        if tag == "hr":
            para = FormattedParagraph(
                lines=[FormattedLine(spans=[FormattedSpan(
                    text="---",
                    x0=0, y0=0, x1=0, y1=0,
                    font=_DEFAULT_FONT, size=_DEFAULT_SIZE,
                )])],
                style="page_break",
            )
            self.paragraphs.append(para)
            return

        # Line break
        if tag == "br":
            self._current_spans.append(FormattedSpan(
                text="\n", x0=0, y0=0, x1=0, y1=0,
                font=self._fmt.font, size=self._fmt.size,
            ))
            return

        # Inline formatting
        if tag in ("strong", "b"):
            self._push_fmt(bold=True)
            return
        if tag in ("em", "i"):
            self._push_fmt(italic=True)
            return
        if tag == "u":
            self._push_fmt(underline=True)
            return
        if tag == "sup":
            self._push_fmt(superscript=True)
            return
        if tag == "sub":
            self._push_fmt(subscript=True)
            return
        if tag in ("code", "tt"):
            self._push_fmt(font="Courier New")
            return
        if tag in ("s", "del", "strike"):
            self._push_fmt()  # strikethrough — no IR flag, push to keep stack balanced
            return

        # Span with inline styles
        if tag == "span":
            style_attr = attr_dict.get("style", "")
            overrides = self._parse_inline_style(style_attr)
            self._push_fmt(**overrides)
            return

        # Images
        if tag == "img":
            src = attr_dict.get("src", "")
            alt = attr_dict.get("alt", "")
            if src:
                self._flush_paragraph()
                img_para = FormattedParagraph(
                    style="image",
                    lines=[FormattedLine(spans=[FormattedSpan(
                        text=src,
                        x0=0, y0=0,
                        x1=float(attr_dict.get("width", "0") or "0"),
                        y1=float(attr_dict.get("height", "0") or "0"),
                        font="", size=0,
                    )])],
                )
                self.paragraphs.append(img_para)
            return

        # Tables
        if tag == "table":
            self._in_table = True
            self._table_rows = []
            return
        if tag == "tr":
            self._current_row = []
            return
        if tag in ("td", "th"):
            self._cell_text = ""
            self._cell_is_header = tag == "th"
            colspan = int(attr_dict.get("colspan", "1") or "1")
            rowspan = int(attr_dict.get("rowspan", "1") or "1")
            # Store spans for later
            self._cell_text = ""
            # Stash colspan/rowspan on instance for handle_endtag
            self._cell_colspan = colspan
            self._cell_rowspan = rowspan
            return

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        # Ignored tags
        if tag in _IGNORE_TAGS:
            self._ignore_depth = max(0, self._ignore_depth - 1)
            return
        if self._ignore_depth:
            return

        # Headings
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._pop_fmt()
            self._flush_paragraph()
            return

        # Paragraph / div
        if tag in ("p", "div"):
            self._flush_paragraph()
            return

        # Lists
        if tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            return
        if tag == "li":
            self._flush_paragraph()
            return

        # Blockquote
        if tag == "blockquote":
            self._flush_paragraph()
            self._current_indent = max(0, self._current_indent - 1)
            return

        # Inline formatting — pop the matching format state
        if tag in ("strong", "b", "em", "i", "u", "sup", "sub",
                    "code", "tt", "s", "del", "strike", "span"):
            self._pop_fmt()
            return

        # Table elements
        if tag in ("td", "th"):
            colspan = getattr(self, "_cell_colspan", 1)
            rowspan = getattr(self, "_cell_rowspan", 1)
            cell = FormattedTableCell(
                text=self._cell_text.strip(),
                row=len(self._table_rows),
                col=len(self._current_row),
                colspan=colspan,
                rowspan=rowspan,
                bold=self._cell_is_header,
                is_header=self._cell_is_header,
            )
            self._current_row.append(cell)
            return

        if tag == "tr":
            if self._current_row:
                self._table_rows.append(self._current_row)
                self._current_row = []
            return

        if tag == "table":
            if self._table_rows:
                num_rows = len(self._table_rows)
                num_cols = max((len(r) for r in self._table_rows), default=0)
                self.tables.append(FormattedTable(
                    rows=self._table_rows,
                    num_rows=num_rows,
                    num_cols=num_cols,
                ))
            self._in_table = False
            self._table_rows = []
            return

    def handle_data(self, data: str) -> None:
        if self._ignore_depth:
            return

        # Inside a table cell, accumulate text
        if self._in_table:
            self._cell_text += data
            return

        if not data:
            return

        # Collapse whitespace (HTML default behaviour)
        text = re.sub(r"\s+", " ", data)
        if not text or text == " " and not self._current_spans:
            return

        fmt = self._fmt
        span = FormattedSpan(
            text=text,
            x0=0.0, y0=0.0, x1=0.0, y1=0.0,
            font=fmt.font,
            size=fmt.size,
            color=fmt.color,
            bold=fmt.bold,
            italic=fmt.italic,
            underline=fmt.underline,
            superscript=fmt.superscript,
            subscript=fmt.subscript,
        )
        self._current_spans.append(span)

    # -- style parsing helpers ---------------------------------------------

    def _apply_block_style(self, style_attr: str) -> None:
        """Apply block-level CSS properties from a style attribute."""
        if not style_attr:
            return
        props = self._parse_css(style_attr)
        if "text-align" in props:
            self._current_alignment = props["text-align"]

    def _parse_inline_style(self, style_attr: str) -> dict[str, Any]:
        """Parse a ``style`` attribute and return _FormatState overrides."""
        if not style_attr:
            return {}

        props = self._parse_css(style_attr)
        overrides: dict[str, Any] = {}

        # Color
        if "color" in props:
            rgb = self._parse_color(props["color"])
            if rgb is not None:
                overrides["color"] = rgb

        # Font size
        if "font-size" in props:
            size = self._parse_font_size(props["font-size"])
            if size is not None:
                overrides["size"] = size

        # Font family
        if "font-family" in props:
            font = props["font-family"].split(",")[0].strip().strip("'\"")
            if font:
                overrides["font"] = font

        # Font weight
        if "font-weight" in props:
            val = props["font-weight"].lower()
            if val in ("bold", "700", "800", "900"):
                overrides["bold"] = True

        # Font style
        if "font-style" in props:
            if "italic" in props["font-style"].lower():
                overrides["italic"] = True

        # Text decoration
        if "text-decoration" in props:
            if "underline" in props["text-decoration"].lower():
                overrides["underline"] = True

        return overrides

    @staticmethod
    def _parse_css(style_str: str) -> dict[str, str]:
        """Parse a CSS ``style`` string into a property dict."""
        result: dict[str, str] = {}
        for declaration in style_str.split(";"):
            declaration = declaration.strip()
            if ":" not in declaration:
                continue
            prop, _, value = declaration.partition(":")
            result[prop.strip().lower()] = value.strip()
        return result

    @staticmethod
    def _parse_color(color_str: str) -> int | None:
        """Parse a CSS color value to packed RGB integer."""
        color_str = color_str.strip().lower()

        # Hex colors
        hex_match = re.match(r"^#([0-9a-f]{6})$", color_str)
        if hex_match:
            return int(hex_match.group(1), 16)
        hex3_match = re.match(r"^#([0-9a-f]{3})$", color_str)
        if hex3_match:
            h = hex3_match.group(1)
            expanded = h[0] * 2 + h[1] * 2 + h[2] * 2
            return int(expanded, 16)

        # rgb(r, g, b)
        rgb_match = re.match(r"^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$", color_str)
        if rgb_match:
            r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
            return (r << 16) | (g << 8) | b

        # Named colors (common subset)
        named = {
            "black": 0x000000, "white": 0xFFFFFF, "red": 0xFF0000,
            "green": 0x008000, "blue": 0x0000FF, "yellow": 0xFFFF00,
            "gray": 0x808080, "grey": 0x808080, "orange": 0xFFA500,
            "purple": 0x800080, "navy": 0x000080, "teal": 0x008080,
        }
        return named.get(color_str)

    @staticmethod
    def _parse_font_size(size_str: str) -> float | None:
        """Parse a CSS font-size value to points."""
        size_str = size_str.strip().lower()

        # pt value
        pt_match = re.match(r"^([\d.]+)\s*pt$", size_str)
        if pt_match:
            return float(pt_match.group(1))

        # px value (approximate 1px ≈ 0.75pt)
        px_match = re.match(r"^([\d.]+)\s*px$", size_str)
        if px_match:
            return float(px_match.group(1)) * 0.75

        # em value (relative to default)
        em_match = re.match(r"^([\d.]+)\s*em$", size_str)
        if em_match:
            return float(em_match.group(1)) * _DEFAULT_SIZE

        # rem value (treat same as em for simplicity)
        rem_match = re.match(r"^([\d.]+)\s*rem$", size_str)
        if rem_match:
            return float(rem_match.group(1)) * _DEFAULT_SIZE

        return None


class HTMLIngestor:
    """Converts an HTML string into a FormattedDocument IR.

    Usage::

        ingestor = HTMLIngestor()
        doc = ingestor.ingest("<h1>Title</h1><p>Body text.</p>")
    """

    def ingest(self, content: str, filename: str = "") -> FormattedDocument:
        """Parse HTML content and return a FormattedDocument.

        Args:
            content: The HTML string to parse.
            filename: Optional source filename for metadata.

        Returns:
            A FormattedDocument with a single page of parsed elements.
        """
        if not content or not content.strip():
            return self._empty_doc(filename)

        walker = _HTMLWalker()
        walker.feed(content)
        # Flush any trailing inline content
        walker._flush_paragraph()

        paragraphs = walker.paragraphs
        tables = walker.tables

        page = FormattedPage(
            page_number=0,
            width=_PAGE_WIDTH,
            height=_PAGE_HEIGHT,
            paragraphs=paragraphs,
            tables=tables,
        )

        # Build inventories
        font_inv: dict[str, int] = {}
        color_inv: dict[str, int] = {}
        style_inv: dict[str, int] = {}

        for para in paragraphs:
            style_inv[para.style] = style_inv.get(para.style, 0) + 1
            for line in para.lines:
                for span in line.spans:
                    f = span.font_family or span.font
                    font_inv[f] = font_inv.get(f, 0) + 1
                    hex_c = f"#{span.color:06X}"
                    color_inv[hex_c] = color_inv.get(hex_c, 0) + 1

        return FormattedDocument(
            filename=filename,
            pages=[page],
            font_inventory=font_inv,
            color_inventory=color_inv,
            style_inventory=style_inv,
        )

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
