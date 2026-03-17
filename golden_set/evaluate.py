"""
Golden Set Evaluation Runner.

Downloads golden set protocols, runs the extraction pipeline on each,
and compares results against ground truth annotations.

Usage:
    python -m golden_set.evaluate --protocol P-01 --all --report
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from src.models.schema import PipelineConfig
from src.pipeline.orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

GOLDEN_SET_DIR = Path(__file__).parent
REGISTRY_PATH = GOLDEN_SET_DIR / "registry.json"
ANNOTATIONS_DIR = GOLDEN_SET_DIR / "annotations"
CACHE_DIR = GOLDEN_SET_DIR / "cached_pdfs"


@dataclass
class CellMetric:
    """Per-cell evaluation result."""
    row: int
    col: int
    expected: str
    extracted: str
    match: bool
    difficulty: str


@dataclass
class TableMetric:
    """Per-table evaluation result."""
    table_id: str
    cell_metrics: list[CellMetric] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.cell_metrics)

    @property
    def correct(self) -> int:
        return sum(1 for m in self.cell_metrics if m.match)

    @property
    def precision(self) -> float:
        return self.correct / self.total if self.total > 0 else 0.0

    def precision_by_difficulty(self) -> dict[str, float]:
        result: dict[str, dict[str, int]] = {}
        for m in self.cell_metrics:
            if m.difficulty not in result:
                result[m.difficulty] = {"correct": 0, "total": 0}
            result[m.difficulty]["total"] += 1
            if m.match:
                result[m.difficulty]["correct"] += 1
        return {
            k: v["correct"] / v["total"] if v["total"] > 0 else 0.0
            for k, v in result.items()
        }


@dataclass
class ProtocolMetric:
    """Per-protocol evaluation result."""
    protocol_id: str
    complexity_tier: int
    table_metrics: list[TableMetric] = field(default_factory=list)
    processing_time: float = 0.0
    error: str | None = None

    @property
    def overall_precision(self) -> float:
        total = sum(t.total for t in self.table_metrics)
        correct = sum(t.correct for t in self.table_metrics)
        return correct / total if total > 0 else 0.0


def load_registry() -> dict:
    with open(REGISTRY_PATH) as f:
        return json.load(f)


async def download_protocol(url: str, protocol_id: str) -> bytes:
    """Download or use cached protocol PDF."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / f"{protocol_id}.pdf"

    if cache_path.exists():
        logger.info(f"Using cached PDF for {protocol_id}")
        return cache_path.read_bytes()

    logger.info(f"Downloading {protocol_id} from {url}")
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        pdf_bytes = resp.content
        cache_path.write_bytes(pdf_bytes)
        return pdf_bytes


def load_annotation(protocol_id: str) -> dict | None:
    """Load ground truth annotation if it exists."""
    path = ANNOTATIONS_DIR / f"{protocol_id}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def compare_cells(extracted_cells, ground_truth_cells) -> list[CellMetric]:
    """Compare extracted cells against ground truth."""
    metrics = []

    gt_map = {(c["row"], c["col"]): c for c in ground_truth_cells}
    ex_map = {(c.row, c.col): c for c in extracted_cells}

    for key, gt in gt_map.items():
        extracted = ex_map.get(key)
        if extracted:
            match = extracted.raw_value.strip().lower() == gt["value"].strip().lower()
        else:
            match = False

        metrics.append(CellMetric(
            row=key[0],
            col=key[1],
            expected=gt["value"],
            extracted=extracted.raw_value if extracted else "",
            match=match,
            difficulty=gt.get("difficulty", "moderate"),
        ))

    return metrics


