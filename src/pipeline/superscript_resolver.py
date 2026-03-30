"""
Superscript/Subscript Resolver — cross-checks VLM output with PyMuPDF font data.

The VLM extracts cell text as flat strings (e.g., "CO2", "X4", "HbA1c").
PyMuPDF can detect the actual font flags (superscript bit 0) and font size
(subscript = significantly smaller). This module reconciles the two.

Usage:
    resolver = SuperscriptResolver(pdf_bytes)
    annotated = resolver.annotate_cell("CO2", page=67, x=150, y=200)
    # Returns: "CO<sub>2</sub>" if PyMuPDF confirms subscript
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Known chemical/scientific subscript patterns
_SUBSCRIPT_PATTERNS = [
    (re.compile(r'CO2(?=\b|\s|$)'), 'CO<sub>2</sub>'),
    (re.compile(r'H2O(?=\b|\s|$)'), 'H<sub>2</sub>O'),
    (re.compile(r'(?<![A-Z])O2(?=\b|\s|$)'), 'O<sub>2</sub>'),
    (re.compile(r'(?<![A-Z])N2(?=\b|\s|$)'), 'N<sub>2</sub>'),
    (re.compile(r'HbA1c', re.IGNORECASE), 'HbA<sub>1c</sub>'),
    (re.compile(r'PO4(?=\b|\s|$)'), 'PO<sub>4</sub>'),
    (re.compile(r'SO4(?=\b|\s|$)'), 'SO<sub>4</sub>'),
    (re.compile(r'NH4(?=\b|\s|$)'), 'NH<sub>4</sub>'),
]

# Known superscript patterns (footnote markers, exponents)
_SUPERSCRIPT_FOOTNOTE_RE = re.compile(
    r'(?<=[A-Za-z\u2713\u2714])([a-g\d])$'  # Trailing single letter/digit after text
)

# Exponent patterns
_EXPONENT_PATTERNS = [
    (re.compile(r'(\d+)\s*x\s*10(\d+)'), r'\1 × 10<sup>\2</sup>'),
    (re.compile(r'10(\d+)\s*cells', re.IGNORECASE), r'10<sup>\1</sup> cells'),
    (re.compile(r'(\d+)mm2(?=\b|\s|$)'), r'\1mm<sup>2</sup>'),
    (re.compile(r'(\d+)cm2(?=\b|\s|$)'), r'\1cm<sup>2</sup>'),
    (re.compile(r'mg/m2(?=\b|\s|$)'), 'mg/m<sup>2</sup>'),
]


def parse_vlm_markers(text: str) -> str:
    """Parse ^{} and _{} markers from VLM output into HTML sup/sub tags.

    The VLM is prompted to output superscript as ^{text} and subscript as _{text}.
    This function converts those markers to proper HTML.

    Examples:
        "X^{a}" → "X<sup>a</sup>"
        "CO_{2}" → "CO<sub>2</sub>"
        "10^{6} cells/mL" → "10<sup>6</sup> cells/mL"
        "HbA_{1c}" → "HbA<sub>1c</sub>"
    """
    if "^{" not in text and "_{" not in text:
        return text

    # Superscript: ^{content}
    result = re.sub(r'\^\{([^}]+)\}', r'<sup>\1</sup>', text)
    # Subscript: _{content}
    result = re.sub(r'_\{([^}]+)\}', r'<sub>\1</sub>', result)

    return result


class SuperscriptResolver:
    """Cross-checks VLM text output with PyMuPDF font data for sub/superscript."""

    def __init__(self, pdf_bytes: bytes | None = None):
        self._pdf_bytes = pdf_bytes
        self._page_spans: dict[int, list[dict]] = {}  # Cached per page

    def annotate_text(self, text: str, page: int | None = None) -> str:
        """Annotate a text string with <sup>/<sub> tags.

        Strategy:
        1. Check PyMuPDF font flags if PDF available (most accurate)
        2. Apply known chemical/scientific patterns (deterministic)
        3. Apply exponent patterns (deterministic)
        """
        if not text or len(text) < 2:
            return text

        result = text

        # Strategy 1: PyMuPDF cross-check (if PDF available and page known)
        if self._pdf_bytes and page is not None:
            result = self._annotate_from_pymupdf(result, page)

        # Strategy 2: Known chemical patterns
        for pattern, replacement in _SUBSCRIPT_PATTERNS:
            result = pattern.sub(replacement, result)

        # Strategy 3: Exponent patterns
        for pattern, replacement in _EXPONENT_PATTERNS:
            result = pattern.sub(replacement, result)

        return result

    def annotate_cell_value(self, value: str) -> str:
        """Lightweight annotation for SoA cell values.

        Only applies the deterministic patterns (no PDF lookup needed).
        For cell values like "X4", we DON'T annotate — the budget
        calculator handles footnote stripping separately.
        """
        if not value or len(value) < 3:
            return value

        result = value
        for pattern, replacement in _SUBSCRIPT_PATTERNS:
            result = pattern.sub(replacement, result)
        for pattern, replacement in _EXPONENT_PATTERNS:
            result = pattern.sub(replacement, result)

        return result

    def _annotate_from_pymupdf(self, text: str, page: int) -> str:
        """Use PyMuPDF font flags to detect actual super/subscript."""
        if page not in self._page_spans:
            self._load_page_spans(page)

        spans = self._page_spans.get(page, [])
        if not spans:
            return text

        # Find spans that match text content and have super/subscript flags
        for span in spans:
            span_text = span.get("text", "").strip()
            if not span_text or span_text not in text:
                continue

            flags = span.get("flags", 0)
            size = span.get("size", 10)

            if flags & 1:  # Superscript flag
                text = text.replace(span_text, f"<sup>{span_text}</sup>", 1)
            elif size < 7 and len(span_text) <= 3:
                # Small font, short text — likely subscript
                text = text.replace(span_text, f"<sub>{span_text}</sub>", 1)

        return text

    def _load_page_spans(self, page: int) -> None:
        """Load all text spans from a PDF page."""
        try:
            import fitz
            doc = fitz.open(stream=self._pdf_bytes, filetype="pdf")
            if page < doc.page_count:
                pg = doc[page]
                spans = []
                for block in pg.get_text("dict")["blocks"]:
                    if "lines" not in block:
                        continue
                    for line in block["lines"]:
                        for span in line["spans"]:
                            spans.append({
                                "text": span["text"],
                                "flags": span["flags"],
                                "size": span["size"],
                                "font": span.get("font", ""),
                            })
                self._page_spans[page] = spans
            doc.close()
        except Exception as e:
            logger.debug(f"Failed to load page spans for page {page}: {e}")
            self._page_spans[page] = []
