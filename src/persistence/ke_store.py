"""
Knowledge Element Store — persistence hook for protocol KE graph.

Provides an abstract interface with two implementations:
1. Neo4jKEStore — writes to Neo4j (requires neo4j driver)
2. JsonKEStore — writes to local JSON files (default fallback)

The pipeline calls store.save_protocol(protocol) after extraction.
The UI calls store.load_protocol(protocol_id) to retrieve.
"""

from __future__ import annotations

import abc
import json
import logging
import os
from pathlib import Path
from typing import Any

from src.models.protocol import KnowledgeElement, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class KEStore(abc.ABC):
    """Abstract base for KE persistence."""

    @abc.abstractmethod
    def save_protocol(self, protocol: Protocol) -> str:
        """Save a Protocol object. Returns protocol_id."""
        ...

    @abc.abstractmethod
    def load_protocol(self, protocol_id: str) -> Protocol | None:
        """Load a Protocol by ID. Returns Protocol or None."""
        ...

    @abc.abstractmethod
    def list_protocols(self) -> list[dict[str, Any]]:
        """List all stored protocols (id, name, date, metadata summary)."""
        ...

    @abc.abstractmethod
    def save_knowledge_elements(
        self, protocol_id: str, kes: list[KnowledgeElement]
    ) -> int:
        """Save KEs to the graph. Returns count saved."""
        ...

    @abc.abstractmethod
    def get_knowledge_elements(
        self, protocol_id: str, ke_type: str | None = None
    ) -> list[KnowledgeElement]:
        """Retrieve KEs for a protocol, optionally filtered by type."""
        ...


# ---------------------------------------------------------------------------
# JSON file-based implementation (default)
# ---------------------------------------------------------------------------

