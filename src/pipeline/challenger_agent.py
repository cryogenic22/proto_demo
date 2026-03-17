"""
Challenger Agent — adversarial validation that hunts for errors.

Takes the extracted table data + source images and specifically looks for:
- Values that don't match the source image
- Structural inconsistencies
- Unresolved footnotes
- Implausible values
"""

from __future__ import annotations

import logging
from typing import Any

from src.llm.client import LLMClient
from src.models.schema import (
    CellRef,
    ChallengeIssue,
    ChallengeType,
    ExtractedCell,
    PageImage,
    PipelineConfig,
    TableRegion,
    TableSchema,
)

logger = logging.getLogger(__name__)

CHALLENGER_PROMPT = """You are a critical reviewer of clinical trial protocol table extraction.
You are given:
1. A table image from a clinical protocol document
2. The extracted data in JSON format

Your job is to find ERRORS in the extraction. Be adversarial — look for:
- Cells where the extracted value does NOT match what you see in the image
- Missing cells that exist in the image but are not in the extracted data
- Fabricated/hallucinated values that appear in the data but NOT in the image
- Structural mismatches (wrong row/column assignment)
- Footnote markers in the image that are not captured in the extraction
- Values that are implausible for a clinical protocol (e.g., impossibly high frequencies)

TABLE SCHEMA:
{schema_json}

EXTRACTED DATA:
{cells_json}

For each issue found, return a JSON array of objects:
{{
  "cell_ref": {{"row": <int>, "col": <int>}} or null if structural issue,
  "challenge_type": "MISSING_VALUE" | "HALLUCINATED_VALUE" | "STRUCTURAL_MISMATCH" | "FOOTNOTE_UNRESOLVED" | "IMPLAUSIBLE_VALUE",
  "description": "<specific description of what's wrong>",
  "extracted_value": "<what the extraction says>",
  "suggested_value": "<what you think it should be, or null>",
  "severity": <0.0 to 1.0, where 1.0 is critical>
}}

If the extraction looks correct, return an empty array: []

Be thorough but precise — only flag genuine issues, not stylistic differences.
Return ONLY the JSON array."""


class ChallengerAgent:
    """Adversarial agent that validates extracted data against source images."""

    def __init__(self, config: PipelineConfig, llm_client: LLMClient | None = None):
        self.config = config
        self.llm = llm_client or LLMClient(config)

    async def challenge(
        self,
        region: TableRegion,
        schema: TableSchema,
        cells: list[ExtractedCell],
        pages: list[PageImage],
    ) -> list[ChallengeIssue]:
        """
        Run adversarial validation on extracted table data.

        Returns list of issues found.
        """
        table_images = self._get_table_images(region, pages)
        if not table_images:
            return []

        # Serialize schema and cells for the prompt
        schema_json = schema.model_dump_json(indent=2)
        cells_json = _cells_to_summary_json(cells)

        prompt = CHALLENGER_PROMPT.format(
            schema_json=schema_json,
            cells_json=cells_json,
        )

        try:
            if len(table_images) == 1:
                raw = await self.llm.vision_json_query(
                    table_images[0], prompt,
                    system="You are an adversarial clinical data reviewer. Find errors. Return JSON only.",
                    max_tokens=4096,
                )
            else:
                raw = await self.llm.vision_json_query_multi(
                    table_images, prompt,
                    system="You are an adversarial clinical data reviewer. Find errors. Return JSON only.",
                    max_tokens=4096,
                )

            if not isinstance(raw, list):
                return []

            return [self._parse_issue(item) for item in raw]

        except Exception as e:
            logger.error(f"Challenger agent failed: {e}")
            return []

    def _parse_issue(self, raw: dict[str, Any]) -> ChallengeIssue:
        """Parse a raw issue dict into a ChallengeIssue."""
        cell_ref = None
        if raw.get("cell_ref"):
            cell_ref = CellRef(
                row=raw["cell_ref"].get("row", 0),
                col=raw["cell_ref"].get("col", 0),
            )

        raw_type = raw.get("challenge_type", "IMPLAUSIBLE_VALUE")
        try:
            challenge_type = ChallengeType(raw_type)
        except ValueError:
            challenge_type = ChallengeType.IMPLAUSIBLE_VALUE

        return ChallengeIssue(
            cell_ref=cell_ref,
            challenge_type=challenge_type,
            description=raw.get("description", ""),
            extracted_value=raw.get("extracted_value", ""),
            suggested_value=raw.get("suggested_value"),
            severity=min(1.0, max(0.0, float(raw.get("severity", 0.5)))),
        )

    @staticmethod
    def _get_table_images(
        region: TableRegion, pages: list[PageImage]
    ) -> list[bytes]:
        page_map = {p.page_number: p for p in pages}
        return [
            page_map[pn].image_bytes
            for pn in region.pages
            if pn in page_map
        ]


def _cells_to_summary_json(cells: list[ExtractedCell]) -> str:
    """Create a compact JSON summary of cells for the prompt."""
    import json
    summary = []
    for c in cells:
        entry: dict[str, Any] = {
            "row": c.row, "col": c.col,
            "value": c.raw_value,
            "type": c.data_type.value,
        }
        if c.footnote_markers:
            entry["footnotes"] = c.footnote_markers
        if c.row_header:
            entry["row_header"] = c.row_header
        if c.col_header:
            entry["col_header"] = c.col_header
        summary.append(entry)
    return json.dumps(summary, indent=2)
