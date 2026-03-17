"""Tests for table detection module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from src.models.schema import (
    BoundingBox,
    PageImage,
    PipelineConfig,
    TableRegion,
    TableType,
)
from src.pipeline.table_detection import TableDetector


def _make_page(page_num: int = 0) -> PageImage:
    return PageImage(
        page_number=page_num,
        image_bytes=b"\x89PNG_fake",
        width=2550,
        height=3300,
        dpi=300,
    )


class TestTableDetector:
    def setup_method(self):
        self.config = PipelineConfig()
        self.detector = TableDetector(self.config)

    def test_creation(self):
        assert self.detector is not None

    @pytest.mark.asyncio
    async def test_detect_tables_single_page(self):
        """Detector should return table regions from VLM analysis."""
        pages = [_make_page(0)]

        mock_response = [
            {
                "table_id": "t1",
                "title": "Schedule of Activities",
                "table_type": "SOA",
                "bbox": {"x0": 50, "y0": 100, "x1": 2500, "y1": 3000},
            }
        ]

        with patch.object(
            self.detector, "_detect_on_page", new_callable=AsyncMock,
            return_value=mock_response
        ):
            regions = await self.detector.detect(pages)
            assert len(regions) == 1
            assert regions[0].table_type == TableType.SOA
            assert regions[0].title == "Schedule of Activities"

    @pytest.mark.asyncio
    async def test_detect_no_tables(self):
        """Pages with no tables should return empty list."""
        pages = [_make_page(0)]

        with patch.object(
            self.detector, "_detect_on_page", new_callable=AsyncMock,
            return_value=[]
        ):
            regions = await self.detector.detect(pages)
            assert regions == []

    @pytest.mark.asyncio
    async def test_detect_multiple_tables_multi_page(self):
        """Should handle multiple tables across multiple pages."""
        pages = [_make_page(0), _make_page(1), _make_page(2)]

        responses = [
            [{"table_id": "t1", "title": "Table 1", "table_type": "SOA",
              "bbox": {"x0": 50, "y0": 100, "x1": 2500, "y1": 3000}}],
            [],  # Page 2 has no tables
            [{"table_id": "t2", "title": "Table 2", "table_type": "LAB_PARAMS",
              "bbox": {"x0": 50, "y0": 50, "x1": 2500, "y1": 1500}}],
        ]

        call_count = 0

        async def mock_detect(page):
            nonlocal call_count
            result = responses[call_count]
            call_count += 1
            return result

        with patch.object(self.detector, "_detect_on_page", side_effect=mock_detect):
            regions = await self.detector.detect(pages)
            assert len(regions) == 2

    def test_parse_detection_response_valid(self):
        raw = {
            "table_id": "t1",
            "title": "Schedule of Activities",
            "table_type": "SOA",
            "bbox": {"x0": 50, "y0": 100, "x1": 2500, "y1": 3000},
        }
        region = self.detector._parse_detection(raw, page_num=3)
        assert region.table_id == "t1"
        assert region.pages == [3]
        assert region.bounding_boxes[0].page == 3

    def test_parse_detection_unknown_type_defaults_to_other(self):
        raw = {
            "table_id": "t2",
            "title": "Random Table",
            "table_type": "UNKNOWN",
            "bbox": {"x0": 10, "y0": 10, "x1": 100, "y1": 100},
        }
        region = self.detector._parse_detection(raw, page_num=0)
        assert region.table_type == TableType.OTHER
