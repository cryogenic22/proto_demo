"""
Regex-based formula detector — wraps existing FormulaDetector as a registered tool.

Handles Tier 1+2 (inline) formulas: chemical, dosing, PK, statistical,
mathematical patterns. This is the workhorse — covers ~75% of pharma formulas.

Now also generates LaTeX alongside HTML for each detected formula,
enabling the rendering pipeline to produce MathML, OMML, etc.
"""

from __future__ import annotations

import re

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
# Pattern bank: (regex, html_replacement, latex_replacement, FormulaType)
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[re.Pattern, str, str, FormulaType]] = [
    # --- Chemical subscripts ---
    (re.compile(r"\bCO2\b"), r"CO<sub>2</sub>", "\\text{CO}_2", FormulaType.CHEMICAL),
    (re.compile(r"\bH2O\b"), r"H<sub>2</sub>O", "\\text{H}_2\\text{O}", FormulaType.CHEMICAL),
    (re.compile(r"\bO2\b"), r"O<sub>2</sub>", "\\text{O}_2", FormulaType.CHEMICAL),
    (re.compile(r"\bN2\b"), r"N<sub>2</sub>", "\\text{N}_2", FormulaType.CHEMICAL),
    (re.compile(r"\bHbA1c\b"), r"HbA<sub>1c</sub>", "\\text{HbA}_{1c}", FormulaType.CHEMICAL),
    (re.compile(r"\bPO4\b"), r"PO<sub>4</sub>", "\\text{PO}_4", FormulaType.CHEMICAL),
    (re.compile(r"\bCa2\+"), r"Ca<sup>2+</sup>", "\\text{Ca}^{2+}", FormulaType.CHEMICAL),
    (re.compile(r"\bNa\+"), r"Na<sup>+</sup>", "\\text{Na}^+", FormulaType.CHEMICAL),
    (re.compile(r"\bK\+"), r"K<sup>+</sup>", "\\text{K}^+", FormulaType.CHEMICAL),
    (re.compile(r"\bCl\-"), r"Cl<sup>-</sup>", "\\text{Cl}^-", FormulaType.CHEMICAL),

    # --- Dosing superscripts ---
    (re.compile(r"\b(\w+)/m2\b"), r"\1/m<sup>2</sup>", "\\1/\\text{m}^2", FormulaType.DOSING),
    (re.compile(r"\b(\w+)/mm3\b"), r"\1/mm<sup>3</sup>", "\\1/\\text{mm}^3", FormulaType.DOSING),
    (re.compile(r"[x\u00d7]10\^?(\d+)"), "\u00d710<sup>\\1</sup>", "\\times 10^{\\1}", FormulaType.DOSING),

    # --- PK parameters ---
    (re.compile(r"\bAUC\s*0?\s*[-\u2013]\s*(?:inf|infinity|\u221e)\b", re.IGNORECASE),
     "AUC<sub>0-\u221e</sub>", "\\text{AUC}_{0-\\infty}", FormulaType.PK),
    (re.compile(r"\bAUC\s*0?\s*[-\u2013]\s*t\b", re.IGNORECASE),
     r"AUC<sub>0-t</sub>", "\\text{AUC}_{0-t}", FormulaType.PK),
    (re.compile(r"\bAUC\s*0?\s*[-\u2013]\s*(\d+)\b"),
     r"AUC<sub>0-\1</sub>", "\\text{AUC}_{0-\\1}", FormulaType.PK),
    (re.compile(r"\bCmax\b"), r"C<sub>max</sub>", r"C_{\max}", FormulaType.PK),
    (re.compile(r"\bCmin\b"), r"C<sub>min</sub>", r"C_{\min}", FormulaType.PK),
    (re.compile(r"\bCss\b"), r"C<sub>ss</sub>", r"C_{ss}", FormulaType.PK),
    (re.compile(r"\bt1/2\b"), r"t<sub>1/2</sub>", r"t_{1/2}", FormulaType.PK),
    (re.compile(r"\btmax\b"), r"t<sub>max</sub>", r"t_{\max}", FormulaType.PK),
    (re.compile(r"\bVd\b"), r"V<sub>d</sub>", r"V_d", FormulaType.PK),

    # --- Exponents ---
    (re.compile(r"\b(mm|cm|m|km)2\b"), r"\1<sup>2</sup>", "\\text{\\1}^2", FormulaType.MATHEMATICAL),
    (re.compile(r"\b(mm|cm|m)3\b"), r"\1<sup>3</sup>", "\\text{\\1}^3", FormulaType.MATHEMATICAL),
    (re.compile(r"\b10\^(\d+)\b"), r"10<sup>\1</sup>", "10^{\\1}", FormulaType.MATHEMATICAL),
    (re.compile(r"\b([sS]|sigma|\u03c3)\^?2\b"), r"\1<sup>2</sup>", r"\1^2", FormulaType.MATHEMATICAL),

    # --- Logarithms ---
    (re.compile(r"\blog10\b"), r"log<sub>10</sub>", "\\log_{10}", FormulaType.MATHEMATICAL),
    (re.compile(r"\blog_10\b"), r"log<sub>10</sub>", "\\log_{10}", FormulaType.MATHEMATICAL),
    (re.compile(r"\blog2\b"), r"log<sub>2</sub>", "\\log_2", FormulaType.MATHEMATICAL),
    (re.compile(r"\bln\b"), r"ln", "\\ln", FormulaType.MATHEMATICAL),

    # --- Statistics ---
    (re.compile(r"\bp\s*[<>=]\s*0\.\d+"), None, None, FormulaType.STATISTICAL),
    (re.compile(r"\b(?:HR|OR|RR)\s+\d+\.\d+"), None, None, FormulaType.STATISTICAL),
    (re.compile(r"\d+%\s*CI[:\s,]+\d+\.\d+[\s\u2013\-]+\d+\.\d+"), None, None, FormulaType.STATISTICAL),
    (re.compile(r"%\s*RSD\b"), None, None, FormulaType.STATISTICAL),
    (re.compile(r"%\s*CV\b"), None, None, FormulaType.STATISTICAL),
    (re.compile(r"\bGMT\b"), None, None, FormulaType.STATISTICAL),
    (re.compile(r"\bGMFR\b"), None, None, FormulaType.STATISTICAL),
    (re.compile(r"\bSD\b"), None, None, FormulaType.STATISTICAL),
    (re.compile(r"\bSEM\b"), None, None, FormulaType.STATISTICAL),

    # --- Efficacy formulas ---
    (re.compile(r"\bVE\s*="), None, None, FormulaType.EFFICACY),
    (re.compile(r"\bNNT\s*="), None, None, FormulaType.EFFICACY),
    (re.compile(r"\bARR\b"), None, None, FormulaType.EFFICACY),
    (re.compile(r"\bH[01a]\s*:"), None, None, FormulaType.STATISTICAL),

    # --- Analytical ---
    (re.compile(r"\bLOD\b"), None, None, FormulaType.ANALYTICAL),
    (re.compile(r"\bLOQ\b"), None, None, FormulaType.ANALYTICAL),

    # --- Named clinical formulas ---
    (re.compile(r"\bCockcroft[-\s]Gault\b", re.IGNORECASE), None, None, FormulaType.DOSING),
    (re.compile(r"\bCKD[-\s]EPI\b", re.IGNORECASE), None, None, FormulaType.DOSING),
    (re.compile(r"\bCalvert\b"), None, None, FormulaType.DOSING),
    (re.compile(r"\bBSA\b"), None, None, FormulaType.DOSING),

    # --- Nested exponents ---
    (re.compile(r"\b10\^ln\(10\)"), r"10<sup>ln(10)</sup>", "10^{\\ln(10)}", FormulaType.MATHEMATICAL),
    (re.compile(r"\be\^([a-zA-Z0-9()+\-*/]+)"), r"e<sup>\1</sup>", "e^{\\1}", FormulaType.MATHEMATICAL),

    # --- log10 Titer ---
    (re.compile(r"\blog10\s*Titer\b", re.IGNORECASE),
     r"log<sub>10</sub> Titer", "\\log_{10} \\text{Titer}", FormulaType.MATHEMATICAL),
]


