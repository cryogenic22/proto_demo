"""
Tests for the Tier 3 StructuredParser formula detector.

Verifies: partial derivatives, integrals, factorials, combinations,
summations, product notation, limits, named pharma formulas,
PK differential equations, no false positives, and factory registration.
"""

from __future__ import annotations

import pytest

from src.formatter.formula.ir import (
    FormulaComplexity,
    FormulaSource,
    FormulaType,
)
from src.formatter.formula.tools.structured_parser import StructuredParser


class TestStructuredParserMetadata:
    """Verify the tool's registry metadata."""

    def setup_method(self):
        self.parser = StructuredParser()

    def test_metadata_name(self):
        assert self.parser.metadata().name == "structured_parser"

    def test_metadata_complexity(self):
        assert FormulaComplexity.STRUCTURED in self.parser.metadata().supported_complexities

    def test_metadata_source_is_parser(self):
        """All detections should use FormulaSource.PARSER."""
        spans = self.parser.detect("n!")
        assert len(spans) >= 1
        assert spans[0].formula.source == FormulaSource.PARSER

    def test_metadata_complexity_is_structured(self):
        """All detections should use FormulaComplexity.STRUCTURED."""
        spans = self.parser.detect("n!")
        assert len(spans) >= 1
        assert spans[0].formula.complexity == FormulaComplexity.STRUCTURED


class TestPartialDerivatives:
    """Category 1: Partial derivatives."""

    def setup_method(self):
        self.parser = StructuredParser()

    def test_second_order_partial(self):
        spans = self.parser.detect("d2y/dx2")
        assert len(spans) >= 1
        s = spans[0]
        assert "\\partial^2 y" in s.formula.latex
        assert "\\partial x^2" in s.formula.latex
        assert s.formula.plain_text == "d2y/dx2"

    def test_first_order_partial_df_dt(self):
        spans = self.parser.detect("df/dt")
        assert len(spans) >= 1
        s = spans[0]
        assert "\\partial f" in s.formula.latex
        assert "\\partial t" in s.formula.latex

    def test_first_order_ordinary_dC_dt(self):
        """dC/dt should use ordinary d (not partial) for PK context."""
        spans = self.parser.detect("dC/dt")
        assert len(spans) >= 1
        s = spans[0]
        assert "dC" in s.formula.latex or "d C" in s.formula.latex
        # Should NOT use partial symbol for uppercase + t pattern
        assert "\\partial C" not in s.formula.latex

    def test_positions_correct(self):
        text = "We compute d2y/dx2 here"
        spans = self.parser.detect(text)
        assert len(spans) >= 1
        s = spans[0]
        assert text[s.start:s.end] == s.original_text


class TestIntegrals:
    """Category 2: Integrals."""

    def setup_method(self):
        self.parser = StructuredParser()

    def test_integral_with_bounds(self):
        spans = self.parser.detect("int_0^inf f(x)dx")
        assert len(spans) >= 1
        s = spans[0]
        assert "\\int" in s.formula.latex
        assert "\\infty" in s.formula.latex
        assert "dx" in s.formula.latex

    def test_integral_unicode(self):
        spans = self.parser.detect("\u222b f(x)dx")
        assert len(spans) >= 1
        assert "\\int" in spans[0].formula.latex

    def test_integral_keyword(self):
        spans = self.parser.detect("integral_0^1 g(t)dt")
        assert len(spans) >= 1
        assert "\\int" in spans[0].formula.latex

    def test_latex_has_both_fields(self):
        spans = self.parser.detect("int_0^inf f(x)dx")
        assert len(spans) >= 1
        s = spans[0]
        assert s.formula.latex != ""
        assert s.formula.plain_text != ""


class TestFactorials:
    """Category 3: Factorials."""

    def setup_method(self):
        self.parser = StructuredParser()

    def test_simple_factorial(self):
        spans = self.parser.detect("n!")
        assert len(spans) >= 1
        assert spans[0].formula.latex == "n!"

    def test_numeric_factorial(self):
        spans = self.parser.detect("5!")
        assert len(spans) >= 1
        assert spans[0].formula.latex == "5!"

    def test_paren_factorial(self):
        spans = self.parser.detect("(n-k)!")
        assert len(spans) >= 1
        s = spans[0]
        assert "(n-k)!" in s.formula.latex

    def test_factorial_type(self):
        spans = self.parser.detect("k!")
        assert len(spans) >= 1
        assert spans[0].formula.formula_type == FormulaType.MATHEMATICAL


