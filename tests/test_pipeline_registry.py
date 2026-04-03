"""
Tests for the pipeline registry/orchestrator pattern.

Validates that all ingestors and renderers register correctly, that the
registry routes to the right tool for each format, and that the full
pipeline produces working end-to-end conversions.
"""

from __future__ import annotations

import pytest

from src.formatter.pipeline.base import IngestorTool, RendererTool
from src.formatter.pipeline.registry import PipelineToolRegistry
from src.formatter.pipeline.orchestrator import PipelineOrchestrator
from src.formatter.pipeline.factory import create_pipeline
from src.formatter.pipeline.adapters import (
    ALL_INGESTOR_ADAPTERS,
    ALL_RENDERER_ADAPTERS,
    PDFIngestorAdapter,
    DOCXIngestorAdapter,
    HTMLIngestorAdapter,
    MarkdownIngestorAdapter,
    TextIngestorAdapter,
    PPTXIngestorAdapter,
    ExcelIngestorAdapter,
    DOCXRendererAdapter,
    HTMLRendererAdapter,
    MarkdownRendererAdapter,
    TextRendererAdapter,
    JSONRendererAdapter,
    PDFRendererAdapter,
    PPTXRendererAdapter,
)
from src.formatter.formula.base import ToolMetadata, ToolSideEffect


class TestIngestorAdapters:
    """Test that all 7 ingestor adapters conform to the IngestorTool contract."""

    def test_all_ingestors_are_ingestor_tools(self):
        """Every adapter in ALL_INGESTOR_ADAPTERS is an IngestorTool subclass."""
        assert len(ALL_INGESTOR_ADAPTERS) == 7
        for cls in ALL_INGESTOR_ADAPTERS:
            instance = cls()
            assert isinstance(instance, IngestorTool), (
                f"{cls.__name__} is not an IngestorTool"
            )

    @pytest.mark.parametrize(
        "adapter_cls,expected_formats",
        [
            (PDFIngestorAdapter, ["pdf"]),
            (DOCXIngestorAdapter, ["docx"]),
            (HTMLIngestorAdapter, ["html"]),
            (MarkdownIngestorAdapter, ["markdown"]),
            (TextIngestorAdapter, ["text"]),
            (PPTXIngestorAdapter, ["pptx"]),
            (ExcelIngestorAdapter, ["xlsx"]),
        ],
    )
    def test_ingestor_supported_formats(self, adapter_cls, expected_formats):
        """Each ingestor declares the correct supported formats."""
        adapter = adapter_cls()
        assert adapter.supported_formats() == expected_formats

    @pytest.mark.parametrize(
        "adapter_cls",
        ALL_INGESTOR_ADAPTERS,
    )
    def test_ingestor_metadata_is_valid(self, adapter_cls):
        """Each ingestor has valid ToolMetadata with name, version, description."""
        adapter = adapter_cls()
        meta = adapter.metadata()
        assert isinstance(meta, ToolMetadata)
        assert meta.name, "Metadata name must not be empty"
        assert meta.version, "Metadata version must not be empty"
        assert meta.description, "Metadata description must not be empty"
        assert meta.side_effects == ToolSideEffect.NONE

    def test_all_seven_ingestor_formats_registered(self):
        """Registering all 7 adapters covers pdf, docx, html, markdown, text, pptx, xlsx."""
        registry = PipelineToolRegistry()
        for cls in ALL_INGESTOR_ADAPTERS:
            registry.register_ingestor(cls())

        expected = {"pdf", "docx", "html", "markdown", "text", "pptx", "xlsx"}
        for fmt in expected:
            assert registry.get_ingestor(fmt) is not None, (
                f"No ingestor registered for '{fmt}'"
            )


