"""
Footnote Extractor — extracts footnote definitions from table images.

Uses a vision LLM to read the footnote block at the bottom of tables
and return a mapping of marker → footnote text.
"""

from __future__ import annotations

import logging
from typing import Any

from src.llm.client import LLMClient
from src.models.schema import (
    PageImage,
    PipelineConfig,
    TableRegion,
    TableSchema,
)

logger = logging.getLogger(__name__)

FOOTNOTE_PROMPT = """Look at this clinical trial protocol table image carefully.

At the bottom of the table (or sometimes below it), there are footnotes —
lines of text marked with superscript symbols like a, b, c, *, †, ‡, §, ¶, #,
or numbers like 1, 2, 3.

Extract ALL footnote definitions. Return a JSON object where each key is
the footnote marker and each value is the footnote text.

Example:
{{
  "a": "Only if clinically indicated",
  "b": "At screening visit only",
  "c": "Every 4 weeks after Week 12",
  "*": "Required for female participants of childbearing potential"
}}

Rules:
- Include EVERY footnote visible in or below the table
- The marker is the superscript symbol (a, b, *, †, 1, 2, etc.)
- The text is the full footnote definition
- If there are no footnotes, return an empty object: {{}}
- Look carefully — footnotes may be in small print below the table
- Some footnotes span multiple lines — include the complete text
- Abbreviation lists at the bottom are NOT footnotes — skip those

Known footnote markers in this table: {markers}

Return ONLY valid JSON, no markdown, no explanation."""


class FootnoteExtractor:
    """Extracts footnote definitions from table images using vision LLM."""

    def __init__(self, config: PipelineConfig, llm_client: LLMClient | None = None):
        self.config = config
        self.llm = llm_client or LLMClient(config)

    async def extract(
        self,
        region: TableRegion,
        schema: TableSchema,
        pages: list[PageImage],
    ) -> dict[str, str]:
        """
        Extract footnote definitions from table images.

        Args:
            region: Table region with page references.
            schema: Table schema with known footnote markers.
            pages: All page images.

        Returns:
            Dict mapping marker → footnote text.
        """
        table_images = self._get_table_images(region, pages)
        if not table_images:
            return {}

        markers_hint = ", ".join(schema.footnote_markers) if schema.footnote_markers else "unknown"
        prompt = FOOTNOTE_PROMPT.format(markers=markers_hint)

        try:
            # Use the last page image of the table — footnotes are typically
            # at the bottom of the last page of a multi-page table
            # But also check all pages for completeness
            all_footnotes: dict[str, str] = {}

            for img in table_images:
                try:
                    raw = await self.llm.vision_json_query(
                        img,
                        prompt,
                        system="You are a clinical document expert. Extract footnotes precisely. Return valid JSON only.",
                    )

                    if isinstance(raw, dict):
                        # Merge — later pages may have continuation footnotes
                        for marker, text in raw.items():
                            if isinstance(text, str) and text.strip():
                                # Keep the longest definition if duplicated
                                existing = all_footnotes.get(marker, "")
                                if len(text) > len(existing):
                                    all_footnotes[marker] = text.strip()
                except Exception as e:
                    logger.warning(f"Footnote extraction failed on one page: {e}")
                    continue

            logger.info(
                f"Extracted {len(all_footnotes)} footnote definitions for table {region.table_id}"
            )
            return all_footnotes

        except Exception as e:
            logger.error(f"Footnote extraction failed for table {region.table_id}: {e}")
            return {}

    @staticmethod
    def _get_table_images(
        region: TableRegion, pages: list[PageImage]
    ) -> list[bytes]:
        page_map = {p.page_number: p for p in pages}
        return [page_map[pn].image_bytes for pn in region.pages if pn in page_map]
