"""
Structured math parser — Tier 3 formula detector for complex notation.

Handles formulas that need LaTeX output and cannot be represented with
simple sub/sup HTML: partial derivatives, integrals, factorials,
combinations, summations, product notation, limits, named pharma
formulas, and PK differential equations.

These patterns complement the RegexDetector (Tier 1+2) by covering
structured mathematical notation that requires full LaTeX rendering.
"""

from __future__ import annotations

import re
from typing import Callable

from src.formatter.formula.base import (
    DetectedFormulaSpan,
    FormulaDetectorTool,
    ToolMetadata,
    ToolSideEffect,
)
from src.formatter.formula.ir import (
    FormattedFormula,
    FormulaComplexity,
    FormulaSource,
    FormulaType,
)


# ---------------------------------------------------------------------------
# Helper: build a DetectedFormulaSpan from a regex match
# ---------------------------------------------------------------------------

def _normalize_infinity(text: str) -> str:
    """Replace common infinity tokens with LaTeX \\infty.

    Uses re.sub with a lambda to avoid backreference interpretation
    of the backslash-i in '\\infty'.
    """
    return re.sub(
        r"(?:inf|infinity|\u221e)",
        lambda _m: "\\infty",
        text,
        flags=re.IGNORECASE,
    )


def _span(
    match: re.Match,
    latex: str,
    plain: str,
    ftype: FormulaType,
    confidence: float = 0.95,
    html: str = "",
) -> DetectedFormulaSpan:
    """Convenience builder for a detected structured formula span."""
    return DetectedFormulaSpan(
        formula=FormattedFormula(
            latex=latex,
            plain_text=plain,
            html=html or plain,  # Use HTML if provided, else plain text
            formula_type=ftype,
            complexity=FormulaComplexity.STRUCTURED,
            source=FormulaSource.PARSER,
            confidence=confidence,
        ),
        start=match.start(),
        end=match.end(),
        original_text=match.group(),
    )


# ---------------------------------------------------------------------------
# Pattern definitions
# Each entry: (compiled regex, handler function)
# The handler receives a re.Match and returns a DetectedFormulaSpan.
# Order matters: more specific patterns should come first.
# ---------------------------------------------------------------------------

_STRUCTURED_PATTERNS: list[tuple[re.Pattern, Callable[[re.Match], DetectedFormulaSpan]]] = []


def _register(pattern: re.Pattern, handler: Callable[[re.Match], DetectedFormulaSpan]) -> None:
    _STRUCTURED_PATTERNS.append((pattern, handler))


# -----------------------------------------------------------------------
# 1a. Second-order partial derivatives (most specific, register first)
# -----------------------------------------------------------------------

# d2y/dx2 style — second-order partial
_RE_PARTIAL2 = re.compile(
    r"\bd([2-9])([A-Za-z])\s*/\s*d([A-Za-z])([2-9])\b"
)

def _handle_partial2(m: re.Match) -> DetectedFormulaSpan:
    order = m.group(1)
    numer_var = m.group(2)
    denom_var = m.group(3)
    return _span(
        m,
        latex="\\frac{\\partial^%s %s}{\\partial %s^%s}" % (order, numer_var, denom_var, order),
        plain=m.group(),
        ftype=FormulaType.MATHEMATICAL,
        html="\u2202<sup>%s</sup>%s/\u2202%s<sup>%s</sup>" % (order, numer_var, denom_var, order),
    )

_register(_RE_PARTIAL2, _handle_partial2)


# -----------------------------------------------------------------------
# 9. PK differential equations  (before generic dX/dt partial derivative
#    because this is more specific: requires "= <rhs>" after dC/dt)
# -----------------------------------------------------------------------

_RE_PK_ODE = re.compile(
    r"\bd([A-Z])\s*/\s*dt\s*=\s*([^\n,;]{3,60})"
)

def _handle_pk_ode(m: re.Match) -> DetectedFormulaSpan:
    var = m.group(1)
    rhs = m.group(2).strip()
    rhs_latex = rhs.replace("*", " \\cdot ")
    latex = "\\frac{d%s}{dt} = %s" % (var, rhs_latex)
    rhs_html = rhs.replace("*", "\u00b7")
    return _span(
        m,
        latex=latex,
        plain=m.group(),
        ftype=FormulaType.PK,
        html="d%s/dt = %s" % (var, rhs_html),
    )

_register(_RE_PK_ODE, _handle_pk_ode)


# -----------------------------------------------------------------------
# 1b. First-order partial derivatives (generic dX/dY — after PK ODE)
# -----------------------------------------------------------------------

