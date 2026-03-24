"""
Entity — base node in the SMB knowledge graph.

Every entity has: type, name, properties, provenance, confidence.
Entity types are defined in YAML domain schemas.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MANUAL = "manual"


class ProvenanceInfo(BaseModel):
    """Tracks where an entity came from — essential for audit."""
    source_type: str = ""  # "table_cell", "section_text", "footnote", "inference"
    source_id: str | None = None
    table_name: str | None = None
    row_index: int | None = None
    col_index: int | None = None
    section_title: str | None = None
    page_number: int | None = None
    raw_text: str | None = None
    extraction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    extraction_method: str | None = None  # "ocr", "vlm", "text", "rule", "inference"


class Entity(BaseModel):
    """Base entity in the structured model knowledge graph."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_type: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    provenance: ProvenanceInfo = Field(default_factory=ProvenanceInfo)
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    version: int = 1
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    tags: list[str] = Field(default_factory=list)

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        if not v or not v[0].isupper():
            raise ValueError(f"Entity type must be PascalCase, got: {v}")
        return v

    def get_property(self, key: str, default: Any = None) -> Any:
        return self.properties.get(key, default)

    def has_property(self, key: str) -> bool:
        return key in self.properties

    def deterministic_id(self, document_id: str) -> str:
        """Generate a deterministic ID for merge/dedup across re-extractions."""
        key_parts = [document_id, self.entity_type, self.name]
        for k in sorted(self.properties.keys()):
            if k in ("day_number", "arm_name", "phase_name", "cpt_code",
                      "visit_label", "canonical_name", "footnote_marker"):
                key_parts.append(f"{k}={self.properties[k]}")
        raw = "|".join(str(p) for p in key_parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage/API."""
        return self.model_dump(mode="json")
