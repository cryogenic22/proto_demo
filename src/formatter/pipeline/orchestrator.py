"""
Pipeline Orchestrator — registry-based routing for document conversion.

Replaces DocHandler's hardcoded dict with a registry-queried pipeline.
The orchestrator does NOT hardcode which tools to use — it queries the
PipelineToolRegistry for the right ingestor or renderer for each format.

Mirrors the pattern from src/formatter/formula/orchestrator.py:
- Thin orchestrator: delegates all work to registered tools
- Configurable: behavior changes via registry, not code
- Optional FormulaOrchestrator integration for formula processing
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.formatter.extractor import FormattedDocument
from src.formatter.pipeline.registry import PipelineToolRegistry

if TYPE_CHECKING:
    from src.formatter.formula.orchestrator import FormulaOrchestrator

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Registry-based document conversion orchestrator.

    Usage:
        registry = PipelineToolRegistry()
        # ... register tools ...
        orchestrator = PipelineOrchestrator(registry)

        doc = orchestrator.ingest(pdf_bytes, "pdf")
        html = orchestrator.render(doc, "html")
        # or one-shot:
        html = orchestrator.convert(pdf_bytes, "pdf", "html")
    """

    def __init__(
        self,
        registry: PipelineToolRegistry,
        formula_orchestrator: FormulaOrchestrator | None = None,
    ):
        self._registry = registry
        self._formula_orchestrator = formula_orchestrator

    @property
    def registry(self) -> PipelineToolRegistry:
        """Access the underlying tool registry."""
        return self._registry

    @property
    def formula_orchestrator(self) -> FormulaOrchestrator | None:
        """Access the optional formula orchestrator."""
        return self._formula_orchestrator

    def ingest(
        self,
        content: bytes | str,
        format: str,
        filename: str = "",
    ) -> FormattedDocument:
        """Ingest content in the given format and return a FormattedDocument IR.

        Finds the registered ingestor for the format and delegates to it.
        Optionally runs formula processing on the result.

        Args:
            content: Raw document content (bytes or str).
            format: Input format identifier (e.g., "pdf", "html", "text").
            filename: Optional source filename for metadata.

        Returns:
            A FormattedDocument intermediate representation.

        Raises:
            ValueError: If no ingestor is registered for the format.
        """
        ingestor = self._registry.get_ingestor(format)
        if ingestor is None:
            supported = [
                f for f in ("pdf", "docx", "html", "markdown", "text", "pptx", "xlsx")
                if self._registry.get_ingestor(f) is not None
            ]
            raise ValueError(
                f"No ingestor registered for format '{format}'. "
                f"Supported: {supported}"
            )

        logger.debug(
            "Ingesting %s content with %s",
            format, ingestor.metadata().name,
        )
        doc = ingestor.ingest(content, filename)

        # Optional: run formula processing on ingested text
        if self._formula_orchestrator is not None:
            doc = self._process_formulas(doc)

        return doc

    def render(
        self,
        doc: FormattedDocument,
        format: str,
    ) -> bytes | str:
        """Render a FormattedDocument to the given output format.

        Finds the registered renderer for the format and delegates to it.

        Args:
            doc: A FormattedDocument IR instance.
            format: Output format identifier (e.g., "html", "docx", "text").

        Returns:
            Rendered output (str for text formats, bytes for binary formats).

        Raises:
            ValueError: If no renderer is registered for the format.
        """
        renderer = self._registry.get_renderer(format)
        if renderer is None:
            supported = [
                f for f in ("docx", "html", "markdown", "text", "json", "pdf", "pptx")
                if self._registry.get_renderer(f) is not None
            ]
            raise ValueError(
                f"No renderer registered for format '{format}'. "
                f"Supported: {supported}"
            )

        logger.debug(
            "Rendering to %s with %s",
            format, renderer.metadata().name,
        )
        return renderer.render(doc)

    def convert(
        self,
        content: bytes | str,
        input_format: str,
        output_format: str,
        filename: str = "",
    ) -> bytes | str:
        """Convenience method: ingest + render in one call.

        Args:
            content: Raw document content.
            input_format: Source format (e.g., "html", "markdown", "text").
            output_format: Target format (e.g., "docx", "html", "text").
            filename: Optional source filename.

        Returns:
            The rendered output (str or bytes depending on output format).
        """
        doc = self.ingest(content, input_format, filename)
        return self.render(doc, output_format)

    # ------------------------------------------------------------------
    # Formula integration (optional)
    # ------------------------------------------------------------------

    def _process_formulas(self, doc: FormattedDocument) -> FormattedDocument:
        """Run formula detection on all text content in the document.

        Uses the FormulaEnricher to detect formulas in paragraph text and
        map them back to individual FormattedSpan objects. The enricher
        handles offset mapping, edge cases, and error recovery.
        """
        if self._formula_orchestrator is None:
            return doc

        from src.formatter.formula.enricher import FormulaEnricher
        enricher = FormulaEnricher(self._formula_orchestrator)
        return enricher.enrich(doc)
