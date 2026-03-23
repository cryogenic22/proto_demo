"""
Procedure Hierarchy — parent-child relationships for procedure families.

Many clinical procedures exist at multiple specificity levels:
  Generic: "Tumor Biopsy" (no CPT — varies by site)
  Site-specific: "Liver Biopsy" (CPT 47000), "Breast Biopsy" (CPT 19081)

This module manages these hierarchies so the pipeline can:
1. Fuzzy-match generic terms during extraction
2. Flag for site-specific resolution during budget calculation
3. Provide the right CPT code once the site is determined

Architecture:
  - Each hierarchy has a generic PARENT (catch-all for fuzzy matching)
  - Parents have CHILDREN with specific CPT codes
  - Parents carry resolution_required=True to flag for user review
  - The budget wizard shows children as options when a parent is used

Storage: data/procedure_hierarchies.json (editable config)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_HIERARCHIES_FILE = Path(__file__).parent.parent.parent.parent / "data" / "procedure_hierarchies.json"


@dataclass
class ProcedureChild:
    """A site/technique-specific variant of a generic procedure."""
    canonical_name: str
    cpt_code: str
    site_or_technique: str  # e.g., "Breast", "Liver", "CT-guided"
    cost_tier: str = "MEDIUM"
    typical_cost_low: int = 0
    typical_cost_high: int = 0


@dataclass
class ProcedureFamily:
    """A hierarchy of related procedures with a generic parent."""
    parent_name: str  # Generic name for fuzzy matching
    category: str
    description: str
    resolution_required: bool = True  # Flag for budget wizard
    default_cost_tier: str = "HIGH"  # Conservative estimate when site unknown
    children: list[ProcedureChild] = field(default_factory=list)
    generic_aliases: list[str] = field(default_factory=list)

    def get_child(self, site: str) -> ProcedureChild | None:
        """Find a child by site/technique name."""
        for child in self.children:
            if child.site_or_technique.lower() == site.lower():
                return child
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_name": self.parent_name,
            "category": self.category,
            "description": self.description,
            "resolution_required": self.resolution_required,
            "default_cost_tier": self.default_cost_tier,
            "children": [
                {
                    "canonical_name": c.canonical_name,
                    "cpt_code": c.cpt_code,
                    "site_or_technique": c.site_or_technique,
                    "cost_tier": c.cost_tier,
                }
                for c in self.children
            ],
            "generic_aliases": self.generic_aliases,
        }


class ProcedureHierarchyManager:
    """Manages procedure family hierarchies."""

    def __init__(self):
        self._families: dict[str, ProcedureFamily] = {}
        self._load()

    def _load(self) -> None:
        """Load hierarchies from JSON config."""
        if not _HIERARCHIES_FILE.exists():
            self._create_default()
            return

        try:
            with open(_HIERARCHIES_FILE, encoding="utf-8") as f:
                data = json.load(f)
            for fam in data.get("families", []):
                family = ProcedureFamily(
                    parent_name=fam["parent_name"],
                    category=fam.get("category", ""),
                    description=fam.get("description", ""),
                    resolution_required=fam.get("resolution_required", True),
                    default_cost_tier=fam.get("default_cost_tier", "HIGH"),
                    children=[
                        ProcedureChild(**c) for c in fam.get("children", [])
                    ],
                    generic_aliases=fam.get("generic_aliases", []),
                )
                self._families[family.parent_name.lower()] = family
            logger.info(f"Loaded {len(self._families)} procedure hierarchies")
        except Exception as e:
            logger.warning(f"Failed to load hierarchies: {e}")
            self._create_default()

    def _create_default(self) -> None:
        """Create default hierarchy definitions."""
        defaults = [
            ProcedureFamily(
                parent_name="Tumor Biopsy (Core Needle)",
                category="Biopsy",
                description="Core needle biopsy — CPT varies by anatomical site",
                default_cost_tier="HIGH",
                generic_aliases=[
                    "core needle biopsy", "tumor biopsy", "tissue biopsy",
                    "biopsy at progression", "mandatory tumor biopsy",
                    "optional tumor biopsy", "FFPE tumor sample",
                    "newly acquired tumor biopsy",
                ],
                children=[
                    ProcedureChild("Core Needle Biopsy Breast", "19081", "Breast", "MEDIUM"),
                    ProcedureChild("Core Needle Biopsy Liver", "47000", "Liver", "MEDIUM"),
                    ProcedureChild("Lung Biopsy (Percutaneous)", "32408", "Lung", "HIGH"),
                    ProcedureChild("Kidney Biopsy (Percutaneous)", "50200", "Kidney", "HIGH"),
                    ProcedureChild("Lymph Node Biopsy (Needle)", "38505", "Lymph Node", "MEDIUM"),
                    ProcedureChild("Bone Marrow Biopsy", "38221", "Bone Marrow", "HIGH"),
                    ProcedureChild("Soft Tissue Biopsy (Needle)", "20206", "Soft Tissue", "LOW"),
                    ProcedureChild("Thyroid Biopsy (FNA)", "60100", "Thyroid", "MEDIUM"),
                    ProcedureChild("Prostate Biopsy (Needle)", "55700", "Prostate", "MEDIUM"),
                ],
            ),
            ProcedureFamily(
                parent_name="CT Scan (Generic)",
                category="Imaging",
                description="Computed tomography — CPT varies by body region",
                default_cost_tier="HIGH",
                generic_aliases=[
                    "CT scan", "CT", "computed tomography", "CAT scan",
                ],
                children=[
                    ProcedureChild("CT Scan Chest", "71260", "Chest", "HIGH"),
                    ProcedureChild("CT Scan Abdomen/Pelvis", "74178", "Abdomen/Pelvis", "HIGH"),
                    ProcedureChild("CT Scan Brain/Head", "70553", "Brain/Head", "HIGH"),
                    ProcedureChild("CT Scan Neck", "70491", "Neck", "HIGH"),
                ],
            ),
            ProcedureFamily(
                parent_name="Endoscopy (Generic)",
                category="Procedure",
                description="Endoscopic examination — CPT varies by type",
                default_cost_tier="HIGH",
                generic_aliases=[
                    "endoscopy", "endoscopic examination",
                ],
                children=[
                    ProcedureChild("Esophagogastroduodenoscopy (EGD)", "43239", "Upper GI", "HIGH"),
                    ProcedureChild("Colonoscopy", "45378", "Colon", "HIGH"),
                    ProcedureChild("Flexible Sigmoidoscopy", "45330", "Sigmoid", "MEDIUM"),
                    ProcedureChild("ERCP", "43260", "Biliary/Pancreatic", "VERY_HIGH"),
                    ProcedureChild("Bronchoscopy", "31622", "Airway", "HIGH"),
                ],
            ),
            ProcedureFamily(
                parent_name="Study Drug Administration (Generic)",
                category="Drug Administration",
                description="Drug administration — CPT varies by route",
                default_cost_tier="MEDIUM",
                generic_aliases=[
                    "study drug administration", "drug administration",
                    "IP administration", "dosing",
                ],
                children=[
                    ProcedureChild("IV Infusion (Initial Hour)", "96365", "IV Infusion", "MEDIUM"),
                    ProcedureChild("SC Injection", "96372", "Subcutaneous", "LOW"),
                    ProcedureChild("IM Injection", "96372", "Intramuscular", "LOW"),
                    ProcedureChild("Oral Administration", "99211", "Oral", "LOW"),
                    ProcedureChild("Intrathecal Administration", "62322", "Intrathecal", "VERY_HIGH"),
                ],
            ),
            ProcedureFamily(
                parent_name="Ultrasound (Generic)",
                category="Imaging",
                description="Ultrasound examination — CPT varies by body region",
                default_cost_tier="MEDIUM",
                generic_aliases=[
                    "ultrasound", "US", "sonography",
                ],
                children=[
                    ProcedureChild("Ultrasound Abdomen", "76700", "Abdomen", "MEDIUM"),
                    ProcedureChild("Ultrasound Pelvis", "76856", "Pelvis", "MEDIUM"),
                    ProcedureChild("Vascular Duplex Ultrasound", "93880", "Vascular", "MEDIUM"),
                    ProcedureChild("Thyroid Ultrasound", "76536", "Thyroid", "MEDIUM"),
                    ProcedureChild("Echocardiogram (TTE)", "93306", "Cardiac", "HIGH"),
                ],
            ),
        ]

        self._families = {f.parent_name.lower(): f for f in defaults}
        self._save()

    def _save(self) -> None:
        """Persist hierarchies to JSON."""
        _HIERARCHIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {"families": [f.to_dict() for f in self._families.values()]}
        with open(_HIERARCHIES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_family(self, name: str) -> ProcedureFamily | None:
        """Look up a family by parent name or generic alias."""
        key = name.lower()
        if key in self._families:
            return self._families[key]
        # Check aliases
        for family in self._families.values():
            if any(a.lower() == key for a in family.generic_aliases):
                return family
        return None

    def is_generic(self, procedure_name: str) -> bool:
        """Check if a procedure name matches a generic parent."""
        return self.get_family(procedure_name) is not None

    def get_children(self, parent_name: str) -> list[ProcedureChild]:
        """Get site-specific children for a generic procedure."""
        family = self.get_family(parent_name)
        return family.children if family else []

    def list_families(self) -> list[ProcedureFamily]:
        """Return all procedure families."""
        return list(self._families.values())


# Singleton
_instance: ProcedureHierarchyManager | None = None


def get_procedure_hierarchy() -> ProcedureHierarchyManager:
    """Return the singleton hierarchy manager."""
    global _instance
    if _instance is None:
        _instance = ProcedureHierarchyManager()
    return _instance