class TestRendererAdapters:
    """Test that all 7 renderer adapters conform to the RendererTool contract."""

    def test_all_renderers_are_renderer_tools(self):
        """Every adapter in ALL_RENDERER_ADAPTERS is a RendererTool subclass."""
        assert len(ALL_RENDERER_ADAPTERS) == 7
        for cls in ALL_RENDERER_ADAPTERS:
            instance = cls()
            assert isinstance(instance, RendererTool), (
                f"{cls.__name__} is not a RendererTool"
            )

    @pytest.mark.parametrize(
        "adapter_cls,expected_format",
        [
            (DOCXRendererAdapter, "docx"),
            (HTMLRendererAdapter, "html"),
            (MarkdownRendererAdapter, "markdown"),
            (TextRendererAdapter, "text"),
            (JSONRendererAdapter, "json"),
            (PDFRendererAdapter, "pdf"),
            (PPTXRendererAdapter, "pptx"),
        ],
    )
    def test_renderer_output_format(self, adapter_cls, expected_format):
        """Each renderer declares the correct output format."""
        adapter = adapter_cls()
        assert adapter.output_format() == expected_format

    @pytest.mark.parametrize(
        "adapter_cls",
        ALL_RENDERER_ADAPTERS,
    )
    def test_renderer_metadata_is_valid(self, adapter_cls):
        """Each renderer has valid ToolMetadata with name, version, description."""
        adapter = adapter_cls()
        meta = adapter.metadata()
        assert isinstance(meta, ToolMetadata)
        assert meta.name, "Metadata name must not be empty"
        assert meta.version, "Metadata version must not be empty"
        assert meta.description, "Metadata description must not be empty"
        assert meta.side_effects == ToolSideEffect.NONE

    def test_all_seven_renderer_formats_registered(self):
        """Registering all 7 adapters covers docx, html, markdown, text, json, pdf, pptx."""
        registry = PipelineToolRegistry()
        for cls in ALL_RENDERER_ADAPTERS:
            registry.register_renderer(cls())

        expected = {"docx", "html", "markdown", "text", "json", "pdf", "pptx"}
        for fmt in expected:
            assert registry.get_renderer(fmt) is not None, (
                f"No renderer registered for '{fmt}'"
            )


class TestPipelineToolRegistry:
    """Test registry registration, lookup, and introspection."""

    def setup_method(self):
        self.registry = PipelineToolRegistry()

    def test_get_ingestor_returns_pdf_adapter(self):
        """get_ingestor('pdf') returns the PDF adapter."""
        adapter = PDFIngestorAdapter()
        self.registry.register_ingestor(adapter)
        result = self.registry.get_ingestor("pdf")
        assert result is adapter
        assert result.metadata().name == "pdf-ingestor"

    def test_get_ingestor_returns_none_for_unknown(self):
        """get_ingestor for unknown format returns None."""
        assert self.registry.get_ingestor("unknown") is None

    def test_get_renderer_returns_html_adapter(self):
        """get_renderer('html') returns the HTML adapter."""
        adapter = HTMLRendererAdapter()
        self.registry.register_renderer(adapter)
        result = self.registry.get_renderer("html")
        assert result is adapter
        assert result.metadata().name == "html-renderer"

    def test_get_renderer_returns_none_for_unknown(self):
        """get_renderer for unknown format returns None."""
        assert self.registry.get_renderer("unknown") is None

    def test_list_tools_structure(self):
        """list_tools returns ingestors and renderers dicts."""
        self.registry.register_ingestor(TextIngestorAdapter())
        self.registry.register_renderer(HTMLRendererAdapter())
        tools = self.registry.list_tools()

        assert "ingestors" in tools
        assert "renderers" in tools
        assert len(tools["ingestors"]) == 1
        assert len(tools["renderers"]) == 1
        assert tools["ingestors"][0]["name"] == "text-ingestor"
        assert tools["renderers"][0]["name"] == "html-renderer"

    def test_total_tools_count(self):
        """total_tools counts unique tools across all formats."""
        self.registry.register_ingestor(PDFIngestorAdapter())
        self.registry.register_renderer(HTMLRendererAdapter())
        self.registry.register_renderer(TextRendererAdapter())
        assert self.registry.total_tools == 3