class TestCombinationsPermutations:
    """Category 4: Combinations and permutations."""

    def setup_method(self):
        self.parser = StructuredParser()

    def test_c_function(self):
        spans = self.parser.detect("C(n,k)")
        assert len(spans) >= 1
        s = spans[0]
        assert "\\binom{n}{k}" == s.formula.latex

    def test_c_function_with_spaces(self):
        spans = self.parser.detect("C( n , k )")
        assert len(spans) >= 1
        assert "\\binom" in spans[0].formula.latex

    def test_ncr(self):
        spans = self.parser.detect("nCr")
        assert len(spans) >= 1
        assert "\\binom" in spans[0].formula.latex

    def test_npr(self):
        spans = self.parser.detect("nPr")
        assert len(spans) >= 1
        s = spans[0]
        assert "P" in s.formula.latex


class TestSummation:
    """Category 5: Summation with bounds."""

    def setup_method(self):
        self.parser = StructuredParser()

    def test_sum_with_braces(self):
        spans = self.parser.detect("sum_{i=1}^{n}")
        assert len(spans) >= 1
        s = spans[0]
        assert "\\sum_{i=1}^{n}" == s.formula.latex

    def test_sigma_with_bounds(self):
        spans = self.parser.detect("Sigma_{i=1}^{N}")
        assert len(spans) >= 1
        assert "\\sum" in spans[0].formula.latex

    def test_unicode_sigma(self):
        # U+03A3 = Greek capital sigma
        spans = self.parser.detect("\u03a3_{i=1}^{n}")
        assert len(spans) >= 1
        assert "\\sum" in spans[0].formula.latex

    def test_summation_sign_unicode(self):
        # U+2211 = N-ARY SUMMATION
        spans = self.parser.detect("\u2211_{i=1}^{n}")
        assert len(spans) >= 1
        assert "\\sum" in spans[0].formula.latex


class TestProductNotation:
    """Category 6: Product notation."""

    def setup_method(self):
        self.parser = StructuredParser()

    def test_prod_with_bounds(self):
        spans = self.parser.detect("prod_{i=1}^{n}")
        assert len(spans) >= 1
        s = spans[0]
        assert "\\prod_{i=1}^{n}" == s.formula.latex

    def test_unicode_product(self):
        # U+220F = N-ARY PRODUCT
        spans = self.parser.detect("\u220f_{i=1}^{n}")
        assert len(spans) >= 1
        assert "\\prod" in spans[0].formula.latex


class TestLimits:
    """Category 7: Limits."""

    def setup_method(self):
        self.parser = StructuredParser()

    def test_limit_arrow(self):
        spans = self.parser.detect("lim_{x->0}")
        assert len(spans) >= 1
        s = spans[0]
        assert "\\lim" in s.formula.latex
        assert "\\to" in s.formula.latex
        assert "0" in s.formula.latex

    def test_limit_verbal(self):
        spans = self.parser.detect("lim as x approaches 0")
        assert len(spans) >= 1
        s = spans[0]
        assert "\\lim" in s.formula.latex
        assert "x" in s.formula.latex
        assert "0" in s.formula.latex

    def test_limit_to_infinity(self):
        spans = self.parser.detect("lim_{x->inf}")
        assert len(spans) >= 1
        assert "\\infty" in spans[0].formula.latex


class TestNamedPharmaFormulas:
    """Category 8: Named pharma formulas."""

    def setup_method(self):
        self.parser = StructuredParser()

    def test_kaplan_meier(self):
        spans = self.parser.detect("S(t) = prod(1 - di/ni)")
        assert len(spans) >= 1
        s = spans[0]
        assert "\\prod" in s.formula.latex
        assert "\\frac{d_i}{n_i}" in s.formula.latex
        assert s.formula.formula_type == FormulaType.STATISTICAL

    def test_sample_size(self):
        spans = self.parser.detect("n = (Za + Zb)^2 * 2s^2 / d^2")
        assert len(spans) >= 1
        s = spans[0]
        assert "Z_{\\alpha}" in s.formula.latex
        assert "Z_{\\beta}" in s.formula.latex
        assert "\\sigma" in s.formula.latex

    def test_dissolution_f2(self):
        spans = self.parser.detect("f2 = 50 * log(something)")
        assert len(spans) >= 1
        s = spans[0]
        assert s.formula.formula_type == FormulaType.REGULATORY

    def test_cockcroft_gault(self):
        spans = self.parser.detect("CrCl = ((140-age) * weight) / (72 * SCr)")
        assert len(spans) >= 1
        s = spans[0]
        assert s.formula.formula_type == FormulaType.DOSING
        assert "\\frac" in s.formula.latex or "CrCl" in s.formula.latex


