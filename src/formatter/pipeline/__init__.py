"""
Pipeline module — registry-based ingestor/renderer orchestration.

Mirrors the formula system's architecture (formula/base.py, formula/registry.py,
formula/orchestrator.py) but applied to the full document conversion pipeline.

Usage:
    from src.formatter.pipeline import create_pipeline

    pipeline = create_pipeline()
    doc = pipeline.ingest(pdf_bytes, "pdf")
    html = pipeline.render(doc, "html")
    # or one-shot:
    html = pipeline.convert(pdf_bytes, "pdf", "html")
"""

from src.formatter.pipeline.base import IngestorTool, RendererTool
from src.formatter.pipeline.registry import PipelineToolRegistry
from src.formatter.pipeline.orchestrator import PipelineOrchestrator
from src.formatter.pipeline.factory import create_pipeline

__all__ = [
    "IngestorTool",
    "RendererTool",
    "PipelineToolRegistry",
    "PipelineOrchestrator",
    "create_pipeline",
]