class TestPipelineOrchestrator:
    """Test the orchestrator routing logic."""

    def setup_method(self):
        self.registry = PipelineToolRegistry()
        self.registry.register_ingestor(TextIngestorAdapter())
        self.registry.register_ingestor(HTMLIngestorAdapter())
        self.registry.register_renderer(HTMLRendererAdapter())
        self.registry.register_renderer(TextRendererAdapter())
        self.orchestrator = PipelineOrchestrator(self.registry)

    def test_ingest_text(self):
        """Ingest plain text produces a FormattedDocument."""
        doc = self.orchestrator.ingest("Hello world", "text")
        assert doc is not None
        assert len(doc.pages) > 0

    def test_ingest_unsupported_raises(self):
        """Ingesting unsupported format raises ValueError."""
        with pytest.raises(ValueError, match="No ingestor registered"):
            self.orchestrator.ingest(b"data", "pdf")

    def test_render_to_html(self):
        """Render a document to HTML produces a string."""
        doc = self.orchestrator.ingest("Hello world", "text")
        result = self.orchestrator.render(doc, "html")
        assert isinstance(result, str)
        assert "Hello" in result

    def test_render_unsupported_raises(self):
        """Rendering to unsupported format raises ValueError."""
        doc = self.orchestrator.ingest("Hello", "text")
        with pytest.raises(ValueError, match="No renderer registered"):
            self.orchestrator.render(doc, "pdf")

    def test_convert_text_to_html(self):
        """convert('hello', 'text', 'html') end-to-end."""
        result = self.orchestrator.convert("Hello world", "text", "html")
        assert isinstance(result, str)
        assert "Hello" in result

    def test_convert_html_to_text(self):
        """convert HTML to text end-to-end."""
        html = "<p>Hello <b>world</b></p>"
        result = self.orchestrator.convert(html, "html", "text")
        assert isinstance(result, str)
        assert "Hello" in result
        assert "world" in result


class TestCreatePipeline:
    """Test the factory function produces a working orchestrator."""

    def test_create_pipeline_returns_orchestrator(self):
        """create_pipeline() returns a PipelineOrchestrator."""
        pipeline = create_pipeline()
        assert isinstance(pipeline, PipelineOrchestrator)

    def test_create_pipeline_has_all_ingestors(self):
        """The factory-created pipeline has all 7 ingestors registered."""
        pipeline = create_pipeline()
        for fmt in ("pdf", "docx", "html", "markdown", "text", "pptx", "xlsx"):
            assert pipeline.registry.get_ingestor(fmt) is not None, (
                f"Missing ingestor for '{fmt}'"
            )

    def test_create_pipeline_has_all_renderers(self):
        """The factory-created pipeline has all 7 renderers registered."""
        pipeline = create_pipeline()
        for fmt in ("docx", "html", "markdown", "text", "json", "pdf", "pptx"):
            assert pipeline.registry.get_renderer(fmt) is not None, (
                f"Missing renderer for '{fmt}'"
            )

    def test_create_pipeline_total_tools(self):
        """The factory pipeline has 14 total tools (7 ingestors + 7 renderers)."""
        pipeline = create_pipeline()
        assert pipeline.registry.total_tools == 14

    def test_create_pipeline_convert_text_to_html(self):
        """End-to-end: create_pipeline().convert('hello', 'text', 'html')."""
        pipeline = create_pipeline()
        result = pipeline.convert("hello", "text", "html")
        assert isinstance(result, str)
        assert "hello" in result.lower()

    def test_create_pipeline_convert_markdown_to_text(self):
        """End-to-end: convert Markdown to text through the pipeline."""
        pipeline = create_pipeline()
        result = pipeline.convert("# Title\n\nSome text", "markdown", "text")
        assert isinstance(result, str)
        assert "title" in result.lower()

    def test_create_pipeline_no_formula_orchestrator_by_default(self):
        """By default, formula_orchestrator is None."""
        pipeline = create_pipeline()
        assert pipeline.formula_orchestrator is None
