"""
Pipeline Tool base classes — abstract contracts for ingestors and renderers.

Every pipeline tool implements a typed interface with explicit input/output
contracts. Tools are registered in the PipelineToolRegistry and discovered
by the PipelineOrchestrator at runtime.

Design mirrors src/formatter/formula/base.py:
- Metadata-first: description, version, supported formats declared upfront
- Side-effect profile declared explicitly
- Tools are versioned; the registry is queryable
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.formatter.extractor import FormattedDocument
from src.formatter.formula.base import ToolMetadata


class IngestorTool(ABC):
    """Converts raw document bytes/string to FormattedDocument IR.

    Implementations wrap existing ingestors (FormattingExtractor, DOCXIngestor,
    HTMLIngestor, etc.) as registered tools with metadata and typed contracts.

    Input:  bytes or str content + optional filename
    Output: FormattedDocument intermediate representation
    """

    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Tool registry metadata."""
        ...

    @abstractmethod
    def ingest(self, content: bytes | str, filename: str = "") -> FormattedDocument:
        """Convert raw content to the FormattedDocument IR.

        Args:
            content: Raw document content (bytes for binary formats, str for text).
            filename: Optional source filename for metadata.

        Returns:
            A FormattedDocument intermediate representation.
        """
        ...

    @abstractmethod
    def supported_formats(self) -> list[str]:
        """List of format identifiers this ingestor handles (e.g., ["pdf"])."""
        ...


class RendererTool(ABC):
    """Converts FormattedDocument IR to output bytes or string.

    Implementations wrap existing renderers (DOCXRenderer, HTMLRenderer, etc.)
    as registered tools with metadata and typed contracts.

    Input:  FormattedDocument intermediate representation
    Output: bytes (binary formats) or str (text formats)
    """

    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Tool registry metadata."""
        ...

    @abstractmethod
    def render(self, doc: FormattedDocument) -> bytes | str:
        """Convert a FormattedDocument to the target output format.

        Args:
            doc: A FormattedDocument IR instance.

        Returns:
            Rendered output (str for text formats, bytes for binary formats).
        """
        ...

    @abstractmethod
    def output_format(self) -> str:
        """The format identifier this renderer produces (e.g., "html", "docx")."""
        ...
