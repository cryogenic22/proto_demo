"""
Tests for PK equation extraction and rendering pipeline.

Validates:
- LaTeX -> MathML rendering via MathMLFormulaRenderer
- MathML contains proper <math> and <mfrac> tags for fractions
- Full pipeline: FormattedDocument with formula spans -> HTML with MathML
- DOCX rendering of formula-bearing documents produces valid output
- HTML output saved to output/pk_formula_test.html for visual inspection
"""

from __future__ import annotations

import os
import zipfile

import pytest

from src.formatter.extractor import (
    FormattedDocument,
    FormattedLine,
    FormattedPage,
    FormattedParagraph,
    FormattedSpan,
)
from src.formatter.formula.ir import (
    FormattedFormula,
    FormulaComplexity,
    FormulaSource,
    FormulaType,
)
from src.formatter.formula.tools.renderers import MathMLFormulaRenderer
from src.formatter.render.html_renderer import HTMLRenderer
from src.formatter.docx_renderer import DOCXRenderer


# ---------------------------------------------------------------------------
# PK formula test data
# ---------------------------------------------------------------------------

PK_FORMULAS = [
    # (name, latex, expected_plain)
    ("Elimination rate constant", r"k_e = \frac{CL}{V_d}", "ke = CL/Vd"),
    ("Half-life", r"t_{1/2} = \frac{0.693}{k_e}", "t1/2 = 0.693/ke"),
    ("Initial concentration", r"C_p = \frac{D}{V_d}", "Cp = D/Vd"),
    ("Single dose plasma", r"C_p = C_p^0 \cdot e^{-k_e \cdot t}", "Cp = Cp0 * e^(-ke*t)"),
    (
        "Oral single dose",
        r"C_p = \frac{F \cdot D \cdot k_a}{V_d(k_a - k_e)} \cdot (e^{-k_e \cdot t} - e^{-k_a \cdot t})",
        "Cp = F*D*ka / Vd(ka-ke) * (e^(-ke*t) - e^(-ka*t))",
    ),
    ("Steady state", r"C_{ss} = \frac{F \cdot D}{CL \cdot \tau}", "Css = F*D/(CL*tau)"),
    ("Clearance", r"CL = \frac{Dose \cdot F}{AUC}", "CL = Dose*F/AUC"),
    (
        "Trough multiple dose",
        r"C_{min} = \frac{C_p^0 \cdot e^{-k_e \cdot \tau}}{1 - e^{-k_e \cdot \tau}}",
        "Cmin = Cp0*e^(-ke*tau) / (1 - e^(-ke*tau))",
    ),
]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_span(text: str, formula: FormattedFormula | None = None) -> FormattedSpan:
    """Create a minimal FormattedSpan."""
    return FormattedSpan(text=text, x0=0, y0=0, x1=0, y1=0, formula=formula)


def _make_paragraph(spans: list[FormattedSpan], style: str = "body") -> FormattedParagraph:
    line = FormattedLine(spans=spans)
    return FormattedParagraph(lines=[line], style=style)


def _make_doc(paragraphs: list[FormattedParagraph]) -> FormattedDocument:
    page = FormattedPage(page_number=0, width=612, height=792, paragraphs=paragraphs)
    return FormattedDocument(pages=[page])


# ---------------------------------------------------------------------------
# Tests: MathML rendering of individual PK formulas
# ---------------------------------------------------------------------------

