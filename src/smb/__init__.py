"""
Structured Model Builder (SMB)
==============================

Transforms extraction output into a typed, relationship-rich knowledge graph.
Document-type agnostic — behavior driven by YAML domain schemas.

Usage::

    from src.smb import SMBEngine

    engine = SMBEngine(domain="protocol")
    result = engine.build(extraction_input)

    # Query the model
    visits = result.model.get_entities("Visit")
    schedule = result.model.get_schedule_entries()
"""

from src.smb.core.entity import Entity, ProvenanceInfo, ConfidenceLevel
from src.smb.core.relationship import Relationship
from src.smb.core.model import StructuredModel
from src.smb.core.engine import SMBEngine

__all__ = [
    "SMBEngine",
    "Entity",
    "Relationship",
    "StructuredModel",
    "ProvenanceInfo",
    "ConfidenceLevel",
]
