"""Document Formatter — format-preserving document conversion.

Supports: PDF, DOCX, HTML, Markdown, plain text, PPTX, XLSX, JSON
"""
from src.formatter.extractor import FormattingExtractor, FormattedDocument
from src.formatter.docx_renderer import DOCXRenderer
from src.formatter.ingest.html_ingestor import HTMLIngestor
from src.formatter.ingest.markdown_ingestor import MarkdownIngestor
from src.formatter.ingest.text_ingestor import TextIngestor
from src.formatter.render.html_renderer import HTMLRenderer
from src.formatter.render.markdown_renderer import MarkdownRenderer
from src.formatter.render.text_renderer import TextRenderer
from src.formatter.render.json_renderer import JSONRenderer
from src.formatter.render.pdf_renderer import PDFRenderer
from src.formatter.render.pptx_renderer import PPTXRenderer
from src.formatter.ingest.pptx_ingestor import PPTXIngestor
from src.formatter.ingest.excel_ingestor import ExcelIngestor
from src.formatter.ingest.docx_ingestor import DOCXIngestor
from src.formatter.ingest.json_ingestor import JsonIngestor, create_default_registry


class DocHandler:
    """Universal document handler — ingest any format, render to any format.

    Usage:
        handler = DocHandler()
        doc = handler.ingest(content, format="pdf")  # or html, markdown, text, docx
        html = handler.render(doc, format="html")
        docx = handler.render(doc, format="docx")
        md = handler.render(doc, format="markdown")
    """

    def __init__(self):
        self._ingestors = {
            "pdf": FormattingExtractor(),
            "docx": DOCXIngestor(),
            "html": HTMLIngestor(),
            "markdown": MarkdownIngestor(),
            "text": TextIngestor(),
            "pptx": PPTXIngestor(),
            "xlsx": ExcelIngestor(),
            "json": JsonIngestor(create_default_registry()),
        }
        self._renderers = {
            "docx": DOCXRenderer(),
            "html": HTMLRenderer(),
            "markdown": MarkdownRenderer(),
            "text": TextRenderer(),
            "json": JSONRenderer(),
            "pdf": PDFRenderer(),
            "pptx": PPTXRenderer(),
        }

    def ingest(self, content, format: str, filename: str = "") -> FormattedDocument:
        """Ingest content in the given format and return a FormattedDocument IR.

        Args:
            content: The input content (bytes for PDF, str for others).
            format: One of "pdf", "html", "markdown", "text".
            filename: Optional source filename for metadata.

        Returns:
            A FormattedDocument intermediate representation.

        Raises:
            ValueError: If the format is not supported.
        """
        ingestor = self._ingestors.get(format)
        if not ingestor:
            raise ValueError(f"Unsupported input format: {format}")
        if format == "pdf":
            return ingestor.extract(content, filename)
        return ingestor.ingest(content, filename)

    def render(self, doc: FormattedDocument, format: str):
        """Render a FormattedDocument to the given output format.

        Args:
            doc: A FormattedDocument IR instance.
            format: One of "docx", "html", "markdown", "text", "json".

        Returns:
            str for text-based formats, bytes for binary formats (DOCX).

        Raises:
            ValueError: If the format is not supported.
        """
        renderer = self._renderers.get(format)
        if not renderer:
            raise ValueError(f"Unsupported output format: {format}")
        return renderer.render(doc)

    def convert(self, content, input_format: str, output_format: str, filename: str = ""):
        """Convenience method: ingest + render in one call.

        Args:
            content: The input content.
            input_format: Source format (e.g. "html", "markdown").
            output_format: Target format (e.g. "docx", "text").
            filename: Optional source filename.

        Returns:
            The rendered output (str or bytes depending on output format).
        """
        doc = self.ingest(content, input_format, filename)
        return self.render(doc, output_format)