class TestMathMLRendering:
    """Test LaTeX -> MathML conversion for PK equations."""

    def setup_method(self):
        self.renderer = MathMLFormulaRenderer()

    def test_renderer_is_available(self):
        """latex2mathml must be installed for MathML rendering."""
        assert self.renderer._available, "latex2mathml not installed — MathML rendering disabled"

    @pytest.mark.parametrize(
        "name, latex, expected_plain",
        PK_FORMULAS,
        ids=[f[0] for f in PK_FORMULAS],
    )
    def test_mathml_populated_for_pk_formula(self, name, latex, expected_plain):
        """Each PK formula should produce MathML with <math> tags."""
        formula = FormattedFormula(
            latex=latex,
            plain_text=expected_plain,
            formula_type=FormulaType.PK,
            complexity=FormulaComplexity.STRUCTURED,
            source=FormulaSource.MANUAL,
            confidence=1.0,
        )

        result = self.renderer.render(formula)

        assert result.mathml, f"MathML not generated for {name}: {latex}"
        assert "<math" in result.mathml, f"Missing <math> tag for {name}"

    @pytest.mark.parametrize(
        "name, latex, expected_plain",
        [f for f in PK_FORMULAS if r"\frac" in f[1]],
        ids=[f[0] for f in PK_FORMULAS if r"\frac" in f[1]],
    )
    def test_fraction_formulas_have_mfrac(self, name, latex, expected_plain):
        """Fraction formulas should produce <mfrac> in MathML."""
        formula = FormattedFormula(
            latex=latex,
            plain_text=expected_plain,
            formula_type=FormulaType.PK,
            complexity=FormulaComplexity.STRUCTURED,
            source=FormulaSource.MANUAL,
        )

        result = self.renderer.render(formula)

        assert "<mfrac>" in result.mathml, (
            f"Missing <mfrac> for fraction formula {name}: {latex}"
        )


# ---------------------------------------------------------------------------
# Tests: Full HTML pipeline with MathML in spans
# ---------------------------------------------------------------------------

