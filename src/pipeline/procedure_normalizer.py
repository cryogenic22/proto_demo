"""
Procedure Normalizer — maps free-text procedure names to canonical codes.

Loads the procedure vocabulary from data/procedure_mapping.csv so it can
be reviewed, corrected, and extended by clinical teams without code changes.

Produces a deterministic mapping: same input always yields same output.
Every mapping decision is logged for audit.
"""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from src.models.schema import CostTier, NormalizedProcedure

logger = logging.getLogger(__name__)

MAPPING_CSV = Path(__file__).parent.parent.parent / "data" / "procedure_mapping.csv"


@dataclass
class ProcedureEntry:
    canonical_name: str
    code: str | None
    code_system: str | None
    category: str
    cost_tier: CostTier
    aliases: list[str]


def _load_vocabulary(csv_path: Path | None = None) -> list[ProcedureEntry]:
    """Load procedure vocabulary from CSV file."""
    path = csv_path or MAPPING_CSV
    entries: list[ProcedureEntry] = []

    if not path.exists():
        logger.warning(f"Procedure mapping CSV not found: {path}")
        return entries

    import io
    with open(path, newline="", encoding="utf-8") as f:
        # Filter out comment lines before passing to DictReader
        lines = [line for line in f if not line.strip().startswith("#")]

    reader = csv.DictReader(io.StringIO("".join(lines)))
    for row in reader:
        canonical = (row.get("canonical_name") or "").strip()
        if not canonical:
            continue

        try:
            cost = CostTier((row.get("cost_tier") or "LOW").strip())
        except ValueError:
            cost = CostTier.LOW

        aliases_raw = row.get("aliases") or ""
        aliases = [a.strip().lower() for a in aliases_raw.split(",") if a.strip()]

        code = (row.get("cpt_code") or "").strip() or None
        code_system = (row.get("code_system") or "").strip() or None

        entries.append(ProcedureEntry(
            canonical_name=canonical,
            code=code,
            code_system=code_system,
            category=(row.get("category") or "").strip(),
            cost_tier=cost,
            aliases=aliases,
        ))

    logger.info(f"Loaded {len(entries)} procedures from {path}")
    return entries


class ProcedureNormalizer:
    """Maps free-text procedure names to canonical entries.

    Deterministic: same input always produces the same output.
    Auditable: every mapping decision is logged.
    """

    def __init__(self, csv_path: Path | None = None):
        vocabulary = _load_vocabulary(csv_path)

        # Build lookup: lowercase alias → ProcedureEntry
        # Deterministic ordering: first match wins
        self._alias_map: dict[str, ProcedureEntry] = {}
        for entry in vocabulary:
            for alias in entry.aliases:
                key = alias.lower()
                if key not in self._alias_map:
                    self._alias_map[key] = entry

        self._vocabulary = vocabulary
        logger.info(f"Procedure normalizer initialized: {len(self._alias_map)} aliases → {len(vocabulary)} canonical procedures")

    def normalize(self, raw_name: str) -> NormalizedProcedure:
        """Normalize a single procedure name. Deterministic."""
        cleaned = raw_name.strip()
        lookup_key = cleaned.lower()

        # 1. Exact match
        if lookup_key in self._alias_map:
            entry = self._alias_map[lookup_key]
            logger.debug(f"Procedure '{cleaned}' → '{entry.canonical_name}' (exact match)")
            return self._to_model(cleaned, entry, "exact")

        # 2. Whole-word alias match in input text
        for alias, entry in self._alias_map.items():
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, lookup_key):
                logger.debug(f"Procedure '{cleaned}' → '{entry.canonical_name}' (word match: '{alias}')")
                return self._to_model(cleaned, entry, f"word_match:{alias}")

        # 3. Fuzzy match using key clinical terms
        match = self._fuzzy_match(lookup_key)
        if match:
            logger.debug(f"Procedure '{cleaned}' → '{match.canonical_name}' (fuzzy)")
            return self._to_model(cleaned, match, "fuzzy")

        # 4. Unknown — preserve raw name
        logger.info(f"Procedure '{cleaned}' → UNMAPPED (no match found)")
        return NormalizedProcedure(
            raw_name=cleaned,
            canonical_name=cleaned,
            code=None,
            code_system=None,
            category="Unknown",
            estimated_cost_tier=CostTier.LOW,
        )

    def normalize_batch(self, names: list[str]) -> list[NormalizedProcedure]:
        """Normalize a list of procedure names. Deterministic ordering."""
        # Sort input for deterministic output order
        return [self.normalize(name) for name in sorted(set(names))]

    def get_mapping_table(self) -> list[dict]:
        """Export the full mapping table for review.

        Returns a list of dicts suitable for CSV/JSON export.
        """
        rows = []
        for entry in self._vocabulary:
            rows.append({
                "canonical_name": entry.canonical_name,
                "cpt_code": entry.code or "",
                "code_system": entry.code_system or "",
                "category": entry.category,
                "cost_tier": entry.cost_tier.value,
                "alias_count": len(entry.aliases),
                "aliases": ", ".join(entry.aliases),
            })
        return rows

    def get_unmapped_report(self, raw_names: list[str]) -> list[dict]:
        """Report which procedure names could NOT be mapped.

        Returns a list of unmapped names for clinical review.
        """
        unmapped = []
        for name in sorted(set(raw_names)):
            result = self.normalize(name)
            if result.canonical_name == name.strip() and result.code is None:
                unmapped.append({
                    "raw_name": name,
                    "suggested_category": "Unknown",
                    "action_needed": "Map to canonical procedure or confirm as custom",
                })
        return unmapped

    def _fuzzy_match(self, text: str) -> ProcedureEntry | None:
        """Attempt fuzzy matching using key clinical terms."""
        key_terms = {
            "ecg": "ecg",
            "electrocardiogram": "ecg",
            "mri": "mri",
            "ct": "ct scan",
            "pet": "pet/ct",
            "biopsy": "tumor biopsy",
            "x-ray": "x-ray",
            "xray": "x-ray",
            "spirometry": "spirometry",
            "echo": "echocardiogram",
        }
        for term, alias in key_terms.items():
            if term in text:
                if alias in self._alias_map:
                    return self._alias_map[alias]
        return None

    @staticmethod
    def _to_model(raw_name: str, entry: ProcedureEntry, match_type: str) -> NormalizedProcedure:
        return NormalizedProcedure(
            raw_name=raw_name,
            canonical_name=entry.canonical_name,
            code=entry.code,
            code_system=entry.code_system,
            category=entry.category,
            estimated_cost_tier=entry.cost_tier,
        )
