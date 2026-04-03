"""
Formula Orchestrator — selects and chains formula tools per complexity.

Follows rough_notes.md:
- Module 9 (Tool Pool Assembly): assembles tools per step, not the full registry
- Section 9 (Agent Types): orchestrator decomposes, executors carry out
- Section 10 (Harness Pattern): configurable, not hardcoded workflows

The orchestrator does NOT hardcode which tools to use. It queries the
registry for tools matching the current formula's complexity, then chains
them in order: detect → validate → render.

Different formula complexities trigger different tool chains:
- INLINE:     RegexDetector → HTMLRenderer
- STRUCTURED: RegexDetector + StructuredParser → MathMLRenderer → OmmlRenderer
- RENDERED:   ImageClassifier → OCRTool → Validator → MathMLRenderer → OmmlRenderer
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.formatter.formula.base import (
    ClassificationResult,
    DetectedFormulaSpan,
    ValidationResult,
)
from src.formatter.formula.ir import (
    FormattedFormula,
    FormulaComplexity,
    FormulaSource,
    FormulaType,
)
from src.formatter.formula.registry import FormulaToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for the formula orchestrator.

    This is the YAML-equivalent config (rough_notes.md Section 10).
    Change behavior by changing config, not code.
    """
    # Detection
    enable_regex: bool = True
    enable_structured_parser: bool = True
    enable_image_ocr: bool = False          # Off by default — opt-in

    # Rendering targets (which output formats to pre-render)
    render_targets: list[str] = field(default_factory=lambda: ["html", "mathml"])

    # Validation
    validate_formulas: bool = False         # SymPy validation — opt-in
    min_ocr_confidence: float = 0.6         # Below this → flag for review
    escalate_to_vlm: bool = False           # Use Claude Vision as fallback

    # Image classification
    classify_images: bool = False           # Auto-detect equation images
    min_classification_confidence: float = 0.7

    # Tool pool limits
    max_detectors_per_step: int = 3
    max_ocr_tools_per_step: int = 2


