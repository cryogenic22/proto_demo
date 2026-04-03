"""
Formula Tool Registry — central, queryable registry for all formula tools.

Follows rough_notes.md Module 1 (Tool Registry):
- Metadata-first: the registry entry is the source of truth
- Tools are versioned and queryable by capability
- Side-effect profiles declared and enforced
- No inline tool definitions — everything goes through the registry

The orchestrator queries this registry to assemble the right tool pool
for each formula processing step.
"""

from __future__ import annotations

import logging
from typing import Any

from src.formatter.formula.base import (
    FormulaClassifierTool,
    FormulaDetectorTool,
    FormulaOCRTool,
    FormulaRendererTool,
    FormulaValidatorTool,
    ToolMetadata,
)
from src.formatter.formula.ir import FormulaComplexity, FormulaType

logger = logging.getLogger(__name__)


class FormulaToolRegistry:
    """Central registry for all formula processing tools.

    Usage:
        registry = FormulaToolRegistry()
        registry.register_detector(RegexDetector())
        registry.register_renderer(MathMLRenderer())

        # Query by capability
        detectors = registry.get_detectors(complexity=FormulaComplexity.INLINE)
        renderers = registry.get_renderers(target_format="mathml")
    """

    def __init__(self):
        self._detectors: dict[str, FormulaDetectorTool] = {}
        self._ocr_tools: dict[str, FormulaOCRTool] = {}
        self._renderers: dict[str, FormulaRendererTool] = {}
        self._validators: dict[str, FormulaValidatorTool] = {}
        self._classifiers: dict[str, FormulaClassifierTool] = {}

    # -- Registration --

    def register_detector(self, tool: FormulaDetectorTool) -> None:
        meta = tool.metadata()
        self._detectors[meta.name] = tool
        logger.debug("Registered detector: %s v%s", meta.name, meta.version)

    def register_ocr(self, tool: FormulaOCRTool) -> None:
        meta = tool.metadata()
        self._ocr_tools[meta.name] = tool
        logger.debug("Registered OCR: %s v%s", meta.name, meta.version)

    def register_renderer(self, tool: FormulaRendererTool) -> None:
        meta = tool.metadata()
        self._renderers[meta.name] = tool
        logger.debug("Registered renderer: %s v%s", meta.name, meta.version)

    def register_validator(self, tool: FormulaValidatorTool) -> None:
        meta = tool.metadata()
        self._validators[meta.name] = tool
        logger.debug("Registered validator: %s v%s", meta.name, meta.version)

    def register_classifier(self, tool: FormulaClassifierTool) -> None:
        meta = tool.metadata()
        self._classifiers[meta.name] = tool
        logger.debug("Registered classifier: %s v%s", meta.name, meta.version)

    # -- Discovery (queryable registry) --

    def get_detectors(
        self,
        complexity: FormulaComplexity | None = None,
        formula_type: FormulaType | None = None,
    ) -> list[FormulaDetectorTool]:
        """Get detectors that support the given complexity/type, ranked by priority."""
        results = list(self._detectors.values())
        if complexity:
            results = [
                t for t in results
                if complexity in t.metadata().supported_complexities
            ]
        if formula_type:
            results = [
                t for t in results
                if formula_type in t.metadata().supported_types
            ]
        results.sort(key=lambda t: t.metadata().priority, reverse=True)
        return results

    def get_ocr_tools(self, requires_gpu: bool | None = None) -> list[FormulaOCRTool]:
        """Get OCR tools, optionally filtered by GPU requirement."""
        results = list(self._ocr_tools.values())
        if requires_gpu is not None:
            results = [t for t in results if t.metadata().requires_gpu == requires_gpu]
        results.sort(key=lambda t: t.metadata().priority, reverse=True)
        return results

    def get_renderers(self, target_format: str | None = None) -> list[FormulaRendererTool]:
        """Get renderers, optionally filtered by target format."""
        results = list(self._renderers.values())
        if target_format:
            results = [t for t in results if t.target_format() == target_format]
        results.sort(key=lambda t: t.metadata().priority, reverse=True)
        return results

    def get_validators(self) -> list[FormulaValidatorTool]:
        results = list(self._validators.values())
        results.sort(key=lambda t: t.metadata().priority, reverse=True)
        return results

    def get_classifiers(self) -> list[FormulaClassifierTool]:
        results = list(self._classifiers.values())
        results.sort(key=lambda t: t.metadata().priority, reverse=True)
        return results

    # -- Introspection --

    def list_tools(self) -> dict[str, list[dict]]:
        """List all registered tools with metadata (for debugging/observability)."""
        def _meta_dict(tool: Any) -> dict:
            m = tool.metadata()
            return {
                "name": m.name,
                "version": m.version,
                "side_effects": m.side_effects.value,
                "priority": m.priority,
            }

        return {
            "detectors": [_meta_dict(t) for t in self._detectors.values()],
            "ocr": [_meta_dict(t) for t in self._ocr_tools.values()],
            "renderers": [_meta_dict(t) for t in self._renderers.values()],
            "validators": [_meta_dict(t) for t in self._validators.values()],
            "classifiers": [_meta_dict(t) for t in self._classifiers.values()],
        }

    @property
    def total_tools(self) -> int:
        return (
            len(self._detectors) + len(self._ocr_tools) + len(self._renderers)
            + len(self._validators) + len(self._classifiers)
        )
