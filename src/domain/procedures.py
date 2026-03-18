"""
Procedure Vocabulary — standalone clinical procedure database.

Loads from CSV, supports SME corrections overlay, provides
lookup by alias, category filtering, and export capabilities.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CSV = Path(__file__).parent.parent.parent / "data" / "procedure_mapping.csv"
SME_CORRECTIONS_DIR = Path(__file__).parent.parent.parent / "golden_set" / "sme_inputs"


@dataclass
class Procedure:
    canonical_name: str
    cpt_code: str | None
    code_system: str | None
    category: str
    cost_tier: str  # LOW, MEDIUM, HIGH, VERY_HIGH
    aliases: list[str]
    source: str = "base"  # "base" or "sme_correction"


class ProcedureVocabulary:
    """Clinical procedure vocabulary with alias lookup and SME corrections."""

    def __init__(self, csv_path: Path | None = None):
        self._procedures: list[Procedure] = []
        self._alias_index: dict[str, Procedure] = {}
        self._load_base(csv_path or DEFAULT_CSV)
        self._load_sme_corrections()
        self._rebuild_index()

    def _load_base(self, path: Path):
        if not path.exists():
            logger.warning(f"Procedure CSV not found: {path}")
            return
        with open(path, newline="", encoding="utf-8") as f:
            lines = [line for line in f if not line.strip().startswith("#")]
        reader = csv.DictReader(io.StringIO("".join(lines)))
        for row in reader:
            name = (row.get("canonical_name") or "").strip()
            if not name:
                continue
            self._procedures.append(Procedure(
                canonical_name=name,
                cpt_code=(row.get("cpt_code") or "").strip() or None,
                code_system=(row.get("code_system") or "").strip() or None,
                category=(row.get("category") or "").strip(),
                cost_tier=(row.get("cost_tier") or "LOW").strip(),
                aliases=[a.strip().lower() for a in (row.get("aliases") or "").split(",") if a.strip()],
                source="base",
            ))

    def _load_sme_corrections(self):
        """Load SME corrections from JSON files in sme_inputs directory."""
        if not SME_CORRECTIONS_DIR.exists():
            return
        for path in sorted(SME_CORRECTIONS_DIR.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                corrections = data.get("procedure_corrections", [])
                for c in corrections:
                    action = c.get("action", "add")
                    if action == "add":
                        self._procedures.append(Procedure(
                            canonical_name=c["canonical_name"],
                            cpt_code=c.get("cpt_code"),
                            code_system=c.get("code_system"),
                            category=c.get("category", "Unknown"),
                            cost_tier=c.get("cost_tier", "LOW"),
                            aliases=[a.lower() for a in c.get("aliases", [])],
                            source=f"sme:{path.stem}",
                        ))
                    elif action == "update_aliases":
                        target = c["canonical_name"]
                        for proc in self._procedures:
                            if proc.canonical_name == target:
                                new_aliases = [a.lower() for a in c.get("add_aliases", [])]
                                proc.aliases.extend(new_aliases)
                                proc.source = f"sme:{path.stem}"
                                break
                    elif action == "update_code":
                        target = c["canonical_name"]
                        for proc in self._procedures:
                            if proc.canonical_name == target:
                                if c.get("cpt_code"):
                                    proc.cpt_code = c["cpt_code"]
                                if c.get("code_system"):
                                    proc.code_system = c["code_system"]
                                if c.get("cost_tier"):
                                    proc.cost_tier = c["cost_tier"]
                                proc.source = f"sme:{path.stem}"
                                break

                logger.info(f"Loaded {len(corrections)} SME corrections from {path.name}")
            except Exception as e:
                logger.warning(f"Failed to load SME corrections from {path}: {e}")

    def _rebuild_index(self):
        self._alias_index.clear()
        for proc in self._procedures:
            for alias in proc.aliases:
                key = alias.lower()
                if key not in self._alias_index:
                    self._alias_index[key] = proc

    def lookup(self, raw_name: str) -> Procedure | None:
        """Look up a procedure by raw name. Returns None if not found."""
        key = raw_name.strip().lower()
        if key in self._alias_index:
            return self._alias_index[key]
        # Word-boundary match
        for alias, proc in self._alias_index.items():
            if re.search(r"\b" + re.escape(alias) + r"\b", key):
                return proc
        return None

    def all_procedures(self) -> list[Procedure]:
        return list(self._procedures)

    def by_category(self, category: str) -> list[Procedure]:
        return [p for p in self._procedures if p.category.lower() == category.lower()]

    def by_cost_tier(self, tier: str) -> list[Procedure]:
        return [p for p in self._procedures if p.cost_tier == tier]

    def export_json(self) -> list[dict]:
        return [
            {
                "canonical_name": p.canonical_name,
                "cpt_code": p.cpt_code,
                "code_system": p.code_system,
                "category": p.category,
                "cost_tier": p.cost_tier,
                "aliases": p.aliases,
                "source": p.source,
            }
            for p in self._procedures
        ]
