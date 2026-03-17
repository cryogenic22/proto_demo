"""Tests for temporal extractor (visit window parsing)."""

import pytest

from src.models.schema import VisitWindow, WindowUnit
from src.pipeline.temporal_extractor import TemporalExtractor


class TestTemporalExtractor:
    def setup_method(self):
        self.extractor = TemporalExtractor()

    def test_screening_visit(self):
        result = self.extractor.parse_visit("Screening", col_index=0)
        assert result.visit_name == "Screening"
        assert result.is_unscheduled is False

    def test_day_visit(self):
        result = self.extractor.parse_visit("Day 1", col_index=1)
        assert result.target_day == 1

    def test_week_visit(self):
        result = self.extractor.parse_visit("Week 4", col_index=3)
        assert result.target_day == 28  # 4 weeks * 7

    def test_week_visit_with_window(self):
        result = self.extractor.parse_visit("Week 4 (±3 days)", col_index=3)
        assert result.target_day == 28
        assert result.window_minus == 3
        assert result.window_plus == 3
        assert result.window_unit == WindowUnit.DAYS

    def test_asymmetric_window(self):
        result = self.extractor.parse_visit("Day 15 (-2/+5 days)", col_index=4)
        assert result.target_day == 15
        assert result.window_minus == 2
        assert result.window_plus == 5

    def test_month_visit(self):
        result = self.extractor.parse_visit("Month 3", col_index=5)
        assert result.target_day == 90  # 3 * 30 approximation
        assert result.window_unit == WindowUnit.MONTHS

    def test_early_termination(self):
        result = self.extractor.parse_visit("Early Termination", col_index=10)
        assert result.is_unscheduled is True
        assert result.target_day is None

    def test_et_abbreviation(self):
        result = self.extractor.parse_visit("ET", col_index=10)
        assert result.is_unscheduled is True

    def test_end_of_study(self):
        result = self.extractor.parse_visit("End of Study", col_index=11)
        assert result.is_unscheduled is True

    def test_cycle_day_oncology(self):
        result = self.extractor.parse_visit("C1D1", col_index=1)
        assert result.cycle == 1
        assert result.target_day == 1

    def test_cycle_day_long_form(self):
        result = self.extractor.parse_visit("Cycle 2 Day 15", col_index=5)
        assert result.cycle == 2
        assert result.target_day == 15

    def test_screening_with_range(self):
        result = self.extractor.parse_visit("Screening (-28 to -1 days)", col_index=0)
        assert result.visit_name == "Screening (-28 to -1 days)"
        assert result.window_minus == 28
        assert result.window_plus == 0

    def test_follow_up_visit(self):
        result = self.extractor.parse_visit("Follow-up (30 days post-dose)", col_index=12)
        assert result.target_day == 30

    def test_parse_batch(self):
        headers = ["Screening", "Day 1", "Week 4 (±3 days)", "ET"]
        results = self.extractor.parse_batch(headers)
        assert len(results) == 4
        assert results[0].col_index == 0
        assert results[3].is_unscheduled is True

    def test_visit_number(self):
        result = self.extractor.parse_visit("Visit 1", col_index=0)
        assert result.visit_name == "Visit 1"
