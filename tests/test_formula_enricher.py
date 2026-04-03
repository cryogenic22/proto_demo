"""
Tests for FormulaEnricher — validates formula detection is wired into the document IR.

Tests:
- Spans with formula text get span.formula set
- Formula types are correct (CHEMICAL for CO2, DOSING for mg/m2)
- Paragraphs with no formulas → all spans have formula=None
- Empty paragraphs → no crash
- Image paragraphs → skipped (no crash)
- End-to-end: create_pipeline().ingest(html, "html") → enriched spans
"""

from __future__ import annotations

import pytest

from src.formatter.extractor import (
    FormattedDocument,
    FormattedLine,
    FormattedPage,
    FormattedParagraph,
    FormattedSpan,
)
from src.formatter.formula.enricher import FormulaEnricher
from src.formatter.formula.factory import create_formula_system
from src.formatter.formula.ir import FormulaType
from src.formatter.pipeline.factory import create_pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_span(text: str) -> FormattedSpan:
    """Create a minimal FormattedSpan with just text."""
    return FormattedSpan(text=text, x0=0, y0=0, x1=0, y1=0)


def _make_paragraph(texts: list[str], style: str = "body") -> FormattedParagraph:
    """Create a paragraph with one line containing spans from texts."""
    spans = [_make_span(t) for t in texts]
    line = FormattedLine(spans=spans)
    return FormattedParagraph(lines=[line], style=style)


def _make_doc(paragraphs: list[FormattedParagraph]) -> FormattedDocument:
    """Wrap paragraphs in a single-page FormattedDocument."""
    page = FormattedPage(page_number=0, width=612, height=792, paragraphs=paragraphs)
    return FormattedDocument(pages=[page])


# ---------------------------------------------------------------------------
# Unit tests for FormulaEnricher
# ---------------------------------------------------------------------------

class TestFormulaEnricher:
    """Test the enricher maps formula detections to IR spans."""

    def setup_method(self):
        self.orchestrator = create_formula_system()
        self.enricher = FormulaEnricher(self.orchestrator)

    def test_co2_span_gets_formula(self):
        """CO2 in a span → span.formula is set with CHEMICAL type."""
        para = _make_paragraph(["CO2 levels are elevated"])
        doc = _make_doc([para])

        self.enricher.enrich(doc)

        span = doc.pages[0].paragraphs[0].lines[0].spans[0]
        assert span.formula is not None, "CO2 span should have formula set"
        assert span.formula.formula_type == FormulaType.CHEMICAL

    def test_dosing_mg_m2_span_gets_formula(self):
        """mg/m2 in a span → span.formula is set with DOSING type."""
        para = _make_paragraph(["200 mg/m2 daily"])
        doc = _make_doc([para])

        self.enricher.enrich(doc)

        span = doc.pages[0].paragraphs[0].lines[0].spans[0]
        assert span.formula is not None, "mg/m2 span should have formula set"
        assert span.formula.formula_type == FormulaType.DOSING

    def test_mixed_formulas_across_spans(self):
        """CO2 and mg/m2 in separate spans → each gets the right formula type."""
        para = _make_paragraph(["CO2", " levels at ", "200 mg/m2"])
        doc = _make_doc([para])

        self.enricher.enrich(doc)

        spans = doc.pages[0].paragraphs[0].lines[0].spans
        # First span: "CO2" → CHEMICAL
        assert spans[0].formula is not None
        assert spans[0].formula.formula_type == FormulaType.CHEMICAL
        # Middle span: " levels at " → no formula
        assert spans[1].formula is None
        # Third span: "200 mg/m2" → DOSING
        assert spans[2].formula is not None
        assert spans[2].formula.formula_type == FormulaType.DOSING

    def test_no_formula_paragraph(self):
        """Paragraph with no formulas → all spans have formula=None."""
        para = _make_paragraph(["This is plain text with no formulas."])
        doc = _make_doc([para])

        self.enricher.enrich(doc)

        for line in doc.pages[0].paragraphs[0].lines:
            for span in line.spans:
                assert span.formula is None

    def test_empty_paragraph_no_crash(self):
        """Empty paragraph (no lines) → no crash."""
        para = FormattedParagraph(lines=[], style="body")
        doc = _make_doc([para])

        # Should not raise
        self.enricher.enrich(doc)

    def test_image_paragraph_skipped(self):
        """Paragraphs with style='image' are skipped."""
        para = _make_paragraph(["data:image/png;base64,abc"], style="image")
        doc = _make_doc([para])

        self.enricher.enrich(doc)

        span = doc.pages[0].paragraphs[0].lines[0].spans[0]
        assert span.formula is None, "Image paragraph spans should not be enriched"

    def test_multi_line_paragraph(self):
        """Formula detection works across multi-line paragraphs."""
        line1 = FormattedLine(spans=[_make_span("Measure CO2")])
        line2 = FormattedLine(spans=[_make_span("at 200 mg/m2")])
        para = FormattedParagraph(lines=[line1, line2], style="body")
        doc = _make_doc([para])

        self.enricher.enrich(doc)

        # Line 1 span contains CO2
        assert doc.pages[0].paragraphs[0].lines[0].spans[0].formula is not None
        assert doc.pages[0].paragraphs[0].lines[0].spans[0].formula.formula_type == FormulaType.CHEMICAL
        # Line 2 span contains mg/m2
        assert doc.pages[0].paragraphs[0].lines[1].spans[0].formula is not None
        assert doc.pages[0].paragraphs[0].lines[1].spans[0].formula.formula_type == FormulaType.DOSING

    def test_whitespace_only_paragraph(self):
        """Paragraph with only whitespace → no crash, no formulas."""
        para = _make_paragraph(["   ", "  "])
        doc = _make_doc([para])

        self.enricher.enrich(doc)

        for line in doc.pages[0].paragraphs[0].lines:
            for span in line.spans:
                assert span.formula is None

    def test_multiple_pages(self):
        """Enrichment works across multiple pages."""
        para1 = _make_paragraph(["CO2 is measured"])
        para2 = _make_paragraph(["H2O is used"])
        page1 = FormattedPage(page_number=0, width=612, height=792, paragraphs=[para1])
        page2 = FormattedPage(page_number=1, width=612, height=792, paragraphs=[para2])
        doc = FormattedDocument(pages=[page1, page2])

        self.enricher.enrich(doc)

        assert doc.pages[0].paragraphs[0].lines[0].spans[0].formula is not None
        assert doc.pages[0].paragraphs[0].lines[0].spans[0].formula.formula_type == FormulaType.CHEMICAL
        assert doc.pages[1].paragraphs[0].lines[0].spans[0].formula is not None
        assert doc.pages[1].paragraphs[0].lines[0].spans[0].formula.formula_type == FormulaType.CHEMICAL


