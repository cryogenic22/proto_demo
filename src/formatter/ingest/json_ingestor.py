"""
JSON Ingestor — pluggable, auto-detecting JSON document ingestor.

Provides a schema-agnostic framework for ingesting JSON documents. Each JSON
schema (USDM, Protocol IR, FormattedDocument IR, etc.) is handled by a
pluggable detector + parser pair registered in a JsonSchemaRegistry.

Detection is content-based (inspects root keys), not filename-based.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from src.formatter.extractor import FormattedDocument

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract contracts
# ---------------------------------------------------------------------------

class JsonSchemaDetector(ABC):
    """Detects whether a parsed JSON dict matches a specific schema."""

    @abstractmethod
    def schema_id(self) -> str:
        """Unique identifier for this schema (e.g., 'usdm', 'protocol_ir')."""
        ...

    @abstractmethod
    def detect(self, data: dict) -> bool:
        """Return True if the data matches this schema's signature."""
        ...

    @abstractmethod
    def priority(self) -> int:
        """Lower values are checked first. Most specific detectors get lower priority."""
        ...


class JsonSchemaParser(ABC):
    """Parses a detected JSON schema into pipeline-consumable objects.

    Not all parsers implement all three output methods. Return None for
    unsupported output types.
    """

    @abstractmethod
    def schema_id(self) -> str:
        """Must match the corresponding detector's schema_id."""
        ...

    @abstractmethod
    def to_formatted_document(self, data: dict, filename: str = "") -> FormattedDocument:
        """Convert JSON data to a FormattedDocument for the formatter pipeline."""
        ...

    def to_protocol(self, data: dict, filename: str = "") -> Any:
        """Convert JSON data to a Protocol for persistence + KE generation.

        Returns None if this schema doesn't support Protocol output.
        """
        return None

    def to_extraction_input(self, data: dict, filename: str = "") -> Any:
        """Convert JSON data to an ExtractionInput for the SMB engine.

        Returns None if this schema doesn't support SMB output.
        """
        return None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class JsonSchemaRegistry:
    """Registry of detector-parser pairs. Detectors run in priority order."""

    def __init__(self) -> None:
        self._entries: list[tuple[JsonSchemaDetector, JsonSchemaParser]] = []

    def register(self, detector: JsonSchemaDetector, parser: JsonSchemaParser) -> None:
        """Register a detector-parser pair. Validates matching schema_id."""
        if detector.schema_id() != parser.schema_id():
            raise ValueError(
                f"Detector schema_id '{detector.schema_id()}' != "
                f"parser schema_id '{parser.schema_id()}'"
            )
        self._entries.append((detector, parser))
        # Keep sorted by priority (lowest first)
        self._entries.sort(key=lambda e: e[0].priority())
        logger.debug("Registered JSON schema: %s (priority=%d)",
                      detector.schema_id(), detector.priority())

    def detect_schema(self, data: dict) -> str:
        """Run detectors in priority order, return first match.

        Raises ValueError if no detector matches.
        """
        for detector, _ in self._entries:
            if detector.detect(data):
                return detector.schema_id()
        keys_preview = list(data.keys())[:10]
        raise ValueError(
            f"No JSON schema detector matched. Root keys: {keys_preview}. "
            f"Registered schemas: {[d.schema_id() for d, _ in self._entries]}"
        )

    def get_parser(self, schema_id: str) -> JsonSchemaParser:
        """Get the parser for a given schema_id."""
        for detector, parser in self._entries:
            if detector.schema_id() == schema_id:
                return parser
        raise ValueError(f"No parser registered for schema: {schema_id}")

    @property
    def registered_schemas(self) -> list[str]:
        """List all registered schema IDs in priority order."""
        return [d.schema_id() for d, _ in self._entries]


# ---------------------------------------------------------------------------
# Master ingestor
# ---------------------------------------------------------------------------

class JsonIngestor:
    """Top-level JSON ingestor. Parses JSON, detects schema, routes to parser.

    This is the class that gets wrapped as an IngestorTool in the pipeline.
    """

    def __init__(self, registry: JsonSchemaRegistry) -> None:
        self._registry = registry

    def ingest(self, content: bytes | str, filename: str = "") -> FormattedDocument:
        """Parse JSON content and return a FormattedDocument.

        Args:
            content: JSON string or bytes.
            filename: Optional source filename for metadata.

        Returns:
            FormattedDocument from the matched schema parser.

        Raises:
            ValueError: If JSON is invalid or no schema detector matches.
        """
        if isinstance(content, bytes):
            content = content.decode("utf-8")

        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("JSON root must be an object, not an array or scalar.")

        schema_id = self._registry.detect_schema(data)
        parser = self._registry.get_parser(schema_id)
        logger.info("JSON schema detected: %s (file: %s)", schema_id, filename)
        return parser.to_formatted_document(data, filename)

    def detect_and_parse(self, data: dict, filename: str = "") -> tuple[str, JsonSchemaParser]:
        """Detect schema and return (schema_id, parser) for advanced callers.

        Useful when the caller needs access to to_protocol() or
        to_extraction_input() beyond just to_formatted_document().
        """
        schema_id = self._registry.detect_schema(data)
        parser = self._registry.get_parser(schema_id)
        return schema_id, parser

    @property
    def registry(self) -> JsonSchemaRegistry:
        return self._registry


# ---------------------------------------------------------------------------
# Default registry factory
# ---------------------------------------------------------------------------

def create_default_registry() -> JsonSchemaRegistry:
    """Create a registry pre-loaded with all built-in schema plugins."""
    registry = JsonSchemaRegistry()

    # Import plugins — each module exports DETECTOR and PARSER instances
    from src.formatter.ingest.json_schemas import ALL_PLUGINS
    for detector, parser in ALL_PLUGINS:
        registry.register(detector, parser)

    return registry
