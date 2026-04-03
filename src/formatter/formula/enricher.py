"""
Formula Enricher — post-ingestion step that maps formula detections to IR spans.

The enricher runs formula detection on each paragraph's full text, then maps
the detected formula offsets back to individual FormattedSpan objects. This
bridges the gap between the formula orchestrator (which works on plain text)
and the document IR (which stores formatting per-span).

Design:
- Post-processing step, runs AFTER any ingestor produces a FormattedDocument
- Does NOT modify ingestors or renderers
- If no FormulaOrchestrator is provided, this is a no-op
- Handles edge cases: empty paragraphs, image paragraphs, zero-length spans
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.formatter.extractor import FormattedDocument, FormattedParagraph

if TYPE_CHECKING:
    from src.formatter.formula.orchestrator import FormulaOrchestrator

logger = logging.getLogger(__name__)


class FormulaEnricher:
    """Post-ingestion: runs formula detection on document text, maps results to spans."""

    def __init__(self, orchestrator: FormulaOrchestrator):
        self._orchestrator = orchestrator

    def enrich(self, doc: FormattedDocument) -> FormattedDocument:
        """Run formula detection on all paragraphs and annotate spans.

        Walks every paragraph in every page. For each paragraph, detects
        formulas in the full text and maps them back to the underlying
        FormattedSpan objects by tracking cumulative character offsets.

        Args:
            doc: The FormattedDocument to enrich (mutated in place).

        Returns:
            The same FormattedDocument with span.formula populated where detected.
        """
        for page in doc.pages:
            for para in page.paragraphs:
                self._enrich_paragraph(para)
        return doc

    def _enrich_paragraph(self, para: FormattedParagraph) -> None:
        """Detect formulas in paragraph text and map to spans.

        Algorithm:
        1. Skip non-text paragraphs (e.g., image style).
        2. Collect all spans across all lines, building a full-text string
           with spaces between lines (matching FormattedParagraph.text property).
        3. Run formula detection on the full text.
        4. Walk spans tracking cumulative char offset; when a span's character
           range overlaps a detected formula, set span.formula.
        """
        # Skip image paragraphs and empty paragraphs
        if para.style == "image":
            return
        if not para.lines:
            return

        # Collect all spans in order, with their offsets in the paragraph text.
        # FormattedParagraph.text joins lines with " " (space), so we replicate
        # that logic to get correct offsets.
        all_spans = []
        offset = 0
        for line_idx, line in enumerate(para.lines):
            if line_idx > 0:
                # Account for the space between lines
                offset += 1
            for span in line.spans:
                span_start = offset
                span_end = offset + len(span.text)
                all_spans.append((span, span_start, span_end))
                offset = span_end

        if not all_spans:
            return

        # Build full paragraph text (same as para.text)
        full_text = para.text
        if not full_text.strip():
            return

        # Run formula detection
        try:
            detected = self._orchestrator.process_text(full_text)
        except Exception as e:
            logger.debug("Formula detection failed for paragraph: %s", e)
            return

        if not detected:
            return

        # Map detected formula spans to IR spans via offset overlap
        for span, span_start, span_end in all_spans:
            if span_end <= span_start:
                # Zero-length span, skip
                continue
            for det in detected:
                # Check overlap: the span range [span_start, span_end) overlaps
                # the detection range [det.start, det.end) if:
                #   span_start < det.end AND det.start < span_end
                if span_start < det.end and det.start < span_end:
                    span.formula = det.formula
                    break  # First matching detection wins for this span
