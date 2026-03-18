"""
SME Correction Manager — mechanism for domain experts to add/correct rules.

Experts provide corrections as JSON files in golden_set/sme_inputs/.
These overlay the base procedure mapping and domain rules without
modifying the base data.

Correction types:
- procedure_corrections: add/update procedures, aliases, CPT codes
- footnote_rules: add new footnote classification patterns
- validation_rules: add domain-specific plausibility rules
- mapping_overrides: force specific raw→canonical mappings
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SME_DIR = Path(__file__).parent.parent.parent / "golden_set" / "sme_inputs"


class SMECorrectionManager:
    """Manages SME corrections to domain knowledge."""

    def __init__(self, sme_dir: Path | None = None):
        self.sme_dir = sme_dir or SME_DIR
        self.sme_dir.mkdir(parents=True, exist_ok=True)

    def add_procedure(
        self,
        canonical_name: str,
        aliases: list[str],
        cpt_code: str | None = None,
        code_system: str | None = None,
        category: str = "Unknown",
        cost_tier: str = "LOW",
        expert_name: str = "unknown",
        reason: str = "",
    ) -> Path:
        """Add a new procedure to the vocabulary via SME correction."""
        correction = {
            "action": "add",
            "canonical_name": canonical_name,
            "aliases": aliases,
            "cpt_code": cpt_code,
            "code_system": code_system,
            "category": category,
            "cost_tier": cost_tier,
        }
        return self._save_correction("procedure_corrections", correction, expert_name, reason)

    def add_aliases(
        self,
        canonical_name: str,
        new_aliases: list[str],
        expert_name: str = "unknown",
        reason: str = "",
    ) -> Path:
        """Add aliases to an existing procedure."""
        correction = {
            "action": "update_aliases",
            "canonical_name": canonical_name,
            "add_aliases": new_aliases,
        }
        return self._save_correction("procedure_corrections", correction, expert_name, reason)

    def update_cpt_code(
        self,
        canonical_name: str,
        cpt_code: str,
        code_system: str = "CPT",
        expert_name: str = "unknown",
        reason: str = "",
    ) -> Path:
        """Update/correct the CPT code for a procedure."""
        correction = {
            "action": "update_code",
            "canonical_name": canonical_name,
            "cpt_code": cpt_code,
            "code_system": code_system,
        }
        return self._save_correction("procedure_corrections", correction, expert_name, reason)

    def add_mapping_override(
        self,
        raw_name: str,
        correct_canonical: str,
        expert_name: str = "unknown",
        reason: str = "",
    ) -> Path:
        """Force a specific raw name to map to a specific canonical procedure."""
        correction = {
            "action": "override",
            "raw_name": raw_name,
            "correct_canonical": correct_canonical,
        }
        return self._save_correction("mapping_overrides", correction, expert_name, reason)

    def add_validation_rule(
        self,
        rule: str,
        domain: str = "GENERAL",
        expert_name: str = "unknown",
        reason: str = "",
    ) -> Path:
        """Add a clinical validation rule."""
        correction = {
            "rule": rule,
            "domain": domain,
        }
        return self._save_correction("validation_rules", correction, expert_name, reason)

    def list_corrections(self) -> list[dict]:
        """List all SME corrections."""
        corrections = []
        for path in sorted(self.sme_dir.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                corrections.append({
                    "file": path.name,
                    "expert": data.get("expert_name", "unknown"),
                    "date": data.get("date", "unknown"),
                    "reason": data.get("reason", ""),
                    "correction_count": sum(len(v) for v in data.values() if isinstance(v, list)),
                })
            except Exception:
                pass
        return corrections

    def _save_correction(
        self,
        correction_type: str,
        correction: dict,
        expert_name: str,
        reason: str,
    ) -> Path:
        """Save a correction to a JSON file."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"sme_{correction_type}_{timestamp}.json"
        path = self.sme_dir / filename

        # Check if we can append to an existing recent file from the same expert
        existing = self._find_recent_file(correction_type, expert_name)
        if existing:
            with open(existing, encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault(correction_type, []).append(correction)
            with open(existing, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Appended correction to {existing.name}")
            return existing

        data = {
            "expert_name": expert_name,
            "date": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            correction_type: [correction],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved SME correction to {path.name}")
        return path

    def _find_recent_file(self, correction_type: str, expert_name: str) -> Path | None:
        """Find a recent correction file from the same expert to append to."""
        for path in sorted(self.sme_dir.glob(f"sme_{correction_type}_*.json"), reverse=True):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("expert_name") == expert_name:
                    return path
            except Exception:
                pass
        return None
