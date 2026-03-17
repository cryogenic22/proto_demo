"""Tests for multi-page table stitcher."""

import pytest

from src.models.schema import BoundingBox, TableRegion, TableType
from src.pipeline.table_stitcher import TableStitcher


def _region(table_id: str, pages: list[int], title: str = "",
            markers: list[str] | None = None) -> TableRegion:
    return TableRegion(
        table_id=table_id,
        pages=pages,
        bounding_boxes=[
            BoundingBox(page=p, x0=50, y0=100, x1=2500, y1=3000)
            for p in pages
        ],
        table_type=TableType.SOA,
        title=title,
        continuation_markers=markers or [],
    )


class TestTableStitcher:
    def setup_method(self):
        self.stitcher = TableStitcher()

    def test_no_stitching_needed(self):
        """Distinct tables on different pages stay separate."""
        regions = [
            _region("t1", [0], title="Table 1"),
            _region("t2", [2], title="Table 2"),
        ]
        result = self.stitcher.stitch(regions)
        assert len(result) == 2

    def test_stitch_by_continuation_marker(self):
        """Tables with 'continued' markers on consecutive pages get merged."""
        regions = [
            _region("t1", [3], title="Schedule of Activities"),
            _region("t2", [4], title="Schedule of Activities (continued)",
                    markers=["continued"]),
        ]
        result = self.stitcher.stitch(regions)
        assert len(result) == 1
        assert set(result[0].pages) == {3, 4}
        assert len(result[0].bounding_boxes) == 2

    def test_stitch_three_pages(self):
        """Three consecutive continuation pages merge into one."""
        regions = [
            _region("t1", [5], title="Schedule of Assessments"),
            _region("t2", [6], title="Schedule of Assessments (cont'd)",
                    markers=["cont'd"]),
            _region("t3", [7], title="Schedule of Assessments (continued)",
                    markers=["continued"]),
        ]
        result = self.stitcher.stitch(regions)
        assert len(result) == 1
        assert result[0].pages == [5, 6, 7]

    def test_stitch_by_matching_title(self):
        """Tables with identical titles on consecutive pages get merged."""
        regions = [
            _region("t1", [10], title="Table 14.1"),
            _region("t2", [11], title="Table 14.1"),
        ]
        result = self.stitcher.stitch(regions)
        assert len(result) == 1

    def test_no_stitch_non_consecutive(self):
        """Same title on non-consecutive pages does NOT merge."""
        regions = [
            _region("t1", [2], title="Table 14.1"),
            _region("t2", [8], title="Table 14.1"),
        ]
        result = self.stitcher.stitch(regions)
        assert len(result) == 2

    def test_mixed_stitching(self):
        """Mix of continuations and standalone tables."""
        regions = [
            _region("t1", [0], title="Demographics"),
            _region("t2", [2], title="Schedule of Activities"),
            _region("t3", [3], title="Schedule of Activities (continued)",
                    markers=["continued"]),
            _region("t4", [5], title="Lab Parameters"),
        ]
        result = self.stitcher.stitch(regions)
        assert len(result) == 3
        # The SoA should be stitched
        soa = [r for r in result if "Schedule" in (r.title or "")]
        assert len(soa) == 1
        assert soa[0].pages == [2, 3]

    def test_empty_input(self):
        result = self.stitcher.stitch([])
        assert result == []

    def test_single_table(self):
        regions = [_region("t1", [0], title="Table 1")]
        result = self.stitcher.stitch(regions)
        assert len(result) == 1
