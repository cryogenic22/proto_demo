"""
Tests for OmmlExtractor — OMML equation extraction from DOCX XML.

Uses inline OMML XML strings to verify plain-text and LaTeX conversion
for fractions, superscripts, subscripts, radicals, n-ary operators,
and delimiters.
"""

from __future__ import annotations

import pytest
from lxml import etree

from src.formatter.formula.ir import FormulaComplexity, FormulaSource
from src.formatter.formula.tools.omml_extractor import OmmlExtractor

OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _omath(inner_xml: str) -> etree._Element:
    """Build an <m:oMath> element from inner XML string."""
    xml = (
        f'<m:oMath xmlns:m="{OMML_NS}">'
        f"{inner_xml}"
        f"</m:oMath>"
    )
    return etree.fromstring(xml.encode())


def _wrap_paragraph(omath_xml: str) -> etree._Element:
    """Wrap oMath XML inside a container element (simulating w:p)."""
    xml = (
        f'<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
        f' xmlns:m="{OMML_NS}">'
        f"<m:oMath>{omath_xml}</m:oMath>"
        f"</w:p>"
    )
    return etree.fromstring(xml.encode())


class TestOmmlToPlainText:
    """Plain-text conversion tests."""

    def setup_method(self):
        self.extractor = OmmlExtractor()

    def test_fraction(self):
        """m:f → 'a/b'"""
        omath = _omath(
            "<m:f>"
            "  <m:num><m:r><m:t>a</m:t></m:r></m:num>"
            "  <m:den><m:r><m:t>b</m:t></m:r></m:den>"
            "</m:f>"
        )
        result = self.extractor.omml_to_plain_text(omath)
        assert result == "a/b"

    def test_superscript(self):
        """m:sSup → 'x^2'"""
        omath = _omath(
            "<m:sSup>"
            "  <m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "  <m:sup><m:r><m:t>2</m:t></m:r></m:sup>"
            "</m:sSup>"
        )
        result = self.extractor.omml_to_plain_text(omath)
        assert result == "x^2"

    def test_subscript(self):
        """m:sSub → 'x_i'"""
        omath = _omath(
            "<m:sSub>"
            "  <m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "  <m:sub><m:r><m:t>i</m:t></m:r></m:sub>"
            "</m:sSub>"
        )
        result = self.extractor.omml_to_plain_text(omath)
        assert result == "x_i"

    def test_sqrt(self):
        """m:rad → 'sqrt(x)'"""
        omath = _omath(
            "<m:rad>"
            "  <m:radPr><m:degHide m:val=\"1\"/></m:radPr>"
            "  <m:deg/>"
            "  <m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "</m:rad>"
        )
        result = self.extractor.omml_to_plain_text(omath)
        assert result == "sqrt(x)"

    def test_sqrt_with_degree(self):
        """m:rad with degree → 'root(3, x)'"""
        omath = _omath(
            "<m:rad>"
            "  <m:deg><m:r><m:t>3</m:t></m:r></m:deg>"
            "  <m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "</m:rad>"
        )
        result = self.extractor.omml_to_plain_text(omath)
        assert result == "root(3, x)"

    def test_nary_sum(self):
        """m:nary with ∑ → summation notation."""
        omath = _omath(
            "<m:nary>"
            "  <m:naryPr>"
            f'    <m:chr m:val="\u2211"/>'
            "  </m:naryPr>"
            "  <m:sub><m:r><m:t>i=1</m:t></m:r></m:sub>"
            "  <m:sup><m:r><m:t>n</m:t></m:r></m:sup>"
            "  <m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "</m:nary>"
        )
        result = self.extractor.omml_to_plain_text(omath)
        assert "\u2211" in result or "sum" in result.lower()
        assert "i=1" in result
        assert "n" in result

    def test_delimiter_parens(self):
        """m:d → '(x+y)'"""
        omath = _omath(
            "<m:d>"
            "  <m:e><m:r><m:t>x+y</m:t></m:r></m:e>"
            "</m:d>"
        )
        result = self.extractor.omml_to_plain_text(omath)
        assert result == "(x+y)"

    def test_simple_text_run(self):
        """m:r/m:t → literal text."""
        omath = _omath("<m:r><m:t>abc</m:t></m:r>")
        result = self.extractor.omml_to_plain_text(omath)
        assert result == "abc"

    def test_nested_fraction_superscript(self):
        """Nested: x^{a/b}"""
        omath = _omath(
            "<m:sSup>"
            "  <m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "  <m:sup>"
            "    <m:f>"
            "      <m:num><m:r><m:t>a</m:t></m:r></m:num>"
            "      <m:den><m:r><m:t>b</m:t></m:r></m:den>"
            "    </m:f>"
            "  </m:sup>"
            "</m:sSup>"
        )
        result = self.extractor.omml_to_plain_text(omath)
        assert "a/b" in result
        assert "x^" in result