_RE_PARTIAL1 = re.compile(
    r"\bd([A-Za-z])\s*/\s*d([A-Za-z])\b"
)

def _handle_partial1(m: re.Match) -> DetectedFormulaSpan:
    numer_var = m.group(1)
    denom_var = m.group(2)
    # Use partial symbol for generic math (df/dt, df/dx etc.)
    # Use ordinary d for single-variable PK-style (dC/dt, dA/dt)
    # Heuristic: if the numerator var is uppercase and denom is t, use ordinary d
    if numer_var.isupper() and denom_var == "t":
        d_symbol = "d"
    else:
        d_symbol = "\\partial"
    return _span(
        m,
        latex="\\frac{%s %s}{%s %s}" % (d_symbol, numer_var, d_symbol, denom_var),
        plain=m.group(),
        ftype=FormulaType.MATHEMATICAL,
    )

_register(_RE_PARTIAL1, _handle_partial1)


# -----------------------------------------------------------------------
# 2. Integrals
# -----------------------------------------------------------------------

# int_a^b f(x)dx  or  integral_a^b ...
_RE_INTEGRAL_BOUNDS = re.compile(
    r"(?:int|integral|\u222b)\s*_\s*([^\s^]+)\s*\^\s*([^\s]+)\s+(.+?)d([A-Za-z])\b",
    re.IGNORECASE,
)

def _handle_integral_bounds(m: re.Match) -> DetectedFormulaSpan:
    lower = m.group(1)
    upper = m.group(2)
    body = m.group(3).strip()
    var = m.group(4)
    upper_latex = _normalize_infinity(upper)
    lower_latex = _normalize_infinity(lower)
    latex = "\\int_{%s}^{%s} %s\\,d%s" % (lower_latex, upper_latex, body, var)
    upper_html = upper.replace("inf", "\u221e")
    lower_html = lower.replace("inf", "\u221e") if "inf" in lower.lower() else lower
    html = "\u222b<sub>%s</sub><sup>%s</sup> %s d%s" % (lower_html, upper_html, body, var)
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.MATHEMATICAL, html=html)

_register(_RE_INTEGRAL_BOUNDS, _handle_integral_bounds)

# Bare integral sign (U+222B) without bounds
_RE_INTEGRAL_BARE = re.compile(r"\u222b\s*(.+?)d([A-Za-z])\b")

def _handle_integral_bare(m: re.Match) -> DetectedFormulaSpan:
    body = m.group(1).strip()
    var = m.group(2)
    latex = "\\int %s\\,d%s" % (body, var)
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.MATHEMATICAL)

_register(_RE_INTEGRAL_BARE, _handle_integral_bare)


# -----------------------------------------------------------------------
# 5. Summation with bounds
# -----------------------------------------------------------------------

# sum_{i=1}^{n} or Sigma_{i=1}^{N} or sigma_{i=1}^{n}
_RE_SUM_BOUNDS = re.compile(
    r"(?:sum|Sigma|sigma|\u03a3|\u2211)\s*_\s*\{?\s*([^}^]+?)\s*\}?\s*\^\s*\{?\s*([^}\s]+)\s*\}?",
    re.IGNORECASE,
)

def _handle_sum_bounds(m: re.Match) -> DetectedFormulaSpan:
    lower = m.group(1).strip()
    upper = m.group(2).strip()
    latex = "\\sum_{%s}^{%s}" % (lower, upper)
    html = "\u03a3<sub>%s</sub><sup>%s</sup>" % (lower, upper)
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.MATHEMATICAL, html=html)

_register(_RE_SUM_BOUNDS, _handle_sum_bounds)


# -----------------------------------------------------------------------
# 6. Product notation
# -----------------------------------------------------------------------

_RE_PROD_BOUNDS = re.compile(
    r"(?:prod|\u220f)\s*_\s*\{?\s*([^}^]+?)\s*\}?\s*\^\s*\{?\s*([^}\s]+)\s*\}?",
    re.IGNORECASE,
)

def _handle_prod_bounds(m: re.Match) -> DetectedFormulaSpan:
    lower = m.group(1).strip()
    upper = m.group(2).strip()
    latex = "\\prod_{%s}^{%s}" % (lower, upper)
    html = "\u220f<sub>%s</sub><sup>%s</sup>" % (lower, upper)
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.MATHEMATICAL, html=html)

_register(_RE_PROD_BOUNDS, _handle_prod_bounds)


