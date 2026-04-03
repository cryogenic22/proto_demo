"""
Formula system factory — assembles the registry and orchestrator with defaults.

This is the entry point for the formula system. Call `create_formula_system()`
to get a fully configured orchestrator ready to process formulas.

The factory pattern keeps configuration in one place and lets you swap
backends by changing config, not code.
"""

from __future__ import annotations

from src.formatter.formula.orchestrator import FormulaOrchestrator, OrchestratorConfig
from src.formatter.formula.registry import FormulaToolRegistry
from src.formatter.formula.tools.regex_detector import RegexFormulaDetector
from src.formatter.formula.tools.structured_parser import StructuredParser
from src.formatter.formula.tools.renderers import (
    HTMLFormulaRenderer,
    MathMLFormulaRenderer,
    OmmlFormulaRenderer,
)


def create_formula_system(
    config: OrchestratorConfig | None = None,
) -> FormulaOrchestrator:
    """Create a fully wired formula orchestrator with default tools.

    Usage:
        orchestrator = create_formula_system()
        spans = orchestrator.process_text("CO2 and AUC0-inf")

    With custom config:
        config = OrchestratorConfig(enable_image_ocr=True)
        orchestrator = create_formula_system(config)
    """
    registry = FormulaToolRegistry()

    # -- Register detectors --
    registry.register_detector(RegexFormulaDetector())
    registry.register_detector(StructuredParser())

    # -- Register renderers --
    registry.register_renderer(HTMLFormulaRenderer())
    registry.register_renderer(MathMLFormulaRenderer())
    registry.register_renderer(OmmlFormulaRenderer())

    # -- Future: register OCR tools, validators, classifiers --
    # registry.register_ocr(Pix2TextOCR())
    # registry.register_validator(SympyValidator())
    # registry.register_classifier(HeuristicImageClassifier())

    return FormulaOrchestrator(registry, config or OrchestratorConfig())
