"""
Inference engine — rule-based reasoning over the StructuredModel.

Each InferenceRule inspects entities/relationships and modifies properties
(occurrence counts, probabilities, cost tiers). Rules fire sequentially
by priority (lowest number first). Every modification is tracked via
inference_trail on the affected entity.

Zero ProtoExtract imports — domain_config is a plain dict.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from src.smb.core.model import StructuredModel

logger = logging.getLogger(__name__)


# ── Base class ──────────────────────────────────────────────────────────


class InferenceRule(ABC):
    """Base class for all inference rules."""

    def __init__(self, name: str, priority: int):
        self.name = name
        self.priority = priority

    @abstractmethod
    def apply(
        self, model: StructuredModel, config: dict[str, Any]
    ) -> list[str]:
        """Apply the rule to the model.

        Args:
            model: The structured model to modify in-place.
            config: Domain config dict (from ExtractionInput.domain_config).

        Returns:
            List of human-readable descriptions of what was modified.
        """
        ...

    def _tag(self, entity: Any) -> None:
        """Append this rule's name to the entity's inference_trail."""
        trail = entity.properties.get("inference_trail")
        if isinstance(trail, list):
            trail.append(self.name)
        else:
            entity.properties["inference_trail"] = [self.name]


# ── Inference Engine ────────────────────────────────────────────────────


class InferenceEngine:
    """Loads rules, sorts by priority, fires sequentially."""

    def __init__(self, rules: list[InferenceRule] | None = None):
        if rules is None:
            rules = self._default_rules()
        self.rules = sorted(rules, key=lambda r: r.priority)

    def run(
        self, model: StructuredModel, config: dict[str, Any]
    ) -> list[str]:
        """Fire all rules in priority order.

        Returns list of rule names that actually modified the model.
        """
        fired: list[str] = []
        for rule in self.rules:
            try:
                modifications = rule.apply(model, config)
                if modifications:
                    fired.append(rule.name)
                    model.inference_log.append(
                        {
                            "rule": rule.name,
                            "priority": rule.priority,
                            "modifications": modifications,
                        }
                    )
                    logger.debug(
                        f"Rule {rule.name} fired: {len(modifications)} modifications"
                    )
            except Exception:
                logger.exception(f"Rule {rule.name} failed")
        return fired

    @staticmethod
    def _default_rules() -> list[InferenceRule]:
        return [
            CycleInference(),
            SpanInference(),
            FrequencyModifierInference(),
            ConditionalInference(),
            SubsetInference(),
            CostOverrideInference(),
            PhoneCallInference(),
        ]


# ── Rule 1: CycleInference (priority 10) ───────────────────────────────


class CycleInference(InferenceRule):
    """Detect representative cycles from Visit.cycle and multiply
    ScheduleEntry.total_occurrences to reflect expected total cycles.

    Uses domain_config ta_specific.treat_to_progression when enabled.
    """

    def __init__(self) -> None:
        super().__init__("CycleInference", priority=10)

    def apply(
        self, model: StructuredModel, config: dict[str, Any]
    ) -> list[str]:
        visit_structure = (
            config.get("domain", {}).get("visit_structure", "fixed_duration")
        )
        if visit_structure != "cycle_based":
            return []

        # Count unique cycles from Visit entities
        visits = model.get_entities("Visit")
        cycles_seen: set[int] = set()
        for v in visits:
            cycle = v.get_property("cycle")
            if cycle is not None:
                cycles_seen.add(cycle)

        if len(cycles_seen) <= 1:
            return []

        # Compute expected total cycles
        ta = config.get("ta_specific", {})
        ttp = ta.get("treat_to_progression", {})
        if ttp.get("enabled"):
            median_months = ttp.get("default_median_months", 9)
            cycle_days = ta.get("cycle_length_days", 21)
            total_cycles = int(median_months * 30 / max(cycle_days, 1))
        else:
            total_cycles = config.get("visit_counting", {}).get(
                "default_cycles", 6
            )

        represented = len(cycles_seen)
        if represented >= total_cycles:
            return []

        multiplier = total_cycles / represented
        modifications: list[str] = []

        for entry in model.get_schedule_entries():
            if entry.get_property("mark_type") == "excluded":
                continue
            base = entry.get_property("occurrence_count", 1)
            entry.properties["applied_cycle_count"] = total_cycles
            entry.properties["cycle_multiplier"] = round(multiplier, 2)
            entry.properties["total_occurrences"] = int(base * multiplier)
            self._tag(entry)
            modifications.append(
                f"{entry.name}: {base} x {multiplier:.1f} = "
                f"{entry.properties['total_occurrences']}"
            )

        return modifications


# ── Rule 2: SpanInference (priority 20) ─────────────────────────────────

# Day range regex — matches "Day 1 through Day 28", etc.
_DAY_RANGE_RE = re.compile(
    r"Day\s+(\d+)\s+(?:through|to|thru|[-\u2013\u2014])\s+Day\s+(\d+)",
    re.IGNORECASE,
)

# Frequency word regex
_FREQ_RE = re.compile(
    r"\b(daily|weekly|monthly|continuous)\b", re.IGNORECASE
)


class SpanInference(InferenceRule):
    """Parse span cells (is_span=True) to compute occurrences from
    frequency + day range.
    """

    def __init__(self) -> None:
        super().__init__("SpanInference", priority=20)

    def apply(
        self, model: StructuredModel, config: dict[str, Any]
    ) -> list[str]:
        modifications: list[str] = []
        for entry in model.get_schedule_entries():
            if not entry.get_property("is_span"):
                continue
            # Already computed by builder — but if raw_mark has day range, recompute
            raw = entry.get_property("raw_mark", "")
            freq_str = entry.get_property("span_frequency") or ""
            start = entry.get_property("span_start_day")
            end = entry.get_property("span_end_day")

            # Try to extract from raw_mark if not already set
            if start is None or end is None:
                day_match = _DAY_RANGE_RE.search(raw)
                if day_match:
                    start = int(day_match.group(1))
                    end = int(day_match.group(2))
                    entry.properties["span_start_day"] = start
                    entry.properties["span_end_day"] = end

            if not freq_str:
                freq_match = _FREQ_RE.search(raw)
                if freq_match:
                    freq_str = freq_match.group(1).lower()
                    entry.properties["span_frequency"] = freq_str

            # Compute occurrences from frequency + range
            if start is not None and end is not None:
                total_days = end - start + 1
                freq_lower = (freq_str or "daily").lower()
                if freq_lower == "weekly":
                    occ = max(1, total_days // 7)
                elif freq_lower == "monthly":
                    occ = max(1, total_days // 30)
                else:
                    occ = total_days

                entry.properties["occurrence_count"] = occ
                entry.properties["total_occurrences"] = occ
                self._tag(entry)
                modifications.append(
                    f"{entry.name}: span {freq_lower} Day {start}-{end} = {occ}"
                )

        return modifications


# ── Rule 3: FrequencyModifierInference (priority 30) ────────────────────


class FrequencyModifierInference(InferenceRule):
    """Footnotes with classification=FREQUENCY_MODIFIER adjust
    occurrence_count on the affected ScheduleEntries.
    """

    # e.g., "every 2 weeks", "3 times per cycle", "twice weekly"
    _FREQ_PATTERN = re.compile(
        r"(?:every\s+(\d+)\s+(week|day|month)s?)|"
        r"(?:(\d+)\s+times?\s+(?:per|each|every)\s+\w+)|"
        r"(?:(twice|three\s+times?)\s+(?:weekly|daily|per\s+\w+))",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        super().__init__("FrequencyModifierInference", priority=30)

    def apply(
        self, model: StructuredModel, config: dict[str, Any]
    ) -> list[str]:
        # Build footnote marker → entity lookup
        fn_entities = {
            e.get_property("footnote_marker"): e
            for e in model.get_entities("Footnote")
            if e.has_property("footnote_marker")
        }

        # Find frequency-modifier footnotes
        freq_footnotes: dict[str, float] = {}
        for marker, fn_entity in fn_entities.items():
            classification = fn_entity.get_property("classification", "")
            if classification != "FREQUENCY_MODIFIER":
                continue
            text = fn_entity.get_property("footnote_text", "")
            multiplier = self._parse_frequency_multiplier(text)
            if multiplier is not None:
                freq_footnotes[marker] = multiplier

        if not freq_footnotes:
            return []

        modifications: list[str] = []
        for entry in model.get_schedule_entries():
            markers = entry.get_property("footnote_markers", [])
            for marker in markers:
                if marker in freq_footnotes:
                    mult = freq_footnotes[marker]
                    base = entry.get_property("occurrence_count", 1)
                    new_count = max(1, int(base * mult))
                    entry.properties["occurrence_count"] = new_count
                    entry.properties["total_occurrences"] = new_count
                    entry.properties["frequency_modifier"] = mult
                    self._tag(entry)
                    modifications.append(
                        f"{entry.name}: freq modifier {mult}x -> {new_count}"
                    )
        return modifications

    def _parse_frequency_multiplier(self, text: str) -> float | None:
        """Extract a numeric multiplier from footnote text."""
        m = self._FREQ_PATTERN.search(text)
        if not m:
            return None
        if m.group(1):
            # "every N weeks/days" — convert to multiplier relative to base
            interval = int(m.group(1))
            unit = m.group(2).lower()
            if unit.startswith("week"):
                return 1.0 / interval  # every 2 weeks → 0.5x per week
            elif unit.startswith("month"):
                return 1.0 / interval
            return 1.0 / max(interval, 1)
        if m.group(3):
            # "N times per cycle"
            return float(m.group(3))
        if m.group(4):
            word = m.group(4).lower()
            if "twice" in word:
                return 2.0
            if "three" in word:
                return 3.0
        return None


# ── Rule 4: ConditionalInference (priority 40) ──────────────────────────


class ConditionalInference(InferenceRule):
    """mark_type=conditional -> probability=0.6 (default)."""

    DEFAULT_PROBABILITY = 0.6

    def __init__(self) -> None:
        super().__init__("ConditionalInference", priority=40)

    def apply(
        self, model: StructuredModel, config: dict[str, Any]
    ) -> list[str]:
        conditional_entries = model.get_conditional_entries()
        if not conditional_entries:
            return []

        # Allow domain config to override the default probability
        probability = config.get("footnote_rules", {}).get(
            "conditional_probability", self.DEFAULT_PROBABILITY
        )

        modifications: list[str] = []
        for entry in conditional_entries:
            entry.properties["probability"] = probability
            self._tag(entry)
            modifications.append(
                f"{entry.name}: conditional p={probability}"
            )

        return modifications


# ── Rule 5: SubsetInference (priority 50) ───────────────────────────────

_PERCENT_RE = re.compile(r"(\d+)\s*%\s*(?:of\s+)?(?:patients|subjects|participants)?", re.IGNORECASE)
_FRACTION_WORDS = {
    "half": 0.5,
    "one-third": 0.33,
    "one third": 0.33,
    "two-thirds": 0.67,
    "two thirds": 0.67,
    "one-quarter": 0.25,
    "one quarter": 0.25,
    "three-quarters": 0.75,
    "three quarters": 0.75,
}


class SubsetInference(InferenceRule):
    """Footnotes with classification=SUBSET -> subset_fraction on
    affected ScheduleEntries (e.g., 0.3 for "30% of patients").
    """

    def __init__(self) -> None:
        super().__init__("SubsetInference", priority=50)

    def apply(
        self, model: StructuredModel, config: dict[str, Any]
    ) -> list[str]:
        fn_entities = {
            e.get_property("footnote_marker"): e
            for e in model.get_entities("Footnote")
            if e.has_property("footnote_marker")
        }

        subset_footnotes: dict[str, float] = {}
        for marker, fn_entity in fn_entities.items():
            classification = fn_entity.get_property("classification", "")
            if classification != "SUBSET":
                continue
            text = fn_entity.get_property("footnote_text", "")
            fraction = self._parse_fraction(text)
            if fraction is not None:
                subset_footnotes[marker] = fraction

        if not subset_footnotes:
            return []

        modifications: list[str] = []
        for entry in model.get_schedule_entries():
            markers = entry.get_property("footnote_markers", [])
            for marker in markers:
                if marker in subset_footnotes:
                    frac = subset_footnotes[marker]
                    entry.properties["subset_fraction"] = frac
                    self._tag(entry)
                    modifications.append(
                        f"{entry.name}: subset {frac:.0%}"
                    )
        return modifications

    @staticmethod
    def _parse_fraction(text: str) -> float | None:
        """Extract a fraction from text like '30% of patients'."""
        m = _PERCENT_RE.search(text)
        if m:
            pct = int(m.group(1))
            if 1 <= pct <= 100:
                return pct / 100.0
        text_lower = text.lower()
        for word, val in _FRACTION_WORDS.items():
            if word in text_lower:
                return val
        return None


# ── Rule 6: CostOverrideInference (priority 60) ─────────────────────────


class CostOverrideInference(InferenceRule):
    """Apply domain YAML procedure_cost_overrides to ScheduleEntry
    cost_multiplier based on the linked Procedure's canonical_name.
    """

    def __init__(self) -> None:
        super().__init__("CostOverrideInference", priority=60)

    def apply(
        self, model: StructuredModel, config: dict[str, Any]
    ) -> list[str]:
        overrides = config.get("procedure_cost_overrides", {})
        cost_tiers = config.get("cost_tiers", {})
        if not overrides or not cost_tiers:
            return []

        # Build procedure_id → canonical_name map
        proc_map: dict[str, str] = {}
        proc_tier_map: dict[str, str] = {}
        for proc in model.get_entities("Procedure"):
            proc_map[proc.id] = proc.get_property("canonical_name", proc.name)
            proc_tier_map[proc.id] = proc.get_property("cost_tier", "LOW")

        modifications: list[str] = []
        for entry in model.get_schedule_entries():
            proc_id = entry.get_property("procedure_entity_id")
            if not proc_id or proc_id not in proc_map:
                continue

            canonical = proc_map[proc_id]
            override_tier = overrides.get(canonical)
            if not override_tier:
                continue

            current_tier = proc_tier_map.get(proc_id, "LOW")
            override_cost = cost_tiers.get(override_tier, 0)
            current_cost = cost_tiers.get(current_tier, 0)

            if override_cost and current_cost and override_cost != current_cost:
                multiplier = override_cost / max(current_cost, 1)
                entry.properties["cost_multiplier"] = round(multiplier, 2)
                entry.properties["override_cost_tier"] = override_tier
                self._tag(entry)
                modifications.append(
                    f"{entry.name}: cost {current_tier}->{override_tier} "
                    f"({multiplier:.2f}x)"
                )
            elif override_cost and not current_cost:
                entry.properties["override_cost_tier"] = override_tier
                self._tag(entry)
                modifications.append(
                    f"{entry.name}: cost tier set to {override_tier}"
                )

        return modifications


# ── Rule 7: PhoneCallInference (priority 70) ────────────────────────────

_PHONE_KEYWORDS = {"phone", "call", "telephone"}


class PhoneCallInference(InferenceRule):
    """Footnote text containing 'phone'/'call'/'telephone' -> override
    cost_tier to PHONE_CALL on affected ScheduleEntries.
    """

    def __init__(self) -> None:
        super().__init__("PhoneCallInference", priority=70)

    def apply(
        self, model: StructuredModel, config: dict[str, Any]
    ) -> list[str]:
        # Get phone-call keywords from config, with fallback
        keywords = set(
            config.get("footnote_rules", {}).get(
                "phone_call_keywords", list(_PHONE_KEYWORDS)
            )
        )

        fn_entities = {
            e.get_property("footnote_marker"): e
            for e in model.get_entities("Footnote")
            if e.has_property("footnote_marker")
        }

        # Find footnotes that indicate phone calls
        phone_markers: set[str] = set()
        for marker, fn_entity in fn_entities.items():
            text = fn_entity.get_property("footnote_text", "").lower()
            # Must be a meaningful phone-call reference, not incidental mention
            if any(kw in text for kw in keywords):
                # Heuristic: only treat as phone if the footnote is primarily
                # about phone/call visits, not just mentioning it in passing
                if self._is_phone_call_footnote(text, keywords):
                    phone_markers.add(marker)

        if not phone_markers:
            return []

        modifications: list[str] = []
        for entry in model.get_schedule_entries():
            markers = entry.get_property("footnote_markers", [])
            if any(m in phone_markers for m in markers):
                entry.properties["override_cost_tier"] = "PHONE_CALL"
                entry.properties["is_phone_call"] = True
                self._tag(entry)
                modifications.append(
                    f"{entry.name}: phone call override"
                )

        return modifications

    @staticmethod
    def _is_phone_call_footnote(text: str, keywords: set[str]) -> bool:
        """Check whether a footnote is specifically about phone/call visits.

        We look for patterns like "will call", "phone visit", "telephone
        contact" rather than incidental mentions like "call the site".
        """
        phone_patterns = [
            r"\bcall\s+(?:all\s+)?(?:participants?|patients?|subjects?)\b",
            r"\bphone\s+(?:visit|contact|call|interview)\b",
            r"\btelephone\s+(?:visit|contact|call|interview)\b",
            r"\bvia\s+(?:phone|telephone)\b",
            r"\btelemedicine\s+visit",
            r"\bremote\s+(?:visit|contact|assessment)\b",
            r"\bwill\s+call\b",
            r"\bby\s+(?:phone|telephone)\b",
        ]
        for pat in phone_patterns:
            if re.search(pat, text, re.IGNORECASE):
                return True
        return False
