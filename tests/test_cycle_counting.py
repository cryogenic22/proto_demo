"""Tests for oncology cycle counting in budget calculator."""

import pytest

from src.pipeline.budget_calculator import (
    _infer_cycle_multiplier,
    BudgetLine,
)
from src.models.schema import VisitWindow, WindowUnit


def _make_visit_windows(cycles: list[int], days_per_cycle: list[int] = None) -> list[VisitWindow]:
    """Create visit windows with cycle metadata."""
    windows = []
    if days_per_cycle is None:
        days_per_cycle = [1] * len(cycles)
    for i, (cycle, day) in enumerate(zip(cycles, days_per_cycle)):
        windows.append(VisitWindow(
            visit_name=f"C{cycle}D{day}",
            col_index=i,
            target_day=None,
            window_minus=0,
            window_plus=0,
            window_unit=WindowUnit.DAYS,
            relative_to="randomization",
            is_unscheduled=False,
            cycle=cycle,
        ))
    return windows


class TestCycleMultiplier:
    def test_detect_representative_cycles_from_visit_windows(self):
        """Should detect that SoA shows 3 cycles."""
        windows = _make_visit_windows([1, 1, 1, 2, 2, 2, 3, 3, 3])
        config = {
            "domain": {"visit_structure": "cycle_based"},
            "ta_specific": {"cycle_based": True, "default_cycles": 6},
        }
        rep, total, source = _infer_cycle_multiplier(windows, config)
        assert rep == 3  # 3 unique cycles visible
        assert total >= 6  # at least default_cycles

    def test_cycle_multiplier_oncology_default(self):
        """Should use oncology default cycles when no protocol info."""
        windows = _make_visit_windows([1, 1, 2, 2, 3, 3])
        config = {
            "domain": {"visit_structure": "cycle_based"},
            "ta_specific": {"cycle_based": True, "default_cycles": 6},
        }
        rep, total, source = _infer_cycle_multiplier(windows, config)
        assert total == 6
        assert "default" in source.lower()

    def test_cycle_multiplier_not_applied_to_vaccines(self):
        """Should return multiplier=1 for fixed-duration visit structure."""
        windows = _make_visit_windows([1, 1, 1])
        config = {
            "domain": {"visit_structure": "fixed_duration"},
        }
        rep, total, source = _infer_cycle_multiplier(windows, config)
        assert rep == total  # No multiplication

    def test_no_cycles_detected(self):
        """Should return 1,1 when no cycle metadata in visit windows."""
        windows = [
            VisitWindow(
                visit_name="Screening", col_index=0, target_day=None,
                window_minus=0, window_plus=0, window_unit=WindowUnit.DAYS,
                relative_to="", is_unscheduled=False, cycle=None,
            ),
        ]
        config = {"domain": {"visit_structure": "cycle_based"}}
        rep, total, source = _infer_cycle_multiplier(windows, config)
        assert rep == 1
        assert total == 1

    def test_cycle_source_tracking(self):
        """Should report where the cycle count came from."""
        windows = _make_visit_windows([1, 2, 3])
        config = {
            "domain": {"visit_structure": "cycle_based"},
            "ta_specific": {"cycle_based": True, "default_cycles": 9},
        }
        _, _, source = _infer_cycle_multiplier(windows, config)
        assert source  # Non-empty source string

    def test_single_cycle_not_multiplied(self):
        """If SoA only shows 1 cycle, don't multiply (could be single-cycle protocol)."""
        windows = _make_visit_windows([1, 1, 1])
        config = {
            "domain": {"visit_structure": "cycle_based"},
            "ta_specific": {"cycle_based": True, "default_cycles": 6},
        }
        rep, total, source = _infer_cycle_multiplier(windows, config)
        # With only 1 cycle shown, we can't be sure it's representative
        # Conservative: don't multiply
        assert rep == 1
