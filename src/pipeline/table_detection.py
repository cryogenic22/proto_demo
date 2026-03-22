"""
Table Detection — identifies table regions in page images using vision LLM.

Supports two modes:
- SOA-only: Focused detection of Schedule of Activities tables (fast, cheap)
- All tables: Detects every table type (comprehensive, expensive)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import re

import fitz

from src.llm.client import LLMClient
from src.models.schema import (
    BoundingBox,
    PageImage,
    PipelineConfig,
    TableRegion,
    TableType,
)

logger = logging.getLogger(__name__)


# Deterministic SoA page detection patterns — catches pages without LLM cost
_SOA_TEXT_PATTERNS = [
    re.compile(r"schedule of (?:activities|assessments|events|study)", re.IGNORECASE),
    re.compile(r"schedule of study (?:activities|procedures|assessments)", re.IGNORECASE),
    re.compile(r"study\s+(?:activities|procedures)\s+(?:schedule|table)", re.IGNORECASE),
    re.compile(r"table\s+\w*\.?\d*\.?\s*(?:schedule of|study activities)", re.IGNORECASE),
]

# Patterns for table continuation pages (no title but table-like content)
_CONTINUATION_PATTERNS = [
    re.compile(r"(?:continued|cont['']?d)", re.IGNORECASE),
    re.compile(r"table\s+\w*\.?\d+\s*\(cont", re.IGNORECASE),
]


def _deterministic_soa_prescreen(pdf_bytes: bytes) -> dict[int, str]:
    """Scan PDF text for SoA pages without any LLM calls.

    Returns dict of {page_number: detection_type} where detection_type
    is 'title_match', 'continuation', or 'table_dense'.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    soa_pages: dict[int, str] = {}

    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        text = page.get_text("text")

        # Check for SoA title patterns
        for pattern in _SOA_TEXT_PATTERNS:
            if pattern.search(text):
                soa_pages[page_idx] = "title_match"
                break

        # Check for table continuation markers
        if page_idx not in soa_pages:
            for pattern in _CONTINUATION_PATTERNS:
                if pattern.search(text):
                    soa_pages[page_idx] = "continuation"
                    break

        # Check for table-dense pages using PyMuPDF table detection
        if page_idx not in soa_pages:
            try:
                tables = page.find_tables()
                if tables.tables:
                    for t in tables.tables:
                        extracted = t.extract()
                        if extracted and len(extracted) >= 5:
                            # Table with 5+ rows — likely an SoA
                            # Check if rows have X marks or procedure-like names
                            x_count = sum(
                                1 for row in extracted
                                for cell in row
                                if cell and str(cell).strip() in ("X", "x", "✓", "✔")
                            )
                            if x_count >= 3:
                                soa_pages[page_idx] = "table_dense"
                                break
            except Exception:
                pass

    # Expand: if page N is SoA, nearby pages with tables are likely continuations.
    # Range ±10 pages to catch long multi-page SoA tables (P-14 soa_1 spans
    # 21 pages, P-09 soa_2 spans 7 pages). Run iteratively — each newly found
    # page extends the search frontier.
    max_expansion_range = 10
    changed = True
    while changed:
        changed = False
        expansion = {}
        for page_idx in list(soa_pages.keys()):
            for offset in range(-max_expansion_range, max_expansion_range + 1):
                neighbor = page_idx + offset
                if neighbor in soa_pages or neighbor in expansion:
                    continue
                if neighbor < 0 or neighbor >= doc.page_count:
                    continue
                try:
                    page = doc[neighbor]
                    tables = page.find_tables()
                    if tables.tables and any(
                        len(t.extract()) >= 3 for t in tables.tables
                    ):
                        expansion[neighbor] = "neighbor_expansion"
                except Exception:
                    pass
        if expansion:
            soa_pages.update(expansion)
            changed = True  # Re-expand from newly found pages

    doc.close()
    return soa_pages

# Fast pre-screening prompt — just asks "is there an SOA table on this page?"
SOA_PRESCREEN_PROMPT = """Look at this page from a clinical trial protocol.

Does this page contain a Schedule of Activities (SoA) table, or a
Schedule of Assessments table? These are the large grid tables that show
clinical procedures (rows) mapped against study visits (columns), with
X marks or checkmarks in the cells.

Also check if this page contains a CONTINUATION of such a table from a
previous page (repeated column headers, data rows without a title, or
"continued" / "cont'd" markers).

Return a JSON object:
{
  "has_soa": true or false,
  "is_continuation": true or false,
  "title": "table title if visible" or null
}

Return ONLY the JSON object."""

# Detailed SOA extraction prompt — only runs on pages that passed pre-screen
SOA_DETAIL_PROMPT = """This page contains a Schedule of Activities (SoA) table
from a clinical trial protocol.

Return a JSON array with ONE object for this table:
[{
  "table_id": "soa",
  "title": "the table title/caption if visible, or null",
  "table_type": "SOA",
  "bbox": {"x0": <left>, "y0": <top>, "x1": <right>, "y1": <bottom>},
  "is_continuation": true if this is a continuation from a previous page,
  "continuation_markers": ["continued"] if applicable, or []
}]

The bbox should be percentage of page dimensions (0-100).
Return ONLY the JSON array."""

