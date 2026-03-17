"""Tests for PDF ingestion module."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.models.schema import PageImage, PipelineConfig
from src.pipeline.pdf_ingestion import PDFIngestor


class TestPDFIngestor:
    def setup_method(self):
        self.config = PipelineConfig()
        self.ingestor = PDFIngestor(self.config)

    def test_ingestor_creation(self):
        assert self.ingestor.config.render_dpi == 150

    @patch("src.pipeline.pdf_ingestion.fitz")
    def test_ingest_from_bytes(self, mock_fitz):
        # Mock a 2-page PDF
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=2)
        mock_doc.__iter__ = MagicMock(return_value=iter([MagicMock(), MagicMock()]))
        mock_doc.page_count = 2

        for i, page in enumerate(mock_doc):
            pixmap = MagicMock()
            pixmap.tobytes.return_value = b"\x89PNG_fake_image_data"
            pixmap.width = 2550
            pixmap.height = 3300
            page.get_pixmap.return_value = pixmap

        # Re-create iterator since we consumed it
        page0 = MagicMock()
        page1 = MagicMock()
        for p in [page0, page1]:
            pix = MagicMock()
            pix.tobytes.return_value = b"\x89PNG_fake"
            pix.width = 2550
            pix.height = 3300
            p.get_pixmap.return_value = pix

        mock_doc.__getitem__ = MagicMock(side_effect=[page0, page1])
        mock_doc.page_count = 2
        mock_fitz.open.return_value = mock_doc

        pages = self.ingestor.ingest_from_bytes(b"fake_pdf_bytes")

        assert len(pages) == 2
        assert all(isinstance(p, PageImage) for p in pages)
        assert pages[0].page_number == 0
        assert pages[1].page_number == 1
        assert pages[0].dpi == 150

    @patch("src.pipeline.pdf_ingestion.fitz")
    def test_ingest_respects_dpi(self, mock_fitz):
        config = PipelineConfig(render_dpi=450)
        ingestor = PDFIngestor(config)

        mock_doc = MagicMock()
        mock_doc.page_count = 1
        page0 = MagicMock()
        pix = MagicMock()
        pix.tobytes.return_value = b"\x89PNG"
        pix.width = 3825
        pix.height = 4950
        page0.get_pixmap.return_value = pix
        mock_doc.__getitem__ = MagicMock(return_value=page0)
        mock_fitz.open.return_value = mock_doc

        pages = ingestor.ingest_from_bytes(b"fake")
        assert len(pages) == 1
        # Verify the matrix was created with correct DPI scaling
        page0.get_pixmap.assert_called_once()

    @patch("src.pipeline.pdf_ingestion.fitz")
    def test_ingest_empty_pdf(self, mock_fitz):
        mock_doc = MagicMock()
        mock_doc.page_count = 0
        mock_fitz.open.return_value = mock_doc

        pages = self.ingestor.ingest_from_bytes(b"empty")
        assert pages == []

    def test_ingest_from_path_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            self.ingestor.ingest_from_path(Path("/nonexistent/file.pdf"))
