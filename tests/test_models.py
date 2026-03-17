"""Tests for data models — validates all Pydantic schemas and their constraints."""

import pytest
from pydantic import ValidationError

from src.models.schema import (
    BoundingBox,
    CellDataType,
    CellRef,
    ChallengeIssue,
    ChallengeType,
    ColumnHeader,
    CostTier,
    ExtractedCell,
    ExtractedTable,
    ExtractionMetadata,
    FootnoteType,
    MergedRegion,
    NormalizedProcedure,
    PageImage,
    PipelineConfig,
    PipelineOutput,
    ResolvedFootnote,
    ReviewItem,
    ReviewType,
    RowGroup,
    TableRegion,
    TableSchema,
    TableType,
    VisitWindow,
    WindowUnit,
)


# ---------------------------------------------------------------------------
# BoundingBox
# ---------------------------------------------------------------------------

class TestBoundingBox:
    def test_valid_bbox(self):
        bb = BoundingBox(page=0, x0=10, y0=20, x1=100, y1=200)
        assert bb.width == 90
        assert bb.height == 180
        assert bb.area == 90 * 180

    def test_x1_must_exceed_x0(self):
        with pytest.raises(ValidationError):
            BoundingBox(page=0, x0=100, y0=20, x1=50, y1=200)

    def test_y1_must_exceed_y0(self):
        with pytest.raises(ValidationError):
            BoundingBox(page=0, x0=10, y0=200, x1=100, y1=100)

    def test_negative_coords_rejected(self):
        with pytest.raises(ValidationError):
            BoundingBox(page=0, x0=-1, y0=20, x1=100, y1=200)

    def test_negative_page_rejected(self):
        with pytest.raises(ValidationError):
            BoundingBox(page=-1, x0=10, y0=20, x1=100, y1=200)


# ---------------------------------------------------------------------------
# PageImage
# ---------------------------------------------------------------------------

class TestPageImage:
    def test_valid_page_image(self):
        pi = PageImage(page_number=0, image_bytes=b"\x89PNG", width=2550, height=3300, dpi=300)
        assert pi.dpi == 300

    def test_zero_width_rejected(self):
        with pytest.raises(ValidationError):
            PageImage(page_number=0, image_bytes=b"x", width=0, height=100, dpi=300)


# ---------------------------------------------------------------------------
# TableRegion
# ---------------------------------------------------------------------------

class TestTableRegion:
    def test_valid_table_region(self):
        bb = BoundingBox(page=0, x0=10, y0=10, x1=500, y1=700)
        tr = TableRegion(table_id="t1", pages=[0], bounding_boxes=[bb], table_type=TableType.SOA)
        assert tr.table_type == TableType.SOA
        assert tr.title is None

    def test_empty_pages_rejected(self):
        bb = BoundingBox(page=0, x0=10, y0=10, x1=500, y1=700)
        with pytest.raises(ValidationError):
            TableRegion(table_id="t1", pages=[], bounding_boxes=[bb])


# ---------------------------------------------------------------------------
# TableSchema
# ---------------------------------------------------------------------------

class TestTableSchema:
    def test_valid_schema(self):
        ts = TableSchema(
            table_id="t1",
            column_headers=[
                ColumnHeader(col_index=0, text="Procedure"),
                ColumnHeader(col_index=1, text="Screening"),
                ColumnHeader(col_index=2, text="Day 1"),
            ],
            row_groups=[RowGroup(name="Safety", start_row=0, end_row=5, category="Safety")],
            footnote_markers=["a", "b"],
            num_rows=6,
            num_cols=3,
        )
        assert len(ts.column_headers) == 3
        assert ts.footnote_markers == ["a", "b"]

    def test_spanning_header(self):
        h = ColumnHeader(col_index=1, text="Treatment Period", span=4, level=0)
        assert h.span == 4


# ---------------------------------------------------------------------------
# ExtractedCell
# ---------------------------------------------------------------------------

class TestExtractedCell:
    def test_marker_cell(self):
        cell = ExtractedCell(
            row=0, col=1, raw_value="X",
            data_type=CellDataType.MARKER,
            confidence=0.98,
            row_header="ECG", col_header="Screening",
        )
        assert cell.data_type == CellDataType.MARKER
        assert cell.confidence == 0.98

    def test_conditional_cell_with_footnote(self):
        cell = ExtractedCell(
            row=2, col=3, raw_value="X",
            data_type=CellDataType.CONDITIONAL,
            footnote_markers=["a"],
            resolved_footnotes=["Only if QTc > 450ms"],
            confidence=0.72,
        )
        assert cell.footnote_markers == ["a"]
        assert len(cell.resolved_footnotes) == 1

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            ExtractedCell(row=0, col=0, confidence=1.5)

    def test_empty_cell(self):
        cell = ExtractedCell(row=0, col=0, raw_value="", data_type=CellDataType.EMPTY)
        assert cell.raw_value == ""


