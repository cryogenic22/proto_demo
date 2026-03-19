"""
Comprehensive tests for section parser and verbatim extractor.

Tests:
1. Section parsing accuracy on the Pfizer BNT162b2 protocol
2. Section lookup by number
3. Section lookup by title keyword
4. Verbatim text extraction accuracy
5. Deterministic repeatability (same input → same output)
"""

import pytest
from pathlib import Path

from src.pipeline.section_parser import SectionParser

# Use Pfizer protocol if available for integration tests
PFIZER_PDF = Path("C:/Users/kapil/Downloads/Prot_0001 1.pdf")


@pytest.mark.skipif(not PFIZER_PDF.exists(), reason="Pfizer protocol PDF not available")
class TestSectionParserOnPfizer:
    """Integration tests using the real Pfizer BNT162b2 protocol."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.parser = SectionParser()
        self.pdf_bytes = PFIZER_PDF.read_bytes()
        self.sections = self.parser.parse(self.pdf_bytes)

    def test_finds_substantial_sections(self):
        """Should find 100+ sections in a 252-page protocol."""
        assert len(self.sections) > 100

    def test_has_top_level_sections(self):
        """Should find the standard ICH protocol sections."""
        numbers = {s.number for s in self.sections}
        # Every protocol has these top-level sections
        for expected in ["1", "2", "3", "4", "5", "6"]:
            assert expected in numbers, f"Missing top-level section {expected}"

    def test_section_1_is_summary(self):
        """Section 1 should be Protocol Summary or Synopsis."""
        s1 = self.parser.find(self.sections, "1")
        assert s1 is not None
        assert any(kw in s1.title.upper() for kw in ["SUMMARY", "SYNOPSIS", "PROTOCOL"])

    def test_section_5_is_population(self):
        """Section 5 should be Study Population."""
        s5 = self.parser.find(self.sections, "5")
        assert s5 is not None
        assert "POPULATION" in s5.title.upper()

    def test_inclusion_criteria_findable(self):
        """Should find inclusion criteria by keyword."""
        results = self.parser.find_by_title(self.sections, "inclusion")
        assert len(results) >= 1
        assert any("5.1" in r.number for r in results)

    def test_exclusion_criteria_findable(self):
        """Should find exclusion criteria by keyword."""
        results = self.parser.find_by_title(self.sections, "exclusion")
        assert len(results) >= 1

    def test_schedule_of_activities_findable(self):
        """Should find Schedule of Activities sections."""
        results = self.parser.find_by_title(self.sections, "schedule of activities")
        assert len(results) >= 1

    def test_section_numbers_are_valid(self):
        """All section numbers should be properly formatted."""
        import re
        for s in self.sections:
            if s.number:
                assert re.match(r"^\d{1,2}(\.\d{1,3}){0,4}$", s.number), \
                    f"Invalid section number: {s.number}"

    def test_pages_are_valid(self):
        """All page numbers should be within document range."""
        for s in self.sections:
            assert s.page >= 0, f"Negative page for {s.number}: {s.page}"
            # 252-page doc
            assert s.page < 300, f"Page out of range for {s.number}: {s.page}"

    def test_outline_is_readable(self):
        """Outline should produce readable text."""
        outline = self.parser.to_outline(self.sections)
        assert len(outline) > 500
        assert "1 " in outline  # Section 1 present
        assert "INTRODUCTION" in outline.upper() or "SUMMARY" in outline.upper()

    def test_deterministic_repeatability(self):
        """Parsing the same PDF twice should produce identical results."""
        sections2 = self.parser.parse(self.pdf_bytes)
        assert len(self.sections) == len(sections2)
        for s1, s2 in zip(self.sections[:50], sections2[:50]):
            assert s1.number == s2.number
            assert s1.title == s2.title
            assert s1.page == s2.page

    def test_verbatim_text_extraction(self):
        """Verbatim text extraction should return non-empty content."""
        s51 = self.parser.find(self.sections, "5.1")
        if s51:
            text = self.parser.get_section_text(self.pdf_bytes, s51)
            assert len(text) > 100
            # Should contain the section header
            assert "5.1" in text or "Inclusion" in text

    def test_nested_sections(self):
        """Should find nested subsections like 4.1.1."""
        s411 = self.parser.find(self.sections, "4.1.1")
        if s411:
            assert s411.level >= 3

    def test_find_nonexistent_section(self):
        """Looking up a nonexistent section should return None."""
        result = self.parser.find(self.sections, "99.99")
        assert result is None

    def test_study_design_section(self):
        """Section 4 should be Study Design."""
        s4 = self.parser.find(self.sections, "4")
        assert s4 is not None
        assert "DESIGN" in s4.title.upper()

    def test_adverse_events_section(self):
        """Should find adverse events section by keyword."""
        results = self.parser.find_by_title(self.sections, "adverse")
        assert len(results) >= 1


class TestSectionParserUnit:
    """Unit tests that don't require external files."""

    def setup_method(self):
        self.parser = SectionParser()

    def test_empty_sections_find(self):
        result = self.parser.find([], "1")
        assert result is None

    def test_find_by_title_empty(self):
        result = self.parser.find_by_title([], "test")
        assert result == []

    def test_outline_empty(self):
        outline = self.parser.to_outline([])
        assert outline == ""
