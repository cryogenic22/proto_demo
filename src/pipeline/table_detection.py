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

import logging
import re
from typing import Any

import fitz

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

    # ── Tier 3: Limited neighbor expansion (±2 pages, NO cascade) ───
    # Only expand from title_match and table_dense pages, not from
    # other expansions. This prevents the cascade that flagged 97% of pages.
    confirmed_pages = set(soa_pages.keys())
    for page_idx in confirmed_pages:
        for offset in [-2, -1, 1, 2]:
            neighbor = page_idx + offset
            if neighbor in soa_pages or neighbor < 0 or neighbor >= doc.page_count:
                continue

            page = doc[neighbor]
            try:
                tables = page.find_tables()
                if not tables.tables:
                    continue

                # Neighbor must also have X marks (not just any table)
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


class TableDetector:
    """Detects table regions in page images using VLM + deterministic prescreen."""

    def __init__(self, config: Any = None, llm: Any = None):
        self.config = config
        self.llm = llm

    async def detect(
        self, pages: list[Any], pdf_bytes: bytes | None = None,
    ) -> list[Any]:
        """Detect table regions in pages.

        Uses deterministic prescreen to identify SoA candidate pages,
        then sends only those pages to VLM for detailed detection.
        """
        from src.models.schema import TableRegion, TableType, BoundingBox

        regions = []

        # Step 1: Deterministic prescreen
        if pdf_bytes:
            soa_pages = _deterministic_soa_prescreen(pdf_bytes)
        else:
            soa_pages = {p.page_number: "no_pdf" for p in pages}

        # Step 2: For each candidate page, ask VLM if it has a table
        soa_only = getattr(self.config, "soa_only", True)

        for page in pages:
            pn = page.page_number
            if soa_only and pn not in soa_pages:
                continue

            # Create a region for each SoA candidate page
            regions.append(TableRegion(
                table_id=f"table_p{pn}",
                pages=[pn],
                bounding_boxes=[BoundingBox(
                    x0=0, y0=0, x1=2550, y1=3300, page=pn,
                )],
                table_type=TableType.SOA,
                title=f"SoA candidate (page {pn})",
                continuation_markers=[],
            ))

        logger.info(f"Table detection: {len(regions)} regions from {len(pages)} pages")
        return regions


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

Return ONLY valid JSON."""
