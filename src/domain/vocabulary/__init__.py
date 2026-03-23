"""
Clinical Vocabulary Module — manages procedures, CPT codes, MedDRA terms,
and other domain reference data.

This module provides a unified interface for:
- Procedure library (canonical names, CPT codes, aliases, cost tiers)
- Future: MedDRA coding (adverse events, medical history)
- Future: SNOMED CT terms
- Future: Drug/compound dictionary

Storage is abstracted — currently file-based (CSV/JSON), designed to
migrate to Postgres when needed without changing the API layer.
"""

from src.domain.vocabulary.procedure_vocab import (
    ProcedureVocab,
    ProcedureEntry,
    get_procedure_vocab,
)
from src.domain.vocabulary.procedure_hierarchy import (
    ProcedureHierarchyManager,
    ProcedureFamily,
    ProcedureChild,
    get_procedure_hierarchy,
)

__all__ = [
    "ProcedureVocab", "ProcedureEntry", "get_procedure_vocab",
    "ProcedureHierarchyManager", "ProcedureFamily", "ProcedureChild",
    "get_procedure_hierarchy",
]