class TestHTMLPipelineWithMathML:
    """Build a FormattedDocument with formula spans and render to HTML."""

    def setup_method(self):
        self.mathml_renderer = MathMLFormulaRenderer()
        self.html_renderer = HTMLRenderer()

    def _build_pk_document(self) -> FormattedDocument:
        """Build a FormattedDocument containing all PK formulas as spans."""
        paragraphs = []

        # Title
        title_span = _make_span("Pharmacokinetic Equations")
        title_para = _make_paragraph([title_span], style="heading1")
        paragraphs.append(title_para)

        # One paragraph per formula
        for name, latex, plain in PK_FORMULAS:
            formula = FormattedFormula(
                latex=latex,
                plain_text=plain,
                formula_type=FormulaType.PK,
                complexity=FormulaComplexity.STRUCTURED,
                source=FormulaSource.MANUAL,
                confidence=1.0,
            )
            # Render MathML
            self.mathml_renderer.render(formula)

            # Build label + formula span
            label_span = _make_span(f"{name}: ")
            formula_span = _make_span(plain, formula=formula)
            para = _make_paragraph([label_span, formula_span])
            paragraphs.append(para)

        return _make_doc(paragraphs)

    def test_html_output_contains_math_tags(self):
        """Rendered HTML should contain MathML <math> tags."""
        doc = self._build_pk_document()
        html = self.html_renderer.render(doc)

        assert "<math" in html, "HTML output missing MathML <math> tags"

    def test_html_output_contains_mfrac(self):
        """Rendered HTML should contain <mfrac> for fraction formulas."""
        doc = self._build_pk_document()
        html = self.html_renderer.render(doc)

        assert "<mfrac>" in html, "HTML output missing <mfrac> for stacked fractions"

    def test_each_formula_has_math_tag(self):
        """Each formula paragraph should have a <math> element."""
        doc = self._build_pk_document()
        html = self.html_renderer.render(doc)

        # Count <math occurrences — should have one per formula
        math_count = html.count("<math")
        assert math_count >= len(PK_FORMULAS), (
            f"Expected >= {len(PK_FORMULAS)} <math> tags, found {math_count}"
        )

    def test_save_html_to_output(self):
        """Save rendered HTML to output/pk_formula_test.html for visual inspection."""
        doc = self._build_pk_document()
        html_body = self.html_renderer.render(doc)

        # Wrap in full HTML document with charset for browser viewing
        full_html = (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="UTF-8">\n'
            "  <title>PK Formula Test</title>\n"
            "  <style>\n"
            "    body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; }\n"
            "    math { font-size: 1.2em; }\n"
            "    p { margin: 12px 0; line-height: 1.6; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            f"{html_body}\n"
            "</body>\n"
            "</html>"
        )

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        out_path = os.path.join(OUTPUT_DIR, "pk_formula_test.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(full_html)

        assert os.path.exists(out_path), "HTML output file not created"
        assert os.path.getsize(out_path) > 100, "HTML output file too small"


# ---------------------------------------------------------------------------
# Tests: DOCX rendering
# ---------------------------------------------------------------------------

class TestDOCXRendering:
    """Render a PK formula document to DOCX and verify validity."""

    def setup_method(self):
        self.mathml_renderer = MathMLFormulaRenderer()
        self.docx_renderer = DOCXRenderer()

    def _build_pk_document(self) -> FormattedDocument:
        paragraphs = []

        title_span = _make_span("Pharmacokinetic Equations")
        title_para = _make_paragraph([title_span], style="heading1")
        paragraphs.append(title_para)

        for name, latex, plain in PK_FORMULAS:
            formula = FormattedFormula(
                latex=latex,
                plain_text=plain,
                formula_type=FormulaType.PK,
                complexity=FormulaComplexity.STRUCTURED,
                source=FormulaSource.MANUAL,
                confidence=1.0,
            )
            self.mathml_renderer.render(formula)

            label_span = _make_span(f"{name}: ")
            formula_span = _make_span(plain, formula=formula)
            para = _make_paragraph([label_span, formula_span])
            paragraphs.append(para)

        return _make_doc(paragraphs)

    def test_docx_renders_without_error(self):
        """DOCX rendering of formula document should not crash."""
        doc = self._build_pk_document()
        docx_bytes = self.docx_renderer.render(doc)

        assert docx_bytes is not None
        assert len(docx_bytes) > 0

    def test_docx_is_valid_zip(self):
        """DOCX output should be a valid ZIP archive (OOXML)."""
        import io

        doc = self._build_pk_document()
        docx_bytes = self.docx_renderer.render(doc)

        buf = io.BytesIO(docx_bytes)
        assert zipfile.is_zipfile(buf), "DOCX output is not a valid ZIP file"

    def test_docx_contains_content_types(self):
        """DOCX should contain [Content_Types].xml (valid OOXML package)."""
        import io

        doc = self._build_pk_document()
        docx_bytes = self.docx_renderer.render(doc)

        buf = io.BytesIO(docx_bytes)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert "[Content_Types].xml" in names, (
                "DOCX missing [Content_Types].xml — invalid package"
            )

    def test_docx_save_to_output(self):
        """Save DOCX to output directory for manual inspection."""
        doc = self._build_pk_document()
        docx_bytes = self.docx_renderer.render(doc)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        out_path = os.path.join(OUTPUT_DIR, "pk_formula_test.docx")
        with open(out_path, "wb") as f:
            f.write(docx_bytes)

        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 1000, "DOCX file unexpectedly small"


# ---------------------------------------------------------------------------
# Tests: OpenAI Vision OCR graceful degradation
# ---------------------------------------------------------------------------

class TestOpenAIVisionOCRGraceful:
    """OpenAI Vision OCR should degrade gracefully with missing deps/keys."""

    def test_no_api_key_returns_none(self):
        """Without API key, recognize() should return None."""
        from src.formatter.formula.tools.ocr_backends import OpenAIVisionOCR

        ocr = OpenAIVisionOCR(api_key="")
        # Force _available to False (no env key expected in CI)
        ocr._available = False
        result = ocr.recognize(b"\x89PNG\r\n\x1a\n fake image data")
        assert result is None

    def test_metadata_correct(self):
        """Metadata should report correct name and priority."""
        from src.formatter.formula.tools.ocr_backends import OpenAIVisionOCR

        ocr = OpenAIVisionOCR(api_key="")
        meta = ocr.metadata()
        assert meta.name == "openai_vision_ocr"
        assert meta.priority == 75
        assert meta.requires_network is True
        assert meta.timeout_ms == 30000
