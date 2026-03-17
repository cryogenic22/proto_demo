"""Tests for pipeline orchestrator — end-to-end coordination."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.models.schema import (
    BoundingBox,
    ExtractedCell,
    ExtractedTable,
    PageImage,
    PipelineConfig,
    PipelineOutput,
    TableRegion,
    TableSchema,
    TableType,
)
from src.pipeline.orchestrator import PipelineOrchestrator


def _fake_pages(n: int) -> list[PageImage]:
    return [
        PageImage(page_number=i, image_bytes=b"\x89PNG", width=2550, height=3300)
        for i in range(n)
    ]


def _fake_region(table_id: str = "t1", pages: list[int] | None = None) -> TableRegion:
    pages = pages or [0]
    return TableRegion(
        table_id=table_id,
        pages=pages,
        bounding_boxes=[
            BoundingBox(page=p, x0=50, y0=100, x1=2500, y1=3000) for p in pages
        ],
        table_type=TableType.SOA,
        title="Schedule of Activities",
    )


class TestPipelineOrchestrator:
    def setup_method(self):
        self.config = PipelineConfig()

    @pytest.mark.asyncio
    async def test_full_pipeline_smoke(self):
        """Smoke test: pipeline runs end-to-end without crashing."""
        orchestrator = PipelineOrchestrator(self.config)

        # Mock all sub-components
        orchestrator.ingestor = MagicMock()
        orchestrator.ingestor.ingest_from_bytes.return_value = _fake_pages(2)

        orchestrator.detector = AsyncMock()
        orchestrator.detector.detect.return_value = [_fake_region()]

        orchestrator.stitcher = MagicMock()
        orchestrator.stitcher.stitch.return_value = [_fake_region()]

        orchestrator.structural_analyzer = AsyncMock()
        orchestrator.structural_analyzer.analyze.return_value = TableSchema(
            table_id="t1", num_rows=3, num_cols=5
        )

        orchestrator.cell_extractor = AsyncMock()
        orchestrator.cell_extractor.extract.return_value = [
            ExtractedCell(row=0, col=0, raw_value="ECG"),
            ExtractedCell(row=0, col=1, raw_value="X"),
        ]

        orchestrator.footnote_resolver = MagicMock()
        orchestrator.footnote_resolver.resolve.return_value = (
            [ExtractedCell(row=0, col=0, raw_value="ECG"),
             ExtractedCell(row=0, col=1, raw_value="X")],
            [],
        )

        orchestrator.procedure_normalizer = MagicMock()
        orchestrator.procedure_normalizer.normalize_batch.return_value = []

        orchestrator.temporal_extractor = MagicMock()
        orchestrator.temporal_extractor.parse_batch.return_value = []

        orchestrator.reconciler = MagicMock()
        from src.pipeline.reconciler import ReconciliationResult
        orchestrator.reconciler.reconcile.return_value = ReconciliationResult(
            cells=[ExtractedCell(row=0, col=0, raw_value="ECG"),
                   ExtractedCell(row=0, col=1, raw_value="X")],
            flagged=[],
            review_items=[],
        )

        result = await orchestrator.run(b"fake_pdf", "test.pdf")

        assert isinstance(result, PipelineOutput)
        assert result.document_name == "test.pdf"
        assert len(result.tables) == 1

    @pytest.mark.asyncio
    async def test_pipeline_no_tables(self):
        """Pipeline handles PDFs with no tables gracefully."""
        orchestrator = PipelineOrchestrator(self.config)

        orchestrator.ingestor = MagicMock()
        orchestrator.ingestor.ingest_from_bytes.return_value = _fake_pages(5)

        orchestrator.detector = AsyncMock()
        orchestrator.detector.detect.return_value = []

        orchestrator.stitcher = MagicMock()
        orchestrator.stitcher.stitch.return_value = []

        result = await orchestrator.run(b"fake_pdf", "empty.pdf")

        assert isinstance(result, PipelineOutput)
        assert result.tables == []
        assert any("No tables detected" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_pipeline_error_in_one_table_continues(self):
        """If one table fails, pipeline continues with others."""
        orchestrator = PipelineOrchestrator(self.config)

        orchestrator.ingestor = MagicMock()
        orchestrator.ingestor.ingest_from_bytes.return_value = _fake_pages(3)

        regions = [_fake_region("t1", [0]), _fake_region("t2", [2])]
        orchestrator.detector = AsyncMock()
        orchestrator.detector.detect.return_value = regions

        orchestrator.stitcher = MagicMock()
        orchestrator.stitcher.stitch.return_value = regions

        call_count = 0

        async def mock_analyze(region, pages):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Simulated failure on table 1")
            return TableSchema(table_id="t2", num_rows=2, num_cols=3)

        orchestrator.structural_analyzer = AsyncMock()
        orchestrator.structural_analyzer.analyze = mock_analyze

        orchestrator.cell_extractor = AsyncMock()
        orchestrator.cell_extractor.extract.return_value = [
            ExtractedCell(row=0, col=0, raw_value="Test")
        ]

        orchestrator.footnote_resolver = MagicMock()
        orchestrator.footnote_resolver.resolve.return_value = (
            [ExtractedCell(row=0, col=0, raw_value="Test")], []
        )

        orchestrator.procedure_normalizer = MagicMock()
        orchestrator.procedure_normalizer.normalize_batch.return_value = []

        orchestrator.temporal_extractor = MagicMock()
        orchestrator.temporal_extractor.parse_batch.return_value = []

        orchestrator.reconciler = MagicMock()
        from src.pipeline.reconciler import ReconciliationResult
        orchestrator.reconciler.reconcile.return_value = ReconciliationResult(
            cells=[ExtractedCell(row=0, col=0, raw_value="Test")],
            flagged=[], review_items=[],
        )

        result = await orchestrator.run(b"fake_pdf", "partial.pdf")
        # Should have 1 table (t2 succeeded) and a warning about t1
        assert len(result.tables) == 1
        assert any("t1" in w for w in result.warnings)