# -----------------------------------------------------------------------
# 7. Limits
# -----------------------------------------------------------------------

# lim_{x->0}  or  lim_{x \to 0}
_RE_LIMIT_BRACE = re.compile(
    r"\blim\s*_\s*\{?\s*([A-Za-z])\s*(?:->|\\to|\u2192)\s*([^}\s]+)\s*\}?",
)

def _handle_limit_brace(m: re.Match) -> DetectedFormulaSpan:
    var = m.group(1)
    target = m.group(2).strip()
    target_latex = _normalize_infinity(target)
    latex = "\\lim_{%s \\to %s}" % (var, target_latex)
    target_html = target.replace("inf", "\u221e")
    html = "lim<sub>%s\u2192%s</sub>" % (var, target_html)
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.MATHEMATICAL, html=html)

_register(_RE_LIMIT_BRACE, _handle_limit_brace)

# lim as x approaches 0
_RE_LIMIT_VERBAL = re.compile(
    r"\blim\s+as\s+([A-Za-z])\s+approaches?\s+([^\s,;]+)",
    re.IGNORECASE,
)

def _handle_limit_verbal(m: re.Match) -> DetectedFormulaSpan:
    var = m.group(1)
    target = m.group(2).strip()
    target_latex = _normalize_infinity(target)
    latex = "\\lim_{%s \\to %s}" % (var, target_latex)
    target_html = target.replace("inf", "\u221e")
    html = "lim<sub>%s\u2192%s</sub>" % (var, target_html)
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.MATHEMATICAL, html=html)

_register(_RE_LIMIT_VERBAL, _handle_limit_verbal)


# -----------------------------------------------------------------------
# 4. Combinations / Permutations
# -----------------------------------------------------------------------

# C(n,k) or C(n, k)
_RE_COMB_FUNC = re.compile(r"\bC\(\s*([A-Za-z0-9]+)\s*,\s*([A-Za-z0-9]+)\s*\)")

def _handle_comb_func(m: re.Match) -> DetectedFormulaSpan:
    n = m.group(1)
    k = m.group(2)
    latex = "\\binom{%s}{%s}" % (n, k)
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.MATHEMATICAL)

_register(_RE_COMB_FUNC, _handle_comb_func)

# nCr (where n, r are single lowercase letters or single digits)
_RE_NCR = re.compile(r"\b([a-z0-9])\s*C\s*([a-z0-9])\b")

def _handle_ncr(m: re.Match) -> DetectedFormulaSpan:
    n = m.group(1)
    r = m.group(2)
    latex = "\\binom{%s}{%s}" % (n, r)
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.MATHEMATICAL)

_register(_RE_NCR, _handle_ncr)

_RE_NPR = re.compile(r"\b([a-z0-9])\s*P\s*([a-z0-9])\b")

def _handle_npr(m: re.Match) -> DetectedFormulaSpan:
    n = m.group(1)
    r = m.group(2)
    latex = "%s P %s" % (n, r)
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.MATHEMATICAL)

_register(_RE_NPR, _handle_npr)


# -----------------------------------------------------------------------
# 3. Factorials
# -----------------------------------------------------------------------

# (n-k)! or (n+k)! or simple n! or k! or 5!
_RE_FACTORIAL_PAREN = re.compile(r"\(([A-Za-z0-9+\-*/\s]+)\)!")

def _handle_factorial_paren(m: re.Match) -> DetectedFormulaSpan:
    expr = m.group(1).strip()
    latex = "(%s)!" % expr
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.MATHEMATICAL)

_register(_RE_FACTORIAL_PAREN, _handle_factorial_paren)

_RE_FACTORIAL_SIMPLE = re.compile(r"\b([A-Za-z0-9]+)!")

def _handle_factorial_simple(m: re.Match) -> DetectedFormulaSpan:
    base = m.group(1)
    latex = "%s!" % base
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.MATHEMATICAL)

_register(_RE_FACTORIAL_SIMPLE, _handle_factorial_simple)


# -----------------------------------------------------------------------
# 8. Named pharma formulas
# -----------------------------------------------------------------------

# Kaplan-Meier: S(t) = prod(1 - di/ni)  or  S(t)=product(1-d_i/n_i)
_RE_KAPLAN_MEIER = re.compile(
    r"S\s*\(\s*t\s*\)\s*=\s*(?:prod|product|\u220f)\s*\(?\s*1\s*-\s*d[_i]*\s*/\s*n[_i]*\s*\)?",
    re.IGNORECASE,
)