# ---------------------------------------------------------------------------
# ResolvedFootnote
# ---------------------------------------------------------------------------

class TestResolvedFootnote:
    def test_conditional_footnote(self):
        fn = ResolvedFootnote(
            marker="a",
            text="Only if QTc > 450ms at baseline",
            applies_to=[CellRef(row=2, col=3), CellRef(row=2, col=5)],
            footnote_type=FootnoteType.CONDITIONAL,
        )
        assert len(fn.applies_to) == 2
        assert fn.footnote_type == FootnoteType.CONDITIONAL


# ---------------------------------------------------------------------------
# NormalizedProcedure
# ---------------------------------------------------------------------------

class TestNormalizedProcedure:
    def test_procedure_with_code(self):
        proc = NormalizedProcedure(
            raw_name="12-lead ECG",
            canonical_name="Electrocardiogram, 12-lead",
            code="93000",
            code_system="CPT",
            category="Cardiac",
            estimated_cost_tier=CostTier.MEDIUM,
        )
        assert proc.code == "93000"
        assert proc.estimated_cost_tier == CostTier.MEDIUM

    def test_procedure_without_code(self):
        proc = NormalizedProcedure(
            raw_name="Vital Signs",
            canonical_name="Vital Signs",
            category="General",
        )
        assert proc.code is None
        assert proc.estimated_cost_tier == CostTier.LOW


# ---------------------------------------------------------------------------
# VisitWindow
# ---------------------------------------------------------------------------

class TestVisitWindow:
    def test_standard_visit(self):
        vw = VisitWindow(
            visit_name="Week 4",
            col_index=3,
            target_day=28,
            window_minus=3,
            window_plus=3,
            window_unit=WindowUnit.DAYS,
        )
        assert vw.target_day == 28
        assert vw.is_unscheduled is False

    def test_unscheduled_visit(self):
        vw = VisitWindow(
            visit_name="Early Termination",
            col_index=10,
            is_unscheduled=True,
        )
        assert vw.target_day is None
        assert vw.is_unscheduled is True

    def test_cycle_based_visit(self):
        vw = VisitWindow(
            visit_name="C2D1",
            col_index=5,
            target_day=28,
            cycle=2,
        )
        assert vw.cycle == 2


# ---------------------------------------------------------------------------
# ChallengeIssue
# ---------------------------------------------------------------------------

class TestChallengeIssue:
    def test_hallucination_challenge(self):
        ci = ChallengeIssue(
            cell_ref=CellRef(row=3, col=5),
            challenge_type=ChallengeType.HALLUCINATED_VALUE,
            description="Cell shows 'X' but source image shows empty cell",
            extracted_value="X",
            suggested_value="",
            severity=0.9,
        )
        assert ci.severity == 0.9


# ---------------------------------------------------------------------------
# ExtractedTable / PipelineOutput composite
# ---------------------------------------------------------------------------

class TestExtractedTable:
    def test_full_table(self):
        schema = TableSchema(table_id="t1", num_rows=3, num_cols=3)
        table = ExtractedTable(
            table_id="t1",
            table_type=TableType.SOA,
            title="Schedule of Activities",
            source_pages=[4, 5],
            schema_info=schema,
            cells=[
                ExtractedCell(row=0, col=0, raw_value="ECG", data_type=CellDataType.TEXT),
                ExtractedCell(row=0, col=1, raw_value="X", data_type=CellDataType.MARKER),
            ],
            overall_confidence=0.91,
        )
        assert len(table.cells) == 2
        assert table.overall_confidence == 0.91


class TestPipelineOutput:
    def test_document_hash(self):
        h = PipelineOutput.compute_hash(b"fake pdf content")
        assert len(h) == 64  # SHA-256 hex digest

    def test_empty_output(self):
        out = PipelineOutput(
            document_name="test.pdf",
            total_pages=10,
            tables=[],
            warnings=["No tables detected"],
        )
        assert len(out.tables) == 0
        assert len(out.warnings) == 1


# ---------------------------------------------------------------------------
# PipelineConfig
# ---------------------------------------------------------------------------

class TestPipelineConfig:
    def test_defaults(self):
        cfg = PipelineConfig()
        assert cfg.render_dpi == 300
        assert cfg.confidence_threshold == 0.85
        assert cfg.max_extraction_passes == 2

    def test_dpi_out_of_range(self):
        with pytest.raises(ValidationError):
            PipelineConfig(render_dpi=50)

    def test_custom_config(self):
        cfg = PipelineConfig(
            render_dpi=450,
            confidence_threshold=0.90,
            enable_challenger=False,
        )
        assert cfg.render_dpi == 450
        assert cfg.enable_challenger is False