class TestPKDifferentialEquations:
    """Category 9: PK differential equations."""

    def setup_method(self):
        self.parser = StructuredParser()

    def test_simple_pk_ode(self):
        spans = self.parser.detect("dC/dt = -k*C")
        assert len(spans) >= 1
        s = spans[0]
        assert "\\frac{dC}{dt}" in s.formula.latex
        assert s.formula.formula_type == FormulaType.PK

    def test_complex_pk_ode(self):
        spans = self.parser.detect("dA/dt = ka*D*e^(-ka*t) - ke*A")
        assert len(spans) >= 1
        s = spans[0]
        assert "\\frac{dA}{dt}" in s.formula.latex
        assert s.formula.formula_type == FormulaType.PK

    def test_pk_ode_latex_has_cdot(self):
        """Multiplication operators should be rendered as \\cdot in LaTeX."""
        spans = self.parser.detect("dC/dt = -k*C")
        assert len(spans) >= 1
        assert "\\cdot" in spans[0].formula.latex


class TestNoFalsePositives:
    """Ensure normal text does not trigger false detections."""

    def setup_method(self):
        self.parser = StructuredParser()

    def test_plain_english(self):
        spans = self.parser.detect("The patient was given 500mg of drug daily.")
        assert len(spans) == 0

    def test_normal_sentence(self):
        spans = self.parser.detect("This is a normal sentence without formulas.")
        assert len(spans) == 0

    def test_date_not_factorial(self):
        """Dates like '2024' should not trigger factorial patterns."""
        spans = self.parser.detect("The study was conducted in 2024.")
        assert len(spans) == 0

    def test_abbreviations_not_combinations(self):
        """Medical abbreviations should not trigger combination patterns."""
        # nPr might match on isolated text — check it doesn't match in context
        text = "Blood pressure was measured at baseline."
        spans = self.parser.detect(text)
        assert len(spans) == 0

    def test_short_text(self):
        spans = self.parser.detect("")
        assert len(spans) == 0

    def test_just_numbers(self):
        spans = self.parser.detect("42 100 3.14")
        assert len(spans) == 0


class TestLaTeXOutputValidity:
    """Verify that LaTeX output is well-formed."""

    def setup_method(self):
        self.parser = StructuredParser()

    def test_no_raw_tab_chars(self):
        """LaTeX must not contain raw tab characters (\\t byte)."""
        test_cases = [
            "d2y/dx2",
            "int_0^inf f(x)dx",
            "sum_{i=1}^{n}",
            "lim_{x->0}",
            "n!",
            "C(n,k)",
            "dC/dt = -k*C",
            "S(t) = prod(1 - di/ni)",
        ]
        for text in test_cases:
            spans = self.parser.detect(text)
            for s in spans:
                assert "\t" not in s.formula.latex, (
                    f"Raw tab in LaTeX for '{text}': {s.formula.latex!r}"
                )

    def test_braces_balanced(self):
        """LaTeX braces should be balanced."""
        test_cases = [
            "d2y/dx2",
            "int_0^inf f(x)dx",
            "sum_{i=1}^{n}",
            "prod_{i=1}^{n}",
            "lim_{x->0}",
            "C(n,k)",
        ]
        for text in test_cases:
            spans = self.parser.detect(text)
            for s in spans:
                latex = s.formula.latex
                assert latex.count("{") == latex.count("}"), (
                    f"Unbalanced braces in LaTeX for '{text}': {latex}"
                )

    def test_latex_and_plain_text_populated(self):
        """Both latex and plain_text must be non-empty."""
        test_cases = [
            "d2y/dx2",
            "n!",
            "C(n,k)",
            "sum_{i=1}^{n}",
            "lim_{x->0}",
            "dC/dt = -k*C",
        ]
        for text in test_cases:
            spans = self.parser.detect(text)
            assert len(spans) >= 1, f"No detection for '{text}'"
            for s in spans:
                assert s.formula.latex, f"Empty latex for '{text}'"
                assert s.formula.plain_text, f"Empty plain_text for '{text}'"


class TestFactoryRegistration:
    """Verify the factory creates a system with both detectors."""

    def test_factory_has_both_detectors(self):
        from src.formatter.formula.factory import create_formula_system
        orchestrator = create_formula_system()
        registry = orchestrator._registry
        tool_list = registry.list_tools()
        detector_names = [d["name"] for d in tool_list["detectors"]]
        assert "regex_detector" in detector_names
        assert "structured_parser" in detector_names

    def test_factory_structured_query(self):
        from src.formatter.formula.factory import create_formula_system
        from src.formatter.formula.ir import FormulaComplexity
        orchestrator = create_formula_system()
        structured = orchestrator._registry.get_detectors(
            complexity=FormulaComplexity.STRUCTURED
        )
        assert len(structured) >= 1
        names = [d.metadata().name for d in structured]
        assert "structured_parser" in names

    def test_factory_inline_query_excludes_structured(self):
        from src.formatter.formula.factory import create_formula_system
        from src.formatter.formula.ir import FormulaComplexity
        orchestrator = create_formula_system()
        inline = orchestrator._registry.get_detectors(
            complexity=FormulaComplexity.INLINE
        )
        names = [d.metadata().name for d in inline]
        assert "structured_parser" not in names
        assert "regex_detector" in names
