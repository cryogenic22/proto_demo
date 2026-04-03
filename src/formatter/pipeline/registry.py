"""
Pipeline Tool Registry — central, queryable registry for ingestors and renderers.

Follows the same pattern as src/formatter/formula/registry.py:
- Metadata-first: the registry entry is the source of truth
- Tools are versioned and queryable by format
- Side-effect profiles declared
- No inline tool definitions — everything goes through the registry

The PipelineOrchestrator queries this registry to find the right ingestor
or renderer for a given format.
"""

from __future__ import annotations

import logging
from typing import Any

from src.formatter.pipeline.base import IngestorTool, RendererTool

logger = logging.getLogger(__name__)


class PipelineToolRegistry:
    """Central registry for all document ingestors and renderers.

    Usage:
        registry = PipelineToolRegistry()
        registry.register_ingestor(PDFIngestorAdapter())
        registry.register_renderer(HTMLRendererAdapter())

        # Query by format
        pdf_ingestor = registry.get_ingestor("pdf")
        html_renderer = registry.get_renderer("html")
    """

    def __init__(self):
        self._ingestors: dict[str, IngestorTool] = {}
        self._renderers: dict[str, RendererTool] = {}

    # -- Registration --

    def register_ingestor(self, tool: IngestorTool) -> None:
        """Register an ingestor tool. Keyed by each supported format."""
        meta = tool.metadata()
        for fmt in tool.supported_formats():
            self._ingestors[fmt] = tool
            logger.debug(
                "Registered ingestor: %s v%s for format '%s'",
                meta.name, meta.version, fmt,
            )

    def register_renderer(self, tool: RendererTool) -> None:
        """Register a renderer tool. Keyed by its output format."""
        meta = tool.metadata()
        fmt = tool.output_format()
        self._renderers[fmt] = tool
        logger.debug(
            "Registered renderer: %s v%s for format '%s'",
            meta.name, meta.version, fmt,
        )

    # -- Discovery --

    def get_ingestor(self, format: str) -> IngestorTool | None:
        """Get the ingestor registered for the given format."""
        return self._ingestors.get(format)

    def get_renderer(self, format: str) -> RendererTool | None:
        """Get the renderer registered for the given format."""
        return self._renderers.get(format)

    # -- Introspection --

    def list_tools(self) -> dict[str, list[dict]]:
        """List all registered tools with metadata (for debugging/observability)."""
        def _meta_dict(tool: Any) -> dict:
            m = tool.metadata()
            return {
                "name": m.name,
                "version": m.version,
                "description": m.description,
                "side_effects": m.side_effects.value,
            }

        # Deduplicate ingestors (one tool may cover multiple formats)
        seen_ingestors: dict[str, dict] = {}
        for tool in self._ingestors.values():
            name = tool.metadata().name
            if name not in seen_ingestors:
                entry = _meta_dict(tool)
                entry["supported_formats"] = tool.supported_formats()
                seen_ingestors[name] = entry

        seen_renderers: dict[str, dict] = {}
        for tool in self._renderers.values():
            name = tool.metadata().name
            if name not in seen_renderers:
                entry = _meta_dict(tool)
                entry["output_format"] = tool.output_format()
                seen_renderers[name] = entry

        return {
            "ingestors": list(seen_ingestors.values()),
            "renderers": list(seen_renderers.values()),
        }

    @property
    def total_tools(self) -> int:
        """Total number of unique tools registered."""
        ingestor_names = {t.metadata().name for t in self._ingestors.values()}
        renderer_names = {t.metadata().name for t in self._renderers.values()}
        return len(ingestor_names) + len(renderer_names)
