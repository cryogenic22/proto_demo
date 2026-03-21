"""
Verification Agent for ProtoExtract Pipeline
=============================================
Lightweight VLM verification pass that validates extracted cell values
without performing full extraction. Adapted from proto_demo's challenger
agent concept.

Key insight: verification is 10x cheaper than extraction.
- Extraction: ~200 tokens/cell (describe what you see)
- Verification: ~10 tokens/cell (YES/NO/UNCERTAIN)

Usage:
    from verification_agent import VerificationAgent

    agent = VerificationAgent(api_key="sk-...")
    results = agent.verify_table(page_images, extracted_cells)
"""

import os
import re
import json
import time
import base64
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class VerificationVerdict(Enum):
    """Verification outcome for a single cell."""
    CONFIRMED = "confirmed"       # VLM confirms the extracted value
    REJECTED = "rejected"         # VLM disagrees with the extracted value
    UNCERTAIN = "uncertain"       # VLM cannot determine correctness
    CORRECTED = "corrected"       # VLM provides a correction
    SKIPPED = "skipped"           # Cell was not verified (too small, empty, etc.)


@dataclass
class CellVerification:
    """Verification result for a single cell."""
    row: int
    col: int
    extracted_text: str
    verdict: VerificationVerdict
    vlm_response: str = ""
    corrected_text: Optional[str] = None
    confidence: float = 0.0
    tokens_used: int = 0


@dataclass
class TableVerificationResult:
    """Aggregate verification result for a full table."""
    cells: List[CellVerification]
    total_cells: int = 0
    confirmed_count: int = 0
    rejected_count: int = 0
    uncertain_count: int = 0
    corrected_count: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    verification_time_sec: float = 0.0

    @property
    def confirmation_rate(self) -> float:
        if self.total_cells == 0:
            return 0.0
        return self.confirmed_count / self.total_cells

    @property
    def accuracy_estimate(self) -> float:
        """Estimated accuracy based on verification results."""
        if self.total_cells == 0:
            return 0.0
        return (self.confirmed_count + self.corrected_count) / self.total_cells


# ── Prompt Templates ──────────────────────────────────────────────────

BATCH_VERIFICATION_PROMPT = """You are verifying extracted table cell values against the original document image.

For each cell below, check if the extracted value matches what appears in the table at the specified location. Respond with EXACTLY one of:
- YES — the extracted value is correct
- NO [correct value] — the extracted value is wrong; provide the correct value
- UNCERTAIN — you cannot determine if the value is correct

Cells to verify:
{cell_list}

Respond with one line per cell in the format:
CELL_ID: YES|NO [correction]|UNCERTAIN
"""

SINGLE_CELL_PROMPT = """Look at the table in this image. At row {row}, column {col}, does the cell contain the value "{text}"?

Reply with exactly one of:
- YES
- NO [actual value you see]
- UNCERTAIN
"""

STRUCTURE_VERIFICATION_PROMPT = """Examine the table in this image and verify its structure:
1. How many rows does the table have (including header rows)?
2. How many columns does the table have?
3. Are there any merged cells? If so, which ones?
4. Does the table continue on the next page?

Extracted structure claims:
- Rows: {num_rows}
- Columns: {num_cols}
- Merged cells: {merged_cells}

For each claim, respond YES (correct) or NO [actual value].
"""


# ── VLM Client ────────────────────────────────────────────────────────

