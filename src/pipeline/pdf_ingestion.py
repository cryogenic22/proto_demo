"""
PDF Ingestion — converts PDF to high-resolution page images.

Uses PyMuPDF (fitz) for rendering. Handles both native digital
PDFs and scanned documents.
"""

from __future__ import annotations

import gc
import logging
from pathlib import Path

import fitz  # PyMuPDF

from src.models.schema import PageImage, PipelineConfig

logger = logging.getLogger(__name__)


class PDFIngestor:
    """Renders each page of a PDF as a PNG image at configurable DPI."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def ingest_from_path(self, pdf_path: Path) -> list[PageImage]:
        """Ingest a PDF from a file path."""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        pdf_bytes = pdf_path.read_bytes()
        return self.ingest_from_bytes(pdf_bytes)

    def ingest_from_bytes(self, pdf_bytes: bytes) -> list[PageImage]:
        """Ingest a PDF from raw bytes. Returns one PageImage per page."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages: list[PageImage] = []

        # DPI scaling: default PDF resolution is 72 DPI
        scale = self.config.render_dpi / 72.0
        matrix = fitz.Matrix(scale, scale)

        total_pages = doc.page_count
        logger.info(f"PDF has {total_pages} pages, rendering at {self.config.render_dpi} DPI")

        for page_num in range(total_pages):
            page = doc[page_num]
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image_bytes = pixmap.tobytes("png")

            pages.append(PageImage(
                page_number=page_num,
                image_bytes=image_bytes,
                width=pixmap.width,
                height=pixmap.height,
                dpi=self.config.render_dpi,
            ))

            # Free pixmap memory immediately
            pixmap = None

            if (page_num + 1) % 20 == 0:
                logger.info(f"  Rendered {page_num + 1}/{total_pages} pages")
                gc.collect()

        doc.close()
        logger.info(f"Ingested {len(pages)} pages from PDF")
        return pages
