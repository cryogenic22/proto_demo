"""Tests for superscript/subscript resolver."""

import pytest
from src.pipeline.superscript_resolver import SuperscriptResolver, parse_vlm_markers


class TestChemicalPatterns:
    def setup_method(self):
        self.resolver = SuperscriptResolver()

    def test_co2_subscript(self):
        assert self.resolver.annotate_text("CO2 levels") == "CO<sub>2</sub> levels"

    def test_h2o_subscript(self):
        assert self.resolver.annotate_text("H2O intake") == "H<sub>2</sub>O intake"

    def test_hba1c_subscript(self):
        assert self.resolver.annotate_text("HbA1c level") == "HbA<sub>1c</sub> level"

    def test_o2_subscript(self):
        assert self.resolver.annotate_text("O2 saturation") == "O<sub>2</sub> saturation"

    def test_no_false_positive_on_short_text(self):
        assert self.resolver.annotate_text("X") == "X"
        assert self.resolver.annotate_text("") == ""


class TestExponentPatterns:
    def setup_method(self):
        self.resolver = SuperscriptResolver()

    def test_cells_per_ml(self):
        result = self.resolver.annotate_text("106 cells/mL")
        assert "<sup>" in result

    def test_mg_per_m2(self):
        result = self.resolver.annotate_text("75 mg/m2")
        assert "m<sup>2</sup>" in result

    def test_mm2(self):
        result = self.resolver.annotate_text("100mm2")
        assert "mm<sup>2</sup>" in result


class TestCellValueAnnotation:
    def setup_method(self):
        self.resolver = SuperscriptResolver()

    def test_cell_marker_not_modified(self):
        """Short cell markers should NOT be annotated."""
        assert self.resolver.annotate_cell_value("X") == "X"
        assert self.resolver.annotate_cell_value("X4") == "X4"  # Too short

    def test_cell_with_chemical(self):
        result = self.resolver.annotate_cell_value("CO2 measurement performed")
        assert "CO<sub>2</sub>" in result

    def test_cell_empty(self):
        assert self.resolver.annotate_cell_value("") == ""


class TestVLMMarkerParsing:
    """Test parsing of ^{} and _{} markers from VLM output."""

    def test_superscript_footnote(self):
        assert parse_vlm_markers("X^{a}") == "X<sup>a</sup>"

    def test_subscript_chemical(self):
        assert parse_vlm_markers("CO_{2}") == "CO<sub>2</sub>"

    def test_exponent(self):
        assert parse_vlm_markers("10^{6} cells/mL") == "10<sup>6</sup> cells/mL"

    def test_subscript_hba1c(self):
        assert parse_vlm_markers("HbA_{1c}") == "HbA<sub>1c</sub>"

    def test_no_markers_unchanged(self):
        assert parse_vlm_markers("X") == "X"
        assert parse_vlm_markers("CBC") == "CBC"

    def test_mixed_super_and_sub(self):
        result = parse_vlm_markers("Fe^{2+} in H_{2}O")
        assert "<sup>2+</sup>" in result
        assert "<sub>2</sub>" in result

    def test_multiple_superscripts(self):
        assert parse_vlm_markers("X^{a,b}") == "X<sup>a,b</sup>"
