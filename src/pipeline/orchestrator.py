"""
Pipeline Orchestrator — coordinates all extraction stages.

Takes a PDF and produces structured PipelineOutput with all tables
extracted, validated, and confidence-scored.
"""

from __future__ import annotations

import logging
import re
import time

from src.llm.client import LLMClient
from src.models.schema import (
    CellRef,
    CostTier,
    ExtractedCell,
    ExtractedTable,
    ExtractionMetadata,
    PipelineConfig,
    PipelineOutput,
    TableSchema,
    TableType,
)
from src.pipeline.cell_extractor import CellExtractor
from src.pipeline.grid_anchor import GridAnchor
from src.pipeline.challenger_agent import ChallengerAgent
from src.pipeline.clinical_domain import (
    ClinicalDomainClassifier,
    TherapeuticDomain,
    get_extraction_hints,
    detect_pk_pd_rows,
)
from src.pipeline.footnote_extractor import FootnoteExtractor
from src.pipeline.ocr_grounding import OCRGroundingVerifier
from src.pipeline.footnote_resolver import FootnoteResolver
from src.pipeline.output_validator import OutputValidator
from src.pipeline.pdf_ingestion import PDFIngestor
from src.pipeline.procedure_normalizer import ProcedureNormalizer
from src.pipeline.protocol_synopsis import ProtocolSynopsisExtractor
from src.pipeline.reconciler import Reconciler
from src.pipeline.structural_analyzer import StructuralAnalyzer
from src.pipeline.section_parser import SectionParser
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
        self.footnote_extractor = FootnoteExtractor(config, self.llm)
        self.footnote_resolver = FootnoteResolver()
        self.procedure_normalizer = ProcedureNormalizer()
        self.temporal_extractor = TemporalExtractor()
        self.challenger = ChallengerAgent(config, self.llm)
        self.reconciler = Reconciler(config)
        self.grid_anchor = GridAnchor()
        self.ocr_verifier = OCRGroundingVerifier(config)
        self.validator = OutputValidator()
        self.synopsis_extractor = ProtocolSynopsisExtractor(config, self.llm)
        self.section_parser = SectionParser()
        self.protocol_synopsis = None
        self.domain_classifier = ClinicalDomainClassifier()
        self.detected_domain: TherapeuticDomain = TherapeuticDomain.GENERAL

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

        # Stage 1b: Protocol Synopsis Extraction
        _progress(15, "Extracting protocol synopsis...")
        try:
            self.protocol_synopsis = await self.synopsis_extractor.extract(pages)
            synopsis_context = self.protocol_synopsis.to_prompt_context()
            if synopsis_context:
                logger.info(f"Protocol synopsis extracted:\n{synopsis_context[:200]}")
                # Update domain classifier with synopsis info
                if self.protocol_synopsis.therapeutic_area:
                    self.detected_domain = self.domain_classifier.classify_from_text(
                        self.protocol_synopsis.therapeutic_area + " " +
                        self.protocol_synopsis.indication
                    )
        except Exception as e:
            logger.warning(f"Synopsis extraction failed (non-fatal): {e}")
            self.protocol_synopsis = None

        # Stage 2: Table Detection
        # Strategy A (preferred): Find SoA SECTION first, extract all tables
        # within that section's page range. This avoids per-page classification
        # errors (missing SoA pages or flagging non-SoA pages).
        # Strategy B (fallback): Per-page prescreen if section parser fails.
        mode = "SOA tables" if self.config.soa_only else "all tables"
        _progress(20, f"Detecting {mode} across {total_pages} pages...")
        logger.info(f"Stage 2: Table Detection ({mode})")

        regions = []
        try:
            if self.config.soa_only and pdf_bytes:
                regions = self._detect_soa_from_sections(pdf_bytes, pages)
                if regions:
                    logger.info(
                        f"Section-based SoA detection: {len(regions)} table regions "
                        f"from SoA section page ranges"
                    )

            if not regions:
                regions = await self.detector.detect(pages, pdf_bytes=pdf_bytes)
        except Exception as e:
            logger.error(f"Table detection failed: {e}")
            regions = []
            warnings.append(f"Table detection failed: {e}")

        # Stage 3: Table Stitching
        _progress(35, f"Stitching {len(regions)} table regions...")
        logger.info("Stage 3: Table Stitching")
        try:
            self.stitcher._pdf_bytes = pdf_bytes
            regions = self.stitcher.stitch(regions)
        except Exception as e:
            logger.error(f"Table stitching failed: {e}")
            warnings.append(f"Table stitching failed: {e}")

        # Stage 3b: SoA Table Validation — reject non-SoA tables
        if self.config.soa_only:
            # Layer 1: Section-parser page-range gate
            soa_page_range: set[int] = set()
            try:
                from src.pipeline.section_parser import SectionParser
                sp = SectionParser()
                parsed_sections = sp.parse(pdf_bytes, filename=document_name)
                flat_sections = sp._flatten(parsed_sections)
                for s in flat_sections:
                    title_lower = s.title.lower()
                    if any(kw in title_lower for kw in [
                        "schedule of activities", "schedule of assessments",
                        "schedule of evaluations", "schedule of events",
                        "schedule of procedures",
                    ]):
                        start = s.page
                        end = s.end_page or (s.page + 30)
                        soa_page_range.update(range(start, end + 1))
                if soa_page_range:
                    logger.info(
                        f"SoA page range: {min(soa_page_range)}-{max(soa_page_range)}"
                    )
            except Exception as e:
                logger.warning(f"Section parser page-range gate failed: {e}")

            validated_regions = []
            for region in regions:
                # Layer 1: Page-range gate
                if soa_page_range:
                    in_range = any(p in soa_page_range for p in region.pages)
                    if not in_range:
                        logger.info(
                            f"REJECTED (page range): '{region.title}' on pages "
                            f"{region.pages} — outside SoA range "
                            f"{min(soa_page_range)}-{max(soa_page_range)}"
                        )
                        warnings.append(
                            f"Rejected non-SoA table (outside SoA pages): "
                            f"{region.title or region.table_id}"
                        )
                        continue

                # Layer 2: Title + content validation
                if self._is_likely_soa(region, pdf_bytes):
                    validated_regions.append(region)
                else:
                    logger.info(
                        f"REJECTED (content): '{region.title}' on pages {region.pages}"
                    )
                    warnings.append(f"Rejected non-SoA table: {region.title}")

            before = len(regions)
            regions = validated_regions
            if before != len(regions):
                logger.info(
                    f"SoA filter: {before} → {len(regions)} tables "
                    f"({before - len(regions)} rejected)"
                )

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

        # Domain classification from table titles
        title_text = " ".join(r.title or "" for r in regions)
        self.detected_domain = self.domain_classifier.classify_from_text(title_text)
        logger.info(f"Protocol domain: {self.detected_domain.value}")

        # Process each table independently
        # Process each table with incremental checkpointing
        checkpoint = _CheckpointManager(document_name, doc_hash)

        for i, region in enumerate(regions):
            pct = 40 + int(55 * i / max(len(regions), 1))
            _progress(pct, f"Extracting table {i+1}/{len(regions)}: {region.title or region.table_id}...")
            try:
                table = await self._process_table(region, pages, pdf_bytes)

                # Layer 3: Post-extraction marker validation
                if self.config.soa_only:
                    marker_count = sum(
                        1 for c in table.cells
                        if c.data_type.value == "MARKER"
                    )
                    if marker_count == 0 and len(table.cells) > 5:
                        logger.info(
                            f"REJECTED (0 markers): '{table.title}' "
                            f"— {len(table.cells)} cells, 0 MARKER"
                        )
                        warnings.append(
                            f"Rejected: {table.title} (0 markers)"
                        )
                        continue

                    # Layer 4: High-flagged-rate rejection
                    # >80% flagged = almost certainly not SoA
                    if len(table.cells) > 10:
                        flagged_rate = (
                            len(table.flagged_cells) / len(table.cells)
                        )
                        if flagged_rate > 0.80:
                            logger.info(
                                f"REJECTED (flagged rate): '{table.title}' "
                                f"— {flagged_rate:.0%} of cells flagged"
                            )
                            warnings.append(
                                f"Rejected: {table.title} "
                                f"({flagged_rate:.0%} flagged)"
                            )
                            continue

                    # Layer 5: Column header validation
                    # SoA tables have visit/time column headers
                    visit_re = re.compile(
                        r"visit\s*\d|day\s*[-\d]|week\s*\d|month\s*\d"
                        r"|screening|baseline|follow.?up|end of"
                        r"|cycle\s*\d|dose\s*\d|period"
                        r"|vaccination|treatment\s*phase",
                        re.IGNORECASE,
                    )
                    col_headers = [
                        h.text for h in table.schema_info.column_headers
                    ]
                    has_visit_col = any(
                        visit_re.search(h) for h in col_headers
                    )
                    if not has_visit_col and len(col_headers) >= 3:
                        logger.info(
                            f"REJECTED (no visit columns): "
                            f"'{table.title}' — headers: "
                            f"{col_headers[:5]}"
                        )
                        warnings.append(
                            f"Rejected: {table.title} "
                            f"(no visit-like columns)"
                        )
                        continue

                tables.append(table)
                # Save checkpoint after each successful table
                checkpoint.save_table(table, i + 1, len(regions))
            except Exception as e:
                logger.error(f"Failed to process table {region.table_id}: {e}")
                warnings.append(f"Table {region.table_id} failed: {e}")

        elapsed = time.time() - start_time
        checkpoint.finalize()
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

    async def _process_table(self, region, pages, pdf_bytes: bytes = b"") -> ExtractedTable:
        """Process a single table through all extraction stages."""
        table_start = time.time()

        # Stage 4: Structural Analysis (Pass 1)
        logger.info(f"  Table {region.table_id}: Structural Analysis")
        schema = await self.structural_analyzer.analyze(region, pages)

        # Stage 4b: Grid Anchoring (deterministic row skeleton from PyMuPDF)
        # Disabled by default — constrains coverage on some formats.
        # Enable via config for protocols where structural stability matters more.
        grid_skeleton = None
        if pdf_bytes and self.config.enable_grid_anchor:
            try:
                logger.info(f"  Table {region.table_id}: Grid Anchoring")
                grid_skeleton = self.grid_anchor.extract_skeleton(
                    pdf_bytes, region.pages, table_id=region.table_id
                )
                # Update schema with anchored row count if it differs
                if grid_skeleton.num_rows > 0 and grid_skeleton.num_cols > 0:
                    logger.info(
                        f"  Grid anchor: {grid_skeleton.num_rows} rows "
                        f"(schema had {schema.num_rows})"
                    )
            except Exception as e:
                logger.warning(f"  Grid anchoring failed, falling back to VLM: {e}")
                grid_skeleton = None

        # Stage 4c: Detect text-layout tables (no grid lines)
        is_text_layout = False
        if pdf_bytes:
            is_text_layout = CellExtractor.detect_text_layout(
                pdf_bytes, region.pages
            )
            if is_text_layout:
                logger.info(f"  Table {region.table_id}: Detected text-layout format")

        # Stage 5: Cell Extraction (Pass 2 — run twice for consistency)
        logger.info(f"  Table {region.table_id}: Cell Extraction")
        pass1_cells = await self.cell_extractor.extract(
            region, schema, pages, pass_number=1,
            grid_skeleton=grid_skeleton,
            is_text_layout=is_text_layout,
        )

        # Stage 5b: Text-grid fallback — when VLM returns very few cells,
        # try deterministic text-position extraction as fallback.
        if len(pass1_cells) < 20 and pdf_bytes:
            try:
                from src.pipeline.text_grid_extractor import extract_cells_from_text_layout
                text_cells = extract_cells_from_text_layout(pdf_bytes, region.pages)
                if len(text_cells) > len(pass1_cells):
                    logger.info(
                        f"  Text-grid fallback produced {len(text_cells)} cells "
                        f"(VLM only found {len(pass1_cells)})"
                    )
                    # Use text cells as Pass 1, VLM as Pass 2 for reconciliation
                    pass1_cells = text_cells
            except Exception as e:
                logger.warning(f"  Text-grid fallback failed: {e}")

        pass2_cells = None
        if self.config.max_extraction_passes >= 2:
            pass2_cells = await self.cell_extractor.extract(
                region, schema, pages, pass_number=2,
                grid_skeleton=grid_skeleton,
                is_text_layout=is_text_layout,
            )

        # Stage 6: Footnote Extraction + Resolution
        logger.info(f"  Table {region.table_id}: Footnote Extraction")
        footnote_text = await self.footnote_extractor.extract(region, schema, pages)
        logger.info(f"  Table {region.table_id}: Footnote Resolution ({len(footnote_text)} definitions)")
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
        # P1c: Use hierarchical column addresses when available
        logger.info(f"  Table {region.table_id}: Temporal Extraction")
        if schema.column_addresses:
            visit_windows = self.temporal_extractor.parse_from_addresses(
                schema.column_addresses
            )
            logger.info(
                f"  Parsed {len(visit_windows)} visits from hierarchical "
                f"column addresses"
            )
        else:
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

        # Stage 9b: OCR Grounding (cross-modal verification)
        if self.ocr_verifier.available:
            logger.info(f"  Table {region.table_id}: OCR Grounding")
            verdicts = self.ocr_verifier.verify_cells(resolved_cells, region, pages)
            grounding_challenges = self.ocr_verifier.verdicts_to_challenges(verdicts)
            challenges.extend(grounding_challenges)
            if grounding_challenges:
                logger.info(f"  OCR grounding flagged {len(grounding_challenges)} potential hallucinations")

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

        # Stage 9c: Grid Anchor Post-Validation (always runs when PDF available)
        grid_post_warnings: list[str] = []
        if pdf_bytes and reconciliation.cells:
            try:
                grid_skeleton_post = self.grid_anchor.extract_skeleton(
                    pdf_bytes, region.pages, table_id=region.table_id
                )
                if grid_skeleton_post and grid_skeleton_post.rows:
                    # Compare extracted row headers against grid skeleton
                    extracted_procedures = {
                        c.row_header.strip().lower()
                        for c in reconciliation.cells
                        if c.row_header
                    }
                    anchored_procedures = {
                        r.procedure_name.strip().lower()
                        for r in grid_skeleton_post.rows
                    }

                    # Flag procedures in extraction that aren't in the grid
                    phantom_procedures = extracted_procedures - anchored_procedures
                    if (phantom_procedures
                            and len(phantom_procedures) > len(anchored_procedures) * 0.3):
                        msg = (
                            f"Grid validation: {len(phantom_procedures)} extracted "
                            f"procedures not found in PDF text layer — possible "
                            f"phantoms: {list(phantom_procedures)[:5]}"
                        )
                        grid_post_warnings.append(msg)
                        logger.warning(f"  {msg}")

                    # Flag procedures in grid that aren't in extraction (coverage gap)
                    missing_procedures = anchored_procedures - extracted_procedures
                    if missing_procedures:
                        msg = (
                            f"Grid validation: {len(missing_procedures)} procedures "
                            f"in PDF but not extracted: "
                            f"{list(missing_procedures)[:5]}"
                        )
                        grid_post_warnings.append(msg)
                        logger.warning(f"  {msg}")
            except Exception as e:
                logger.warning(f"Grid anchor post-validation failed: {e}")

        # Stage 10b: Propagate marks from spanning parent headers
        reconciliation.cells = self._propagate_spanning_header_marks(
            reconciliation.cells, schema
        )

        # Compute overall confidence
        if reconciliation.cells:
            overall_confidence = sum(
                c.confidence for c in reconciliation.cells
            ) / len(reconciliation.cells)
        else:
            overall_confidence = 0.0

        elapsed = time.time() - table_start

        table = ExtractedTable(
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

        # Stage 11: Output Validation — hard gate
        logger.info(f"  Table {region.table_id}: Output Validation")
        validation = self.validator.validate_table(table)
        if validation.warnings:
            for w in validation.warnings:
                logger.warning(f"  Validation: {w}")
        if validation.errors:
            for e in validation.errors:
                logger.error(f"  Validation ERROR: {e}")

        # Clean the table (removes NONE/NULL values, impossible coords)
        table = self.validator.clean_table(table)

        # Recompute confidence after cleaning
        if table.cells:
            table = table.model_copy(update={
                "overall_confidence": sum(c.confidence for c in table.cells) / len(table.cells)
            })

        return table

    @staticmethod
    def _propagate_spanning_header_marks(
        cells: list[ExtractedCell],
        schema: TableSchema,
    ) -> list[ExtractedCell]:
        """Propagate marks from parent spanning headers to child columns.

        When a table has hierarchical headers like "All Participants" spanning
        columns 1-5, and the VLM puts X only in the parent column, this
        propagates the X to all child columns for that row.

        Only propagates single-character marks (X, checkmarks) — not text content.
        """
        from src.models.schema import ColumnAddress

        if not schema.column_headers or not cells:
            return cells

        # Find parent headers that span multiple columns
        # A parent header has span > 1 (covers multiple leaf columns)
        spanning_parents: list[tuple[int, int, int]] = []  # (col_index, start, end)
        for h in schema.column_headers:
            span = getattr(h, 'span', 1) or 1
            if span > 1:
                spanning_parents.append((h.col_index, h.col_index, h.col_index + span - 1))

        if not spanning_parents:
            return cells

        logger.info(
            f"  Spanning header propagation: {len(spanning_parents)} parent headers found"
        )

        # Build cell lookup: (row, col) → cell
        cell_map: dict[tuple[int, int], ExtractedCell] = {}
        for c in cells:
            cell_map[(c.row, c.col)] = c

        # Identify mark values that should propagate
        mark_chars = {"X", "x", "✓", "✔", "●", "Y", "y"}

        new_cells = list(cells)
        added = 0

        for parent_col, start, end in spanning_parents:
            child_cols = [c for c in range(start, end + 1) if c != parent_col]
            if not child_cols:
                continue

            # Get all rows that have a mark in the parent column
            rows_with_marks = {}
            for (r, c), cell in cell_map.items():
                if c == parent_col and cell.raw_value.strip() in mark_chars:
                    rows_with_marks[r] = cell

            for row, parent_cell in rows_with_marks.items():
                # Check if child columns are empty for this row
                children_empty = all(
                    (row, cc) not in cell_map
                    or cell_map[(row, cc)].raw_value.strip() in ("", "-", "--", "—")
                    for cc in child_cols
                )

                if children_empty:
                    # Propagate the mark to all child columns
                    for cc in child_cols:
                        if (row, cc) not in cell_map:
                            propagated = parent_cell.model_copy(update={
                                "col": cc,
                                "confidence": parent_cell.confidence * 0.9,
                                "col_header": "",  # will be set by downstream
                            })
                            new_cells.append(propagated)
                            cell_map[(row, cc)] = propagated
                            added += 1

        if added:
            logger.info(f"  Propagated {added} marks from spanning parent headers")

        return new_cells

    def _detect_soa_from_sections(
        self, pdf_bytes: bytes, pages: list
    ) -> list:
        """Detect SoA tables by finding the SoA SECTION first.

        Instead of classifying each page independently, find the section titled
        'Schedule of Activities' (or similar) and extract ALL tables within that
        section's page range. This is more reliable than per-page classification.
        """
        from src.models.schema import TableRegion, TableType, BoundingBox

        try:
            sections = self.section_parser.parse(pdf_bytes)
            flat = self.section_parser._flatten(sections)

            soa_keywords = [
                "schedule of activit", "schedule of assess", "schedule of event",
                "schedule of evaluat", "schedule of procedure",
                "time and events", "study procedures schedule",
                "study procedures matrix", "assessment schedule",
            ]

            soa_page_ranges: list[tuple[int, int, str]] = []
            for s in flat:
                title_lower = s.title.lower()
                if any(kw in title_lower for kw in soa_keywords):
                    start = s.page
                    end = s.end_page if s.end_page is not None else start
                    soa_page_ranges.append((start, end, s.title))

            if not soa_page_ranges:
                return []

            # Merge overlapping ranges
            soa_page_ranges.sort()
            merged_ranges: list[tuple[int, int, str]] = []
            for start, end, title in soa_page_ranges:
                if merged_ranges and start <= merged_ranges[-1][1] + 1:
                    prev_start, prev_end, prev_title = merged_ranges[-1]
                    merged_ranges[-1] = (prev_start, max(prev_end, end), prev_title)
                else:
                    merged_ranges.append((start, end, title))

            # Create one TableRegion per merged SoA range
            regions = []
            for start, end, title in merged_ranges:
                region_pages = list(range(start, end + 1))
                regions.append(TableRegion(
                    table_id=f"soa_s{start}",
                    pages=region_pages,
                    bounding_boxes=[
                        BoundingBox(x0=0, y0=0, x1=2550, y1=3300, page=p)
                        for p in region_pages
                    ],
                    table_type=TableType.SOA,
                    title=title,
                    continuation_markers=[],
                ))

            logger.info(
                f"Section-based SoA: found {len(merged_ranges)} SoA regions "
                f"covering pages {[f'{s}-{e}' for s, e, _ in merged_ranges]}"
            )
            return regions

        except Exception as e:
            logger.warning(f"Section-based SoA detection failed: {e}")
            return []

    def _is_likely_soa(self, region, pdf_bytes: bytes) -> bool:
        """Validate that a detected region is actually an SoA table.

        SoA tables have:
        - Multiple columns (visits) -- at least 3 (continuation pages
          may have fewer visit columns)
        - Procedure-like row headers in the first column
        - X marks or checkmarks in the data cells
        - Title containing "Schedule", "SoA", or "Activities"

        Non-SoA tables (synopsis, amendments, endpoints) have:
        - 2-3 columns (label + value)
        - No X marks
        - Titles like "Synopsis", "Amendment", "Objectives"
        """
        # Title-based rejection (expanded keyword list)
        if region.title:
            title_lower = region.title.lower()
            reject_keywords = [
                "synopsis", "amendment", "objective", "endpoint",
                "abbreviation", "definition", "reference", "figure",
                "dosing schedule", "grading scale", "stopping rule",
                # Added from rough_notes analysis:
                "intercurrent event", "estimand", "statistical method",
                "statistical analysis", "sensitivity analys",
                "adverse events of special interest",
                "populations for analys", "sample size",
                "power of demonstrating", "conditions and sample",
                "document history", "blood sampling volume",
                "grading of", "long-term efficacy",
                "immunogenicity endpoint", "summary of major changes",
                "protocol amendment", "schema",
            ]
            if any(kw in title_lower for kw in reject_keywords):
                return False

            # Title-based acceptance — if the title explicitly says
            # "Schedule", "SoA", or "Activities", accept regardless of
            # other checks (catches image-rendered / sparse-text pages)
            accept_keywords = [
                "schedule of activities", "schedule of assessments",
                "schedule of evaluations", "schedule of procedures",
                "schedule of events", "supplemental soe",
                "supplemental schedule",
                "soa", "s.o.a.", "soe",
                "schedule", "activities",
                # Extended patterns from testing team feedback:
                "time and events", "time & events",
                "study procedures schedule", "study procedures matrix",
                "study procedures table", "study procedures overview",
                "assessment schedule", "assessment matrix",
                "assessment overview", "assessment plan",
                "visit schedule", "encounter schedule",
                "protocol flowchart", "study flowchart",
                "clinical trial flowchart",
                "table of activities", "table of assessments",
                "table of procedures", "table of study procedures",
                "treatment schedule", "dosing schedule",
                "evaluation schedule",
            ]
            if any(kw in title_lower for kw in accept_keywords):
                return True

        # Content-based validation using PyMuPDF text layer
        if pdf_bytes:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            x_count = 0
            check_count = 0
            total_cells_text = 0
            single_char_cells = 0
            page_has_soa_title = False
            for pg in region.pages:
                if pg < doc.page_count:
                    text = doc[pg].get_text("text")
                    x_count += len(re.findall(r'\bX\b', text))
                    check_count += text.count('\u2713') + text.count('\u2714')

                    # Count single-character cell values (X, ✓, ✔, etc.)
                    # — SoA tables are dominated by these
                    for line in text.split('\n'):
                        stripped = line.strip()
                        if stripped:
                            total_cells_text += 1
                            if len(stripped) == 1:
                                single_char_cells += 1

                    # Fallback: check page text for SoA-like title
                    title_re = re.compile(
                        r"schedule\s+of\s+(?:activities|assessments|"
                        r"evaluations|procedures|events)"
                        r"|time\s+and\s+events?\s+(?:table|schedule)"
                        r"|study\s+procedures?\s+(?:schedule|table|matrix)"
                        r"|assessment\s+(?:schedule|matrix|overview)"
                        r"|(?:visit|encounter)\s+schedule"
                        r"|table\s+of\s+(?:study\s+)?(?:activities|assessments|procedures)"
                        r"|(?:treatment|dosing|evaluation)\s+schedule"
                        r"|(?:^|\s)soa(?:\s|$)"
                        r"|(?:^|\s)s\.o\.a\.(?:\s|$)",
                        re.IGNORECASE,
                    )
                    if title_re.search(text):
                        page_has_soa_title = True
            doc.close()

            # Fallback: page text contains SoA-related title — accept it
            if page_has_soa_title:
                return True

            # SoA tables have many X marks or checkmarks
            if (x_count + check_count) >= 5:
                return True

            # Fallback: if >50% of cell-like text entries are single-char
            # values (X, ✓), it's very likely an SoA table
            if total_cells_text >= 10:
                single_char_rate = single_char_cells / total_cells_text
                if single_char_rate > 0.50:
                    logger.info(
                        f"Accepting '{region.title or region.table_id}' — "
                        f"{single_char_rate:.0%} single-char cells (likely SoA)"
                    )
                    return True

            # Only reject if zero X marks AND very few cells AND small table
            if (x_count + check_count) == 0 and total_cells_text < 20 and len(region.pages) <= 1:
                return False

        # Default: ACCEPT uncertain tables (include-then-reject strategy)
        # Better to show a non-SoA table than miss a real SoA page.
        # The UI allows users to reject irrelevant tables during review.
        logger.info(
            f"Including ambiguous table '{region.title or region.table_id}' "
            f"— cannot confirm as SoA, included for review"
        )
        return True

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


class _CheckpointManager:
    """Saves extracted tables incrementally so data survives pipeline crashes.

    After each successful table extraction, saves a checkpoint JSON file.
    If the pipeline crashes at table 7/8, the first 6 tables are recoverable.
    """

    def __init__(self, document_name: str, doc_hash: str):
        import os
        from pathlib import Path

        self._dir = Path(os.environ.get("CHECKPOINT_DIR", ".checkpoints"))
        self._dir.mkdir(parents=True, exist_ok=True)
        self._doc_name = document_name
        self._doc_hash = doc_hash[:12]
        self._path = self._dir / f"checkpoint_{self._doc_hash}.json"
        self._tables: list[dict] = []

    def save_table(self, table, current: int, total: int):
        """Save checkpoint after each successfully extracted table."""
        import json
        try:
            self._tables.append(json.loads(table.model_dump_json()))
            checkpoint = {
                "document": self._doc_name,
                "hash": self._doc_hash,
                "tables_completed": current,
                "tables_total": total,
                "tables": self._tables,
                "status": "in_progress" if current < total else "complete",
            }
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(checkpoint, f)
            logger.debug(f"Checkpoint saved: {current}/{total} tables")
        except Exception as e:
            logger.warning(f"Checkpoint save failed: {e}")

    def finalize(self):
        """Mark checkpoint as complete. Keep for recovery."""
        import json
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["status"] = "complete"
                with open(self._path, "w", encoding="utf-8") as f:
                    json.dump(data, f)
        except Exception:
            pass

    @staticmethod
    def load_checkpoint(doc_hash: str) -> dict | None:
        """Load a saved checkpoint for recovery."""
        import json
        from pathlib import Path
        import os

        checkpoint_dir = Path(os.environ.get("CHECKPOINT_DIR", ".checkpoints"))
        path = checkpoint_dir / f"checkpoint_{doc_hash[:12]}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
