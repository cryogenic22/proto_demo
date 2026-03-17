"""Tests for the output validation gate."""

import pytest
from src.models.schema import (
    CellDataType,
    ColumnHeader,
    ExtractedCell,
    ExtractedTable,
    ExtractionMetadata,
    TableSchema,
    TableType,
)
from src.pipeline.output_validator import OutputValidator


def _cell(row: int, col: int, value: str = "X",
          dtype: CellDataType = CellDataType.MARKER) -> ExtractedCell:
    return ExtractedCell(row=row, col=col, raw_value=value, data_type=dtype)


def _table(cells: list[ExtractedCell], num_rows: int = 10,
           num_cols: int = 10) -> ExtractedTable:
    schema = TableSchema(table_id="t1", num_rows=num_rows, num_cols=num_cols)
    return ExtractedTable(
        table_id="t1", table_type=TableType.SOA,
        schema_info=schema, cells=cells,
        extraction_metadata=ExtractionMetadata(),
    )


class TestOutputValidator:
    def setup_method(self):
        self.validator = OutputValidator()

    def test_clean_table_passes(self):
        cells = [_cell(0, 0, "ECG", CellDataType.TEXT), _cell(0, 1, "X")]
        table = _table(cells)
        result = self.validator.validate_table(table)
        assert result.valid

    def test_none_values_flagged(self):
        """NONE pattern detected — high rate triggers error."""
        cells = [_cell(0, 0, "NONE"), _cell(0, 1, "X")]
        table = _table(cells)
        result = self.validator.validate_table(table)
        # 50% NONE rate → error (above 20% threshold)
        assert not result.valid
        assert any("NONE" in e for e in result.errors)

    def test_null_values_flagged(self):
        """NULL pattern detected — 100% rate triggers error."""
        cells = [_cell(0, 0, "NULL", CellDataType.TEXT)]
        table = _table(cells)
        result = self.validator.validate_table(table)
        assert not result.valid
        assert any("NONE" in e or "NULL" in e for e in result.errors)

    def test_impossible_coordinates_error(self):
        cells = [_cell(999, 999, "X")]
        table = _table(cells)
        result = self.validator.validate_table(table)
        assert not result.valid
        assert any("Impossible" in e for e in result.errors)

    def test_impossible_column_count_error(self):
        schema = TableSchema(table_id="t1", num_rows=5, num_cols=500)
        table = ExtractedTable(
            table_id="t1", table_type=TableType.SOA,
            schema_info=schema, cells=[_cell(0, 0)],
            extraction_metadata=ExtractionMetadata(),
        )
        result = self.validator.validate_table(table)
        assert not result.valid

    def test_duplicate_cells_warned(self):
        cells = [_cell(0, 0, "X"), _cell(0, 0, "Y")]
        table = _table(cells)
        result = self.validator.validate_table(table)
        assert any("duplicate" in w.lower() for w in result.warnings)

    def test_high_none_rate_is_error(self):
        """More than 20% NONE values should be an error, not just warning."""
        cells = [_cell(i, 0, "NONE") for i in range(5)]
        cells += [_cell(i, 1, "X") for i in range(5)]
        table = _table(cells, num_rows=5, num_cols=2)
        result = self.validator.validate_table(table)
        assert not result.valid

    def test_clean_removes_none(self):
        cells = [_cell(0, 0, "NONE"), _cell(0, 1, "X")]
        table = _table(cells)
        cleaned = self.validator.clean_table(table)
        none_cell = [c for c in cleaned.cells if c.row == 0 and c.col == 0][0]
        assert none_cell.raw_value == ""
        assert none_cell.data_type == CellDataType.EMPTY
        assert none_cell.confidence <= 0.3

    def test_clean_rejects_impossible_coords(self):
        cells = [_cell(999, 999, "X"), _cell(0, 0, "Y")]
        table = _table(cells)
        cleaned = self.validator.clean_table(table)
        assert len(cleaned.cells) == 1
        assert cleaned.cells[0].raw_value == "Y"

    def test_marker_with_long_text_warned(self):
        cells = [_cell(0, 0, "This is a very long string that should not be a marker type")]
        table = _table(cells)
        result = self.validator.validate_table(table)
        assert any("MARKER" in w and "misclassified" in w for w in result.warnings)

    def test_empty_table_valid(self):
        table = _table([])
        result = self.validator.validate_table(table)
        assert result.valid
