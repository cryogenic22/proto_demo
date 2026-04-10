"""
Pipeline Adapters — wrap existing ingestors and renderers as registered tools.

Each adapter class wraps an existing ingestor or renderer, adding ToolMetadata
and conforming to the IngestorTool / RendererTool abstract interface. This is
the Adapter pattern: the existing code is not modified, only wrapped.

All existing ingestors:
- FormattingExtractor (pdf)     -> PDFIngestorAdapter
- DOCXIngestor (docx)           -> DOCXIngestorAdapter
- HTMLIngestor (html)           -> HTMLIngestorAdapter
- MarkdownIngestor (markdown)   -> MarkdownIngestorAdapter
- TextIngestor (text)           -> TextIngestorAdapter
- PPTXIngestor (pptx)           -> PPTXIngestorAdapter
- ExcelIngestor (xlsx)          -> ExcelIngestorAdapter
- JsonIngestor (json)           -> JSONIngestorAdapter

All existing renderers:
- DOCXRenderer (docx)           -> DOCXRendererAdapter
- HTMLRenderer (html)           -> HTMLRendererAdapter
- MarkdownRenderer (markdown)   -> MarkdownRendererAdapter
- TextRenderer (text)           -> TextRendererAdapter
- JSONRenderer (json)           -> JSONRendererAdapter
- PDFRenderer (pdf)             -> PDFRendererAdapter
- PPTXRenderer (pptx)           -> PPTXRendererAdapter
"""

from __future__ import annotations

from src.formatter.extractor import FormattedDocument, FormattingExtractor
from src.formatter.formula.base import ToolMetadata, ToolSideEffect
from src.formatter.pipeline.base import IngestorTool, RendererTool

# Ingestor imports
from src.formatter.ingest.docx_ingestor import DOCXIngestor
from src.formatter.ingest.html_ingestor import HTMLIngestor
from src.formatter.ingest.markdown_ingestor import MarkdownIngestor
from src.formatter.ingest.text_ingestor import TextIngestor
from src.formatter.ingest.pptx_ingestor import PPTXIngestor
from src.formatter.ingest.excel_ingestor import ExcelIngestor

# Renderer imports
from src.formatter.docx_renderer import DOCXRenderer
from src.formatter.render.html_renderer import HTMLRenderer
from src.formatter.render.markdown_renderer import MarkdownRenderer
from src.formatter.render.text_renderer import TextRenderer
from src.formatter.render.json_renderer import JSONRenderer
from src.formatter.render.pdf_renderer import PDFRenderer
from src.formatter.render.pptx_renderer import PPTXRenderer


# ---------------------------------------------------------------------------
# Ingestor Adapters
# ---------------------------------------------------------------------------

