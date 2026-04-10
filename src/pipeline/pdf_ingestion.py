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

    def ingest_from_bytes(
        self, pdf_bytes: bytes, page_filter: set[int] | None = None
    ) -> list[PageImage]:
        """Ingest a PDF from raw bytes. Returns one PageImage per page.

        Args:
            pdf_bytes: Raw PDF content.
            page_filter: If set, only render these page numbers (0-indexed).
                         Dramatically reduces memory and time for large documents
                         when only specific pages are needed.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages: list[PageImage] = []

        # DPI scaling: default PDF resolution is 72 DPI
        scale = self.config.render_dpi / 72.0
        matrix = fitz.Matrix(scale, scale)

        total_pages = doc.page_count
        pages_to_render = sorted(page_filter) if page_filter else range(total_pages)
        render_count = len(pages_to_render)

        if page_filter:
            logger.info(
                f"PDF has {total_pages} pages, rendering {render_count} selected pages "
                f"at {self.config.render_dpi} DPI"
            )
        else:
            logger.info(f"PDF has {total_pages} pages, rendering at {self.config.render_dpi} DPI")

        for page_num in pages_to_render:
            if page_num >= total_pages:
                continue
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

            if (len(pages)) % 20 == 0:
                logger.info(f"  Rendered {len(pages)}/{render_count} pages")
                gc.collect()

        doc.close()
        logger.info(f"Ingested {len(pages)} pages from PDF")
        return pages