class VLMClient:
    """
    Wrapper for VLM API calls (supports OpenAI-compatible APIs).
    Handles batching, retry logic, and cost tracking.
    """

    # Pricing per 1K tokens (approximate, varies by model)
    PRICING = {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    }

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        max_retries: int = 3,
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout = timeout
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def _encode_image(self, image_bytes: bytes) -> str:
        """Encode image to base64 for API."""
        return base64.b64encode(image_bytes).decode("utf-8")

    def verify_cells(
        self,
        image_bytes: bytes,
        prompt: str,
    ) -> Tuple[str, int]:
        """
        Send verification request to VLM API.

        Returns:
            Tuple of (response_text, tokens_used)
        """
        import requests

        b64_image = self._encode_image(image_bytes)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64_image}",
                                "detail": "high",
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": 500,
            "temperature": 0.0,  # Deterministic for verification
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                tokens = usage.get("total_tokens", 0)
                self.total_input_tokens += usage.get("prompt_tokens", 0)
                self.total_output_tokens += usage.get("completion_tokens", 0)

                return text, tokens

            except Exception as e:
                logger.warning(f"VLM API attempt {attempt+1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise

    @property
    def estimated_cost(self) -> float:
        """Estimate total cost based on token usage."""
        pricing = self.PRICING.get(self.model, {"input": 0.005, "output": 0.015})
        return (
            self.total_input_tokens / 1000 * pricing["input"]
            + self.total_output_tokens / 1000 * pricing["output"]
        )


# ── Verification Agent ────────────────────────────────────────────────

class VerificationAgent:
    """
    Lightweight VLM verification agent for extracted SoA table cells.

    Architecture:
        1. Group cells into batches (8-12 cells per VLM call)
        2. Send page image + batch verification prompt
        3. Parse VLM responses into verdicts
        4. Track costs and flag rejected cells

    Cost model (gpt-4o-mini):
        - ~10 tokens per cell verification
        - ~1000 tokens per page image
        - Total: ~$0.003 per SoA table (vs ~$0.30 for extraction)
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = "gpt-4o-mini",
        batch_size: int = 10,
        skip_empty_cells: bool = True,
        min_text_length: int = 1,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.batch_size = batch_size
        self.skip_empty_cells = skip_empty_cells
        self.min_text_length = min_text_length

        if self.api_key:
            self.vlm_client = VLMClient(api_key=self.api_key, model=model)
        else:
            self.vlm_client = None
            logger.warning("No API key provided — verification will run in dry-run mode")

    def _should_verify(self, cell: Dict) -> bool:
        """Determine if a cell should be verified."""
        text = cell.get("text", "").strip()
        if self.skip_empty_cells and not text:
            return False
        if len(text) < self.min_text_length:
            return False
        # Skip cells that are just checkmarks or symbols
        if text in ("X", "x", "✓", "✗", "•", "-", "—"):
            return False
        return True

    def _build_batch_prompt(self, cells: List[Dict]) -> str:
        """Build a batch verification prompt for multiple cells."""
        cell_lines = []
        for i, cell in enumerate(cells):
            cell_lines.append(
                f"  CELL_{i}: Row {cell['row']}, Col {cell['col']}, "
                f"Value: \"{cell['text']}\""
            )
        cell_list = "\n".join(cell_lines)
        return BATCH_VERIFICATION_PROMPT.format(cell_list=cell_list)

    def _parse_verification_response(
        self, response: str, cells: List[Dict]
    ) -> List[CellVerification]:
        """Parse VLM verification response into structured verdicts."""
        results = []
        lines = response.strip().split("\n")

        for i, cell in enumerate(cells):
            verdict = VerificationVerdict.UNCERTAIN
            corrected_text = None
            vlm_line = ""

            # Find matching line in response
            for line in lines:
                if f"CELL_{i}" in line:
                    vlm_line = line
                    break

            if not vlm_line:
                # Try positional matching
                if i < len(lines):
                    vlm_line = lines[i]

            # Parse verdict
            upper_line = vlm_line.upper().strip()
            if "YES" in upper_line:
                verdict = VerificationVerdict.CONFIRMED
            elif "NO" in upper_line:
                # Extract correction if provided
                no_match = re.search(r'NO\s*[\[:\-]?\s*(.+?)[\]\s]*$', vlm_line, re.IGNORECASE)
                if no_match:
                    corrected_text = no_match.group(1).strip().strip('"\'[]')
                    verdict = VerificationVerdict.CORRECTED
                else:
                    verdict = VerificationVerdict.REJECTED
            elif "UNCERTAIN" in upper_line:
                verdict = VerificationVerdict.UNCERTAIN

            results.append(CellVerification(
                row=cell["row"],
                col=cell["col"],
                extracted_text=cell["text"],
                verdict=verdict,
                vlm_response=vlm_line,
                corrected_text=corrected_text,
            ))

        return results

    def verify_table(
        self,
        page_image_bytes: bytes,
        cells: List[Dict],
    ) -> TableVerificationResult:
        """
        Verify all cells in an extracted table.

        Args:
            page_image_bytes: PNG bytes of the page containing the table
            cells: List of dicts with keys: row, col, text

        Returns:
            TableVerificationResult with per-cell verdicts
        """
        start_time = time.time()

        # Filter cells that should be verified
        verifiable = [(i, c) for i, c in enumerate(cells) if self._should_verify(c)]
        skipped = [(i, c) for i, c in enumerate(cells) if not self._should_verify(c)]

        all_results = []

        # Add skipped cells
        for i, cell in skipped:
            all_results.append(CellVerification(
                row=cell.get("row", 0),
                col=cell.get("col", 0),
                extracted_text=cell.get("text", ""),
                verdict=VerificationVerdict.SKIPPED,
            ))

        # Process verifiable cells in batches
        total_tokens = 0
        verifiable_cells = [c for _, c in verifiable]

        for batch_start in range(0, len(verifiable_cells), self.batch_size):
            batch = verifiable_cells[batch_start:batch_start + self.batch_size]
            prompt = self._build_batch_prompt(batch)

            if self.vlm_client:
                response, tokens = self.vlm_client.verify_cells(page_image_bytes, prompt)
                total_tokens += tokens
                batch_results = self._parse_verification_response(response, batch)
            else:
                # Dry-run mode
                batch_results = [
                    CellVerification(
                        row=c["row"], col=c["col"],
                        extracted_text=c["text"],
                        verdict=VerificationVerdict.UNCERTAIN,
                        vlm_response="[dry-run]",
                    )
                    for c in batch
                ]

            all_results.extend(batch_results)

        elapsed = time.time() - start_time

        # Count verdicts
        confirmed = sum(1 for r in all_results if r.verdict == VerificationVerdict.CONFIRMED)
        rejected = sum(1 for r in all_results if r.verdict == VerificationVerdict.REJECTED)
        uncertain = sum(1 for r in all_results if r.verdict == VerificationVerdict.UNCERTAIN)
        corrected = sum(1 for r in all_results if r.verdict == VerificationVerdict.CORRECTED)

        cost = self.vlm_client.estimated_cost if self.vlm_client else 0.0

        return TableVerificationResult(
            cells=all_results,
            total_cells=len(all_results),
            confirmed_count=confirmed,
            rejected_count=rejected,
            uncertain_count=uncertain,
            corrected_count=corrected,
            total_tokens=total_tokens,
            cost_usd=round(cost, 4),
            verification_time_sec=round(elapsed, 2),
        )

    def apply_corrections(
        self,
        cells: List[Dict],
        verification: TableVerificationResult,
        apply_uncertain: bool = False,
    ) -> List[Dict]:
        """
        Apply verified corrections back to the cell grid.

        Args:
            cells: Original extracted cells
            verification: Verification results
            apply_uncertain: If True, also flag uncertain cells

        Returns:
            Updated cells with corrections applied and flags added
        """
        # Build lookup by (row, col)
        corrections = {}
        for cv in verification.cells:
            if cv.verdict == VerificationVerdict.CORRECTED and cv.corrected_text:
                corrections[(cv.row, cv.col)] = cv.corrected_text

        updated = []
        for cell in cells:
            new_cell = dict(cell)
            key = (cell.get("row", 0), cell.get("col", 0))

            if key in corrections:
                new_cell["text"] = corrections[key]
                new_cell["_corrected"] = True
                new_cell["_original_text"] = cell.get("text", "")

            # Find verification result for this cell
            for cv in verification.cells:
                if cv.row == cell.get("row") and cv.col == cell.get("col"):
                    new_cell["_verification"] = cv.verdict.value
                    break

            updated.append(new_cell)

        return updated


# ── CLI usage ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Verification Agent for SoA tables")
    parser.add_argument("--image", required=True, help="Path to page image (PNG)")
    parser.add_argument("--cells", required=True, help="Path to cells JSON")
    parser.add_argument("--output", default="verification_results.json")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(args.image, "rb") as f:
        image_bytes = f.read()
    with open(args.cells) as f:
        cells = json.load(f)

    api_key = "" if args.dry_run else os.environ.get("OPENAI_API_KEY", "")
    agent = VerificationAgent(api_key=api_key, model=args.model)
    result = agent.verify_table(image_bytes, cells)

    print(f"Total cells: {result.total_cells}")
    print(f"Confirmed: {result.confirmed_count}")
    print(f"Rejected: {result.rejected_count}")
    print(f"Corrected: {result.corrected_count}")
    print(f"Uncertain: {result.uncertain_count}")
    print(f"Accuracy estimate: {result.accuracy_estimate:.1%}")
    print(f"Cost: ${result.cost_usd:.4f}")

    output_data = {
        "summary": {
            "total_cells": result.total_cells,
            "confirmed": result.confirmed_count,
            "rejected": result.rejected_count,
            "corrected": result.corrected_count,
            "accuracy_estimate": result.accuracy_estimate,
            "cost_usd": result.cost_usd,
        },
        "cells": [
            {
                "row": c.row, "col": c.col,
                "extracted_text": c.extracted_text,
                "verdict": c.verdict.value,
                "corrected_text": c.corrected_text,
            }
            for c in result.cells
        ],
    }
    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"Results written to {args.output}")