def _handle_kaplan_meier(m: re.Match) -> DetectedFormulaSpan:
    latex = "S(t) = \\prod_{i} \\left(1 - \\frac{d_i}{n_i}\\right)"
    html = "S(t) = \u220f<sub>i</sub>(1 - d<sub>i</sub>/n<sub>i</sub>)"
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.STATISTICAL, html=html)

_register(_RE_KAPLAN_MEIER, _handle_kaplan_meier)

# Sample size: n = (Za + Zb)^2 * 2s^2 / d^2
_RE_SAMPLE_SIZE = re.compile(
    r"\bn\s*=\s*\(\s*Z\s*[aA\u03b1]\s*\+\s*Z\s*[bB\u03b2]\s*\)\s*\^?\s*2\s*\*?\s*2\s*[sS\u03c3]\s*\^?\s*2\s*/\s*[dD\u03b4]\s*\^?\s*2"
)

def _handle_sample_size(m: re.Match) -> DetectedFormulaSpan:
    latex = "n = \\frac{(Z_{\\alpha} + Z_{\\beta})^2 \\cdot 2\\sigma^2}{\\delta^2}"
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.STATISTICAL)

_register(_RE_SAMPLE_SIZE, _handle_sample_size)

# Dissolution f2 = 50 * log(...)
_RE_DISSOLUTION_F2 = re.compile(
    r"\bf2\s*=\s*50\s*\*?\s*log\s*\(",
    re.IGNORECASE,
)

def _handle_dissolution_f2(m: re.Match) -> DetectedFormulaSpan:
    return _span(
        m,
        latex="f_2 = 50 \\cdot \\log(\\ldots)",
        plain=m.group(),
        ftype=FormulaType.REGULATORY,
        confidence=0.85,
    )

_register(_RE_DISSOLUTION_F2, _handle_dissolution_f2)

# Cockcroft-Gault: CrCl = ((140-age) * weight) / (72 * SCr)
_RE_COCKCROFT = re.compile(
    r"\bCrCl\s*=\s*\(\s*\(\s*140\s*[-\u2013]\s*age\s*\)\s*[*\u00d7]?\s*weight\s*\)\s*/\s*\(\s*72\s*[*\u00d7]?\s*SCr\s*\)",
    re.IGNORECASE,
)

def _handle_cockcroft(m: re.Match) -> DetectedFormulaSpan:
    latex = "\\text{CrCl} = \\frac{(140 - \\text{age}) \\times \\text{weight}}{72 \\times \\text{SCr}}"
    html = "CrCl = (140 - age) \u00d7 weight / (72 \u00d7 SCr)"
    return _span(m, latex=latex, plain=m.group(), ftype=FormulaType.DOSING, html=html)

_register(_RE_COCKCROFT, _handle_cockcroft)


# =========================================================================
# The StructuredParser tool class
# =========================================================================

class StructuredParser(FormulaDetectorTool):
    """Parser-based detector for structured math formulas (Tier 3).

    Covers: partial derivatives, integrals, factorials, combinations,
    summations, product notation, limits, named pharma formulas,
    and PK differential equations.

    Produces LaTeX and plain_text for each detection.
    Complements the RegexDetector which handles Tier 1+2 inline formulas.
    """

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="structured_parser",
            version="1.0.0",
            description=(
                "Detect structured math formulas (fractions, integrals, "
                "summations, limits, derivatives, named clinical formulas). "
                "Use for Tier 3 formulas that need LaTeX rendering. "
                "Do NOT use for simple inline notation (CO2, mg/m2) or images."
            ),
            side_effects=ToolSideEffect.NONE,
            supported_complexities=[FormulaComplexity.STRUCTURED],
            supported_types=[
                FormulaType.MATHEMATICAL,
                FormulaType.STATISTICAL,
                FormulaType.PK,
                FormulaType.DOSING,
                FormulaType.REGULATORY,
            ],
            priority=80,  # Below RegexDetector (90) — regex handles the easy stuff first
            timeout_ms=2000,
        )

    def detect(self, text: str) -> list[DetectedFormulaSpan]:
        """Detect all structured math formulas in text."""
        spans: list[DetectedFormulaSpan] = []
        used_ranges: list[tuple[int, int]] = []

        for pattern, handler in _STRUCTURED_PATTERNS:
            for match in pattern.finditer(text):
                # Avoid overlapping detections
                start, end = match.start(), match.end()
                if any(s <= start < e or s < end <= e for s, e in used_ranges):
                    continue
                span = handler(match)
                spans.append(span)
                used_ranges.append((start, end))

        return spans
