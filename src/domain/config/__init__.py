"""
Domain Configuration — therapeutic area-specific rules for
budget calculation, visit counting, and cost tier assignment.

Each YAML file defines rules for a specific protocol/sponsor/TA
combination. The loader finds the best matching config based on
protocol metadata.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent


def load_domain_config(
    therapeutic_area: str = "",
    sponsor: str = "",
    protocol_id: str = "",
) -> dict[str, Any]:
    """Load the best matching domain config for a protocol.

    Searches for YAML files in order of specificity:
    1. {protocol_id}.yaml (exact match)
    2. {sponsor}_{ta}.yaml (sponsor + TA)
    3. {ta}.yaml (TA only)
    4. default.yaml (fallback)

    Returns the parsed YAML as a dict, or default values if no match.
    """
    try:
        import yaml
    except ImportError:
        # PyYAML not available — return defaults
        logger.debug("PyYAML not installed, using default domain config")
        return _default_config()

    ta_key = therapeutic_area.lower().replace(" ", "_")
    sponsor_key = sponsor.lower().replace(" ", "_").replace("/", "_")

    candidates = [
        f"{protocol_id}.yaml",
        f"{sponsor_key}_{ta_key}.yaml",
        f"{ta_key}.yaml",
        "default.yaml",
    ]

    for filename in candidates:
        path = _CONFIG_DIR / filename
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                logger.info(f"Loaded domain config: {filename}")
                return config or _default_config()
            except Exception as e:
                logger.warning(f"Failed to load {filename}: {e}")

    logger.debug("No domain config found, using defaults")
    return _default_config()


def _default_config() -> dict[str, Any]:
    """Default config when no YAML is found."""
    return {
        "domain": {
            "name": "General",
            "visit_structure": "fixed_duration",
        },
        "visit_counting": {
            "marker_patterns": ["X", "x", "Y", "YES", "\u2713", "\u2714"],
            "text_indicators": [],
            "continuous_range_patterns": [],
            "periodic_procedure_keywords": [],
        },
        "cost_tiers": {
            "LOW": 75,
            "MEDIUM": 350,
            "HIGH": 1200,
            "VERY_HIGH": 3500,
        },
        "procedure_cost_overrides": {},
        "footnote_rules": {
            "conditional_handling": "include",
            "phone_call_keywords": ["call", "telephone", "phone"],
            "unscheduled_visit_rate": 0.10,
        },
        "output": {
            "show_conditional_range": False,
            "group_by": "category",
            "currency": "USD",
        },
    }


def get_cost_tiers(config: dict[str, Any]) -> dict[str, float]:
    """Extract cost tier mapping from config."""
    return config.get("cost_tiers", _default_config()["cost_tiers"])


def get_marker_patterns(config: dict[str, Any]) -> list[str]:
    """Extract visit marker patterns from config."""
    vc = config.get("visit_counting", {})
    return vc.get("marker_patterns", ["X", "x", "Y", "YES", "\u2713", "\u2714"])


def get_text_indicators(config: dict[str, Any]) -> list[str]:
    """Extract text indicators that mean 'procedure performed'."""
    vc = config.get("visit_counting", {})
    return vc.get("text_indicators", [])


def get_procedure_cost_override(
    config: dict[str, Any], procedure_name: str
) -> str | None:
    """Get a cost tier override for a specific procedure."""
    overrides = config.get("procedure_cost_overrides", {})
    return overrides.get(procedure_name)


def is_phone_call(
    config: dict[str, Any], footnote_text: str
) -> bool:
    """Check if a footnote indicates a phone-based procedure."""
    keywords = config.get("footnote_rules", {}).get("phone_call_keywords", [])
    text_lower = footnote_text.lower()
    return any(kw in text_lower for kw in keywords)