class TestOmmlToLatex:
    """LaTeX conversion tests."""

    def setup_method(self):
        self.extractor = OmmlExtractor()

    def test_fraction(self):
        r"""m:f → \frac{a}{b}"""
        omath = _omath(
            "<m:f>"
            "  <m:num><m:r><m:t>a</m:t></m:r></m:num>"
            "  <m:den><m:r><m:t>b</m:t></m:r></m:den>"
            "</m:f>"
        )
        result = self.extractor.omml_to_latex(omath)
        assert result == r"\frac{a}{b}"

    def test_superscript(self):
        """m:sSup → x^{2}"""
        omath = _omath(
            "<m:sSup>"
            "  <m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "  <m:sup><m:r><m:t>2</m:t></m:r></m:sup>"
            "</m:sSup>"
        )
        result = self.extractor.omml_to_latex(omath)
        assert result == "x^{2}"

    def test_subscript(self):
        """m:sSub → x_{i}"""
        omath = _omath(
            "<m:sSub>"
            "  <m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "  <m:sub><m:r><m:t>i</m:t></m:r></m:sub>"
            "</m:sSub>"
        )
        result = self.extractor.omml_to_latex(omath)
        assert result == "x_{i}"

    def test_sqrt(self):
        r"""m:rad → \sqrt{x}"""
        omath = _omath(
            "<m:rad>"
            "  <m:radPr><m:degHide m:val=\"1\"/></m:radPr>"
            "  <m:deg/>"
            "  <m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "</m:rad>"
        )
        result = self.extractor.omml_to_latex(omath)
        assert result == r"\sqrt{x}"

    def test_sqrt_with_degree(self):
        r"""m:rad with degree → \sqrt[3]{x}"""
        omath = _omath(
            "<m:rad>"
            "  <m:deg><m:r><m:t>3</m:t></m:r></m:deg>"
            "  <m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "</m:rad>"
        )
        result = self.extractor.omml_to_latex(omath)
        assert result == r"\sqrt[3]{x}"

    def test_nary_sum(self):
        r"""m:nary with ∑ → \sum_{i=1}^{n} x"""
        omath = _omath(
            "<m:nary>"
            "  <m:naryPr>"
            f'    <m:chr m:val="\u2211"/>'
            "  </m:naryPr>"
            "  <m:sub><m:r><m:t>i=1</m:t></m:r></m:sub>"
            "  <m:sup><m:r><m:t>n</m:t></m:r></m:sup>"
            "  <m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "</m:nary>"
        )
        result = self.extractor.omml_to_latex(omath)
        assert r"\sum" in result
        assert "_{i=1}" in result
        assert "^{n}" in result

    def test_nary_integral(self):
        r"""m:nary with ∫ → \int"""
        omath = _omath(
            "<m:nary>"
            "  <m:naryPr>"
            f'    <m:chr m:val="\u222B"/>'
            "  </m:naryPr>"
            "  <m:sub><m:r><m:t>0</m:t></m:r></m:sub>"
            "  <m:sup><m:r><m:t>1</m:t></m:r></m:sup>"
            "  <m:e><m:r><m:t>f(x)dx</m:t></m:r></m:e>"
            "</m:nary>"
        )
        result = self.extractor.omml_to_latex(omath)
        assert r"\int" in result
        assert "_{0}" in result
        assert "^{1}" in result

    def test_delimiter_parens(self):
        r"""m:d → \left(x+y\right)"""
        omath = _omath(
            "<m:d>"
            "  <m:e><m:r><m:t>x+y</m:t></m:r></m:e>"
            "</m:d>"
        )
        result = self.extractor.omml_to_latex(omath)
        assert r"\left(" in result
        assert r"\right)" in result
        assert "x+y" in result

    def test_delimiter_brackets(self):
        r"""m:d with brackets → \left[...\right]"""
        omath = _omath(
            "<m:d>"
            "  <m:dPr>"
            f'    <m:begChr m:val="["/>'
            f'    <m:endChr m:val="]"/>'
            "  </m:dPr>"
            "  <m:e><m:r><m:t>a</m:t></m:r></m:e>"
            "</m:d>"
        )
        result = self.extractor.omml_to_latex(omath)
        assert r"\left[" in result
        assert r"\right]" in result


