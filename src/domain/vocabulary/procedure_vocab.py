"""
Procedure Vocabulary — canonical clinical procedure library.

Manages the mapping between raw procedure names (as extracted from
protocols) and canonical names with CPT codes, categories, and costs.

Current storage: CSV file (data/procedure_mapping.csv)
Future: Postgres table with full CRUD + audit trail

Usage:
    from src.domain.vocabulary import get_procedure_vocab

    vocab = get_procedure_vocab()
    entry = vocab.lookup("CBC")
    # ProcedureEntry(canonical="Complete Blood Count", cpt="85025", ...)

    all_procs = vocab.list_all()
    vocab.add_alias("CBC", "FBC")
    vocab.update_cpt("Complete Blood Count", "85025")
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_CSV = Path(__file__).parent.parent.parent.parent / "data" / "procedure_mapping.csv"


@dataclass
class ProcedureEntry:
    """A single procedure in the canonical library."""
    canonical_name: str
    cpt_code: str = ""
    code_system: str = "CPT"
    category: str = ""
    cost_tier: str = "LOW"  # LOW, MEDIUM, HIGH, VERY_HIGH
    aliases: list[str] = field(default_factory=list)
    used_in_protocols: int = 0
    notes: str = ""

    def matches(self, query: str) -> bool:
        """Check if this procedure matches a search query."""
        q = query.lower().strip()
        if q in self.canonical_name.lower():
            return True
        if self.cpt_code and q == self.cpt_code:
            return True
        return any(q in alias.lower() for alias in self.aliases)

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_name": self.canonical_name,
            "cpt_code": self.cpt_code,
            "code_system": self.code_system,
            "category": self.category,
            "cost_tier": self.cost_tier,
            "aliases": self.aliases,
            "used_in_protocols": self.used_in_protocols,
            "notes": self.notes,
        }


class ProcedureVocab:
    """Manages the procedure vocabulary with CRUD operations.

    Currently backed by a CSV file. Designed to migrate to Postgres
    by implementing a ProcedureStore interface.
    """

    def __init__(self, csv_path: Path | str | None = None):
        self._path = Path(csv_path) if csv_path else _DEFAULT_CSV
        self._entries: dict[str, ProcedureEntry] = {}
        self._alias_index: dict[str, str] = {}  # alias → canonical
        self._load()

    def _load(self) -> None:
        """Load procedures from CSV."""
        if not self._path.exists():
            logger.warning(f"Procedure CSV not found: {self._path}")
            return

        with open(self._path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("canonical_name", "").strip()
                if not name:
                    continue
                aliases_str = row.get("aliases", "")
                aliases = [
                    a.strip() for a in aliases_str.split(",")
                    if a.strip()
                ] if aliases_str else []

                entry = ProcedureEntry(
                    canonical_name=name,
                    cpt_code=(row.get("cpt_code") or "").strip(),
                    code_system=(row.get("code_system") or "CPT").strip(),
                    category=(row.get("category") or "").strip(),
                    cost_tier=(row.get("cost_tier") or "LOW").strip(),
                    aliases=aliases,
                )
                self._entries[name.lower()] = entry
                for alias in aliases:
                    self._alias_index[alias.lower()] = name.lower()

        logger.info(
            f"Loaded {len(self._entries)} procedures, "
            f"{len(self._alias_index)} aliases"
        )

    def lookup(self, name: str) -> ProcedureEntry | None:
        """Look up a procedure by name or alias."""
        key = name.lower().strip()
        if key in self._entries:
            return self._entries[key]
        canonical_key = self._alias_index.get(key)
        if canonical_key:
            return self._entries.get(canonical_key)
        return None

    def search(self, query: str) -> list[ProcedureEntry]:
        """Search procedures by name, alias, CPT code, or category."""
        q = query.lower().strip()
        return [
            e for e in self._entries.values()
            if e.matches(q)
        ]

    def list_all(self) -> list[ProcedureEntry]:
        """Return all procedures sorted by category then name."""
        return sorted(
            self._entries.values(),
            key=lambda e: (e.category, e.canonical_name),
        )

    def list_by_category(self, category: str) -> list[ProcedureEntry]:
        """Return procedures in a specific category."""
        return [
            e for e in self._entries.values()
            if e.category.lower() == category.lower()
        ]

    def get_categories(self) -> list[str]:
        """Return all unique categories."""
        return sorted(set(e.category for e in self._entries.values() if e.category))

    def add_alias(self, canonical_name: str, alias: str) -> bool:
        """Add an alias for an existing procedure."""
        key = canonical_name.lower()
        entry = self._entries.get(key)
        if not entry:
            return False
        if alias not in entry.aliases:
            entry.aliases.append(alias)
            self._alias_index[alias.lower()] = key
            self._save()
        return True

    def update_cpt(self, canonical_name: str, cpt_code: str) -> bool:
        """Update the CPT code for a procedure."""
        key = canonical_name.lower()
        entry = self._entries.get(key)
        if not entry:
            return False
        entry.cpt_code = cpt_code
        self._save()
        return True

    def update_category(self, canonical_name: str, category: str) -> bool:
        """Update the category for a procedure."""
        key = canonical_name.lower()
        entry = self._entries.get(key)
        if not entry:
            return False
        entry.category = category
        self._save()
        return True

    def update_cost_tier(self, canonical_name: str, cost_tier: str) -> bool:
        """Update the cost tier for a procedure."""
        key = canonical_name.lower()
        entry = self._entries.get(key)
        if not entry:
            return False
        entry.cost_tier = cost_tier
        self._save()
        return True

    def add_procedure(self, entry: ProcedureEntry) -> bool:
        """Add a new procedure to the vocabulary."""
        key = entry.canonical_name.lower()
        if key in self._entries:
            return False
        self._entries[key] = entry
        for alias in entry.aliases:
            self._alias_index[alias.lower()] = key
        self._save()
        return True

    def get_stats(self) -> dict[str, Any]:
        """Return vocabulary statistics."""
        entries = list(self._entries.values())
        return {
            "total_procedures": len(entries),
            "with_cpt_code": sum(1 for e in entries if e.cpt_code),
            "total_aliases": sum(len(e.aliases) for e in entries),
            "categories": len(self.get_categories()),
            "by_category": {
                cat: len(self.list_by_category(cat))
                for cat in self.get_categories()
            },
            "by_cost_tier": {
                tier: sum(1 for e in entries if e.cost_tier == tier)
                for tier in ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
            },
        }

    def _save(self) -> None:
        """Persist changes back to CSV."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        entries = sorted(
            self._entries.values(),
            key=lambda e: (e.category, e.canonical_name),
        )
        with open(self._path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "canonical_name", "cpt_code", "code_system",
                "category", "cost_tier", "aliases",
            ])
            for e in entries:
                writer.writerow([
                    e.canonical_name,
                    e.cpt_code,
                    e.code_system,
                    e.category,
                    e.cost_tier,
                    ", ".join(e.aliases),
                ])


# ─── Singleton accessor ──────────────────────────────────────────────────

_instance: ProcedureVocab | None = None


def get_procedure_vocab() -> ProcedureVocab:
    """Return the singleton ProcedureVocab instance."""
    global _instance
    if _instance is None:
        _instance = ProcedureVocab()
    return _instance


def reset_procedure_vocab() -> None:
    """Clear the singleton (for tests)."""
    global _instance
    _instance = None
