"""
DocumentDigitizer — Layer 1 of the two-layer pipeline architecture.

Performs full document digitization by composing existing components:
1. FormattingExtractor → FormattedDocument (pages, paragraphs, spans, tables)
2. SectionParser → section tree (headings, page ranges)
3. Table classifier → tag each table as SOA / DEMOGRAPHICS / OTHER / etc.
4. Metadata extractor → ProtocolMetadata (title, sponsor, phase, indication)

Output: DigitizedDocument — the contract between Layer 1 and Layer 2.

Layer 2 extractors consume the DigitizedDocument for targeted extraction
(SoA tables for budgets, eligibility criteria for screening, etc.).
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from src.formatter.extractor import (
    FormattedDocument,
    FormattedTable,
    FormattingExtractor,
)
from src.models.digitized import (
    DigitizedDocument,
    TableClassification,
    TableType,
)
from src.models.protocol import ProtocolMetadata, SectionNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SoA detection patterns
# ---------------------------------------------------------------------------

_SOA_TITLE_PATTERNS = re.compile(
    r"schedule\s+of\s+(activities|assessments|events|evaluations|procedures|study)"
    r"|study\s+procedures?\s+matrix"
    r"|assessment\s+schedule"
    r"|table\s+\d+\s*[\.:]\s*schedule",
    re.IGNORECASE,
)

_SOA_REJECT_PATTERNS = re.compile(
    r"adverse\s+event|demograph|abbreviat|reference\s+range"
    r"|pharmacokinetic\s+parameter|dose\s+modification"
    r"|statistical\s+method|signature\s+page",
    re.IGNORECASE,
)

_VISIT_HEADER_PATTERNS = re.compile(
    r"visit\s*\d|day\s*[-\d]|week\s*\d|baseline|screening|cycle\s*\d"
    r"|c\d+d\d+|treatment|follow.?up|randomization|eot|eos",
    re.IGNORECASE,
)

_MARKER_CHARS = {"X", "x", "Y", "y", "✓", "✔", "●", "○", "■", "□"}


class DocumentDigitizer:
    """Layer 1 digitizer — extracts everything from a protocol document.

    Usage:
        digitizer = DocumentDigitizer()
        result = digitizer.digitize(pdf_bytes, "protocol.pdf")
        print(result.summary())
        soa_tables = result.get_soa_tables()
    """

    def digitize(
        self, file_bytes: bytes, filename: str = "",
        deep: bool = False,
    ) -> DigitizedDocument:
        """Fully digitize a document into a DigitizedDocument.

        Args:
            file_bytes: Raw PDF bytes.
            filename: Original filename for metadata.
            deep: If True, run extra quality passes — formula Tier 4,
                  fidelity checking, span forensics, OCR cross-verification.

        Returns:
            DigitizedDocument with formatted IR, sections, table classifications.
        """
        mode_label = "DEEP" if deep else "standard"
        logger.info(
            "Layer 1 digitization starting (%s): %s (%d bytes)",
            mode_label, filename, len(file_bytes),
        )

        # 1. Full formatting extraction
        extractor = FormattingExtractor()
        formatted = extractor.extract(file_bytes, filename)
        logger.info(
            "Formatting extracted: %d pages, %d paragraphs, %d tables",
            len(formatted.pages),
            formatted.total_paragraphs,
            sum(len(p.tables) for p in formatted.pages),
        )

        # 2. Formula enrichment
        try:
            from src.formatter.formula.enricher import FormulaEnricher
            enricher = FormulaEnricher()
            formatted = enricher.enrich(formatted)
            formula_count = sum(
                1 for pg in formatted.pages for p in pg.paragraphs
                for ln in p.lines for s in ln.spans if s.formula
            )
            logger.info("Formula enrichment: %d formulas detected", formula_count)
        except Exception as e:
            logger.warning("Formula enrichment failed (non-fatal): %s", e)

        # 3. Deep mode: fidelity checking + span forensics
        fidelity_score = None
        if deep:
            fidelity_score = self._run_fidelity_check(formatted)

        # 4. Section parsing
        sections = self._parse_sections(file_bytes, filename)

        # 5. Metadata extraction
        metadata = self._extract_metadata(file_bytes, filename)

        # 6. Table classification
        classifications = self._classify_tables(formatted, sections)
        soa_count = sum(1 for tc in classifications if tc.table_type == TableType.SOA)
        logger.info(
            "Tables classified: %d total, %d SOA, %d OTHER",
            len(classifications),
            soa_count,
            len(classifications) - soa_count,
        )

        # 7. Source hash
        source_hash = hashlib.sha256(file_bytes).hexdigest()[:16]

        result = DigitizedDocument(
            formatted=formatted,
            sections=sections,
            table_classifications=classifications,
            metadata=metadata,
            source_hash=source_hash,
            source_filename=filename,
        )

        if fidelity_score is not None:
            logger.info(
                "Layer 1 DEEP digitization complete (fidelity=%.1f/100): %s",
                fidelity_score, result.summary(),
            )
        else:
            logger.info("Layer 1 digitization complete: %s", result.summary())
        return result

    # -- Deep mode: fidelity checking --

    def _run_fidelity_check(self, formatted: FormattedDocument) -> float:
        """Run fidelity checker and span forensics for deep mode.

        Returns a fidelity score 0-100.
        """
        try:
            from src.formatter.fidelity_checker import FidelityChecker
            checker = FidelityChecker()
            report = checker.check(formatted)
            score = report.get("overall_score", 0.0) if isinstance(report, dict) else 0.0
            issues = report.get("issues", []) if isinstance(report, dict) else []
            if issues:
                logger.info(
                    "Deep fidelity check: %.1f/100, %d issues found",
                    score, len(issues),
                )
                for issue in issues[:5]:
                    logger.info("  Fidelity issue: %s", issue)
            else:
                logger.info("Deep fidelity check: %.1f/100, no issues", score)
            return score
        except Exception as e:
            logger.warning("Fidelity check failed (non-fatal): %s", e)
            return 0.0

    # -- Section parsing --

    def _parse_sections(
        self, file_bytes: bytes, filename: str
    ) -> list[SectionNode]:
        """Parse section hierarchy using SectionParser, return as SectionNode list."""
        try:
            from src.pipeline.section_parser import SectionParser
            sp = SectionParser()
            sections = sp.parse(file_bytes, filename)
            return [self._section_to_node(s) for s in sections]
        except Exception as e:
            logger.warning("Section parsing failed: %s", e)
            return []

    def _section_to_node(self, section: Any) -> SectionNode:
        """Convert section_parser.Section to protocol.SectionNode."""
        return SectionNode(
            number=section.number,
            title=section.title,
            page=section.page,
            end_page=section.end_page,
            level=section.level,
            children=[self._section_to_node(c) for c in section.children],
        )

    # -- Metadata extraction --

    def _extract_metadata(
        self, file_bytes: bytes, filename: str
    ) -> ProtocolMetadata:
        """Extract protocol metadata from cover page."""
        try:
            from src.persistence.protocol_bridge import _extract_metadata
            return _extract_metadata(file_bytes, filename)
        except Exception as e:
            logger.warning("Metadata extraction failed: %s", e)
            return ProtocolMetadata()

    # -- Table classification --

    def _classify_tables(
        self,
        formatted: FormattedDocument,
        sections: list[SectionNode],
    ) -> list[TableClassification]:
        """Classify every table in the document without discarding any."""
        # Build section page ranges for SoA detection
        soa_pages = self._find_soa_section_pages(sections)

        classifications: list[TableClassification] = []
        for page in formatted.pages:
            for ti, table in enumerate(page.tables):
                tc = self._classify_single_table(
                    table, page.page_number, ti, soa_pages
                )
                classifications.append(tc)

        return classifications

    def _classify_single_table(
        self,
        table: FormattedTable,
        page_number: int,
        table_index: int,
        soa_pages: set[int],
    ) -> TableClassification:
        """Classify a single FormattedTable."""
        signals: dict[str, Any] = {}

        # Signal 1: Page is inside a SoA section
        in_soa_section = page_number in soa_pages
        signals["in_soa_section"] = in_soa_section

        # Signal 2: Table title matches SoA patterns
        # Look at the preceding paragraph for a title
        title = self._find_table_title(table, page_number)
        title_match = bool(_SOA_TITLE_PATTERNS.search(title)) if title else False
        title_reject = bool(_SOA_REJECT_PATTERNS.search(title)) if title else False
        signals["title"] = title
        signals["title_match"] = title_match
        signals["title_reject"] = title_reject

        # Signal 3: High ratio of single-character marker cells
        marker_count = 0
        total_cells = 0
        for row in table.rows:
            for cell in row:
                if cell.text.strip():
                    total_cells += 1
                    text = cell.text.strip()
                    if text in _MARKER_CHARS or (len(text) <= 3 and text[0] in _MARKER_CHARS):
                        marker_count += 1
        marker_ratio = marker_count / max(total_cells, 1)
        signals["marker_count"] = marker_count
        signals["marker_ratio"] = round(marker_ratio, 2)

        # Signal 4: Visit-like column headers
        header_row = table.rows[0] if table.rows else []
        visit_cols = sum(
            1 for cell in header_row
            if _VISIT_HEADER_PATTERNS.search(cell.text)
        )
        signals["visit_columns"] = visit_cols

        # Signal 5: Table size (SoA tables are typically large)
        signals["rows"] = table.num_rows
        signals["cols"] = table.num_cols

        # -- Classification decision --
        confidence = 0.0
        table_type = TableType.OTHER

        if title_reject:
            table_type = TableType.OTHER
            confidence = 0.8
        elif title_match:
            table_type = TableType.SOA
            confidence = 0.9
        elif in_soa_section and marker_count >= 3:
            table_type = TableType.SOA
            confidence = 0.85
        elif in_soa_section and table.num_rows >= 5 and table.num_cols >= 4:
            table_type = TableType.SOA
            confidence = 0.7
        elif marker_ratio > 0.3 and visit_cols >= 2:
            table_type = TableType.SOA
            confidence = 0.75
        elif marker_ratio > 0.2 and table.num_rows >= 8:
            table_type = TableType.SOA
            confidence = 0.6
        else:
            table_type = TableType.OTHER
            confidence = 0.5

        return TableClassification(
            page_number=page_number,
            table_index=table_index,
            table_type=table_type,
            confidence=confidence,
            title=title or "",
            num_rows=table.num_rows,
            num_cols=table.num_cols,
            signals=signals,
        )

    def _find_table_title(self, table: FormattedTable, page_number: int) -> str:
        """Heuristic: find the table title from preceding text on the same page.

        Returns empty string if no title found. Does not access the
        FormattedDocument directly — works from the table's y_position
        relative to page paragraphs (if we had access).
        """
        # The title is typically embedded in the table's first row or
        # in a preceding paragraph. For now, check the first row for
        # title-like content.
        if not table.rows:
            return ""

        # Check if first row looks like a title (single cell spanning all columns)
        first_row = table.rows[0]
        non_empty = [c for c in first_row if c.text.strip()]
        if len(non_empty) == 1 and len(first_row) > 1:
            text = non_empty[0].text.strip()
            if len(text) > 20:  # Title-length text in a spanning cell
                return text

        return ""

    def _find_soa_section_pages(self, sections: list[SectionNode]) -> set[int]:
        """Find page numbers that fall within SoA-titled sections."""
        soa_pages: set[int] = set()
        flat = self._flatten_sections(sections)
        soa_keywords = [
            "schedule of activities", "schedule of assessments",
            "schedule of evaluations", "schedule of procedures",
            "schedule of events", "study procedures matrix",
            "assessment schedule",
        ]
        for s in flat:
            title_lower = s.title.lower()
            if any(kw in title_lower for kw in soa_keywords):
                start = s.page
                end = s.end_page if s.end_page is not None else start + 10
                soa_pages.update(range(start, end + 1))
        return soa_pages

    @staticmethod
    def _flatten_sections(sections: list[SectionNode]) -> list[SectionNode]:
        """Recursively flatten section tree."""
        flat: list[SectionNode] = []
        for s in sections:
            flat.append(s)
            flat.extend(DocumentDigitizer._flatten_sections(s.children))
        return flat