class JsonKEStore(KEStore):
    """JSON file-based KE store — default when Neo4j is not configured."""

    def __init__(self, base_dir: str | Path = "data/protocols"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_protocol(self, protocol: Protocol) -> str:
        path = self.base_dir / f"{protocol.protocol_id}.json"
        data = protocol.model_dump(mode="json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Saved protocol %s to %s", protocol.protocol_id, path)
        return protocol.protocol_id

    def load_protocol(self, protocol_id: str) -> Protocol | None:
        path = self.base_dir / f"{protocol_id}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return Protocol(**data)

    def list_protocols(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for path in sorted(self.base_dir.glob("*.json")):
            # Skip KE sidecar files
            if path.stem.endswith("_kes"):
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                results.append({
                    "protocol_id": data.get("protocol_id", path.stem),
                    "document_name": data.get("document_name", ""),
                    "metadata": data.get("metadata", {}),
                    "created_at": data.get("created_at", ""),
                    "total_pages": data.get("total_pages", 0),
                })
            except Exception:
                logger.debug("Skipping unreadable file %s", path)
        return results

    def save_knowledge_elements(
        self, protocol_id: str, kes: list[KnowledgeElement]
    ) -> int:
        path = self.base_dir / f"{protocol_id}_kes.json"
        data = [ke.model_dump(mode="json") for ke in kes]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return len(data)

    def get_knowledge_elements(
        self, protocol_id: str, ke_type: str | None = None
    ) -> list[KnowledgeElement]:
        path = self.base_dir / f"{protocol_id}_kes.json"
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        kes = [KnowledgeElement(**d) for d in data]
        if ke_type:
            kes = [ke for ke in kes if ke.ke_type == ke_type]
        return kes


# ---------------------------------------------------------------------------
# Neo4j implementation
# ---------------------------------------------------------------------------

class Neo4jKEStore(KEStore):
    """Neo4j-backed KE store — activated when NEO4J_URI is configured.

    Requires: pip install neo4j

    Environment variables:
        NEO4J_URI: bolt://localhost:7687
        NEO4J_USER: neo4j
        NEO4J_PASSWORD: password
    """

    def __init__(self, uri: str, user: str, password: str):
        try:
            from neo4j import GraphDatabase  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "neo4j package required for Neo4jKEStore: pip install neo4j"
            )
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Connected to Neo4j at %s", uri)

    # -- protocol ---------------------------------------------------------

    def save_protocol(self, protocol: Protocol) -> str:
        with self.driver.session() as session:
            session.run(
                """
                MERGE (p:Protocol {protocol_id: $pid})
                SET p.document_name = $name,
                    p.document_hash = $hash,
                    p.total_pages = $pages,
                    p.title = $title,
                    p.sponsor = $sponsor,
                    p.phase = $phase,
                    p.therapeutic_area = $ta,
                    p.created_at = $created,
                    p.pipeline_version = $version
                """,
                pid=protocol.protocol_id,
                name=protocol.document_name,
                hash=protocol.document_hash,
                pages=protocol.total_pages,
                title=protocol.metadata.title,
                sponsor=protocol.metadata.sponsor,
                phase=protocol.metadata.phase,
                ta=protocol.metadata.therapeutic_area,
                created=protocol.created_at,
                version=protocol.pipeline_version,
            )
        kes = protocol.to_ke_graph()
        self.save_knowledge_elements(protocol.protocol_id, kes)
        # Also persist full JSON for load_protocol fast-path
        JsonKEStore().save_protocol(protocol)
        return protocol.protocol_id

    def load_protocol(self, protocol_id: str) -> Protocol | None:
        # Full Protocol reconstruction from graph is complex; use JSON cache.
        return JsonKEStore().load_protocol(protocol_id)

    def list_protocols(self) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (p:Protocol) RETURN p ORDER BY p.created_at DESC"
            )
            return [dict(record["p"]) for record in result]

    # -- knowledge elements -----------------------------------------------

    def save_knowledge_elements(
        self, protocol_id: str, kes: list[KnowledgeElement]
    ) -> int:
        with self.driver.session() as session:
            for ke in kes:
                # Upsert KE node
                session.run(
                    """
                    MERGE (k:KnowledgeElement {ke_id: $ke_id})
                    SET k.ke_type = $ke_type,
                        k.title = $title,
                        k.content = $content,
                        k.status = $status,
                        k.version = $version,
                        k.source_pages = $pages
                    WITH k
                    MATCH (p:Protocol {protocol_id: $pid})
                    MERGE (p)-[:HAS_KE]->(k)
                    """,
                    ke_id=ke.ke_id,
                    ke_type=ke.ke_type,
                    title=ke.title,
                    content=ke.content[:10_000],
                    status=ke.status,
                    version=ke.version,
                    pages=ke.source_pages,
                    pid=protocol_id,
                )
                # Create inter-KE relationships
                for rel in ke.relationships:
                    session.run(
                        """
                        MATCH (a:KnowledgeElement {ke_id: $from_id})
                        MATCH (b:KnowledgeElement {ke_id: $to_id})
                        CALL apoc.merge.relationship(
                            a, $rel_type, {}, {}, b
                        ) YIELD rel
                        RETURN rel
                        """,
                        from_id=ke.ke_id,
                        to_id=rel.target_ke_id,
                        rel_type=rel.rel_type,
                    )
        # Also persist sidecar JSON for fast retrieval
        JsonKEStore().save_knowledge_elements(protocol_id, kes)
        return len(kes)

    def get_knowledge_elements(
        self, protocol_id: str, ke_type: str | None = None
    ) -> list[KnowledgeElement]:
        with self.driver.session() as session:
            if ke_type:
                result = session.run(
                    """
                    MATCH (p:Protocol {protocol_id: $pid})-[:HAS_KE]->(k:KnowledgeElement {ke_type: $kt})
                    RETURN k
                    """,
                    pid=protocol_id,
                    kt=ke_type,
                )
            else:
                result = session.run(
                    """
                    MATCH (p:Protocol {protocol_id: $pid})-[:HAS_KE]->(k:KnowledgeElement)
                    RETURN k
                    """,
                    pid=protocol_id,
                )
            return [KnowledgeElement(**dict(r["k"])) for r in result]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_ke_store() -> KEStore:
    """Factory: returns Neo4j store if configured, else JSON fallback."""
    neo4j_uri = os.environ.get("NEO4J_URI")
    if neo4j_uri:
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "")
        try:
            return Neo4jKEStore(neo4j_uri, user, password)
        except Exception as e:
            logger.warning(
                "Neo4j connection failed (%s), falling back to JSON store", e
            )
    return JsonKEStore()
