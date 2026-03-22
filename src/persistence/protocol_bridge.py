"""
Protocol Bridge — converts PipelineOutput dicts to Protocol objects.

Bridges the extraction pipeline (which produces PipelineOutput) and the
knowledge-element store (which persists Protocol objects).
"""

from __future__ import annotations

import hashlib
import re

from src.models.protocol import Protocol, ProtocolMetadata


def _slug(text: str) -> str:
    """Convert a filename to a URL-safe slug."""
    name = re.sub(r"\.[^.]+$", "", text)  # strip extension
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return name or "unknown"


def _protocol_id_from(filename: str) -> str:
    """Generate a stable protocol_id from the filename hash + slug."""
    slug = _slug(filename)
    digest = hashlib.sha256(filename.encode()).hexdigest()[:8]
    return f"{slug}_{digest}"


def pipeline_output_to_protocol(
    result_json: dict,
    filename: str,
) -> Protocol:
    """Convert a serialized PipelineOutput dict to a Protocol.

    Args:
        result_json: Serialized PipelineOutput (from model_dump_json()).
        filename: Original uploaded filename.

    Returns:
        A valid Protocol object ready for persistence.
    """
    protocol_id = _protocol_id_from(filename)

    return Protocol(
        protocol_id=protocol_id,
        document_name=result_json.get("document_name", filename),
        document_hash=result_json.get("document_hash", ""),
        total_pages=result_json.get("total_pages", 0),
        metadata=ProtocolMetadata(),
        tables=result_json.get("tables", []),
        procedures=result_json.get("procedures", []),
        pipeline_version=result_json.get("pipeline_version", "0.1.0"),
    )
