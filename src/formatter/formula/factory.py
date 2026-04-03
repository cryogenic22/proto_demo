"""
Formula system factory — assembles the registry and orchestrator with defaults.

This is the entry point for the formula system. Call `create_formula_system()`
to get a fully configured orchestrator ready to process formulas.

The factory pattern keeps configuration in one place and lets you swap
backends by changing config, not code.
"""

from __future__ import annotations

import logging
import os

from src.formatter.formula.orchestrator import FormulaOrchestrator, OrchestratorConfig
from src.formatter.formula.registry import FormulaToolRegistry
from src.formatter.formula.tools.regex_detector import RegexFormulaDetector
from src.formatter.formula.tools.structured_parser import StructuredParser
from src.formatter.formula.tools.renderers import (
    HTMLFormulaRenderer,
    MathMLFormulaRenderer,
    OmmlFormulaRenderer,
)
from src.formatter.formula.tools.image_classifier import HeuristicImageClassifier
from src.formatter.formula.tools.ocr_backends import (
    ClaudeVisionOCR,
    LocalLaTeXOCR,
    PlaceholderOCR,
)

logger = logging.getLogger(__name__)


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

    # -- Register image classifier (always available, no dependencies) --
    registry.register_classifier(HeuristicImageClassifier())

    # -- Register OCR tools (graceful degradation) --

    # Always register placeholder as low-priority fallback
    registry.register_ocr(PlaceholderOCR())

    # Claude Vision OCR — register if API key is available
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        registry.register_ocr(ClaudeVisionOCR(api_key=api_key))
        logger.info("Factory: registered ClaudeVisionOCR")

    # Local LaTeX OCR — register if pix2tex/rapid_latex_ocr is installed
    local_ocr = LocalLaTeXOCR()
    if local_ocr._available:
        registry.register_ocr(local_ocr)
        logger.info("Factory: registered LocalLaTeXOCR (%s)", local_ocr._backend)

    return FormulaOrchestrator(registry, config or OrchestratorConfig())
