"""
Pipeline Orchestrator — coordinates all extraction stages.

Takes a PDF and produces structured PipelineOutput with all tables
extracted, validated, and confidence-scored.
"""

from __future__ import annotations

import logging
import time

from src.llm.client import LLMClient
from src.models.schema import (
    CellRef,
    CostTier,
    ExtractedTable,
    ExtractionMetadata,
    PipelineConfig,
    PipelineOutput,
    TableType,
)
from src.pipeline.cell_extractor import CellExtractor
from src.pipeline.challenger_agent import ChallengerAgent
from src.pipeline.footnote_resolver import FootnoteResolver
from src.pipeline.pdf_ingestion import PDFIngestor
from src.pipeline.procedure_normalizer import ProcedureNormalizer
from src.pipeline.reconciler import Reconciler
from src.pipeline.structural_analyzer import StructuralAnalyzer
from src.pipeline.table_detection import TableDetector
from src.pipeline.table_stitcher import TableStitcher
from src.pipeline.temporal_extractor import TemporalExtractor

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Main pipeline coordinator."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.llm = LLMClient(config)

        # Initialize all sub-components
        self.ingestor = PDFIngestor(config)
        self.detector = TableDetector(config, self.llm)
        self.stitcher = TableStitcher()
        self.structural_analyzer = StructuralAnalyzer(config, self.llm)
        self.cell_extractor = CellExtractor(config, self.llm)
        self.footnote_resolver = FootnoteResolver()
        self.procedure_normalizer = ProcedureNormalizer()
        self.temporal_extractor = TemporalExtractor()
        self.challenger = ChallengerAgent(config, self.llm)
        self.reconciler = Reconciler(config)

    async def run(
        self,
        pdf_bytes: bytes,
        document_name: str = "document.pdf",
        on_progress: callable = None,
    ) -> PipelineOutput:
        """
        Run the full extraction pipeline on a PDF document.

        Args:
            pdf_bytes: Raw PDF file content.
            document_name: Name of the document for output metadata.
            on_progress: Optional callback(progress: int, message: str).

        Returns:
            PipelineOutput with all extracted tables.
        """
        start_time = time.time()
        doc_hash = PipelineOutput.compute_hash(pdf_bytes)
        warnings: list[str] = []
        tables: list[ExtractedTable] = []

        def _progress(pct: int, msg: str):
            if on_progress:
                on_progress(pct, msg)

        # Stage 1: PDF Ingestion
        logger.info("Stage 1: PDF Ingestion")
        _progress(10, "Ingesting PDF pages...")
        try:
            pages = self.ingestor.ingest_from_bytes(pdf_bytes)
        except Exception as e:
            logger.error(f"PDF ingestion failed: {e}")
            return PipelineOutput(
                document_name=document_name,
                document_hash=doc_hash,
                total_pages=0,
                warnings=[f"PDF ingestion failed: {e}"],
                processing_time_seconds=time.time() - start_time,
            )

        total_pages = len(pages)
        logger.info(f"Ingested {total_pages} pages")

        # Stage 2: Table Detection
        _progress(20, f"Detecting tables across {total_pages} pages...")
        logger.info("Stage 2: Table Detection")
        try:
            regions = await self.detector.detect(pages)
        except Exception as e:
            logger.error(f"Table detection failed: {e}")
            regions = []
            warnings.append(f"Table detection failed: {e}")

        # Stage 3: Table Stitching
        _progress(35, f"Stitching {len(regions)} table regions...")
        logger.info("Stage 3: Table Stitching")
        try:
            regions = self.stitcher.stitch(regions)
        except Exception as e:
            logger.error(f"Table stitching failed: {e}")
            warnings.append(f"Table stitching failed: {e}")

        if not regions:
            warnings.append("No tables detected in document")
            return PipelineOutput(
                document_name=document_name,
                document_hash=doc_hash,
                total_pages=total_pages,
                tables=[],
                warnings=warnings,
                processing_time_seconds=time.time() - start_time,
            )

        logger.info(f"Found {len(regions)} logical tables")

        # Process each table independently
        for i, region in enumerate(regions):
            pct = 40 + int(55 * i / max(len(regions), 1))
            _progress(pct, f"Extracting table {i+1}/{len(regions)}: {region.title or region.table_id}...")
            try:
                table = await self._process_table(region, pages)
                tables.append(table)
            except Exception as e:
                logger.error(f"Failed to process table {region.table_id}: {e}")
                warnings.append(f"Table {region.table_id} failed: {e}")

        elapsed = time.time() - start_time
        logger.info(
            f"Pipeline complete: {len(tables)} tables extracted "
            f"in {elapsed:.1f}s"
        )

        return PipelineOutput(
            document_name=document_name,
            document_hash=doc_hash,
            total_pages=total_pages,
            tables=tables,
            warnings=warnings,
            processing_time_seconds=elapsed,
        )

    async def _process_table(self, region, pages) -> ExtractedTable:
        """Process a single table through all extraction stages."""
        table_start = time.time()

        # Stage 4: Structural Analysis (Pass 1)
        logger.info(f"  Table {region.table_id}: Structural Analysis")
        schema = await self.structural_analyzer.analyze(region, pages)

        # Stage 5: Cell Extraction (Pass 2 — run twice for consistency)
        logger.info(f"  Table {region.table_id}: Cell Extraction")
        pass1_cells = await self.cell_extractor.extract(
            region, schema, pages, pass_number=1
        )

        pass2_cells = None
        if self.config.max_extraction_passes >= 2:
            pass2_cells = await self.cell_extractor.extract(
                region, schema, pages, pass_number=2
            )

        # Stage 6: Footnote Resolution
        logger.info(f"  Table {region.table_id}: Footnote Resolution")
        # Extract footnote text from the cells that look like footnote definitions
        footnote_text = self._extract_footnote_definitions(pass1_cells, schema)
        resolved_cells, footnotes = self.footnote_resolver.resolve(
            pass1_cells, footnote_text
        )

        # Stage 7: Procedure Normalization
        logger.info(f"  Table {region.table_id}: Procedure Normalization")
        procedure_names = list({
            c.row_header for c in resolved_cells
            if c.row_header and c.col == 0
        } | {
            c.raw_value for c in resolved_cells
            if c.col == 0 and c.raw_value
        })
        procedures = self.procedure_normalizer.normalize_batch(procedure_names)

        # Stage 8: Temporal Extraction
        logger.info(f"  Table {region.table_id}: Temporal Extraction")
        col_headers = [h.text for h in schema.column_headers]
        visit_windows = self.temporal_extractor.parse_batch(col_headers)

        # Stage 9: Challenger Agent (adversarial validation)
        challenges = []
        if self.config.enable_challenger:
            logger.info(f"  Table {region.table_id}: Challenger Agent")
            challenges = await self.challenger.challenge(
                region, schema, resolved_cells, pages
            )
            logger.info(f"  Challenger found {len(challenges)} issues")

        # Stage 10: Reconciliation
        logger.info(f"  Table {region.table_id}: Reconciliation")
        # Build cost map from procedure normalizations
        cost_map = self._build_cost_map(resolved_cells, procedures)

        reconciliation = self.reconciler.reconcile(
            resolved_cells,
            pass2_cells,
            challenges=challenges,
            cost_map=cost_map,
        )

        # Compute overall confidence
        if reconciliation.cells:
            overall_confidence = sum(
                c.confidence for c in reconciliation.cells
            ) / len(reconciliation.cells)
        else:
            overall_confidence = 0.0

        elapsed = time.time() - table_start

        return ExtractedTable(
            table_id=region.table_id,
            table_type=region.table_type,
            title=region.title or "",
            source_pages=region.pages,
            schema_info=schema,
            cells=reconciliation.cells,
            footnotes=footnotes,
            procedures=procedures,
            visit_windows=visit_windows,
            overall_confidence=overall_confidence,
            flagged_cells=reconciliation.flagged,
            review_items=reconciliation.review_items,
            extraction_metadata=ExtractionMetadata(
                passes_run=self.config.max_extraction_passes,
                challenger_issues_found=len(challenges),
                reconciliation_conflicts=reconciliation.conflicts,
                processing_time_seconds=elapsed,
                model_used=self.config.vision_model,
            ),
        )

    @staticmethod
    def _extract_footnote_definitions(
        cells: list, schema
    ) -> dict[str, str]:
        """
        Extract footnote definitions from the table.
        This is a simplified version — in production, footnotes would
        be extracted from the table image directly by a dedicated pass.
        """
        footnote_text: dict[str, str] = {}
        # For now, return empty — footnotes will be extracted by the
        # structural analyzer in a future enhancement
        return footnote_text

    @staticmethod
    def _build_cost_map(cells, procedures) -> dict:
        """Build a cell → cost tier mapping from procedure normalizations."""
        from src.models.schema import CellRef

        proc_cost: dict[str, CostTier] = {}
        for p in procedures:
            proc_cost[p.raw_name.lower()] = p.estimated_cost_tier
            proc_cost[p.canonical_name.lower()] = p.estimated_cost_tier

        cost_map: dict[CellRef, CostTier] = {}
        for cell in cells:
            if cell.row_header:
                tier = proc_cost.get(cell.row_header.lower(), CostTier.LOW)
                cost_map[CellRef(row=cell.row, col=cell.col)] = tier

        return cost_map