class RegexFormulaDetector(FormulaDetectorTool):
    """Regex-based detector for inline pharma formulas (Tier 1+2).

    Covers: chemical subscripts, dosing superscripts, PK parameters,
    statistical notation, efficacy formulas, analytical terms.

    Produces both HTML and LaTeX for each detection.
    """

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="regex_detector",
            version="2.0.0",
            description=(
                "Detect inline pharma formulas via regex patterns. "
                "Use for text-based formulas (CO2, AUC0-inf, mg/m2, p < 0.05). "
                "Do NOT use for image-based equations or complex multi-line math."
            ),
            side_effects=ToolSideEffect.NONE,
            supported_complexities=[FormulaComplexity.INLINE],
            supported_types=[
                FormulaType.CHEMICAL, FormulaType.DOSING, FormulaType.PK,
                FormulaType.STATISTICAL, FormulaType.MATHEMATICAL,
                FormulaType.EFFICACY, FormulaType.ANALYTICAL,
            ],
            priority=90,  # High priority — this is the workhorse
            timeout_ms=1000,
        )

    def detect(self, text: str) -> list[DetectedFormulaSpan]:
        """Detect all inline formulas in text."""
        spans: list[DetectedFormulaSpan] = []

        for pattern, html_repl, latex_repl, ftype in _PATTERNS:
            for match in pattern.finditer(text):
                original = match.group()

                # Build HTML (if pattern has a replacement)
                if html_repl is not None:
                    html = pattern.sub(html_repl, original)
                else:
                    html = original

                # Build LaTeX (if pattern has a replacement)
                if latex_repl is not None:
                    try:
                        latex = pattern.sub(latex_repl, original)
                    except re.error:
                        latex = original
                else:
                    latex = ""

                formula = FormattedFormula(
                    latex=latex,
                    plain_text=original,
                    html=html,
                    formula_type=ftype,
                    complexity=FormulaComplexity.INLINE,
                    source=FormulaSource.REGEX,
                    confidence=1.0,
                )

                spans.append(DetectedFormulaSpan(
                    formula=formula,
                    start=match.start(),
                    end=match.end(),
                    original_text=original,
                ))

        return spans
