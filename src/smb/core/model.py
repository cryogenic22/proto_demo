"""
StructuredModel — the knowledge graph container.

Holds all entities and relationships for a document. Provides
query methods for downstream consumers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from src.smb.core.entity import Entity
from src.smb.core.relationship import Relationship


class StructuredModel(BaseModel):
    """Complete knowledge graph for one document."""

    document_id: str
    domain: str = "protocol"
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    inference_log: list[dict[str, Any]] = Field(default_factory=list)
    validation_report: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    version: int = 1

    # ── Entity queries ──────────────────────────────────────────────

    def get_entities(self, entity_type: str | None = None) -> list[Entity]:
        """Get all entities, optionally filtered by type."""
        if entity_type is None:
            return self.entities
        return [e for e in self.entities if e.entity_type == entity_type]

    def get_entity_by_id(self, entity_id: str) -> Entity | None:
        for e in self.entities:
            if e.id == entity_id:
                return e
        return None

    def get_entity_by_name(self, name: str, entity_type: str | None = None) -> Entity | None:
        for e in self.entities:
            if e.name == name and (entity_type is None or e.entity_type == entity_type):
                return e
        return None

    # ── Relationship queries ────────────────────────────────────────

    def get_relationships(
        self,
        rel_type: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> list[Relationship]:
        results = self.relationships
        if rel_type:
            results = [r for r in results if r.relationship_type == rel_type]
        if source_id:
            results = [r for r in results if r.source_entity_id == source_id]
        if target_id:
            results = [r for r in results if r.target_entity_id == target_id]
        return results

    def get_related_entities(
        self, entity_id: str, rel_type: str, direction: str = "outgoing"
    ) -> list[Entity]:
        """Get entities related to a given entity via a relationship type."""
        if direction == "outgoing":
            rels = [r for r in self.relationships
                    if r.source_entity_id == entity_id and r.relationship_type == rel_type]
            ids = [r.target_entity_id for r in rels]
        else:
            rels = [r for r in self.relationships
                    if r.target_entity_id == entity_id and r.relationship_type == rel_type]
            ids = [r.source_entity_id for r in rels]
        return [e for e in self.entities if e.id in ids]

    # ── Protocol-specific convenience queries ───────────────────────

    def get_schedule_entries(self) -> list[Entity]:
        """Get all ScheduleEntry entities (Visit × Procedure matrix)."""
        return self.get_entities("ScheduleEntry")

    def get_procedures_at_visit(self, visit_name: str) -> list[Entity]:
        """Get all procedures performed at a specific visit."""
        visit = self.get_entity_by_name(visit_name, "Visit")
        if not visit:
            return []
        entries = self.get_related_entities(visit.id, "HAS_SCHEDULE_ENTRY", "incoming")
        procedures = []
        for entry in entries:
            procs = self.get_related_entities(entry.id, "FOR_PROCEDURE", "outgoing")
            procedures.extend(procs)
        return procedures

    def get_visit_timeline(self) -> list[Entity]:
        """Get visits ordered by day number."""
        visits = self.get_entities("Visit")
        return sorted(visits, key=lambda v: v.get_property("day_number", 9999))

    def get_conditional_entries(self) -> list[Entity]:
        """Get schedule entries that are conditional."""
        return [
            e for e in self.get_schedule_entries()
            if e.get_property("mark_type") == "conditional"
        ]

    def get_firm_entries(self) -> list[Entity]:
        """Get schedule entries that are firm (definitely performed)."""
        return [
            e for e in self.get_schedule_entries()
            if e.get_property("mark_type") == "firm"
        ]

    # ── Graph export ────────────────────────────────────────────────

    def to_graph_dict(self) -> dict[str, Any]:
        """Export as a graph dict for visualization (nodes + edges)."""
        nodes = []
        for e in self.entities:
            nodes.append({
                "id": e.id,
                "type": e.entity_type,
                "label": e.name,
                "properties": e.properties,
                "confidence": e.confidence.value,
            })
        edges = []
        for r in self.relationships:
            edges.append({
                "id": r.id,
                "type": r.relationship_type,
                "source": r.source_entity_id,
                "target": r.target_entity_id,
                "properties": r.properties,
                "confidence": r.confidence,
            })
        return {
            "document_id": self.document_id,
            "domain": self.domain,
            "nodes": nodes,
            "edges": edges,
            "metadata": self.metadata,
            "entity_counts": {
                t: len(self.get_entities(t))
                for t in set(e.entity_type for e in self.entities)
            },
        }

    # ── Stats ───────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        """Quick summary of the model contents."""
        type_counts = {}
        for e in self.entities:
            type_counts[e.entity_type] = type_counts.get(e.entity_type, 0) + 1
        rel_counts = {}
        for r in self.relationships:
            rel_counts[r.relationship_type] = rel_counts.get(r.relationship_type, 0) + 1
        return {
            "document_id": self.document_id,
            "domain": self.domain,
            "total_entities": len(self.entities),
            "total_relationships": len(self.relationships),
            "entity_types": type_counts,
            "relationship_types": rel_counts,
            "version": self.version,
        }