class PDFIngestorAdapter(IngestorTool):
    """Wraps FormattingExtractor as a registered IngestorTool.

    Extracts rich formatting metadata from PDF documents using PyMuPDF,
    producing a FormattedDocument with per-span position, font, size,
    color, and style flags.
    """

    def __init__(self):
        self._inner = FormattingExtractor()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="pdf-ingestor",
            version="1.0.0",
            description=(
                "Extracts formatting-rich IR from PDF bytes using PyMuPDF. "
                "Produces per-span font, size, color, bold/italic metadata."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def ingest(self, content: bytes | str, filename: str = "") -> FormattedDocument:
        if isinstance(content, str):
            content = content.encode("utf-8")
        return self._inner.extract(content, filename)

    def supported_formats(self) -> list[str]:
        return ["pdf"]


class DOCXIngestorAdapter(IngestorTool):
    """Wraps DOCXIngestor as a registered IngestorTool.

    Reads paragraph formatting, tables, heading styles, and list styles
    from Word documents with style inheritance resolution.
    """

    def __init__(self):
        self._inner = DOCXIngestor()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="docx-ingestor",
            version="1.0.0",
            description=(
                "Parses DOCX files with style inheritance (run -> paragraph "
                "style -> document defaults) into FormattedDocument IR."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def ingest(self, content: bytes | str, filename: str = "") -> FormattedDocument:
        if isinstance(content, str):
            content = content.encode("utf-8")
        return self._inner.ingest(content, filename)

    def supported_formats(self) -> list[str]:
        return ["docx"]


class HTMLIngestorAdapter(IngestorTool):
    """Wraps HTMLIngestor as a registered IngestorTool.

    Parses HTML using stdlib html.parser, mapping semantic tags to the
    FormattedDocument IR model.
    """

    def __init__(self):
        self._inner = HTMLIngestor()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="html-ingestor",
            version="1.0.0",
            description=(
                "Parses HTML content into FormattedDocument IR using stdlib "
                "html.parser. Maps headings, bold, italic, tables, lists."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def ingest(self, content: bytes | str, filename: str = "") -> FormattedDocument:
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        return self._inner.ingest(content, filename)

    def supported_formats(self) -> list[str]:
        return ["html"]


class MarkdownIngestorAdapter(IngestorTool):
    """Wraps MarkdownIngestor as a registered IngestorTool.

    Parses Markdown using regex-based parsing into FormattedDocument IR.
    """

    def __init__(self):
        self._inner = MarkdownIngestor()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="markdown-ingestor",
            version="1.0.0",
            description=(
                "Parses Markdown content into FormattedDocument IR. Handles "
                "headings, bold, italic, code, lists, tables, images."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def ingest(self, content: bytes | str, filename: str = "") -> FormattedDocument:
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        return self._inner.ingest(content, filename)

    def supported_formats(self) -> list[str]:
        return ["markdown"]


class TextIngestorAdapter(IngestorTool):
    """Wraps TextIngestor as a registered IngestorTool.

    Detects basic structure: numbered sections become headings, bullet lines
    become lists, and everything else becomes body paragraphs.
    """

    def __init__(self):
        self._inner = TextIngestor()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="text-ingestor",
            version="1.0.0",
            description=(
                "Parses plain text into FormattedDocument IR with structure "
                "detection (numbered headings, bullet lists, paragraphs)."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def ingest(self, content: bytes | str, filename: str = "") -> FormattedDocument:
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        return self._inner.ingest(content, filename)

    def supported_formats(self) -> list[str]:
        return ["text"]


class PPTXIngestorAdapter(IngestorTool):
    """Wraps PPTXIngestor as a registered IngestorTool.

    Parses PowerPoint slides into FormattedDocument IR using python-pptx.
    Each slide maps to a FormattedPage.
    """

    def __init__(self):
        self._inner = PPTXIngestor()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="pptx-ingestor",
            version="1.0.0",
            description=(
                "Parses PPTX files into FormattedDocument IR using python-pptx. "
                "Each slide becomes a page with text shapes and tables."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def ingest(self, content: bytes | str, filename: str = "") -> FormattedDocument:
        if isinstance(content, str):
            content = content.encode("utf-8")
        return self._inner.ingest(content, filename)

    def supported_formats(self) -> list[str]:
        return ["pptx"]


class ExcelIngestorAdapter(IngestorTool):
    """Wraps ExcelIngestor as a registered IngestorTool.

    Parses XLSX files into FormattedDocument IR using openpyxl. Each
    worksheet maps to a FormattedPage containing a FormattedTable.
    """

    def __init__(self):
        self._inner = ExcelIngestor()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="excel-ingestor",
            version="1.0.0",
            description=(
                "Parses XLSX files into FormattedDocument IR using openpyxl. "
                "Each worksheet becomes a page with a table."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def ingest(self, content: bytes | str, filename: str = "") -> FormattedDocument:
        if isinstance(content, str):
            content = content.encode("utf-8")
        return self._inner.ingest(content, filename)

    def supported_formats(self) -> list[str]:
        return ["xlsx"]


# ---------------------------------------------------------------------------
# Renderer Adapters
# ---------------------------------------------------------------------------

class DOCXRendererAdapter(RendererTool):
    """Wraps DOCXRenderer as a registered RendererTool.

    Produces styled Word documents preserving fonts, sizes, colors,
    formatting flags, paragraph spacing, alignment, heading levels,
    lists, and table structure.
    """

    def __init__(self):
        self._inner = DOCXRenderer()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="docx-renderer",
            version="1.0.0",
            description=(
                "Renders FormattedDocument IR to DOCX bytes with full style "
                "preservation (fonts, sizes, colors, headings, tables)."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def render(self, doc: FormattedDocument) -> bytes:
        return self._inner.render(doc)

    def output_format(self) -> str:
        return "docx"


class HTMLRendererAdapter(RendererTool):
    """Wraps HTMLRenderer as a registered RendererTool.

    Produces semantic HTML5 with inline styles, suitable for CKEditor
    or any rich-text editor.
    """

    def __init__(self):
        self._inner = HTMLRenderer()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="html-renderer",
            version="1.0.0",
            description=(
                "Renders FormattedDocument IR to styled HTML5 with inline "
                "styles, tables, and base64 images."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def render(self, doc: FormattedDocument) -> str:
        return self._inner.render(doc)

    def output_format(self) -> str:
        return "html"


class MarkdownRendererAdapter(RendererTool):
    """Wraps MarkdownRenderer as a registered RendererTool.

    Produces CommonMark-compatible Markdown with extensions for
    superscript and subscript.
    """

    def __init__(self):
        self._inner = MarkdownRenderer()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="markdown-renderer",
            version="1.0.0",
            description=(
                "Renders FormattedDocument IR to CommonMark Markdown with "
                "superscript/subscript extensions."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def render(self, doc: FormattedDocument) -> str:
        return self._inner.render(doc)

    def output_format(self) -> str:
        return "markdown"


class TextRendererAdapter(RendererTool):
    """Wraps TextRenderer as a registered RendererTool.

    Produces plain text with paragraph structure preserved, tables as
    tab-separated columns, and simple markers for headings and lists.
    """

    def __init__(self):
        self._inner = TextRenderer()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="text-renderer",
            version="1.0.0",
            description=(
                "Renders FormattedDocument IR to plain text with paragraph "
                "breaks, tab-separated tables, and heading markers."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def render(self, doc: FormattedDocument) -> str:
        return self._inner.render(doc)

    def output_format(self) -> str:
        return "text"


class JSONRendererAdapter(RendererTool):
    """Wraps JSONRenderer as a registered RendererTool.

    Produces a full JSON serialisation of the IR including pages,
    paragraphs, spans, tables, and metadata.
    """

    def __init__(self):
        self._inner = JSONRenderer()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="json-renderer",
            version="1.0.0",
            description=(
                "Renders FormattedDocument IR to structured JSON with pages, "
                "paragraphs, spans, tables, and metadata inventories."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def render(self, doc: FormattedDocument) -> str:
        return self._inner.render(doc)

    def output_format(self) -> str:
        return "json"


class PDFRendererAdapter(RendererTool):
    """Wraps PDFRenderer as a registered RendererTool.

    Produces styled PDF using reportlab with paragraphs, inline formatting,
    tables, and embedded images.
    """

    def __init__(self):
        self._inner = PDFRenderer()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="pdf-renderer",
            version="1.0.0",
            description=(
                "Renders FormattedDocument IR to PDF bytes using reportlab "
                "with full formatting (fonts, tables, images)."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def render(self, doc: FormattedDocument) -> bytes:
        return self._inner.render(doc)

    def output_format(self) -> str:
        return "pdf"


class PPTXRendererAdapter(RendererTool):
    """Wraps PPTXRenderer as a registered RendererTool.

    Produces PowerPoint presentations with one slide per page, text-box
    shapes with per-run formatting, and native table shapes.
    """

    def __init__(self):
        self._inner = PPTXRenderer()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="pptx-renderer",
            version="1.0.0",
            description=(
                "Renders FormattedDocument IR to PPTX bytes using python-pptx "
                "with per-run formatting and native table shapes."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def render(self, doc: FormattedDocument) -> bytes:
        return self._inner.render(doc)

    def output_format(self) -> str:
        return "pptx"


# ---------------------------------------------------------------------------
# JSON Ingestor Adapter (auto-detecting)
# ---------------------------------------------------------------------------

class JSONIngestorAdapter(IngestorTool):
    """Wraps JsonIngestor as a registered IngestorTool.

    Auto-detects JSON schema (USDM, Protocol IR, FormattedDocument IR)
    from the content and routes to the appropriate parser.
    """

    def __init__(self):
        from src.formatter.ingest.json_ingestor import JsonIngestor, create_default_registry
        self._inner = JsonIngestor(create_default_registry())

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="json-ingestor",
            version="1.0.0",
            description=(
                "Auto-detects JSON schema (USDM, Protocol IR, FormattedDocument IR) "
                "and converts to FormattedDocument IR."
            ),
            side_effects=ToolSideEffect.NONE,
        )

    def ingest(self, content: bytes | str, filename: str = "") -> FormattedDocument:
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        return self._inner.ingest(content, filename)

    def supported_formats(self) -> list[str]:
        return ["json"]


# ---------------------------------------------------------------------------
# Convenience: all adapters for factory registration
# ---------------------------------------------------------------------------

ALL_INGESTOR_ADAPTERS = [
    PDFIngestorAdapter,
    DOCXIngestorAdapter,
    HTMLIngestorAdapter,
    MarkdownIngestorAdapter,
    TextIngestorAdapter,
    PPTXIngestorAdapter,
    ExcelIngestorAdapter,
    JSONIngestorAdapter,
]

ALL_RENDERER_ADAPTERS = [
    DOCXRendererAdapter,
    HTMLRendererAdapter,
    MarkdownRendererAdapter,
    TextRendererAdapter,
    JSONRendererAdapter,
    PDFRendererAdapter,
    PPTXRendererAdapter,
]
