"""
Table Stitcher — merges multi-page table fragments into logical units.

Uses content-continuity scoring instead of rigid page-gap limits:
1. Column fingerprint similarity (column count + header text)
2. Procedure name overlap (leverages 551-procedure vocabulary)
3. Continuation markers ("continued", "cont'd")
4. Page proximity (decays with distance)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.models.schema import TableRegion, TableType

logger = logging.getLogger(__name__)

CONTINUATION_PATTERNS = [
    r"\(continued\)",
    r"\(cont['']?d\)",
    r"\bcontinued\b",
    r"\bcont['']?d\b",
]
_CONTINUATION_RE = re.compile("|".join(CONTINUATION_PATTERNS), re.IGNORECASE)

# Merge threshold — fragments with score > this are the same logical table
MERGE_THRESHOLD = 0.45


class TableStitcher:
    """Merges table regions that span multiple pages."""

    def __init__(self, pdf_bytes: bytes | None = None):
        """Initialize with optional PDF bytes for column fingerprinting."""
        self._pdf_bytes = pdf_bytes
        self._column_cache: dict[int, list[str]] = {}  # page → column headers
        self._procedure_cache: dict[int, set[str]] = {}  # page → procedure names

    def stitch(self, regions: list[TableRegion]) -> list[TableRegion]:
        """Merge multi-page table fragments using content-continuity scoring."""
        if len(regions) <= 1:
            return regions

        # Pre-compute column fingerprints and procedure names from PDF
        if self._pdf_bytes:
            self._precompute_page_features(regions)

        sorted_regions = sorted(regions, key=lambda r: r.pages[0])
        merged: list[TableRegion] = []

        for region in sorted_regions:
            if not merged:
                merged.append(region)
                continue

            # Try merging with the last merged region using continuity score
            prev = merged[-1]
            score = self.continuity_score(prev, region)

            if score >= MERGE_THRESHOLD:
                merged[-1] = self._merge(prev, region)
                logger.info(
                    f"Stitched table on page {region.pages[0]} into pages {prev.pages} "
                    f"(score={score:.2f})"
                )
            else:
                # Also try merging with any earlier region (handles interleaved pages)
                merged_into = False
                for i in range(len(merged) - 1, -1, -1):
                    s = self.continuity_score(merged[i], region)
                    if s >= MERGE_THRESHOLD:
                        merged[i] = self._merge(merged[i], region)
                        logger.info(
                            f"Stitched table on page {region.pages[0]} into "
                            f"earlier table at pages {merged[i].pages} (score={s:.2f})"
                        )
                        merged_into = True
                        break
                if not merged_into:
                    merged.append(region)

        logger.info(f"Stitching: {len(regions)} regions → {len(merged)} logical tables")
        return merged

    def continuity_score(self, prev: TableRegion, curr: TableRegion) -> float:
        """Score how likely curr is a continuation of prev.

        Returns 0.0-1.0. Higher = more likely same table.
        Components:
        - 0.35: column fingerprint similarity
        - 0.25: procedure name overlap
        - 0.25: continuation marker presence
        - 0.15: page proximity
        """
        score = 0.0

        # Component 1: Column fingerprint similarity (0.35)
        col_sim = self._column_fingerprint_similarity(prev, curr)
        score += 0.35 * col_sim

        # Component 2: Procedure name overlap (0.25)
        proc_overlap = self._procedure_name_overlap(prev, curr)
        score += 0.25 * proc_overlap

        # Component 3: Continuation markers (0.25)
        has_marker = (
            bool(curr.continuation_markers)
            or (curr.title and bool(_CONTINUATION_RE.search(curr.title)))
        )
        score += 0.25 * (1.0 if has_marker else 0.0)

        # Also: matching base titles count as a marker
        if prev.title and curr.title:
            base_prev = self._base_title(prev.title)
            base_curr = self._base_title(curr.title)
            if base_prev and base_curr and base_prev == base_curr:
                score += 0.25 * 0.8  # Strong but not full marker weight

        # Component 4: Page proximity (0.15) — decays with distance
        page_gap = min(curr.pages) - max(prev.pages)
        if page_gap <= 1:
            score += 0.15 * 1.0
        elif page_gap <= 3:
            score += 0.15 * 0.7
        elif page_gap <= 5:
            score += 0.15 * 0.3
        # Beyond 5 pages: 0 proximity score (but can still merge via other signals)

        # Both SOA type bonus (only when titles are absent or match)
        if prev.table_type == TableType.SOA and curr.table_type == TableType.SOA:
            if not prev.title or not curr.title or self._base_title(prev.title) == self._base_title(curr.title):
                score += 0.05

        # Penalty: different non-empty titles that don't match = likely different tables
        if prev.title and curr.title:
            if self._base_title(prev.title) != self._base_title(curr.title):
                score -= 0.15

        return max(0.0, min(1.0, score))

    def _column_fingerprint_similarity(self, prev: TableRegion, curr: TableRegion) -> float:
        """Compare column structure between two table fragments."""
        prev_cols = self._get_column_headers(prev)
        curr_cols = self._get_column_headers(curr)

        if not prev_cols or not curr_cols:
            # Can't compare — return neutral score
            return 0.5

        # Column count similarity
        count_sim = 1.0 - abs(len(prev_cols) - len(curr_cols)) / max(len(prev_cols), len(curr_cols))

        # Column header text overlap
        prev_set = set(h.lower() for h in prev_cols if h.strip())
        curr_set = set(h.lower() for h in curr_cols if h.strip())
        if prev_set and curr_set:
            overlap = len(prev_set & curr_set) / max(len(prev_set), len(curr_set))
        else:
            overlap = count_sim  # Fallback to count similarity

        return (count_sim * 0.4 + overlap * 0.6)

    def _procedure_name_overlap(self, prev: TableRegion, curr: TableRegion) -> float:
        """Check procedure name overlap between table fragments."""
        prev_procs = self._get_procedure_names(prev)
        curr_procs = self._get_procedure_names(curr)

        if not prev_procs or not curr_procs:
            return 0.3  # Neutral when data unavailable

        # Check overlap with known procedure vocabulary
        try:
            from src.pipeline.procedure_normalizer import ProcedureNormalizer
            normalizer = ProcedureNormalizer()

            # Count how many of curr's procedures are known clinical procedures
            known_count = sum(
                1 for p in curr_procs
                if not normalizer.is_not_procedure(p) and len(p) > 3
            )
            if curr_procs:
                known_ratio = known_count / len(curr_procs)
            else:
                known_ratio = 0.0

            # If curr has many known procedures, it's likely SoA content
            return min(1.0, known_ratio * 1.2)
        except Exception:
            # Fallback: simple text overlap
            prev_set = set(p.lower() for p in prev_procs)
            curr_set = set(p.lower() for p in curr_procs)
            if prev_set and curr_set:
                return len(prev_set & curr_set) / max(len(prev_set), len(curr_set))
            return 0.3

    def _get_column_headers(self, region: TableRegion) -> list[str]:
        """Extract column headers from a table region's pages."""
        # Check cache first
        first_page = region.pages[0] if region.pages else -1
        if first_page in self._column_cache:
            return self._column_cache[first_page]

        if not self._pdf_bytes:
            return []

        try:
            import fitz
            doc = fitz.open(stream=self._pdf_bytes, filetype="pdf")
            page = doc[first_page] if first_page < doc.page_count else None
            if not page:
                doc.close()
                return []

            # Try find_tables for structured extraction
            try:
                tables = page.find_tables()
                if tables.tables:
                    data = tables.tables[0].extract()
                    if data and len(data) > 0:
                        headers = [str(cell or "") for cell in data[0]]
                        self._column_cache[first_page] = headers
                        doc.close()
                        return headers
            except (AttributeError, Exception):
                pass

            doc.close()
        except Exception:
            pass

        return []

    def _get_procedure_names(self, region: TableRegion) -> list[str]:
        """Extract procedure names (first column values) from table pages."""
        first_page = region.pages[0] if region.pages else -1
        if first_page in self._procedure_cache:
            return list(self._procedure_cache[first_page])

        if not self._pdf_bytes:
            return []

        try:
            import fitz
            doc = fitz.open(stream=self._pdf_bytes, filetype="pdf")
            procs: set[str] = set()

            for pg in region.pages:
                if pg >= doc.page_count:
                    continue
                page = doc[pg]
                try:
                    tables = page.find_tables()
                    if tables.tables:
                        data = tables.tables[0].extract()
                        for row in data[1:]:  # Skip header row
                            if row and row[0] and str(row[0]).strip():
                                procs.add(str(row[0]).strip())
                except (AttributeError, Exception):
                    pass

            doc.close()
            self._procedure_cache[first_page] = procs
            return list(procs)
        except Exception:
            return []

    def _precompute_page_features(self, regions: list[TableRegion]) -> None:
        """Pre-compute column headers and procedure names for all pages."""
        for region in regions:
            self._get_column_headers(region)
            self._get_procedure_names(region)

    @staticmethod
    def _base_title(title: str) -> str:
        """Strip continuation markers to get the base title."""
        cleaned = _CONTINUATION_RE.sub("", title).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.lower()

    @staticmethod
    def _merge(prev: TableRegion, curr: TableRegion) -> TableRegion:
        """Merge two table regions."""
        return TableRegion(
            table_id=prev.table_id,
            pages=sorted(set(prev.pages + curr.pages)),
            bounding_boxes=prev.bounding_boxes + curr.bounding_boxes,
            table_type=prev.table_type,
            title=prev.title,
            continuation_markers=prev.continuation_markers + curr.continuation_markers,
        )
