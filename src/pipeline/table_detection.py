"""
Table Detection — identifies table regions in page images using vision LLM.

Sends each page image to a VLM and asks it to identify all table regions,
their bounding boxes, types, and titles.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from src.llm.client import LLMClient
from src.models.schema import (
    BoundingBox,
    PageImage,
    PipelineConfig,
    TableRegion,
    TableType,
)

logger = logging.getLogger(__name__)

DETECTION_PROMPT = """Analyze this page from a clinical trial protocol document.
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

    async def detect(self, pages: list[PageImage]) -> list[TableRegion]:
        """Detect all table regions across all pages."""
        all_regions: list[TableRegion] = []

        for page in pages:
            try:
                raw_detections = await self._detect_on_page(page)
                for raw in raw_detections:
                    region = self._parse_detection(raw, page.page_number)
                    all_regions.append(region)
            except Exception as e:
                logger.error(f"Table detection failed on page {page.page_number}: {e}")
                continue

        logger.info(f"Detected {len(all_regions)} table regions across {len(pages)} pages")
        return all_regions

    async def _detect_on_page(self, page: PageImage) -> list[dict[str, Any]]:
        """Run table detection on a single page."""
        result = await self.llm.vision_json_query(
            page.image_bytes,
            DETECTION_PROMPT,
            system="You are a clinical document analysis expert. Return valid JSON only.",
        )
        if isinstance(result, list):
            return result
        return []

    def _parse_detection(self, raw: dict[str, Any], page_num: int) -> TableRegion:
        """Parse a raw detection dict into a TableRegion model."""
        bbox_raw = raw.get("bbox", {})

        # Convert percentage-based bbox to absolute if needed
        bbox = BoundingBox(
            page=page_num,
            x0=float(bbox_raw.get("x0", 0)),
            y0=float(bbox_raw.get("y0", 0)),
            x1=float(bbox_raw.get("x1", 100)),
            y1=float(bbox_raw.get("y1", 100)),
        )

        # Parse table type safely
        raw_type = raw.get("table_type", "OTHER")
        try:
            table_type = TableType(raw_type)
        except ValueError:
            table_type = TableType.OTHER

        table_id = raw.get("table_id", f"t_{uuid.uuid4().hex[:8]}")

        return TableRegion(
            table_id=table_id,
            pages=[page_num],
            bounding_boxes=[bbox],
            table_type=table_type,
            title=raw.get("title"),
            continuation_markers=raw.get("continuation_markers", []),
        )
