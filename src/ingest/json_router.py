"""
JSON Import Router — auto-detects JSON schema and dispatches to the right handler.

Sits between the API endpoint and the schema-specific adapters. Produces a
unified JsonImportResult regardless of whether the input was USDM, Protocol IR,
or FormattedDocument IR.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.formatter.ingest.json_ingestor import JsonSchemaRegistry, create_default_registry
from src.models.protocol import Protocol
from src.persistence.ke_store import create_ke_store

logger = logging.getLogger(__name__)


@dataclass
class JsonImportResult:
    """Unified result from JSON import regardless of schema type."""
    protocol: Protocol
    schema_type: str
    warnings: list[str] = field(default_factory=list)
    tables_count: int = 0
    procedures_count: int = 0
    sections_count: int = 0
    ke_count: int = 0
    smb_built: bool = False


def import_json(
    data: dict,
    filename: str = "",
    registry: JsonSchemaRegistry | None = None,
    force_schema: str | None = None,
) -> JsonImportResult:
    """Auto-detect JSON schema, convert to Protocol, persist, and return result.

    Args:
        data: Parsed JSON dict (root must be an object).
        filename: Original filename for ID generation.
        registry: Optional schema registry (uses default if None).
        force_schema: If set, skip auto-detection and use this schema type.

    Returns:
        JsonImportResult with the persisted Protocol and metadata.

    Raises:
        ValueError: If no schema detector matches or conversion fails.
    """
    if registry is None:
        registry = create_default_registry()

    schema_type = force_schema or registry.detect_schema(data)
    parser = registry.get_parser(schema_type)
    warnings: list[str] = []

    logger.info("JSON import: detected schema '%s' for file '%s'", schema_type, filename)

    # -- Route based on schema type --
    if schema_type == "protocol_ir":
        protocol = _handle_protocol_ir(data, filename, warnings)
    elif schema_type == "usdm":
        protocol = _handle_usdm(data, filename, warnings)
    elif schema_type == "formatted_doc_ir":
        protocol = _handle_formatted_doc_ir(data, filename, warnings)
    else:
        raise ValueError(f"No import handler for schema type: {schema_type}")

    # -- Persist --
    store = create_ke_store()
    existing = store.load_protocol(protocol.protocol_id)
    if existing:
        warnings.append(
            f"Protocol '{protocol.protocol_id}' already exists and will be overwritten."
        )

    store.save_protocol(protocol)

    # -- Generate and persist KEs --
    ke_count = 0
    try:
        kes = protocol.to_ke_graph()
        # Include any KEs already on the protocol (e.g., from USDM)
        kes.extend(protocol.knowledge_elements)
        if kes:
            store.save_knowledge_elements(protocol.protocol_id, kes)
            ke_count = len(kes)
    except Exception as exc:
        warnings.append(f"KE graph generation failed (non-fatal): {exc}")

    # -- Count sections recursively --
    def _count(sections: list) -> int:
        n = len(sections)
        for s in sections:
            children = getattr(s, "children", None) or []
            n += _count(children)
        return n

    return JsonImportResult(
        protocol=protocol,
        schema_type=schema_type,
        warnings=warnings,
        tables_count=len(protocol.tables),
        procedures_count=len(protocol.procedures),
        sections_count=_count(protocol.sections),
        ke_count=ke_count,
        smb_built=(schema_type == "usdm"),
    )


# ---------------------------------------------------------------------------
# Schema-specific handlers
# ---------------------------------------------------------------------------

def _handle_protocol_ir(data: dict, filename: str, warnings: list[str]) -> Protocol:
    """Handle Protocol IR JSON — validate and construct."""
    if not data.get("protocol_id"):
        from src.persistence.protocol_bridge import _protocol_id_from
        data["protocol_id"] = _protocol_id_from(filename or "import.json")
        warnings.append(f"No protocol_id; generated '{data['protocol_id']}' from filename.")
    if not data.get("document_name"):
        data["document_name"] = filename or "imported_protocol.json"
    if "metadata" not in data or data["metadata"] is None:
        data["metadata"] = {}
        warnings.append("No metadata block found; created empty metadata.")

    return Protocol.model_validate(data)


def _handle_usdm(data: dict, filename: str, warnings: list[str]) -> Protocol:
    """Handle USDM JSON — convert via USDMAdapter."""
    from src.smb.adapters.usdm import USDMAdapter

    adapter = USDMAdapter()
    protocol = adapter.to_protocol(data, filename)

    # Attempt SMB build (non-fatal)
    try:
        extraction_input = adapter.to_extraction_input(data, filename)
        if extraction_input.tables:
            from src.smb.core.engine import SMBEngine
            engine = SMBEngine(domain="protocol")
            result = engine.build(extraction_input)
            summary = result.model.summary()
            logger.info(
                "SMB build from USDM: %s entities, %s relationships",
                summary.get("total_entities", 0),
                summary.get("total_relationships", 0),
            )
        else:
            warnings.append("No SoA table reconstructed from USDM; SMB build skipped.")
    except Exception as exc:
        warnings.append(f"SMB build failed (non-fatal): {exc}")
        logger.warning("SMB build failed for USDM import: %s", exc)

    return protocol


def _handle_formatted_doc_ir(data: dict, filename: str, warnings: list[str]) -> Protocol:
    """Handle FormattedDocument IR JSON — create minimal Protocol wrapper."""
    from src.persistence.protocol_bridge import _protocol_id_from

    protocol_id = _protocol_id_from(filename or "formatted_doc.json")
    warnings.append(
        "FormattedDocument IR imported as minimal Protocol. "
        "Use the formatter pipeline for document conversion."
    )

    return Protocol(
        protocol_id=protocol_id,
        document_name=filename or "formatted_document.json",
        metadata={},
    )