class TestFormulaEnricherEndToEnd:
    """End-to-end: create_pipeline().ingest() → enriched spans."""

    def test_html_ingest_enriches_co2(self):
        """Ingest HTML with CO2 → spans have formula annotations."""
        pipeline = create_pipeline()
        # Use separate HTML elements so the ingestor produces distinct spans
        doc = pipeline.ingest(
            "<p><span>CO2 levels</span> at <span>200 mg/m2</span></p>",
            "html",
        )

        # Find spans with formulas
        formula_spans = []
        for page in doc.pages:
            for para in page.paragraphs:
                for line in para.lines:
                    for span in line.spans:
                        if span.formula is not None:
                            formula_spans.append(span)

        assert len(formula_spans) > 0, "Expected at least one formula-enriched span"

        # At minimum we expect CHEMICAL for CO2
        formula_types = {s.formula.formula_type for s in formula_spans}
        assert FormulaType.CHEMICAL in formula_types, "Expected CHEMICAL formula for CO2"

    def test_html_ingest_plain_text_no_formulas(self):
        """Ingest HTML without formulas → no span.formula set."""
        pipeline = create_pipeline()
        doc = pipeline.ingest("<p>Hello world</p>", "html")

        for page in doc.pages:
            for para in page.paragraphs:
                for line in para.lines:
                    for span in line.spans:
                        assert span.formula is None

    def test_text_ingest_enriches_formulas(self):
        """Ingest plain text with AUC0-inf → formula annotation."""
        pipeline = create_pipeline()
        doc = pipeline.ingest("The AUC0-inf was measured", "text")

        formula_spans = [
            span
            for page in doc.pages
            for para in page.paragraphs
            for line in para.lines
            for span in line.spans
            if span.formula is not None
        ]

        assert len(formula_spans) > 0, "Expected formula-enriched span for AUC0-inf"
        assert formula_spans[0].formula.formula_type == FormulaType.PK

    def test_pipeline_with_formula_disabled(self):
        """create_pipeline(formula_orchestrator=False) → no formula enrichment."""
        pipeline = create_pipeline(formula_orchestrator=False)
        assert pipeline.formula_orchestrator is None

        doc = pipeline.ingest("<p>CO2 levels</p>", "html")
        for page in doc.pages:
            for para in page.paragraphs:
                for line in para.lines:
                    for span in line.spans:
                        assert span.formula is None
