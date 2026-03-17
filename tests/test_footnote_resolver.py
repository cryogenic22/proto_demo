"""Tests for footnote resolution module."""

import pytest

from src.models.schema import (
    CellDataType,
    CellRef,
    ExtractedCell,
    FootnoteType,
    ResolvedFootnote,
)
from src.pipeline.footnote_resolver import FootnoteResolver


def _cell(row: int, col: int, value: str = "X",
          markers: list[str] | None = None) -> ExtractedCell:
    return ExtractedCell(
        row=row, col=col, raw_value=value,
        data_type=CellDataType.MARKER,
        footnote_markers=markers or [],
    )


class TestFootnoteResolver:
    def setup_method(self):
        self.resolver = FootnoteResolver()

    def test_resolve_simple_footnotes(self):
        cells = [
            _cell(0, 1, "X", markers=["a"]),
            _cell(1, 1, "X"),
            _cell(2, 1, "X", markers=["b"]),
        ]
        footnote_text = {
            "a": "Only at screening visit",
            "b": "If clinically indicated",
        }

        resolved_cells, footnotes = self.resolver.resolve(cells, footnote_text)

        # Cell with marker 'a' should have resolved text
        cell_a = [c for c in resolved_cells if c.row == 0 and c.col == 1][0]
        assert "Only at screening visit" in cell_a.resolved_footnotes

        # Footnote objects should be created
        assert len(footnotes) == 2
        fn_a = [f for f in footnotes if f.marker == "a"][0]
        assert CellRef(row=0, col=1) in fn_a.applies_to

    def test_no_footnotes(self):
        cells = [_cell(0, 0), _cell(0, 1)]
        resolved_cells, footnotes = self.resolver.resolve(cells, {})
        assert footnotes == []
        assert all(c.resolved_footnotes == [] for c in resolved_cells)

    def test_unresolvable_marker(self):
        """Marker in cell but no matching footnote text → marker left unresolved."""
        cells = [_cell(0, 0, markers=["z"])]
        footnote_text = {"a": "Some note"}

        resolved_cells, footnotes = self.resolver.resolve(cells, footnote_text)
        cell = resolved_cells[0]
        # Should still have the marker but no resolved text for 'z'
        assert cell.footnote_markers == ["z"]
        assert cell.resolved_footnotes == []

    def test_multiple_markers_on_single_cell(self):
        cells = [_cell(0, 0, markers=["a", "b"])]
        footnote_text = {
            "a": "First condition",
            "b": "Second condition",
        }

        resolved_cells, footnotes = self.resolver.resolve(cells, footnote_text)
        cell = resolved_cells[0]
        assert len(cell.resolved_footnotes) == 2
        assert "First condition" in cell.resolved_footnotes
        assert "Second condition" in cell.resolved_footnotes

    def test_footnote_type_classification_conditional(self):
        cells = [_cell(0, 0, markers=["a"])]
        footnote_text = {"a": "Only if QTc > 450ms at baseline"}

        _, footnotes = self.resolver.resolve(cells, footnote_text)
        fn = footnotes[0]
        assert fn.footnote_type == FootnoteType.CONDITIONAL

    def test_footnote_type_classification_exception(self):
        cells = [_cell(0, 0, markers=["a"])]
        footnote_text = {"a": "Except at the early termination visit"}

        _, footnotes = self.resolver.resolve(cells, footnote_text)
        fn = footnotes[0]
        assert fn.footnote_type == FootnoteType.EXCEPTION

    def test_same_marker_on_multiple_cells(self):
        cells = [
            _cell(0, 1, markers=["a"]),
            _cell(1, 1, markers=["a"]),
            _cell(2, 3, markers=["a"]),
        ]
        footnote_text = {"a": "Per investigator judgment"}

        _, footnotes = self.resolver.resolve(cells, footnote_text)
        fn_a = [f for f in footnotes if f.marker == "a"][0]
        assert len(fn_a.applies_to) == 3
