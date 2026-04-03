"""
Formula rendering tools — pluggable backends for each output format.

Each renderer takes a FormattedFormula (with LaTeX) and populates one
output format field. Renderers are independently registered and selected
by the orchestrator based on the target format.

Rendering chain:
    LaTeX (canonical) → MathML (for HTML) → OMML (for DOCX)
                      → HTML with <sub>/<sup> (simple fallback)
                      → plain text (pylatexenc or fallback)
"""

from __future__ import annotations

import logging
import re

from src.formatter.formula.base import (
    FormulaRendererTool,
    ToolMetadata,
    ToolSideEffect,
)
from src.formatter.formula.ir import (
    FormattedFormula,
    FormulaComplexity,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTML Renderer (sub/sup tags — always available, no dependencies)
# ---------------------------------------------------------------------------

class HTMLFormulaRenderer(FormulaRendererTool):
    """Renders formulas as HTML with <sub>/<sup> tags.

    This is the simplest renderer — uses the pre-generated HTML from the
    regex detector. Always available, no external dependencies.
    """

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="html_formula_renderer",
            version="1.0.0",
            description=(
                "Render formula as HTML with sub/sup tags. "
                "Use for simple inline formulas (Tier 1+2). "
                "Do NOT use for complex structured math — use MathML renderer instead."
            ),
            side_effects=ToolSideEffect.NONE,
            priority=80,
            timeout_ms=100,
        )

    def target_format(self) -> str:
        return "html"

    def render(self, formula: FormattedFormula) -> FormattedFormula:
        # If HTML already set (e.g., by regex detector), keep it
        if formula.has_html():
            return formula
        # Fallback: use plain text
        formula.html = formula.plain_text or formula.latex
        return formula


# ---------------------------------------------------------------------------
# MathML Renderer (via latex2mathml — production quality)
# ---------------------------------------------------------------------------

class MathMLFormulaRenderer(FormulaRendererTool):
    """Renders LaTeX formulas as MathML for browser-native display.

    Uses latex2mathml (MIT, pure Python). Falls back to HTML sub/sup
    if latex2mathml is not installed or the LaTeX fails to parse.
    """

    def __init__(self):
        self._available = False
        try:
            import latex2mathml.converter  # noqa: F401
            self._available = True
        except ImportError:
            logger.info("latex2mathml not installed — MathML rendering disabled")

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="mathml_formula_renderer",
            version="1.0.0",
            description=(
                "Render LaTeX formula as MathML for browser-native display. "
                "Use for all formulas with LaTeX representation. "
                "Requires latex2mathml package."
            ),
            side_effects=ToolSideEffect.NONE,
            priority=90,  # Prefer over HTML renderer
            timeout_ms=500,
        )

    def target_format(self) -> str:
        return "mathml"

    def render(self, formula: FormattedFormula) -> FormattedFormula:
        if not self._available or not formula.has_latex():
            return formula

        try:
            import latex2mathml.converter
            mathml = latex2mathml.converter.convert(formula.latex)
            formula.mathml = mathml
        except Exception as e:
            logger.debug("MathML conversion failed for '%s': %s", formula.latex, e)

        return formula


# ---------------------------------------------------------------------------
# OMML Renderer (for DOCX — via MathML → XSLT → OMML)
# ---------------------------------------------------------------------------

class OmmlFormulaRenderer(FormulaRendererTool):
    """Renders formulas as OMML (Office Math Markup Language) for DOCX.

    Pipeline: LaTeX → MathML (via latex2mathml) → OMML (via XSLT or mathml2omml).
    Falls back to plain text run if conversion fails.
    """

    def __init__(self):
        self._available = False
        try:
            import latex2mathml.converter  # noqa: F401
            self._available = True
        except ImportError:
            pass

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="omml_formula_renderer",
            version="1.0.0",
            description=(
                "Render formula as OMML for native Word equations. "
                "Use when rendering to DOCX format. "
                "Requires latex2mathml. Optionally uses mathml2omml."
            ),
            side_effects=ToolSideEffect.NONE,
            priority=70,
            timeout_ms=1000,
        )

    def target_format(self) -> str:
        return "omml"

    def render(self, formula: FormattedFormula) -> FormattedFormula:
        if not self._available or not formula.has_latex():
            return formula

        try:
            # Step 1: LaTeX → MathML
            import latex2mathml.converter
            mathml = formula.mathml or latex2mathml.converter.convert(formula.latex)

            # Step 2: MathML → OMML (try mathml2omml if available)
            try:
                from mathml2omml import convert as mathml_to_omml
                omml = mathml_to_omml(mathml)
                formula.omml = omml
            except ImportError:
                # mathml2omml not installed — store MathML for manual conversion
                formula.mathml = mathml
                logger.debug("mathml2omml not installed — OMML not generated")
        except Exception as e:
            logger.debug("OMML conversion failed for '%s': %s", formula.latex, e)

        return formula


# ---------------------------------------------------------------------------
# Image classifier (heuristic-based — no ML dependencies)
# ---------------------------------------------------------------------------

class HeuristicImageClassifier:
    """Classifies images as equations using aspect ratio, size, and color heuristics.

    This is a fast pre-filter (no ML). Runs before OCR to avoid wasting
    compute on non-equation images (charts, photos, logos).
    """

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="heuristic_image_classifier",
            version="1.0.0",
            description=(
                "Classify images as equations using heuristics (aspect ratio, "
                "size, monochromaticity). Use as a fast pre-filter before OCR. "
                "Do NOT use as the sole classifier for high-stakes documents."
            ),
            side_effects=ToolSideEffect.NONE,
            priority=60,
            timeout_ms=100,
        )

    def classify(
        self,
        image_bytes: bytes,
        width: int,
        height: int,
    ) -> dict:
        """Classify whether an image is likely an equation."""
        if width == 0 or height == 0:
            return {"is_equation": False, "confidence": 0.0}

        aspect = width / max(height, 1)

        # Equations are typically wider than tall
        aspect_score = 1.0 if 2.0 < aspect < 12.0 else 0.3

        # Equations are typically small
        size_score = 1.0 if height < 200 and width < 800 else 0.3

        # Combined confidence
        confidence = (aspect_score * 0.5 + size_score * 0.5)
        is_equation = confidence > 0.6

        return {
            "is_equation": is_equation,
            "confidence": confidence,
            "aspect_ratio": round(aspect, 2),
        }
