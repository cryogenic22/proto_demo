"""
Table Detection — identifies table regions in page images using vision LLM.

Supports two modes:
- SOA-only: Focused detection of Schedule of Activities tables (fast, cheap)
- Full: Detects all table types (comprehensive, slower)

The deterministic prescreen (_deterministic_soa_prescreen) runs first
to identify SoA candidate pages without any LLM calls. Only candidate
pages are sent to the VLM for detailed extraction.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

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


# Title patterns that indicate an SoA table
_SOA_TEXT_PATTERNS = [
    re.compile(r"schedule of (?:activities|assessments|events|study|evaluations|procedures)", re.IGNORECASE),
    re.compile(r"schedule of study (?:activities|procedures|assessments)", re.IGNORECASE),
    re.compile(r"study\s+(?:activities|procedures)\s+(?:schedule|table|matrix|overview)", re.IGNORECASE),
    re.compile(r"table\s+\w*\.?\d*\.?\s*(?:schedule of|study activities)", re.IGNORECASE),
    re.compile(r"time\s+and\s+events?\s+(?:table|schedule)", re.IGNORECASE),
    re.compile(r"assessment\s+(?:schedule|matrix|overview)", re.IGNORECASE),
    re.compile(r"(?:visit|encounter)\s+schedule", re.IGNORECASE),
    re.compile(r"(?:treatment|dosing|evaluation)\s+schedule", re.IGNORECASE),
    re.compile(r"table\s+of\s+(?:study\s+)?(?:activities|assessments|procedures)", re.IGNORECASE),
]

# Patterns for table continuation pages
_CONTINUATION_PATTERNS = [
    re.compile(r"(?:continued|cont['']?d)", re.IGNORECASE),
    re.compile(r"table\s+\w*\.?\d+\s*\(cont", re.IGNORECASE),
]


def _deterministic_soa_prescreen(pdf_bytes: bytes) -> dict[int, str]:
    """Scan PDF text for SoA pages without any LLM calls.

    Returns dict of {page_number: detection_type}.

    Strategy (3 tiers, each progressively looser):
    1. Title match — page text contains an SoA title pattern (high precision)
    2. Table density — page has a PyMuPDF-detected table with ≥3 X marks (medium precision)
    3. Neighbor proximity — pages within ±2 of a confirmed SoA page that also
       have tables with X marks (limited expansion, no cascading)
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    soa_pages: dict[int, str] = {}

    # ── Tier 1: Title match (highest precision) ─────────────────────
    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        text = page.get_text("text")

        for pattern in _SOA_TEXT_PATTERNS:
            if pattern.search(text):
                soa_pages[page_idx] = "title_match"
                break

    # ── Tier 2: Table density (X marks in grid tables) ──────────────
    for page_idx in range(doc.page_count):
        if page_idx in soa_pages:
            continue

        page = doc[page_idx]
        try:
            tables = page.find_tables()
            if not tables.tables:
                continue

            for t in tables.tables:
                extracted = t.extract()
                if not extracted or len(extracted) < 5:
                    continue

                # Count X marks and checkmarks in the table
                x_count = 0
                single_char_count = 0
                total_cells = 0
                for row in extracted:
                    for cell in row:
                        if cell is None:
                            continue
                        val = str(cell).strip()
                        total_cells += 1
                        if val.upper() in ("X", "Y", "✓", "✔", "●"):
                            x_count += 1
                        if len(val) == 1:
                            single_char_count += 1

                # SoA signature: ≥3 X marks OR >40% single-char cells in a 5+ row table
                if x_count >= 3:
                    soa_pages[page_idx] = "table_dense"
                    break
                elif total_cells >= 20 and single_char_count / total_cells > 0.4:
                    soa_pages[page_idx] = "table_dense"
                    break

        except Exception:
            pass

    # ── Tier 3: Gap-filling between confirmed SoA pages ──────────────
    # If pages N and N+2 are both confirmed SoA, page N+1 is almost
    # certainly a continuation (even if PyMuPDF can't detect its table
    # because it's a text-layout grid with no visible lines).
    confirmed_pages = sorted(soa_pages.keys())
    for i in range(len(confirmed_pages) - 1):
        p1 = confirmed_pages[i]
        p2 = confirmed_pages[i + 1]
        gap = p2 - p1
        if 1 < gap <= 3:
            # Fill in the gap pages
            for fill in range(p1 + 1, p2):
                if fill not in soa_pages:
                    soa_pages[fill] = "gap_fill"

    # Also expand ±1 from confirmed pages for text-layout continuations
    confirmed_after_fill = set(soa_pages.keys())
    for page_idx in confirmed_after_fill:
        for offset in [-1, 1]:
            neighbor = page_idx + offset
            if neighbor in soa_pages or neighbor < 0 or neighbor >= doc.page_count:
                continue

            page = doc[neighbor]
            try:
                # Check for tables WITH X marks (original Tier 3 logic)
                tables = page.find_tables()
                if tables.tables:
                    for t in tables.tables:
                        extracted = t.extract()
                        if not extracted or len(extracted) < 3:
                            continue
                        x_count = sum(
                            1 for row in extracted for cell in row
                            if cell and str(cell).strip().upper() in ("X", "Y", "✓", "✔")
                        )
                        if x_count >= 2:
                            soa_pages[neighbor] = "neighbor_soa"
                            break
                else:
                    # No PyMuPDF tables — check if page has substantial text
                    # (text-layout tables have lots of text but no grid lines)
                    text = page.get_text("text").strip()
                    if len(text) > 300:
                        # Check if text has SoA-like content (column-aligned data)
                        lines = text.split("\n")
                        short_lines = sum(1 for l in lines if 1 <= len(l.strip()) <= 5)
                        if short_lines > 10:
                            # Many short lines = likely a table with X/Y marks
                            soa_pages[neighbor] = "text_layout_neighbor"
            except Exception:
                pass

    # ── Also check continuation markers on pages adjacent to SoA ────
    all_soa = set(soa_pages.keys())
    for page_idx in range(doc.page_count):
        if page_idx in soa_pages:
            continue
        # Only check pages near known SoA
        if not any(abs(page_idx - sp) <= 3 for sp in all_soa):
            continue

        text = doc[page_idx].get_text("text")
        for pattern in _CONTINUATION_PATTERNS:
            if pattern.search(text):
                soa_pages[page_idx] = "continuation"
                break

    total_pages = doc.page_count
    doc.close()

    logger.info(
        f"SoA prescreen: {len(soa_pages)} of {total_pages} pages flagged "
        f"(title={sum(1 for v in soa_pages.values() if v == 'title_match')}, "
        f"dense={sum(1 for v in soa_pages.values() if v == 'table_dense')}, "
        f"neighbor={sum(1 for v in soa_pages.values() if v == 'neighbor_soa')}, "
        f"continuation={sum(1 for v in soa_pages.values() if v == 'continuation')})"
    )

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
        """Three-phase SOA detection: deterministic pre-screen -> LLM pre-screen -> detailed extraction.

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

            # Also use section parser to find SoA page ranges
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
                        max_tokens=256,
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
        for page_num, det_type in deterministic_pages.items():
            is_cont = det_type in ("continuation", "neighbor_expansion", "neighbor_soa")
            soa_pages.append((page_num, is_cont, f"deterministic:{det_type}"))

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