class FormulaOrchestrator:
    """Orchestrates formula detection, validation, and rendering.

    The orchestrator is the "brain" — it decides WHICH tools to call and in
    what order, but delegates all actual work to registered tools. This keeps
    the orchestrator thin and the tools independently testable.

    Usage:
        registry = FormulaToolRegistry()
        # ... register tools ...
        orchestrator = FormulaOrchestrator(registry, config)

        # Process text formulas
        results = orchestrator.process_text("CO2 levels and AUC0-inf")

        # Process an image that might contain an equation
        formula = orchestrator.process_image(img_bytes, width, height)

        # Render a formula to a specific format
        formula = orchestrator.render_formula(formula, target="mathml")
    """

    def __init__(
        self,
        registry: FormulaToolRegistry,
        config: OrchestratorConfig | None = None,
    ):
        self._registry = registry
        self._config = config or OrchestratorConfig()

    @property
    def config(self) -> OrchestratorConfig:
        return self._config

    # ------------------------------------------------------------------
    # Text formula processing (Tier 1-3)
    # ------------------------------------------------------------------

    def process_text(self, text: str) -> list[DetectedFormulaSpan]:
        """Detect all formulas in a text string.

        Tool chain: detectors (by complexity) → validators → renderers.
        Returns detected spans with fully-populated FormattedFormula objects.
        """
        all_spans: list[DetectedFormulaSpan] = []

        # Step 1: Run detectors (assemble tool pool per complexity tier)
        if self._config.enable_regex:
            detectors = self._registry.get_detectors(
                complexity=FormulaComplexity.INLINE,
            )
            for detector in detectors[:self._config.max_detectors_per_step]:
                try:
                    spans = detector.detect(text)
                    all_spans.extend(spans)
                except Exception as e:
                    logger.warning("Detector %s failed: %s",
                                   detector.metadata().name, e)

        if self._config.enable_structured_parser:
            parsers = self._registry.get_detectors(
                complexity=FormulaComplexity.STRUCTURED,
            )
            for parser in parsers[:self._config.max_detectors_per_step]:
                try:
                    spans = parser.detect(text)
                    all_spans.extend(spans)
                except Exception as e:
                    logger.warning("Parser %s failed: %s",
                                   parser.metadata().name, e)

        # Step 2: Deduplicate overlapping spans (keep longest match)
        all_spans = self._deduplicate_spans(all_spans)

        # Step 3: Validate (optional)
        if self._config.validate_formulas:
            all_spans = self._validate_spans(all_spans)

        # Step 4: Pre-render to target formats
        for span in all_spans:
            for target in self._config.render_targets:
                span.formula = self.render_formula(span.formula, target=target)

        return all_spans

    # ------------------------------------------------------------------
    # Image formula processing (Tier 4)
    # ------------------------------------------------------------------

    def classify_image(
        self,
        image_bytes: bytes,
        width: int,
        height: int,
    ) -> ClassificationResult:
        """Classify whether an image contains a mathematical equation.

        Uses registered classifier tools. Returns classification result.
        """
        classifiers = self._registry.get_classifiers()
        if not classifiers:
            return ClassificationResult(is_equation=False, confidence=0.0)

        for classifier in classifiers:
            try:
                result = classifier.classify(image_bytes, width, height)
                if result.confidence >= self._config.min_classification_confidence:
                    return result
            except Exception as e:
                logger.warning("Classifier %s failed: %s",
                               classifier.metadata().name, e)

        return ClassificationResult(is_equation=False, confidence=0.0)

    def process_image(
        self,
        image_bytes: bytes,
        width: int = 0,
        height: int = 0,
        page_number: int = -1,
    ) -> FormattedFormula | None:
        """Extract a formula from an equation image.

        Tool chain: classifier → OCR → validator → renderers.
        Returns None if the image doesn't contain a recognizable equation.
        """
        if not self._config.enable_image_ocr:
            return None

        # Step 1: Classify (is this an equation?)
        if self._config.classify_images:
            classification = self.classify_image(image_bytes, width, height)
            if not classification.is_equation:
                return None

        # Step 2: OCR (extract LaTeX from image)
        ocr_tools = self._registry.get_ocr_tools()
        formula = None

        for ocr in ocr_tools[:self._config.max_ocr_tools_per_step]:
            try:
                formula = ocr.recognize(image_bytes, width, height)
                if formula and formula.has_latex() and formula.confidence >= self._config.min_ocr_confidence:
                    break
                # Low confidence — try next tool
                formula = None
            except Exception as e:
                logger.warning("OCR %s failed: %s", ocr.metadata().name, e)

        # Step 3: Escalate to VLM if local OCR failed/low confidence
        if formula is None and self._config.escalate_to_vlm:
            vlm_tools = self._registry.get_ocr_tools()
            vlm_tools = [t for t in vlm_tools if t.metadata().requires_network]
            for vlm in vlm_tools:
                try:
                    formula = vlm.recognize(image_bytes, width, height)
                    if formula and formula.has_latex():
                        formula.source = FormulaSource.VLM
                        break
                except Exception as e:
                    logger.warning("VLM %s failed: %s", vlm.metadata().name, e)

        if formula is None:
            return None

        # Step 4: Set provenance
        formula.source_page = page_number
        formula.complexity = FormulaComplexity.RENDERED

        # Step 5: Validate
        if self._config.validate_formulas:
            validators = self._registry.get_validators()
            for validator in validators:
                result = validator.validate(formula)
                if not result.is_valid:
                    formula.needs_review = True
                    logger.info("Formula flagged for review: %s", result.error_message)

        # Step 6: Pre-render
        for target in self._config.render_targets:
            formula = self.render_formula(formula, target=target)

        return formula

    # ------------------------------------------------------------------
    # Rendering (format-specific output)
    # ------------------------------------------------------------------

    def render_formula(
        self,
        formula: FormattedFormula,
        target: str = "html",
    ) -> FormattedFormula:
        """Render a formula to a specific output format.

        Finds the highest-priority renderer for the target format and applies it.
        The renderer populates the corresponding field on the formula
        (e.g., target="mathml" → formula.mathml).

        This is idempotent — re-rendering an already-rendered formula is a no-op.
        """
        # Check if already rendered
        if target == "mathml" and formula.has_mathml():
            return formula
        if target == "html" and formula.has_html():
            return formula

        renderers = self._registry.get_renderers(target_format=target)
        if not renderers:
            logger.debug("No renderer for target format: %s", target)
            return formula

        for renderer in renderers:
            try:
                return renderer.render(formula)
            except Exception as e:
                logger.warning("Renderer %s failed: %s",
                               renderer.metadata().name, e)

        return formula

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _deduplicate_spans(
        self, spans: list[DetectedFormulaSpan],
    ) -> list[DetectedFormulaSpan]:
        """Remove overlapping detections, keeping the longest match."""
        if not spans:
            return []

        spans.sort(key=lambda s: (s.start, -(s.end - s.start)))
        deduped: list[DetectedFormulaSpan] = []
        last_end = -1

        for span in spans:
            if span.start >= last_end:
                deduped.append(span)
                last_end = span.end

        return deduped

    def _validate_spans(
        self, spans: list[DetectedFormulaSpan],
    ) -> list[DetectedFormulaSpan]:
        """Run validators on all detected spans."""
        validators = self._registry.get_validators()
        if not validators:
            return spans

        for span in spans:
            for validator in validators:
                try:
                    result = validator.validate(span.formula)
                    if not result.is_valid:
                        span.formula.needs_review = True
                except Exception:
                    pass

        return spans
