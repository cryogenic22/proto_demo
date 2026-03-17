"""
Temporal Extractor — parses visit column headers into structured VisitWindow objects.

Handles:
- Day N, Week N, Month N formats
- Window notation: ±N days, (-N/+M days)
- Cycle-based nomenclature: C1D1, Cycle 2 Day 15
- Screening ranges: Screening (-28 to -1 days)
- Unscheduled visits: Early Termination, ET, End of Study, Follow-up
"""

from __future__ import annotations

import re
import logging

from src.models.schema import VisitWindow, WindowUnit

logger = logging.getLogger(__name__)

# Unscheduled visit keywords
_UNSCHEDULED_KEYWORDS = {
    "early termination", "et", "end of study", "eos",
    "end of treatment", "eot", "unscheduled",
    "discontinuation", "withdrawal",
}

# Regex patterns
_DAY_RE = re.compile(r"\bday\s+(\d+)\b", re.IGNORECASE)
_WEEK_RE = re.compile(r"\bweek\s+(\d+)\b", re.IGNORECASE)
_MONTH_RE = re.compile(r"\bmonth\s+(\d+)\b", re.IGNORECASE)

# ±N window
_SYMMETRIC_WINDOW_RE = re.compile(
    r"[±\+/-]\s*(\d+)\s*(days?|weeks?|months?)", re.IGNORECASE
)

# (-N/+M days) asymmetric window
_ASYMMETRIC_WINDOW_RE = re.compile(
    r"\(-?\s*(\d+)\s*/\s*\+?\s*(\d+)\s*(days?|weeks?|months?)\)", re.IGNORECASE
)

# Screening range: (-28 to -1 days)
_SCREENING_RANGE_RE = re.compile(
    r"\(-?\s*(\d+)\s+to\s+-?\s*(\d+)\s*(days?|weeks?|months?)?\)", re.IGNORECASE
)

# Cycle-Day: C1D1, C2D15
_CYCLE_SHORT_RE = re.compile(r"\bC(\d+)\s*D(\d+)\b", re.IGNORECASE)

# Cycle N Day M
_CYCLE_LONG_RE = re.compile(
    r"\bcycle\s+(\d+)\s+day\s+(\d+)\b", re.IGNORECASE
)

# Follow-up: "Follow-up (30 days post-dose)"
_FOLLOWUP_RE = re.compile(
    r"follow[-\s]?up.*?(\d+)\s*(days?|weeks?|months?)", re.IGNORECASE
)

# Visit N
_VISIT_RE = re.compile(r"\bvisit\s+(\d+)\b", re.IGNORECASE)


def _parse_unit(text: str) -> WindowUnit:
    t = text.lower().rstrip("s")
    if t == "week":
        return WindowUnit.WEEKS
    if t == "month":
        return WindowUnit.MONTHS
    return WindowUnit.DAYS