class TestExtractFromElement:
    """Tests for extract_from_element (full pipeline)."""

    def setup_method(self):
        self.extractor = OmmlExtractor()

    def test_returns_formatted_formula(self):
        """extract_from_element returns FormattedFormula with source=OMML."""
        para = _wrap_paragraph(
            "<m:r><m:t>E=mc</m:t></m:r>"
            "<m:sSup>"
            "  <m:e><m:r><m:t/></m:r></m:e>"
            "  <m:sup><m:r><m:t>2</m:t></m:r></m:sup>"
            "</m:sSup>"
        )
        results = self.extractor.extract_from_element(para)
        assert len(results) == 1
        formula = results[0]
        assert formula.source == FormulaSource.OMML
        assert formula.plain_text  # non-empty
        assert formula.latex  # non-empty

    def test_returns_multiple_formulas(self):
        """A paragraph with two oMath blocks yields two FormattedFormulas."""
        xml = (
            f'<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
            f' xmlns:m="{OMML_NS}">'
            f"<m:oMath><m:r><m:t>a</m:t></m:r></m:oMath>"
            f"<m:oMath><m:r><m:t>b</m:t></m:r></m:oMath>"
            f"</w:p>"
        )
        para = etree.fromstring(xml.encode())
        results = self.extractor.extract_from_element(para)
        assert len(results) == 2
        assert results[0].plain_text == "a"
        assert results[1].plain_text == "b"

    def test_no_omath_returns_empty(self):
        """A paragraph with no equations returns an empty list."""
        xml = (
            '<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:r><w:t>Hello world</w:t></w:r>"
            "</w:p>"
        )
        para = etree.fromstring(xml.encode())
        results = self.extractor.extract_from_element(para)
        assert results == []

    def test_fraction_has_structured_complexity(self):
        """Fractions should be classified as STRUCTURED complexity."""
        para = _wrap_paragraph(
            "<m:f>"
            "  <m:num><m:r><m:t>x</m:t></m:r></m:num>"
            "  <m:den><m:r><m:t>y</m:t></m:r></m:den>"
            "</m:f>"
        )
        results = self.extractor.extract_from_element(para)
        assert len(results) == 1
        assert results[0].complexity == FormulaComplexity.STRUCTURED

    def test_simple_text_has_inline_complexity(self):
        """A simple text run should be INLINE complexity."""
        para = _wrap_paragraph("<m:r><m:t>x+1</m:t></m:r>")
        results = self.extractor.extract_from_element(para)
        assert len(results) == 1
        assert results[0].complexity == FormulaComplexity.INLINE

    def test_omml_field_populated(self):
        """The omml field should contain the original OMML XML."""
        para = _wrap_paragraph("<m:r><m:t>abc</m:t></m:r>")
        results = self.extractor.extract_from_element(para)
        assert len(results) == 1
        assert "oMath" in results[0].omml


class TestGracefulDegradation:
    """Tests for graceful handling of malformed/unusual input."""

    def setup_method(self):
        self.extractor = OmmlExtractor()

    def test_empty_omath(self):
        """An empty oMath should return empty string, not crash."""
        omath = _omath("")
        plain = self.extractor.omml_to_plain_text(omath)
        latex = self.extractor.omml_to_latex(omath)
        assert plain == ""
        assert latex == ""

    def test_missing_fraction_children(self):
        """A fraction missing num or den should not crash."""
        omath = _omath(
            "<m:f>"
            "  <m:num><m:r><m:t>a</m:t></m:r></m:num>"
            "  <m:den/>"
            "</m:f>"
        )
        plain = self.extractor.omml_to_plain_text(omath)
        # Should produce "a/" — no crash
        assert "a" in plain

    def test_missing_superscript_exp(self):
        """Superscript with empty exponent should not crash."""
        omath = _omath(
            "<m:sSup>"
            "  <m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "  <m:sup/>"
            "</m:sSup>"
        )
        plain = self.extractor.omml_to_plain_text(omath)
        assert "x" in plain

    def test_nary_without_properties(self):
        """An m:nary without naryPr should default to summation."""
        omath = _omath(
            "<m:nary>"
            "  <m:sub><m:r><m:t>i</m:t></m:r></m:sub>"
            "  <m:sup><m:r><m:t>n</m:t></m:r></m:sup>"
            "  <m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "</m:nary>"
        )
        latex = self.extractor.omml_to_latex(omath)
        # Should default to \sum
        assert r"\sum" in latex

    def test_extract_from_non_element(self):
        """Passing a non-element should return empty list, not crash."""
        result = self.extractor.extract_from_element("not an element")
        assert result == []
