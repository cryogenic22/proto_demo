"""
Clinical Domain Library — standalone package for clinical trial domain knowledge.

This package is designed to be used independently of the extraction pipeline.
It provides:
- Procedure vocabulary with CPT/SNOMED codes and cost tiers
- Therapeutic area profiles with domain-specific rules
- Footnote classification patterns
- Visit/temporal parsing
- Clinical plausibility validation rules
- SME input mechanism for expert corrections

Usage:
    from src.domain import ProcedureVocabulary, DomainProfiles, FootnoteClassifier
"""

from src.domain.procedures import ProcedureVocabulary
from src.domain.sme_corrections import SMECorrectionManager

__all__ = ["ProcedureVocabulary", "SMECorrectionManager"]
