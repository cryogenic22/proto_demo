"""Tests for the JSON ingestor framework — schema detection, routing, and parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.formatter.extractor import FormattedDocument
from src.formatter.ingest.json_ingestor import (
    JsonIngestor,
    JsonSchemaDetector,
    JsonSchemaParser,
    JsonSchemaRegistry,
    create_default_registry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def registry():
    return create_default_registry()


@pytest.fixture
def ingestor(registry):
    return JsonIngestor(registry)


@pytest.fixture
def usdm_data():
    with open(FIXTURE_DIR / "usdm_synthetic.json") as f:
        return json.load(f)


def _protocol_ir_data():
    return {
        "protocol_id": "test_proto_001",
        "document_name": "test.pdf",
        "metadata": {
            "title": "Test Protocol",
            "sponsor": "TestCorp",
            "phase": "Phase 2",
            "therapeutic_area": "Oncology",
            "indication": "NSCLC",
        },
        "sections": [
            {"number": "1", "title": "Introduction", "page": 1, "level": 1,
             "content_html": "<p>Test content</p>", "children": []},
        ],
        "tables": [],
        "procedures": [],
    }


def _formatted_doc_ir_data():
    return {
        "filename": "test_doc.pdf",
        "total_pages": 1,
        "total_paragraphs": 2,
        "total_spans": 100,
        "pages": [
            {
                "page_number": 0,
                "width": 612.0,
                "height": 792.0,
                "margins": {"left": 72, "right": 72, "top": 72, "bottom": 72},
                "paragraphs": [
                    {
                        "style": "heading1",
                        "text": "Test Heading",
                        "alignment": "left",
                        "indent_level": 0,
                        "lines": [
                            {
                                "text": "Test Heading",
                                "spans": [
                                    {
                                        "text": "Test Heading",
                                        "font": "Arial-Bold",
                                        "size": 16.0,
                                        "color": "#000000",
                                        "bold": True,
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "style": "body",
                        "text": "Body text here",
                        "alignment": "left",
                        "indent_level": 0,
                        "lines": [
                            {
                                "text": "Body text here",
                                "spans": [
                                    {
                                        "text": "Body text here",
                                        "font": "Arial",
                                        "size": 11.0,
                                        "color": "#000000",
                                    }
                                ],
                            }
                        ],
                    },
                ],
                "tables": [],
            }
        ],
        "metadata": {
            "font_inventory": {"Arial": 100, "Arial-Bold": 20},
            "color_inventory": {"#000000": 120},
            "style_inventory": {"heading1": 1, "body": 1},
        },
    }


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestJsonSchemaRegistry:

    def test_default_registry_has_three_schemas(self, registry):
        assert set(registry.registered_schemas) == {"usdm", "protocol_ir", "formatted_doc_ir"}

    def test_priority_order(self, registry):
        schemas = registry.registered_schemas
        assert schemas[0] == "usdm"  # priority 10
        assert schemas[1] == "formatted_doc_ir"  # priority 15
        assert schemas[2] == "protocol_ir"  # priority 20

    def test_mismatched_schema_id_raises(self):
        class DetA(JsonSchemaDetector):
            def schema_id(self): return "a"
            def detect(self, data): return True
            def priority(self): return 0

        class ParserB(JsonSchemaParser):
            def schema_id(self): return "b"
            def to_formatted_document(self, data, filename=""): ...

        reg = JsonSchemaRegistry()
        with pytest.raises(ValueError, match="!="):
            reg.register(DetA(), ParserB())

    def test_unknown_schema_raises(self, registry):
        with pytest.raises(ValueError, match="No JSON schema detector matched"):
            registry.detect_schema({"random_key": 123})


# ---------------------------------------------------------------------------
# Detection tests
# ---------------------------------------------------------------------------

class TestSchemaDetection:

    def test_detect_usdm_by_study_key(self, registry, usdm_data):
        assert registry.detect_schema(usdm_data) == "usdm"

    def test_detect_usdm_by_version_key(self, registry):
        assert registry.detect_schema({"usdmVersion": "3.0", "study": {}}) == "usdm"

    def test_detect_usdm_by_study_title(self, registry):
        assert registry.detect_schema({"study": {"studyTitle": "Test"}}) == "usdm"

    def test_detect_protocol_ir(self, registry):
        data = _protocol_ir_data()
        assert registry.detect_schema(data) == "protocol_ir"

    def test_detect_formatted_doc_ir(self, registry):
        data = _formatted_doc_ir_data()
        assert registry.detect_schema(data) == "formatted_doc_ir"

    def test_protocol_ir_not_confused_with_usdm(self, registry):
        """Protocol IR should not trigger USDM detector."""
        data = _protocol_ir_data()
        assert registry.detect_schema(data) == "protocol_ir"

    def test_formatted_doc_not_confused_with_protocol(self, registry):
        """FormattedDoc IR has 'pages' but no 'protocol_id'."""
        data = _formatted_doc_ir_data()
        assert registry.detect_schema(data) == "formatted_doc_ir"


# ---------------------------------------------------------------------------
# Ingestor tests
# ---------------------------------------------------------------------------

class TestJsonIngestor:

    def test_ingest_usdm_returns_formatted_document(self, ingestor, usdm_data):
        doc = ingestor.ingest(json.dumps(usdm_data), filename="test.json")
        assert isinstance(doc, FormattedDocument)
        assert len(doc.pages) >= 3  # cover, synopsis, objectives, eligibility, SoA

    def test_ingest_protocol_ir(self, ingestor):
        data = _protocol_ir_data()
        doc = ingestor.ingest(json.dumps(data), filename="proto.json")
        assert isinstance(doc, FormattedDocument)
        assert len(doc.pages) >= 1

    def test_ingest_formatted_doc_ir_roundtrip(self, ingestor):
        data = _formatted_doc_ir_data()
        doc = ingestor.ingest(json.dumps(data), filename="roundtrip.json")
        assert isinstance(doc, FormattedDocument)
        assert len(doc.pages) == 1
        assert doc.pages[0].paragraphs[0].style == "heading1"
        assert doc.pages[0].paragraphs[0].lines[0].spans[0].bold is True
        assert doc.pages[0].paragraphs[1].style == "body"

    def test_ingest_bytes_input(self, ingestor):
        data = _protocol_ir_data()
        doc = ingestor.ingest(json.dumps(data).encode("utf-8"), filename="bytes.json")
        assert isinstance(doc, FormattedDocument)

    def test_ingest_invalid_json_raises(self, ingestor):
        with pytest.raises(Exception):
            ingestor.ingest("{bad json}", filename="bad.json")

    def test_ingest_array_raises(self, ingestor):
        with pytest.raises(ValueError, match="object"):
            ingestor.ingest("[1, 2, 3]")

    def test_detect_and_parse(self, ingestor, usdm_data):
        schema_id, parser = ingestor.detect_and_parse(usdm_data)
        assert schema_id == "usdm"
        assert parser.schema_id() == "usdm"


# ---------------------------------------------------------------------------
# DocHandler integration
# ---------------------------------------------------------------------------

class TestDocHandlerJsonIntegration:

    def test_dochandler_ingests_json(self):
        from src.formatter import DocHandler
        handler = DocHandler()
        data = _protocol_ir_data()
        doc = handler.ingest(json.dumps(data), format="json", filename="test.json")
        assert isinstance(doc, FormattedDocument)

    def test_dochandler_json_to_html(self):
        from src.formatter import DocHandler
        handler = DocHandler()
        data = _protocol_ir_data()
        doc = handler.ingest(json.dumps(data), format="json", filename="test.json")
        html = handler.render(doc, format="html")
        assert "Test Protocol" in html

    def test_dochandler_usdm_to_html(self, usdm_data):
        from src.formatter import DocHandler
        handler = DocHandler()
        doc = handler.ingest(json.dumps(usdm_data), format="json", filename="usdm.json")
        html = handler.render(doc, format="html")
        assert "XYZ-123" in html or "NSCLC" in html or "Schedule" in html

    def test_dochandler_convert_json_to_docx(self):
        from src.formatter import DocHandler
        handler = DocHandler()
        data = _protocol_ir_data()
        docx = handler.convert(json.dumps(data), "json", "docx", filename="test.json")
        assert isinstance(docx, bytes)
        assert len(docx) > 100


# ---------------------------------------------------------------------------
# FormattedDoc IR round-trip fidelity
# ---------------------------------------------------------------------------

class TestFormattedDocRoundTrip:

    def test_json_renderer_to_json_ingestor_roundtrip(self):
        """Test: create doc → JSONRenderer → JSON → JsonIngestor → doc, verify fidelity."""
        from src.formatter.extractor import (
            FormattedDocument, FormattedLine, FormattedPage,
            FormattedParagraph, FormattedSpan, FormattedTable, FormattedTableCell,
        )
        from src.formatter.render.json_renderer import JSONRenderer

        # Create original document
        original = FormattedDocument(
            filename="roundtrip_test.pdf",
            pages=[
                FormattedPage(
                    page_number=0, width=612.0, height=792.0,
                    paragraphs=[
                        FormattedParagraph(
                            lines=[FormattedLine(spans=[
                                FormattedSpan(text="Hello World", x0=0, y0=0, x1=100, y1=12,
                                              font="Arial", size=12.0, bold=True),
                            ])],
                            style="heading1",
                        ),
                        FormattedParagraph(
                            lines=[FormattedLine(spans=[
                                FormattedSpan(text="Normal text", x0=0, y0=20, x1=80, y1=30,
                                              font="Times", size=11.0),
                                FormattedSpan(text=" with subscript", x0=80, y0=20, x1=150, y1=30,
                                              font="Times", size=8.0, subscript=True),
                            ])],
                            style="body",
                        ),
                    ],
                    tables=[
                        FormattedTable(
                            rows=[
                                [FormattedTableCell(text="Header", row=0, col=0, is_header=True, bold=True)],
                                [FormattedTableCell(text="Data", row=1, col=0)],
                            ],
                            num_rows=2, num_cols=1,
                        ),
                    ],
                ),
            ],
            font_inventory={"Arial": 50, "Times": 60},
            color_inventory={"#000000": 110},
            style_inventory={"heading1": 1, "body": 1},
        )

        # Render to JSON
        renderer = JSONRenderer(indent=2)
        json_str = renderer.render(original)

        # Ingest back
        from src.formatter import DocHandler
        handler = DocHandler()
        roundtripped = handler.ingest(json_str, format="json", filename="roundtrip.json")

        # Verify fidelity
        assert len(roundtripped.pages) == len(original.pages)
        assert roundtripped.pages[0].paragraphs[0].style == "heading1"
        assert roundtripped.pages[0].paragraphs[0].lines[0].spans[0].bold is True
        assert roundtripped.pages[0].paragraphs[1].lines[0].spans[1].subscript is True
        assert len(roundtripped.pages[0].tables) == 1
        assert roundtripped.pages[0].tables[0].num_rows == 2
        assert roundtripped.font_inventory == original.font_inventory
