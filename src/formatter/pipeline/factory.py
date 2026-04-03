"""
Pipeline Factory — default assembly of the full pipeline.

Creates a PipelineOrchestrator with all ingestors and renderers registered,
plus optional FormulaOrchestrator integration. This is the single entry
point for consumers who just want "everything wired up."

Usage:
    from src.formatter.pipeline.factory import create_pipeline

    pipeline = create_pipeline()
    html = pipeline.convert("Hello world", "text", "html")
"""

from __future__ import annotations

import logging
from typing import Any

from src.formatter.pipeline.adapters import (
    ALL_INGESTOR_ADAPTERS,
    ALL_RENDERER_ADAPTERS,
)
from src.formatter.pipeline.orchestrator import PipelineOrchestrator
from src.formatter.pipeline.registry import PipelineToolRegistry

logger = logging.getLogger(__name__)


def create_pipeline(
    config: dict[str, Any] | None = None,
    formula_orchestrator: Any | None = None,
) -> PipelineOrchestrator:
    """Assemble the full pipeline with all ingestors, renderers, and formula processing.

    If no formula_orchestrator is provided, the factory creates a default one
    using create_formula_system(). Pass formula_orchestrator=False to explicitly
    disable formula processing.

    Args:
        config: Optional configuration dict (reserved for future use).
        formula_orchestrator: Optional FormulaOrchestrator instance for
            formula detection/rendering integration. Pass False to disable.
            If None (default), a default formula system is created.

    Returns:
        A fully-configured PipelineOrchestrator ready for use.
    """
    registry = PipelineToolRegistry()

    # Register all ingestor adapters
    for adapter_cls in ALL_INGESTOR_ADAPTERS:
        try:
            adapter = adapter_cls()
            registry.register_ingestor(adapter)
        except Exception as e:
            logger.warning(
                "Failed to register ingestor %s: %s",
                adapter_cls.__name__, e,
            )

    # Register all renderer adapters
    for adapter_cls in ALL_RENDERER_ADAPTERS:
        try:
            adapter = adapter_cls()
            registry.register_renderer(adapter)
        except Exception as e:
            logger.warning(
                "Failed to register renderer %s: %s",
                adapter_cls.__name__, e,
            )

    # Wire up formula system (default: auto-create; False: disable)
    if formula_orchestrator is False:
        formula_orchestrator = None
    elif formula_orchestrator is None:
        try:
            from src.formatter.formula.factory import create_formula_system
            formula_orchestrator = create_formula_system()
            logger.info("Formula system wired into pipeline")
        except Exception as e:
            logger.warning("Failed to create formula system: %s", e)
            formula_orchestrator = None

    logger.info(
        "Pipeline assembled: %d tools (%d ingestors, %d renderers)",
        registry.total_tools,
        len(ALL_INGESTOR_ADAPTERS),
        len(ALL_RENDERER_ADAPTERS),
    )

    return PipelineOrchestrator(
        registry=registry,
        formula_orchestrator=formula_orchestrator,
    )
