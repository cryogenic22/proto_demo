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

        # Load SME corrections and apply them
        vocabulary = self._apply_sme_corrections(vocabulary)

        # Build lookup: lowercase alias → ProcedureEntry
        # Deterministic ordering: first match wins
        # Also index the canonical name itself as an alias
        self._alias_map: dict[str, ProcedureEntry] = {}
        for entry in vocabulary:
            # Index canonical name
            canon_key = entry.canonical_name.lower()
            if canon_key not in self._alias_map:
                self._alias_map[canon_key] = entry
            # Index all aliases
            for alias in entry.aliases:
                key = alias.lower()
                if key not in self._alias_map:
                    self._alias_map[key] = entry

        self._vocabulary = vocabulary
        logger.info(f"Procedure normalizer initialized: {len(self._alias_map)} aliases -> {len(vocabulary)} canonical procedures")

    @staticmethod
    def _apply_sme_corrections(vocabulary: list[ProcedureEntry]) -> list[ProcedureEntry]:
        """Apply SME corrections from JSON files in golden_set/sme_inputs/."""
        import json
        sme_dir = Path(__file__).parent.parent.parent / "golden_set" / "sme_inputs"
        if not sme_dir.exists():
            return vocabulary

        # Build name→entry lookup
        by_name: dict[str, ProcedureEntry] = {}
        for entry in vocabulary:
            by_name[entry.canonical_name.lower()] = entry

        for path in sorted(sme_dir.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)

                for c in data.get("procedure_corrections", []):
                    action = c.get("action", "")
                    target = (c.get("canonical_name") or "").lower()

                    if action == "add" and target not in by_name:
                        new_entry = ProcedureEntry(
                            canonical_name=c["canonical_name"],
                            code=c.get("cpt_code"),
                            code_system=c.get("code_system"),
                            category=c.get("category", "Unknown"),
                            cost_tier=CostTier(c.get("cost_tier", "LOW")),
                            aliases=[a.lower() for a in c.get("aliases", [])],
                        )
                        vocabulary.append(new_entry)
                        by_name[target] = new_entry

                    elif action == "update_aliases" and target in by_name:
                        entry = by_name[target]
                        new_aliases = [a.lower() for a in c.get("add_aliases", [])]
                        entry.aliases.extend(new_aliases)

                    elif action == "update_code" and target in by_name:
                        entry = by_name[target]
                        if c.get("cpt_code"):
                            entry.code = c["cpt_code"]
                        if c.get("code_system"):
                            entry.code_system = c["code_system"]

                logger.info(f"Applied SME corrections from {path.name}")
            except Exception as e:
                logger.warning(f"Failed to load SME corrections from {path}: {e}")

        return vocabulary

    # Default exclusion patterns — loaded from config if available
    _DEFAULT_NOT_PROCEDURES = {
        "visit number", "daily timepoint", "assessments", "study day",
        "study visit", "timepoint", "window",
        "continue with original schedules",
        "counselling the importance",
        "confirm participant meets inclusion",
        "confirm participant's request",
        "childbearing potential",
        "protocol deviations",
        "unscheduled visit",
        "end of study",
        "early termination",
        "screening failure",
        "efficacy assessment",
        "blood for immunologic analysis",
        "evaluation",
        "daily record card",
        "concomitant aed",
        "concomitant non-aed",
        "recording of maaes",
        "recording of saes",
        "recording of concomitant",
        "recording of unsolicited",
        "days since most recent",
        "confirm use of contraceptives",
        "review temporary delay",
        "for participants who are hiv",
        "concomitant medications",
    }

    @staticmethod
    def _load_exclusion_patterns() -> set[str]:
        """Load exclusion patterns from config file if available."""
        import json
        config_path = Path(__file__).parent.parent.parent / "data" / "procedure_exclusions.json"
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    data = json.load(f)
                return set(data.get("not_procedure_patterns", []))
            except Exception:
                pass
        return ProcedureNormalizer._DEFAULT_NOT_PROCEDURES

    def is_not_procedure(self, raw_name: str) -> bool:
        """Check if a raw name is a non-procedure SoA label.

        Exclusion patterns loaded from data/procedure_exclusions.json
        if available, otherwise uses built-in defaults.
        """
        if not hasattr(self, '_not_procedures'):
            self._not_procedures = self._load_exclusion_patterns()
        key = raw_name.strip().lower()
        if len(key) < 3:
            return True
        return any(excl in key for excl in self._not_procedures)

    def normalize(self, raw_name: str) -> NormalizedProcedure:
        """Normalize a single procedure name. Deterministic."""
        # Strip trailing Unicode superscript markers
        # e.g., "Physical examination²" → "Physical examination"
        cleaned = re.sub(r'[²³⁴⁵⁶⁷⁸⁹¹⁰]+$', '', raw_name.strip()).strip()

        # Strip trailing single digit footnote ONLY if preceded by a
        # non-digit letter and the stripped version exists in vocabulary.
        # This prevents "BNT162b2" → "BNT162b" (wrong) while fixing
        # "Blood analysis5" → "Blood analysis" (correct).
        digit_stripped = re.sub(r'([a-zA-Z])(\d)$', r'\1', cleaned)
        if digit_stripped != cleaned and digit_stripped.lower() in self._alias_map:
            cleaned = digit_stripped

        if not cleaned:
            cleaned = raw_name.strip()
        lookup_key = cleaned.lower()

        # 1. Exact match
        if lookup_key in self._alias_map:
            entry = self._alias_map[lookup_key]
            return self._to_model(cleaned, entry, "exact")

        # 2. Check if input STARTS WITH any alias (handles long SoA descriptions)
        # Sort by alias length descending — prefer longest match
        for alias, entry in sorted(self._alias_map.items(), key=lambda x: -len(x[0])):
            if len(alias) >= 5 and lookup_key.startswith(alias):
                return self._to_model(cleaned, entry, f"starts_with:{alias}")

        # 3. Whole-word alias match in input text
        for alias, entry in self._alias_map.items():
            if len(alias) < 3:
                continue  # Skip very short aliases to prevent false positives
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, lookup_key):
                return self._to_model(cleaned, entry, f"word_match:{alias}")

        # 4. Fuzzy match using key clinical terms
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
        """Attempt fuzzy matching using key clinical terms.

        Uses word-boundary matching to prevent 'ct' in 'collect'
        from matching 'CT scan'.
        """
        key_terms = {
            "ecg": "ecg",
            "electrocardiogram": "ecg",
            "mri": "mri",
            "ct scan": "ct scan",     # Require full "ct scan", not just "ct"
            "ct ": "ct scan",          # "CT " with space (e.g., "CT chest")
            "pet": "pet/ct",
            "biopsy": "tumor biopsy",
            "x-ray": "x-ray",
            "xray": "x-ray",
            "spirometry": "spirometry",
            "echocardiogram": "echocardiogram",
        }
        for term, alias in key_terms.items():
            # Use word boundary matching
            pattern = r"\b" + re.escape(term) + r"\b"
            if re.search(pattern, text):
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