async def evaluate_protocol(
    protocol_entry: dict,
    config: PipelineConfig,
) -> ProtocolMetric:
    """Run extraction on a single protocol and evaluate against ground truth."""
    protocol_id = protocol_entry["id"]
    metric = ProtocolMetric(
        protocol_id=protocol_id,
        complexity_tier=protocol_entry["complexity_tier"],
    )

    try:
        pdf_bytes = await download_protocol(protocol_entry["url"], protocol_id)

        orchestrator = PipelineOrchestrator(config)
        start = time.time()
        result = await orchestrator.run(pdf_bytes, f"{protocol_id}.pdf")
        metric.processing_time = time.time() - start

        annotation = load_annotation(protocol_id)
        if annotation:
            for gt_table in annotation.get("tables", []):
                # Find matching extracted table
                matching = [t for t in result.tables if t.table_id == gt_table["table_id"]]
                if matching:
                    cell_metrics = compare_cells(
                        matching[0].cells,
                        gt_table.get("ground_truth_cells", []),
                    )
                    metric.table_metrics.append(TableMetric(
                        table_id=gt_table["table_id"],
                        cell_metrics=cell_metrics,
                    ))
        else:
            logger.warning(f"No annotation found for {protocol_id} — extraction-only mode")

    except Exception as e:
        logger.error(f"Evaluation failed for {protocol_id}: {e}")
        metric.error = str(e)

    return metric


async def run_evaluation(
    protocol_ids: list[str] | None = None,
    config: PipelineConfig | None = None,
) -> list[ProtocolMetric]:
    """Run evaluation across selected protocols."""
    registry = load_registry()
    config = config or PipelineConfig()

    if protocol_ids:
        protocols = [p for p in registry["protocols"] if p["id"] in protocol_ids]
    else:
        protocols = registry["protocols"]

    logger.info(f"Evaluating {len(protocols)} protocols")
    metrics = []

    for proto in protocols:
        logger.info(f"--- {proto['id']}: {proto['title']} (Tier {proto['complexity_tier']}) ---")
        metric = await evaluate_protocol(proto, config)
        metrics.append(metric)

        if metric.error:
            logger.error(f"  FAILED: {metric.error}")
        elif metric.table_metrics:
            logger.info(
                f"  Precision: {metric.overall_precision:.1%} "
                f"({sum(t.correct for t in metric.table_metrics)}/"
                f"{sum(t.total for t in metric.table_metrics)} cells) "
                f"in {metric.processing_time:.1f}s"
            )
        else:
            logger.info(f"  No ground truth — extraction completed in {metric.processing_time:.1f}s")

    return metrics


def print_report(metrics: list[ProtocolMetric]):
    """Print a summary report."""
    print("\n" + "=" * 80)
    print("GOLDEN SET EVALUATION REPORT")
    print("=" * 80)

    for m in metrics:
        status = "FAIL" if m.error else "PASS"
        precision = f"{m.overall_precision:.1%}" if m.table_metrics else "N/A"
        print(f"  {m.protocol_id} (Tier {m.complexity_tier}): {status} | "
              f"Precision: {precision} | Time: {m.processing_time:.1f}s")

    # Aggregate by tier
    print("\n--- By Complexity Tier ---")
    for tier in sorted(set(m.complexity_tier for m in metrics)):
        tier_metrics = [m for m in metrics if m.complexity_tier == tier and m.table_metrics]
        if tier_metrics:
            total = sum(sum(t.total for t in m.table_metrics) for m in tier_metrics)
            correct = sum(sum(t.correct for t in m.table_metrics) for m in tier_metrics)
            precision = correct / total if total > 0 else 0
            print(f"  Tier {tier}: {precision:.1%} ({correct}/{total} cells)")

    print("=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Golden Set Evaluation")
    parser.add_argument("--protocol", nargs="*", help="Protocol IDs (e.g., P-01 P-03)")
    parser.add_argument("--all", action="store_true", help="Evaluate all protocols")
    parser.add_argument("--tier", type=int, help="Evaluate protocols in a specific tier")
    parser.add_argument("--report", action="store_true", help="Print summary report")
    args = parser.parse_args()

    protocol_ids = None
    if args.protocol:
        protocol_ids = args.protocol
    elif args.tier:
        registry = load_registry()
        protocol_ids = [
            p["id"] for p in registry["protocols"]
            if p["complexity_tier"] == args.tier
        ]
    elif not args.all:
        print("Specify --protocol, --tier, or --all")
        sys.exit(1)

    metrics = asyncio.run(run_evaluation(protocol_ids))

    if args.report:
        print_report(metrics)
