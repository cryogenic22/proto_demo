"""
Formula Tool base classes — abstract contracts for all formula capabilities.

Every formula tool implements a typed interface with explicit input/output
contracts. Tools are registered in the FormulaToolRegistry and discovered
by the orchestrator at runtime.

Design follows rough_notes.md Module 1 (Tool Registry):
- Metadata-first: description, version, input/output schema declared upfront
- Side-effect profile declared explicitly
- Tools are versioned; the registry is queryable
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.formatter.formula.ir import (
    FormattedFormula,
    FormulaComplexity,
    FormulaSource,
    FormulaType,
)


class ToolSideEffect(str, Enum):
    """Side-effect profile of a tool (rough_notes.md Module 1)."""
    NONE = "none"           # Pure function, no I/O
    READ = "read"           # Reads from filesystem or network
    WRITE = "write"         # Writes to filesystem
    EXTERNAL = "external"   # Calls external API (cost, latency)


@dataclass
class ToolMetadata:
    """Registry metadata for a formula tool."""
    name: str
    version: str
    description: str                    # Written from the orchestrator's perspective
    side_effects: ToolSideEffect = ToolSideEffect.NONE
    supported_complexities: list[FormulaComplexity] = field(default_factory=list)
    supported_types: list[FormulaType] = field(default_factory=list)
    priority: int = 50                  # Higher = preferred (for tool pool ranking)
    requires_gpu: bool = False
    requires_network: bool = False
    timeout_ms: int = 5000


class FormulaDetectorTool(ABC):
    """Detects formulas in text — returns list of FormattedFormula.

    Implementations: RegexDetector, StructuredParser, etc.
    Input: plain text string
    Output: list of detected formulas with positions
    """

    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Tool registry metadata."""
        ...

    @abstractmethod
    def detect(self, text: str) -> list[DetectedFormulaSpan]:
        """Detect formulas in text, return spans with positions."""
        ...


class FormulaOCRTool(ABC):
    """Extracts formulas from images — returns LaTeX.

    Implementations: Pix2TextOCR, RapidLaTeXOCR, ClaudeVisionOCR, etc.
    Input: image bytes
    Output: FormattedFormula with LaTeX
    """

    @abstractmethod
    def metadata(self) -> ToolMetadata:
        ...

    @abstractmethod
    def recognize(self, image_bytes: bytes, width: int = 0, height: int = 0) -> FormattedFormula | None:
        """Convert an equation image to a FormattedFormula."""
        ...


class FormulaRendererTool(ABC):
    """Renders a FormattedFormula to a specific output format.

    Implementations: MathMLRenderer, OmmlRenderer, MathTextRenderer, etc.
    Input: FormattedFormula (with LaTeX)
    Output: FormattedFormula (with target format populated)
    """

    @abstractmethod
    def metadata(self) -> ToolMetadata:
        ...

    @abstractmethod
    def render(self, formula: FormattedFormula) -> FormattedFormula:
        """Populate the target format field on the formula."""
        ...

    @abstractmethod
    def target_format(self) -> str:
        """Which format this renderer produces: 'mathml', 'omml', 'html', etc."""
        ...


class FormulaValidatorTool(ABC):
    """Validates that a formula is well-formed.

    Implementations: SympyValidator, SchemaValidator, etc.
    Input: FormattedFormula
    Output: validation result (pass/fail + reason)
    """

    @abstractmethod
    def metadata(self) -> ToolMetadata:
        ...

    @abstractmethod
    def validate(self, formula: FormattedFormula) -> ValidationResult:
        """Check if the formula is mathematically well-formed."""
        ...


class FormulaClassifierTool(ABC):
    """Classifies whether an image contains an equation.

    Implementations: HeuristicClassifier, MLClassifier, etc.
    Input: image bytes + dimensions
    Output: classification result (is_equation, confidence)
    """

    @abstractmethod
    def metadata(self) -> ToolMetadata:
        ...

    @abstractmethod
    def classify(self, image_bytes: bytes, width: int, height: int) -> ClassificationResult:
        """Determine if an image contains a mathematical equation."""
        ...


# ---------------------------------------------------------------------------
# Result types — explicit contracts (rough_notes.md: handoff contracts)
# ---------------------------------------------------------------------------

@dataclass
class DetectedFormulaSpan:
    """A detected formula with position in the source text."""
    formula: FormattedFormula
    start: int = 0                      # Character offset in source text
    end: int = 0
    original_text: str = ""             # The raw text that was matched


@dataclass
class ValidationResult:
    """Result from a formula validator."""
    is_valid: bool = True
    error_message: str = ""
    parsed_expression: Any = None       # e.g., SymPy expression


@dataclass
class ClassificationResult:
    """Result from an image classifier."""
    is_equation: bool = False
    confidence: float = 0.0
    equation_type: str = ""             # "inline", "display", "table_formula"