# Original comprehensive detection prompt
ALL_TABLES_PROMPT = """Analyze this page from a clinical trial protocol document.
Identify ALL tables on this page. For each table found, return a JSON array with objects containing:

- "table_id": a unique identifier (e.g., "t1", "t2")
- "title": the table title/caption if visible, or null
- "table_type": one of "SOA" (Schedule of Activities/Assessments), "DEMOGRAPHICS",
  "LAB_PARAMS", "DOSING", "INCLUSION_EXCLUSION", or "OTHER"
- "bbox": {"x0": <left>, "y0": <top>, "x1": <right>, "y1": <bottom>} as percentage
  of page dimensions (0-100)
- "is_continuation": true if this appears to be a continuation of a table from a
  previous page (e.g., has "continued" in title, or starts with data rows without
  a clear title)
- "continuation_markers": list of text markers suggesting continuation
  (e.g., ["continued"], ["cont'd"])

If there are NO tables on this page, return an empty array: []

Return ONLY the JSON array, no other text."""


class TableDetector:
    """Detects table regions in page images using vision LLM."""

    def __init__(self, config: PipelineConfig, llm_client: LLMClient | None = None):
        self.config = config
        self.llm = llm_client or LLMClient(config)

    async def detect(self, pages: list[PageImage], pdf_bytes: bytes = b"") -> list[TableRegion]:
        """Detect table regions across all pages."""
        if not pages:
            return []

        if self.config.soa_only:
            return await self._detect_soa_only(pages, pdf_bytes)
        else:
            return await self._detect_all_tables(pages)

    async def _detect_soa_only(self, pages: list[PageImage], pdf_bytes: bytes = b"") -> list[TableRegion]:
        """Three-phase SOA detection: deterministic pre-screen → LLM pre-screen → detailed extraction.

        Phase 0: Deterministic text/table scan (FREE — no LLM cost)
        Phase 1: LLM pre-screen on remaining uncertain pages
        Phase 2: Detailed extraction on confirmed SOA pages
        """
        concurrency = self.config.max_concurrent_llm_calls
        semaphore = asyncio.Semaphore(concurrency)

        # Phase 0: Deterministic pre-screen (FREE)
        deterministic_pages: dict[int, str] = {}
        if pdf_bytes:
            deterministic_pages = _deterministic_soa_prescreen(pdf_bytes)

            # Also use section parser to find SoA page ranges — catches
            # synopsis tables and appendix SoA tables that text patterns miss
            try:
                from src.pipeline.section_parser import SectionParser
                sp = SectionParser()
                sections = sp.parse(pdf_bytes)
                flat = sp._flatten(sections)
                for s in flat:
                    title_lower = s.title.lower()
                    if any(kw in title_lower for kw in [
                        "schedule of", "soa", "schedule of events",
                        "schedule of assessments", "schedule of activities",
                    ]):
                        end = s.end_page if s.end_page is not None else s.page
                        for p in range(s.page, end + 1):
                            if p not in deterministic_pages:
                                deterministic_pages[p] = "section_parser_soa"
                    # Also catch appendix tables (common in Roche format)
                    if "appendix" in title_lower and any(
                        kw in title_lower for kw in ["schedule", "event", "activit"]
                    ):
                        end = s.end_page if s.end_page is not None else s.page
                        for p in range(s.page, end + 1):
                            if p not in deterministic_pages:
                                deterministic_pages[p] = "appendix_soa"
            except Exception as e:
                logger.debug(f"Section parser SoA detection failed: {e}")

            if deterministic_pages:
                logger.info(
                    f"SOA detection Phase 0 (deterministic): {len(deterministic_pages)} "
                    f"candidate pages found (FREE — no LLM cost)"
                )

        # Phase 1: LLM pre-screen only on pages NOT already identified
        already_found = set(deterministic_pages.keys())
        pages_to_llm_screen = [p for p in pages if p.page_number not in already_found]
        logger.info(
            f"SOA detection Phase 1: LLM pre-screening {len(pages_to_llm_screen)} pages "
            f"({len(already_found)} already identified by deterministic scan)"
        )

        async def prescreen_one(page: PageImage) -> tuple[int, bool, bool, str | None]:
            """Returns (page_num, has_soa, is_continuation, title)."""
            async with semaphore:
                try:
                    raw = await self.llm.vision_json_query(
                        page.image_bytes,
                        SOA_PRESCREEN_PROMPT,
                        system="You are a clinical protocol analyst. Return valid JSON only.",
                        max_tokens=256,  # Small response = fast + cheap
                    )
                    if isinstance(raw, dict):
                        return (
                            page.page_number,
                            bool(raw.get("has_soa", False)),
                            bool(raw.get("is_continuation", False)),
                            raw.get("title"),
                        )
                    return (page.page_number, False, False, None)
                except Exception as e:
                    logger.warning(f"Pre-screen failed on page {page.page_number}: {e}")
                    return (page.page_number, False, False, None)

        results = await asyncio.gather(
            *(prescreen_one(p) for p in pages_to_llm_screen),
            return_exceptions=False,
        )

        # Merge: deterministic pages + LLM-detected pages
        soa_pages = []
        # Add deterministic detections first
        for page_num, det_type in deterministic_pages.items():
            is_cont = det_type in ("continuation", "neighbor_expansion")
            soa_pages.append((page_num, is_cont, f"deterministic:{det_type}"))

        # Add LLM detections (avoiding duplicates)
        for pn, has_soa, is_cont, title in results:
            if (has_soa or is_cont) and pn not in deterministic_pages:
                soa_pages.append((pn, is_cont, title))

        non_soa_count = len(pages) - len(soa_pages)
        logger.info(
            f"SOA pre-screen: {len(soa_pages)} SOA pages found, "
            f"{non_soa_count} pages skipped"
        )

        if not soa_pages:
            return []

        # Phase 2: Detailed extraction on SOA pages only
        logger.info(f"SOA detection Phase 2: Extracting from {len(soa_pages)} pages")
        page_map = {p.page_number: p for p in pages}
        all_regions: list[TableRegion] = []

        async def extract_one(page_num: int, is_cont: bool, title: str | None) -> list[TableRegion]:
            async with semaphore:
                page = page_map.get(page_num)
                if not page:
                    return []
                try:
                    raw = await self.llm.vision_json_query(
                        page.image_bytes,
                        SOA_DETAIL_PROMPT,
                        system="You are a clinical protocol analyst. Return valid JSON only.",
                    )
                    if isinstance(raw, list):
                        regions = []
                        for item in raw:
                            if isinstance(item, dict):
                                try:
                                    regions.append(self._parse_detection(item, page_num))
                                except Exception as e:
                                    logger.warning(f"Parse failed on SOA page {page_num}: {e}")
                        return regions
                    return []
                except Exception as e:
                    logger.error(f"SOA detail extraction failed on page {page_num}: {e}")
                    return []

        detail_results = await asyncio.gather(
            *(extract_one(pn, is_cont, title) for pn, is_cont, title in soa_pages),
            return_exceptions=False,
        )

        for page_regions in detail_results:
            all_regions.extend(page_regions)

        logger.info(f"SOA detection complete: {len(all_regions)} SOA table regions found")
        return all_regions

    async def _detect_all_tables(self, pages: list[PageImage]) -> list[TableRegion]:
        """Comprehensive detection of all table types (original behavior)."""
        concurrency = self.config.max_concurrent_llm_calls
        semaphore = asyncio.Semaphore(concurrency)
        logger.info(f"Detecting all tables on {len(pages)} pages (concurrency={concurrency})")

        async def detect_one(page: PageImage) -> list[TableRegion]:
            async with semaphore:
                try:
                    raw_detections = await self._detect_on_page(page)
                    regions = []
                    for raw in raw_detections:
                        if not isinstance(raw, dict):
                            continue
                        try:
                            regions.append(self._parse_detection(raw, page.page_number))
                        except Exception as parse_err:
                            logger.warning(f"Failed to parse detection on page {page.page_number}: {parse_err}")
                    return regions
                except Exception as e:
                    logger.error(f"Table detection failed on page {page.page_number}: {e}")
                    return []

        results = await asyncio.gather(
            *(detect_one(page) for page in pages),
            return_exceptions=False,
        )

        all_regions: list[TableRegion] = []
        for page_regions in results:
            all_regions.extend(page_regions)

        logger.info(f"Detected {len(all_regions)} table regions across {len(pages)} pages")
        return all_regions

    async def _detect_on_page(self, page: PageImage) -> list[dict[str, Any]]:
        result = await self.llm.vision_json_query(
            page.image_bytes,
            ALL_TABLES_PROMPT,
            system="You are a clinical document analysis expert. Return valid JSON only.",
        )
        if isinstance(result, list):
            return result
        return []

    def _parse_detection(self, raw: dict[str, Any], page_num: int) -> TableRegion:
        bbox_raw = raw.get("bbox", {})

        bbox = BoundingBox(
            page=page_num,
            x0=float(bbox_raw.get("x0", 0)),
            y0=float(bbox_raw.get("y0", 0)),
            x1=float(bbox_raw.get("x1", 100)),
            y1=float(bbox_raw.get("y1", 100)),
        )

        raw_type = raw.get("table_type", "SOA" if self.config.soa_only else "OTHER")
        try:
            table_type = TableType(raw_type)
        except ValueError:
            table_type = TableType.SOA if self.config.soa_only else TableType.OTHER

        raw_id = raw.get("table_id", "soa" if self.config.soa_only else "t1")
        table_id = f"p{page_num}_{raw_id}"

        return TableRegion(
            table_id=table_id,
            pages=[page_num],
            bounding_boxes=[bbox],
            table_type=table_type,
            title=raw.get("title"),
            continuation_markers=raw.get("continuation_markers", []),
        )
