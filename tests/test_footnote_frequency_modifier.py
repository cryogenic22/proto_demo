"""Tests for FREQUENCY_MODIFIER footnote classification."""

import pytest

from src.models.schema import FootnoteType
from src.pipeline.footnote_resolver import FootnoteResolver


class TestFrequencyModifierClassification:
    def setup_method(self):
        self.resolver = FootnoteResolver()

    def test_classify_cycles_only(self):
        """'Cycles 1-2 only' should be FREQUENCY_MODIFIER."""
        result = self.resolver._classify_footnote(
            "Day 1 and Day 8 of Cycles 1-2 only, then Day 1 only for subsequent cycles"
        )
        assert result == FootnoteType.FREQUENCY_MODIFIER

    def test_classify_every_n_cycles(self):
        """'Every 2 cycles' should be FREQUENCY_MODIFIER."""
        result = self.resolver._classify_footnote(
            "Perform CT scan every 2 cycles starting from Cycle 3"
        )
        assert result == FootnoteType.FREQUENCY_MODIFIER

    def test_classify_first_n_cycles_only(self):
        """'First 3 cycles only' should be FREQUENCY_MODIFIER."""
        result = self.resolver._classify_footnote(
            "Blood PK sampling required for first 3 cycles only"
        )
        assert result == FootnoteType.FREQUENCY_MODIFIER

    def test_classify_then_day_1_only(self):
        """'Then Day 1 only' pattern should be FREQUENCY_MODIFIER."""
        result = self.resolver._classify_footnote(
            "Day 1 and Day 15 of Cycle 1, then Day 1 only"
        )
        assert result == FootnoteType.FREQUENCY_MODIFIER

    def test_not_confused_with_conditional(self):
        """'If clinically indicated' should stay CONDITIONAL, not FREQUENCY_MODIFIER."""
        result = self.resolver._classify_footnote(
            "Perform only if clinically indicated at the discretion of the investigator"
        )
        assert result == FootnoteType.CONDITIONAL

    def test_not_confused_with_exception(self):
        """'Not required for...' should stay EXCEPTION."""
        result = self.resolver._classify_footnote(
            "Not required for patients in the placebo arm"
        )
        assert result == FootnoteType.EXCEPTION

    def test_every_other_visit(self):
        """'Every other visit' should be FREQUENCY_MODIFIER."""
        result = self.resolver._classify_footnote(
            "ECG performed at every other visit after Week 12"
        )
        assert result == FootnoteType.FREQUENCY_MODIFIER

    def test_reduced_frequency_after(self):
        """'Reduced frequency after' should be FREQUENCY_MODIFIER."""
        result = self.resolver._classify_footnote(
            "CBC performed weekly during Cycle 1, then reduced frequency after Cycle 2"
        )
        assert result == FootnoteType.FREQUENCY_MODIFIER