class TemporalExtractor:
    """Parses visit column headers into structured VisitWindow objects."""

    def parse_visit(self, header: str, col_index: int) -> VisitWindow:
        """Parse a single visit header string."""
        header_stripped = header.strip()
        header_lower = header_stripped.lower()

        # Check unscheduled
        if header_lower in _UNSCHEDULED_KEYWORDS:
            return VisitWindow(
                visit_name=header_stripped,
                col_index=col_index,
                is_unscheduled=True,
            )

        # Cycle-Day short form: C1D1
        m = _CYCLE_SHORT_RE.search(header_stripped)
        if m:
            cycle = int(m.group(1))
            day = int(m.group(2))
            return VisitWindow(
                visit_name=header_stripped,
                col_index=col_index,
                target_day=day,
                cycle=cycle,
            )

        # Cycle-Day long form: Cycle 2 Day 15
        m = _CYCLE_LONG_RE.search(header_stripped)
        if m:
            cycle = int(m.group(1))
            day = int(m.group(2))
            return VisitWindow(
                visit_name=header_stripped,
                col_index=col_index,
                target_day=day,
                cycle=cycle,
            )

        # Follow-up with days
        m = _FOLLOWUP_RE.search(header_stripped)
        if m:
            val = int(m.group(1))
            unit = _parse_unit(m.group(2))
            target_day = self._to_days(val, unit)
            return VisitWindow(
                visit_name=header_stripped,
                col_index=col_index,
                target_day=target_day,
                window_unit=unit,
            )

        # Extract windows first (before day/week parsing eats the numbers)
        window_minus = 0
        window_plus = 0
        window_unit = WindowUnit.DAYS

        # Screening range
        m_screen = _SCREENING_RANGE_RE.search(header_stripped)
        if m_screen:
            window_minus = int(m_screen.group(1))
            window_plus = 0
            if m_screen.group(3):
                window_unit = _parse_unit(m_screen.group(3))

        # Asymmetric window
        m_asym = _ASYMMETRIC_WINDOW_RE.search(header_stripped)
        if m_asym:
            window_minus = int(m_asym.group(1))
            window_plus = int(m_asym.group(2))
            window_unit = _parse_unit(m_asym.group(3))

        # Symmetric window (only if no screening range or asymmetric window matched)
        m_sym = _SYMMETRIC_WINDOW_RE.search(header_stripped)
        if m_sym and not m_asym and not m_screen:
            val = int(m_sym.group(1))
            window_minus = val
            window_plus = val
            window_unit = _parse_unit(m_sym.group(2))

        # Day N
        m_day = _DAY_RE.search(header_stripped)
        if m_day:
            return VisitWindow(
                visit_name=header_stripped,
                col_index=col_index,
                target_day=int(m_day.group(1)),
                window_minus=window_minus,
                window_plus=window_plus,
                window_unit=window_unit,
            )

        # Week N
        m_week = _WEEK_RE.search(header_stripped)
        if m_week:
            weeks = int(m_week.group(1))
            return VisitWindow(
                visit_name=header_stripped,
                col_index=col_index,
                target_day=weeks * 7,
                window_minus=window_minus,
                window_plus=window_plus,
                window_unit=window_unit if window_unit != WindowUnit.DAYS else WindowUnit.DAYS,
            )

        # Month N
        m_month = _MONTH_RE.search(header_stripped)
        if m_month:
            months = int(m_month.group(1))
            return VisitWindow(
                visit_name=header_stripped,
                col_index=col_index,
                target_day=months * 30,
                window_minus=window_minus,
                window_plus=window_plus,
                window_unit=WindowUnit.MONTHS,
            )

        # Check for unscheduled keywords in longer strings
        for kw in _UNSCHEDULED_KEYWORDS:
            if kw in header_lower:
                return VisitWindow(
                    visit_name=header_stripped,
                    col_index=col_index,
                    is_unscheduled=True,
                )

        # Screening without range
        if "screening" in header_lower or "screen" in header_lower:
            return VisitWindow(
                visit_name=header_stripped,
                col_index=col_index,
                window_minus=window_minus,
                window_plus=window_plus,
                window_unit=window_unit,
            )

        # Visit N (generic)
        m_visit = _VISIT_RE.search(header_stripped)
        if m_visit:
            return VisitWindow(
                visit_name=header_stripped,
                col_index=col_index,
            )

        # Fallback — unrecognized format
        return VisitWindow(
            visit_name=header_stripped,
            col_index=col_index,
        )

    def parse_batch(self, headers: list[str]) -> list[VisitWindow]:
        """Parse a list of visit headers."""
        return [
            self.parse_visit(h, col_index=i)
            for i, h in enumerate(headers)
        ]

    @staticmethod
    def _to_days(value: int, unit: WindowUnit) -> int:
        if unit == WindowUnit.WEEKS:
            return value * 7
        if unit == WindowUnit.MONTHS:
            return value * 30
        return value
