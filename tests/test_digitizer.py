"""Tests for DocumentDigitizer and DigitizedDocument model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models.digitized import (
    DigitizedDocument,
    TableClassification,
    TableType,
)
from src.pipeline.digitizer import DocumentDigitizer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GOLDEN_DIR = Path("golden_set/cached_pdfs")


def _get_test_pdf() -> bytes | None:
    """Try to find a test PDF in the golden set."""
    candidates = [Path("C:/Users/kapil/Downloads/P17_durvalumab.pdf")]
    if GOLDEN_DIR.exists():
        candidates.extend(sorted(GOLDEN_DIR.glob("*.pdf"))[:1])
    for p in candidates:
        if p.exists():
            return p.read_bytes()
    return None


@pytest.fixture
def digitizer():
    return DocumentDigitizer()


@pytest.fixture
def test_pdf():
    pdf = _get_test_pdf()
    if pdf is None:
        pytest.skip("No test PDF available")
    return pdf


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestTableClassification:

    def test_create_classification(self):
        tc = TableClassification(
            page_number=16,
            table_index=0,
            table_type=TableType.SOA,
            confidence=0.9,
            title="Schedule of Activities",
            num_rows=23,
            num_cols=8,
        )
        assert tc.table_type == "SOA"
        assert tc.confidence == 0.9

    def test_classification_signals(self):
        tc = TableClassification(
            page_number=5,
            table_index=0,
            table_type=TableType.OTHER,
            confidence=0.5,
            signals={"marker_count": 0, "visit_columns": 0},
        )
        assert tc.signals["marker_count"] == 0


class TestDigitizedDocument:

    def test_get_soa_tables(self):
        from src.formatter.extractor import FormattedDocument
        doc = DigitizedDocument(
            formatted=FormattedDocument(),
            table_classifications=[
                TableClassification(page_number=16, table_index=0,
                                     table_type=TableType.SOA, confidence=0.9),
                TableClassification(page_number=24, table_index=0,
                                     table_type=TableType.OTHER, confidence=0.5),
                TableClassification(page_number=21, table_index=0,
                                     table_type=TableType.SOA, confidence=0.85),
            ],
        )
        soa = doc.get_soa_tables()
        assert len(soa) == 2
        assert all(tc.table_type == TableType.SOA for tc in soa)

    def test_get_soa_pages(self):
        from src.formatter.extractor import FormattedDocument
        doc = DigitizedDocument(
            formatted=FormattedDocument(),
            table_classifications=[
                TableClassification(page_number=16, table_index=0,
                                     table_type=TableType.SOA, confidence=0.9),
                TableClassification(page_number=17, table_index=0,
                                     table_type=TableType.SOA, confidence=0.85),
            ],
        )
        pages = doc.get_soa_pages()
        assert pages == {16, 17}

    def test_summary(self):
        from src.formatter.extractor import FormattedDocument
        doc = DigitizedDocument(
            formatted=FormattedDocument(filename="test.pdf"),
            table_classifications=[
                TableClassification(page_number=1, table_index=0,
                                     table_type=TableType.SOA, confidence=0.9),
                TableClassification(page_number=5, table_index=0,
                                     table_type=TableType.OTHER, confidence=0.5),
            ],
            source_filename="test.pdf",
        )
        s = doc.summary()
        assert s["tables"] == 2
        assert s["table_types"]["SOA"] == 1
        assert s["table_types"]["OTHER"] == 1


# ---------------------------------------------------------------------------
# Digitizer tests (require a PDF)
# ---------------------------------------------------------------------------

class TestDocumentDigitizer:

    def test_digitize_returns_digitized_document(self, digitizer, test_pdf):
        result = digitizer.digitize(test_pdf, "test.pdf")
        assert isinstance(result, DigitizedDocument)
        assert result.total_pages > 0
        assert result.source_filename == "test.pdf"
        assert result.source_hash  # non-empty

    def test_tables_classified(self, digitizer, test_pdf):
        result = digitizer.digitize(test_pdf, "test.pdf")
        assert result.total_tables > 0
        # Each classification has valid fields
        for tc in result.table_classifications:
            assert tc.page_number >= 0
            assert tc.table_index >= 0
            assert tc.table_type in (TableType.SOA, TableType.OTHER,
                                      TableType.DEMOGRAPHICS, TableType.LAB_PARAMS)
            assert 0 <= tc.confidence <= 1.0

    def test_soa_tables_detected(self, digitizer, test_pdf):
        """At least one SoA table should be detected in a protocol PDF."""
        result = digitizer.digitize(test_pdf, "test.pdf")
        soa = result.get_soa_tables()
        assert len(soa) >= 1, f"Expected SoA tables, got {result.total_tables} total"

    def test_sections_parsed(self, digitizer, test_pdf):
        result = digitizer.digitize(test_pdf, "test.pdf")
        # Sections may or may not parse (depends on PDF structure)
        # Just verify the field is populated as a list
        assert isinstance(result.sections, list)

    def test_metadata_extracted(self, digitizer, test_pdf):
        result = digitizer.digitize(test_pdf, "test.pdf")
        assert result.metadata is not None

    def test_formatted_document_has_content(self, digitizer, test_pdf):
        result = digitizer.digitize(test_pdf, "test.pdf")
        assert result.formatted.total_paragraphs > 0
        assert len(result.formatted.pages) > 0


# ---------------------------------------------------------------------------
# API endpoint test
# ---------------------------------------------------------------------------

class TestExtractionModeEndpoint:

    @pytest.fixture
    def client(self):
        from api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_extract_accepts_mode_parameter(self, client):
        """The extract endpoint should accept extraction_mode as a form field."""
        import io
        # Use a minimal PDF (just enough to pass validation)
        # This will fail at pipeline level, but we just want to check
        # the endpoint accepts the parameter
        minimal_pdf = b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\nxref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n109\n%%EOF"

        resp = client.post(
            "/api/extract",
            files={"file": ("test.pdf", io.BytesIO(minimal_pdf), "application/pdf")},
            data={"extraction_mode": "full"},
        )
        # Endpoint should accept and return 200 with job_id
        # (the background task may fail, but the endpoint itself should work)
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert body.get("extraction_mode") == "full"
