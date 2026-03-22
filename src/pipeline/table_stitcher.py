"""
Table Stitcher — merges multi-page table fragments into logical units.

Identifies tables that span multiple pages by matching titles,
detecting continuation markers, and checking page adjacency.
"""

from __future__ import annotations

import logging
import re

from src.models.schema import TableRegion, TableType

logger = logging.getLogger(__name__)

# Patterns that indicate a table is a continuation of a previous one
CONTINUATION_PATTERNS = [
    r"\(continued\)",
    r"\(cont['']?d\)",
    r"\bcontinued\b",
    r"\bcont['']?d\b",
]
_CONTINUATION_RE = re.compile(
    "|".join(CONTINUATION_PATTERNS), re.IGNORECASE
)


class TableStitcher:
    """Merges table regions that span multiple pages."""

    def stitch(self, regions: list[TableRegion]) -> list[TableRegion]:
        """
        Merge multi-page table fragments into unified TableRegions.

        Stitching rules:
        1. A region with continuation markers merges into the preceding region
           (on the immediately prior page) that shares a similar base title.
        2. Regions with identical titles on consecutive pages merge.
        """
        if len(regions) <= 1:
            return regions

        # Sort by first page number
        sorted_regions = sorted(regions, key=lambda r: r.pages[0])

        merged: list[TableRegion] = []

        for region in sorted_regions:
            if not merged:
                merged.append(region)
                continue

            prev = merged[-1]

            if self._should_merge(prev, region):
                merged[-1] = self._merge(prev, region)
                logger.info(
                    f"Stitched table '{region.title}' on page {region.pages[0]} "
                    f"into table on pages {prev.pages}"
                )
            else:
                merged.append(region)

        logger.info(
            f"Stitching: {len(regions)} regions → {len(merged)} logical tables"
        )
        return merged

    def _should_merge(self, prev: TableRegion, curr: TableRegion) -> bool:
        """Determine if curr should be merged into prev."""
        # Must be on consecutive or near-consecutive pages (allow 1 gap for
        # interleaved text pages between SoA table pages)
        if not self._pages_are_near(prev, curr, max_gap=2):
            return False

        # Rule 1: Continuation markers (strongest signal)
        if curr.continuation_markers:
            return True
        if curr.title and _CONTINUATION_RE.search(curr.title):
            return True

        # Rule 2: Matching base titles
        if prev.title and curr.title:
            base_prev = self._base_title(prev.title)
            base_curr = self._base_title(curr.title)
            if base_prev and base_curr and base_prev == base_curr:
                return True

        # Rule 3 (NEW): Both are SOA type and on near-consecutive pages.
        # SoA tables commonly span 2-20 pages without continuation markers.
        if (prev.table_type == TableType.SOA
                and curr.table_type == TableType.SOA
                and self._pages_are_near(prev, curr, max_gap=2)):
            # Continuation pages rarely have titles
            if not curr.title or curr.title == prev.title:
                return True
            # Or curr title starts with same table number pattern
            if prev.title and curr.title:
                prev_num = re.match(r'^Table\s+(\d+[-.]?\d*)', prev.title, re.IGNORECASE)
                curr_num = re.match(r'^Table\s+(\d+[-.]?\d*)', curr.title, re.IGNORECASE)
                if prev_num and curr_num and prev_num.group(1) == curr_num.group(1):
                    return True

        return False

    @staticmethod
    def _pages_are_consecutive(prev: TableRegion, curr: TableRegion) -> bool:
        """Check if curr starts on the page immediately after prev ends."""
        last_page_of_prev = max(prev.pages)
        first_page_of_curr = min(curr.pages)
        return first_page_of_curr == last_page_of_prev + 1

    @staticmethod
    def _pages_are_near(prev: TableRegion, curr: TableRegion, max_gap: int = 1) -> bool:
        """Check if curr starts within max_gap pages after prev ends."""
        last_page_of_prev = max(prev.pages)
        first_page_of_curr = min(curr.pages)
        return 0 < (first_page_of_curr - last_page_of_prev) <= max_gap + 1

    @staticmethod
    def _base_title(title: str) -> str:
        """Strip continuation markers to get the base title for comparison."""
        cleaned = _CONTINUATION_RE.sub("", title).strip()
        # Normalize whitespace
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.lower()

    @staticmethod
    def _merge(prev: TableRegion, curr: TableRegion) -> TableRegion:
        """Merge two table regions into one."""
        return TableRegion(
            table_id=prev.table_id,
            pages=prev.pages + curr.pages,
            bounding_boxes=prev.bounding_boxes + curr.bounding_boxes,
            table_type=prev.table_type,
            title=prev.title,  # Keep the original title
            continuation_markers=prev.continuation_markers + curr.continuation_markers,
        )
