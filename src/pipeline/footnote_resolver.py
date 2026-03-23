"""
Footnote Resolver — anchors footnote markers to specific cells.

Before the main extraction LLM sees the table output, this module:
1. Detects all superscript markers in cells
2. Matches each marker to its definition
3. Classifies footnote type (conditional, exception, etc.)
4. Re-annotates each affected cell with footnote content as metadata
"""

from __future__ import annotations

import re
import logging

from src.models.schema import (
    CellRef,
    ExtractedCell,
    FootnoteType,
    ResolvedFootnote,
)

logger = logging.getLogger(__name__)

# Patterns for classifying footnote types
_CONDITIONAL_PATTERNS = [
    r"\bonly\s+if\b", r"\bif\s+\w+", r"\bwhen\b",
    r"\bbased\s+on\b", r"\bper\s+investigator\b",
    r"\bas\s+needed\b", r"\bprn\b", r"\bclinically\s+indicated\b",
    r"\bat\s+the\s+discretion\b",
]
_EXCEPTION_PATTERNS = [
    r"\bexcept\b", r"\bunless\b", r"\bnot\s+required\b",
    r"\bexcluding\b", r"\bexcept\s+at\b",
]
_REFERENCE_PATTERNS = [
    r"\bsee\s+section\b", r"\brefer\s+to\b", r"\bsee\s+table\b",
    r"\bsee\s+appendix\b",
]
_FREQUENCY_MODIFIER_PATTERNS = [
    r"\bcycles?\s+\d+\s*[-–]\s*\d+\s+only\b",      # "Cycles 1-2 only"
    r"\bfirst\s+\d+\s+cycles?\s+only\b",            # "first 3 cycles only"
    r"\bthen\s+(?:only\s+)?(?:on\s+)?day\s+1\b",    # "then Day 1 only"
    r"\b(?:every|q)\s*\d+\s*(?:cycles?|visits?)\b",  # "every 2 cycles"
    r"\breduced\s+frequency\s+after\b",              # "reduced frequency after"
    r"\bevery\s+other\s+(?:visit|cycle)\b",          # "every other visit"
    r"\bDay\s+\d+\s+and\s+Day\s+\d+\s+of\b",        # "Day 1 and Day 8 of"
    r"\bonly\s+during\s+(?:cycle|induction|maintenance)\b",
]

_CONDITIONAL_RE = re.compile("|".join(_CONDITIONAL_PATTERNS), re.IGNORECASE)
_EXCEPTION_RE = re.compile("|".join(_EXCEPTION_PATTERNS), re.IGNORECASE)
_REFERENCE_RE = re.compile("|".join(_REFERENCE_PATTERNS), re.IGNORECASE)
_FREQUENCY_MODIFIER_RE = re.compile("|".join(_FREQUENCY_MODIFIER_PATTERNS), re.IGNORECASE)


class FootnoteResolver:
    """Resolves footnote markers in extracted cells to their definitions."""

    def resolve(
        self,
        cells: list[ExtractedCell],
        footnote_text: dict[str, str],
    ) -> tuple[list[ExtractedCell], list[ResolvedFootnote]]:
        """
        Resolve footnotes and attach them to cells.

        Args:
            cells: Extracted cells, some with footnote_markers.
            footnote_text: Mapping of marker → footnote text
                           (e.g., {"a": "Only if QTc > 450ms"}).

        Returns:
            Tuple of (updated cells, list of ResolvedFootnote objects).
        """
        # Build marker → list of cells mapping
        marker_to_cells: dict[str, list[CellRef]] = {}
        for cell in cells:
            for marker in cell.footnote_markers:
                if marker not in marker_to_cells:
                    marker_to_cells[marker] = []
                marker_to_cells[marker].append(CellRef(row=cell.row, col=cell.col))

        # Create ResolvedFootnote objects for markers that have definitions
        footnotes: list[ResolvedFootnote] = []
        resolved_lookup: dict[str, str] = {}

        for marker in sorted(marker_to_cells.keys()):
            cell_refs = marker_to_cells[marker]
            if marker in footnote_text:
                text = footnote_text[marker]
                fn_type = self._classify_footnote(text)
                footnotes.append(ResolvedFootnote(
                    marker=marker,
                    text=text,
                    applies_to=cell_refs,
                    footnote_type=fn_type,
                ))
                resolved_lookup[marker] = text
            else:
                logger.warning(
                    f"Footnote marker '{marker}' found in {len(cell_refs)} cells "
                    f"but no definition available"
                )

        # Update cells with resolved footnote text
        updated_cells: list[ExtractedCell] = []
        for cell in cells:
            resolved = [
                resolved_lookup[m]
                for m in cell.footnote_markers
                if m in resolved_lookup
            ]
            updated_cells.append(cell.model_copy(update={
                "resolved_footnotes": resolved,
            }))

        logger.info(
            f"Resolved {len(footnotes)} footnotes across "
            f"{sum(len(fn.applies_to) for fn in footnotes)} cell references"
        )
        return updated_cells, footnotes

    @staticmethod
    def _classify_footnote(text: str) -> FootnoteType:
        """Classify a footnote based on its text content.

        Order matters: FREQUENCY_MODIFIER before CONDITIONAL because
        'Cycles 1-2 only, then Day 1 only' is frequency, not conditional.
        """
        if _EXCEPTION_RE.search(text):
            return FootnoteType.EXCEPTION
        # Check FREQUENCY_MODIFIER before CONDITIONAL (more specific)
        if _FREQUENCY_MODIFIER_RE.search(text):
            return FootnoteType.FREQUENCY_MODIFIER
        if _CONDITIONAL_RE.search(text):
            return FootnoteType.CONDITIONAL
        if _REFERENCE_RE.search(text):
            return FootnoteType.REFERENCE
        return FootnoteType.CLARIFICATION
