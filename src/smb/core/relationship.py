"""
Relationship — directed edge between two entities in the knowledge graph.

Relationships carry properties (e.g., PERFORMED_AT carries mark_type,
occurrence_count, conditions).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class Relationship(BaseModel):
    """A directed relationship between two entities."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    relationship_type: str  # "PERFORMED_AT", "MODIFIED_BY", etc.
    source_entity_id: str
    target_entity_id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    provenance_source: str | None = None  # "table_cell", "inference", "footnote"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class RelationshipBuilder:
    """Fluent builder for creating relationships."""

    def __init__(self, relationship_type: str):
        self._type = relationship_type
        self._source_id: str | None = None
        self._target_id: str | None = None
        self._properties: dict[str, Any] = {}
        self._confidence: float = 1.0
        self._provenance: str | None = None

    def from_entity(self, entity_id: str) -> RelationshipBuilder:
        self._source_id = entity_id
        return self

    def to_entity(self, entity_id: str) -> RelationshipBuilder:
        self._target_id = entity_id
        return self

    def with_property(self, key: str, value: Any) -> RelationshipBuilder:
        self._properties[key] = value
        return self

    def with_properties(self, props: dict[str, Any]) -> RelationshipBuilder:
        self._properties.update(props)
        return self

    def with_confidence(self, score: float) -> RelationshipBuilder:
        self._confidence = score
        return self

    def with_provenance(self, source: str) -> RelationshipBuilder:
        self._provenance = source
        return self

    def build(self) -> Relationship:
        if not self._source_id or not self._target_id:
            raise ValueError("Relationship requires both source and target entity IDs")
        return Relationship(
            relationship_type=self._type,
            source_entity_id=self._source_id,
            target_entity_id=self._target_id,
            properties=self._properties,
            confidence=self._confidence,
            provenance_source=self._provenance,
        )
