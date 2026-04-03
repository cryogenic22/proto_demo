"""
Formula IR — the canonical representation for mathematical formulas.

LaTeX is the canonical internal format. All detection paths (regex, OMML,
image OCR) produce LaTeX. All rendering paths (HTML/MathML, DOCX/OMML,
PDF/mathtext) consume LaTeX.

This decouples detection from rendering — you can add a new detection
backend (e.g., Claude Vision) or a new rendering backend (e.g., KaTeX)
without changing the other side.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FormulaSource(str, Enum):
    """How the formula was detected."""
    REGEX = "regex"           # Tier 1+2: pattern-matched from text
    PARSER = "parser"         # Tier 3: parsed from structured notation
    OMML = "omml"             # Extracted from DOCX equation objects
    IMAGE_OCR = "image_ocr"   # Tier 4: OCR'd from an image
    VLM = "vlm"               # Tier 4: Claude Vision or similar
    MANUAL = "manual"         # User-provided


class FormulaType(str, Enum):
    """Semantic classification of the formula."""
    CHEMICAL = "chemical"         # CO₂, H₂O, HbA₁c
    DOSING = "dosing"             # mg/m², 10⁶ cells
    STATISTICAL = "statistical"   # p < 0.05, HR, CI, %RSD
    PK = "pk"                     # AUC₀₋∞, Cmax, t½
    MATHEMATICAL = "mathematical" # σ², log₁₀, √, ∂
    EFFICACY = "efficacy"         # VE, NNT, ARR
    ANALYTICAL = "analytical"     # LOD, LOQ, %Recovery
    REGULATORY = "regulatory"     # f₂ similarity, bioequivalence
    UNKNOWN = "unknown"


class FormulaComplexity(str, Enum):
    """Complexity tier — drives tool selection in the orchestrator."""
    INLINE = "inline"         # Simple sub/superscript (regex handles)
    STRUCTURED = "structured" # Fractions, integrals, summations (parser needed)
    RENDERED = "rendered"     # Image-based equation (OCR needed)


@dataclass
class FormattedFormula:
    """A mathematical formula with structured, multi-format representation.

    LaTeX is the canonical format. Other representations are derived from it
    by rendering backends. The orchestrator populates this; renderers consume it.

    Design principle: this dataclass is a *value object* — it carries data,
    not behavior. All transformation logic lives in tools/backends.
    """

    # Canonical representation (always populated)
    latex: str = ""                     # e.g., r"\frac{\partial^2 y}{\partial x^2}"
    plain_text: str = ""                # e.g., "d²y/dx²"

    # Pre-rendered outputs (populated lazily by rendering backends)
    mathml: str = ""                    # For HTML output
    omml: str = ""                      # For DOCX output (Office Math ML)
    html: str = ""                      # Pre-rendered HTML with <sub>/<sup>

    # Classification metadata
    formula_type: FormulaType = FormulaType.UNKNOWN
    complexity: FormulaComplexity = FormulaComplexity.INLINE
    source: FormulaSource = FormulaSource.REGEX

    # Quality metadata
    confidence: float = 1.0             # 0.0 to 1.0
    needs_review: bool = False          # Flag for human review

    # Source provenance (for Tier 4 image-based)
    source_image_data: str = ""         # Base64 data URI of source image
    source_page: int = -1               # Page number where found
    source_position: tuple[float, float, float, float] = (0, 0, 0, 0)  # x0,y0,x1,y1

    def has_latex(self) -> bool:
        return bool(self.latex.strip())

    def has_mathml(self) -> bool:
        return bool(self.mathml.strip())

    def has_html(self) -> bool:
        return bool(self.html.strip())

    def best_text(self) -> str:
        """Return the best available text representation."""
        return self.plain_text or self.latex or ""
