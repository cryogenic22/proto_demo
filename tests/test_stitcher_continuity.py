"""TDD tests for content-continuity table stitcher."""

import pytest
from src.models.schema import TableRegion, TableType, BoundingBox
from src.pipeline.table_stitcher import TableStitcher, MERGE_THRESHOLD


def _region(pages, title="", table_type=TableType.SOA, continuation=None):
    return TableRegion(
        table_id=f"t{pages[0]}",
        pages=pages,
        bounding_boxes=[BoundingBox(x0=0, y0=0, x1=100, y1=100, page=p) for p in pages],
        table_type=table_type,
        title=title,
        continuation_markers=continuation or [],
    )


class TestContinuityScore:
    """Test the continuity_score function directly."""

    def setup_method(self):
        self.stitcher = TableStitcher()

    def test_continuation_marker_high_score(self):
        prev = _region([1], title="Schedule of Activities")
        curr = _region([2], title="Schedule of Activities (continued)", continuation=["continued"])
        score = self.stitcher.continuity_score(prev, curr)
        assert score >= MERGE_THRESHOLD

    def test_same_title_consecutive_pages(self):
        prev = _region([5], title="Schedule of Activities")
        curr = _region([6], title="Schedule of Activities")
        score = self.stitcher.continuity_score(prev, curr)
        assert score >= MERGE_THRESHOLD

    def test_different_tables_low_score(self):
        prev = _region([1], title="Synopsis", table_type=TableType.OTHER)
        curr = _region([5], title="Abbreviations", table_type=TableType.OTHER)
        score = self.stitcher.continuity_score(prev, curr)
        assert score < MERGE_THRESHOLD

    def test_distant_pages_penalized(self):
        prev = _region([1], title="SoA")
        curr_near = _region([2], title="SoA")
        curr_far = _region([10], title="SoA")
        score_near = self.stitcher.continuity_score(prev, curr_near)
        score_far = self.stitcher.continuity_score(prev, curr_far)
        assert score_near > score_far

    def test_both_soa_type_bonus(self):
        prev = _region([1], table_type=TableType.SOA)
        curr = _region([2], table_type=TableType.SOA)
        score_soa = self.stitcher.continuity_score(prev, curr)

        prev_other = _region([1], table_type=TableType.OTHER)
        curr_other = _region([2], table_type=TableType.OTHER)
        score_other = self.stitcher.continuity_score(prev_other, curr_other)
        assert score_soa >= score_other


class TestStitchingBehavior:
    """Test stitching end-to-end."""

    def test_no_stitching_single_region(self):
        stitcher = TableStitcher()
        regions = [_region([1], title="SoA")]
        result = stitcher.stitch(regions)
        assert len(result) == 1

    def test_continuation_marker_merges(self):
        stitcher = TableStitcher()
        regions = [
            _region([1], title="Schedule of Activities"),
            _region([2], continuation=["continued"]),
        ]
        result = stitcher.stitch(regions)
        assert len(result) == 1
        assert set(result[0].pages) == {1, 2}

    def test_three_page_table_stitches(self):
        stitcher = TableStitcher()
        regions = [
            _region([5], title="Schedule of Activities"),
            _region([6], title="Schedule of Activities"),
            _region([7], title="Schedule of Activities (continued)"),
        ]
        result = stitcher.stitch(regions)
        assert len(result) == 1
        assert set(result[0].pages) == {5, 6, 7}

    def test_different_tables_not_merged(self):
        stitcher = TableStitcher()
        regions = [
            _region([1], title="Schedule of Activities", table_type=TableType.SOA),
            _region([10], title="Abbreviations", table_type=TableType.OTHER),
        ]
        result = stitcher.stitch(regions)
        assert len(result) == 2

    def test_no_max_gap_limit(self):
        """Tables should merge based on content similarity, not rigid page gap."""
        stitcher = TableStitcher()
        # Same title but 4 pages apart (old stitcher would reject with max_gap=2)
        regions = [
            _region([1], title="Table 15. Schedule of Activities", table_type=TableType.SOA),
            _region([5], title="Table 15. Schedule of Activities", table_type=TableType.SOA),
        ]
        result = stitcher.stitch(regions)
        # Should merge because titles match + both SOA
        assert len(result) == 1

    def test_empty_input(self):
        stitcher = TableStitcher()
        assert stitcher.stitch([]) == []

    def test_preserves_original_title(self):
        stitcher = TableStitcher()
        regions = [
            _region([1], title="Table 8.1 Schedule of Activities"),
            _region([2], title="Table 8.1 Schedule of Activities (continued)"),
        ]
        result = stitcher.stitch(regions)
        assert result[0].title == "Table 8.1 Schedule of Activities"
