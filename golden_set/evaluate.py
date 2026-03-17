"""
Golden Set Evaluation Runner with Repeatability Testing.

Downloads golden set protocols, runs the extraction pipeline multiple times,
compares results against ground truth, and measures run-to-run variability.

Usage:
    # Single run evaluation
    python -m golden_set.evaluate --protocol P-01 --report

    # Repeatability test (10 runs per protocol)
    python -m golden_set.evaluate --protocol P-01 --repeat 10 --report

    # Full golden set, 3 runs each
    python -m golden_set.evaluate --all --repeat 3 --report

    # Specific tier
    python -m golden_set.evaluate --tier 2 --repeat 5 --report
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

from src.models.schema import PipelineConfig, PipelineOutput
from src.pipeline.orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

GOLDEN_SET_DIR = Path(__file__).parent
REGISTRY_PATH = GOLDEN_SET_DIR / "registry.json"
ANNOTATIONS_DIR = GOLDEN_SET_DIR / "annotations"
CACHE_DIR = GOLDEN_SET_DIR / "cached_pdfs"
RESULTS_DIR = GOLDEN_SET_DIR / "results"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CellMetric:
    row: int
    col: int
    expected: str
    extracted: str
    match: bool
    difficulty: str


@dataclass
class TableMetric:
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
        buckets: dict[str, dict[str, int]] = {}
        for m in self.cell_metrics:
            if m.difficulty not in buckets:
                buckets[m.difficulty] = {"correct": 0, "total": 0}
            buckets[m.difficulty]["total"] += 1
            if m.match:
                buckets[m.difficulty]["correct"] += 1
        return {
            k: v["correct"] / v["total"] if v["total"] > 0 else 0.0
            for k, v in buckets.items()
        }


@dataclass
class RunResult:
    """Result of a single extraction run."""
    run_number: int
    tables_found: int
    total_cells: int
    total_footnotes: int
    processing_time: float
    table_metrics: list[TableMetric] = field(default_factory=list)
    error: str | None = None
    # Raw cell values keyed by (table_idx, row, col) for variance calc
    cell_values: dict[tuple[int, int, int], str] = field(default_factory=dict)
    confidence_scores: dict[tuple[int, int, int], float] = field(default_factory=dict)


@dataclass
class CellVariance:
    """Variance data for a single cell across N runs."""
    table_idx: int
    row: int
    col: int
    values: list[str]  # value per run
    confidences: list[float]

    @property
    def is_stable(self) -> bool:
        """True if all runs produced the same value."""
        return len(set(self.values)) <= 1

    @property
    def stability_ratio(self) -> float:
        """Fraction of runs that agree with the majority value."""
        if not self.values:
            return 0.0
        from collections import Counter
        counts = Counter(self.values)
        most_common_count = counts.most_common(1)[0][1]
        return most_common_count / len(self.values)

    @property
    def unique_values(self) -> int:
        return len(set(self.values))


@dataclass
class RepeatabilityResult:
    """Aggregated result across N runs of the same protocol."""
    protocol_id: str
    complexity_tier: int
    num_runs: int
    runs: list[RunResult] = field(default_factory=list)
    cell_variances: list[CellVariance] = field(default_factory=list)

    @property
    def avg_tables(self) -> float:
        counts = [r.tables_found for r in self.runs if not r.error]
        return sum(counts) / len(counts) if counts else 0

    @property
    def table_count_stable(self) -> bool:
        counts = [r.tables_found for r in self.runs if not r.error]
        return len(set(counts)) <= 1

    @property
    def avg_cells(self) -> float:
        counts = [r.total_cells for r in self.runs if not r.error]
        return sum(counts) / len(counts) if counts else 0

    @property
    def cell_count_variance(self) -> float:
        counts = [r.total_cells for r in self.runs if not r.error]
        if len(counts) < 2:
            return 0.0
        mean = sum(counts) / len(counts)
        return math.sqrt(sum((c - mean) ** 2 for c in counts) / (len(counts) - 1))

    @property
    def avg_processing_time(self) -> float:
        times = [r.processing_time for r in self.runs if not r.error]
        return sum(times) / len(times) if times else 0

    @property
    def stable_cells_pct(self) -> float:
        """Percentage of cells that are identical across all runs."""
        if not self.cell_variances:
            return 0.0
        stable = sum(1 for cv in self.cell_variances if cv.is_stable)
        return stable / len(self.cell_variances) * 100

    @property
    def avg_stability_ratio(self) -> float:
        """Average stability ratio across all cells."""
        if not self.cell_variances:
            return 0.0
        return sum(cv.stability_ratio for cv in self.cell_variances) / len(self.cell_variances)

    @property
    def unstable_cells(self) -> list[CellVariance]:
        """Cells that varied across runs."""
        return [cv for cv in self.cell_variances if not cv.is_stable]

    @property
    def error_rate(self) -> float:
        return sum(1 for r in self.runs if r.error) / len(self.runs) if self.runs else 0


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def load_registry() -> dict:
    with open(REGISTRY_PATH) as f:
        return json.load(f)


async def download_protocol(url: str, protocol_id: str) -> bytes:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / f"{protocol_id}.pdf"
    if cache_path.exists():
        logger.info(f"Using cached PDF for {protocol_id}")
        return cache_path.read_bytes()
    logger.info(f"Downloading {protocol_id} from {url}")
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        cache_path.write_bytes(resp.content)
        return resp.content


def load_annotation(protocol_id: str) -> dict | None:
    path = ANNOTATIONS_DIR / f"{protocol_id}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def compare_cells(extracted_cells, ground_truth_cells) -> list[CellMetric]:
    gt_map = {(c["row"], c["col"]): c for c in ground_truth_cells}
    ex_map = {(c.row, c.col): c for c in extracted_cells}

    metrics = []
    for key, gt in gt_map.items():
        extracted = ex_map.get(key)
        match = (
            extracted.raw_value.strip().lower() == gt["value"].strip().lower()
            if extracted else False
        )
        metrics.append(CellMetric(
            row=key[0], col=key[1],
            expected=gt["value"],
            extracted=extracted.raw_value if extracted else "",
            match=match,
            difficulty=gt.get("difficulty", "moderate"),
        ))
    return metrics


async def run_single_extraction(
    pdf_bytes: bytes,
    protocol_id: str,
    run_number: int,
    config: PipelineConfig,
) -> RunResult:
    """Execute one extraction run and capture results."""
    result = RunResult(run_number=run_number, tables_found=0, total_cells=0,
                       total_footnotes=0, processing_time=0)
    try:
        orchestrator = PipelineOrchestrator(config)
        start = time.time()
        output = await orchestrator.run(pdf_bytes, f"{protocol_id}.pdf")
        result.processing_time = time.time() - start
        result.tables_found = len(output.tables)
        result.total_cells = sum(len(t.cells) for t in output.tables)
        result.total_footnotes = sum(len(t.footnotes) for t in output.tables)

        # Capture per-cell values for variance calculation
        for tidx, table in enumerate(output.tables):
            for cell in table.cells:
                key = (tidx, cell.row, cell.col)
                result.cell_values[key] = cell.raw_value.strip()
                result.confidence_scores[key] = cell.confidence

        # Compare against ground truth if available
        annotation = load_annotation(protocol_id)
        if annotation:
            for gt_table in annotation.get("tables", []):
                matching = [t for t in output.tables if t.table_id == gt_table["table_id"]]
                if matching:
                    cell_metrics = compare_cells(
                        matching[0].cells,
                        gt_table.get("ground_truth_cells", []),
                    )
                    result.table_metrics.append(TableMetric(
                        table_id=gt_table["table_id"],
                        cell_metrics=cell_metrics,
                    ))

    except Exception as e:
        logger.error(f"Run {run_number} failed for {protocol_id}: {e}")
        result.error = str(e)

    return result


def compute_cell_variance(runs: list[RunResult]) -> list[CellVariance]:
    """Compute per-cell variance across multiple runs."""
    successful_runs = [r for r in runs if not r.error]
    if len(successful_runs) < 2:
        return []

    # Collect all cell keys seen across any run
    all_keys: set[tuple[int, int, int]] = set()
    for r in successful_runs:
        all_keys.update(r.cell_values.keys())

    variances = []
    for key in sorted(all_keys):
        values = []
        confidences = []
        for r in successful_runs:
            val = r.cell_values.get(key, "")
            conf = r.confidence_scores.get(key, 0.0)
            values.append(val)
            confidences.append(conf)

        variances.append(CellVariance(
            table_idx=key[0], row=key[1], col=key[2],
            values=values, confidences=confidences,
        ))

    return variances


# ---------------------------------------------------------------------------
# Evaluation runners
# ---------------------------------------------------------------------------

async def evaluate_protocol_with_repeatability(
    protocol_entry: dict,
    config: PipelineConfig,
    num_runs: int = 1,
) -> RepeatabilityResult:
    """Run extraction N times on one protocol and measure variability."""
    protocol_id = protocol_entry["id"]
    logger.info(f"=== {protocol_id}: {protocol_entry['title']} ({num_runs} runs) ===")

    result = RepeatabilityResult(
        protocol_id=protocol_id,
        complexity_tier=protocol_entry["complexity_tier"],
        num_runs=num_runs,
    )

    try:
        pdf_bytes = await download_protocol(protocol_entry["url"], protocol_id)
    except Exception as e:
        logger.error(f"Download failed for {protocol_id}: {e}")
        result.runs.append(RunResult(
            run_number=0, tables_found=0, total_cells=0,
            total_footnotes=0, processing_time=0, error=str(e),
        ))
        return result

    for i in range(num_runs):
        logger.info(f"  Run {i+1}/{num_runs}...")
        run = await run_single_extraction(pdf_bytes, protocol_id, i + 1, config)
        result.runs.append(run)

        if run.error:
            logger.error(f"  Run {i+1} FAILED: {run.error}")
        else:
            logger.info(
                f"  Run {i+1}: {run.tables_found} tables, {run.total_cells} cells, "
                f"{run.total_footnotes} footnotes, {run.processing_time:.0f}s"
            )

    # Compute variance
    if num_runs >= 2:
        result.cell_variances = compute_cell_variance(result.runs)
        logger.info(
            f"  Stability: {result.stable_cells_pct:.1f}% cells identical across runs, "
            f"{len(result.unstable_cells)} unstable cells"
        )

    return result


async def run_evaluation(
    protocol_ids: list[str] | None = None,
    config: PipelineConfig | None = None,
    num_runs: int = 1,
) -> list[RepeatabilityResult]:
    """Run evaluation across selected protocols."""
    registry = load_registry()
    config = config or PipelineConfig()

    if protocol_ids:
        protocols = [p for p in registry["protocols"] if p["id"] in protocol_ids]
    else:
        protocols = registry["protocols"]

    logger.info(f"Evaluating {len(protocols)} protocols, {num_runs} run(s) each")
    results = []

    for proto in protocols:
        result = await evaluate_protocol_with_repeatability(proto, config, num_runs)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(results: list[RepeatabilityResult]):
    """Print comprehensive evaluation report."""
    num_runs = results[0].num_runs if results else 1
    is_repeat = num_runs > 1

    print()
    print("=" * 90)
    print(f"GOLDEN SET EVALUATION REPORT — {len(results)} protocols, {num_runs} run(s) each")
    print(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 90)

    # Per-protocol summary
    print(f"\n{'Protocol':<10} {'Tier':>4} {'Tables':>7} {'Cells':>7} {'Footnotes':>9} {'Time':>7}", end="")
    if is_repeat:
        print(f" {'Stability':>10} {'Unstable':>8} {'Errors':>6}", end="")
    print()
    print("-" * (55 + (25 if is_repeat else 0)))

    for r in results:
        successful = [run for run in r.runs if not run.error]
        if not successful:
            print(f"  {r.protocol_id:<8} {r.complexity_tier:>4}   ALL RUNS FAILED")
            continue

        avg_tables = sum(run.tables_found for run in successful) / len(successful)
        avg_cells = sum(run.total_cells for run in successful) / len(successful)
        avg_fn = sum(run.total_footnotes for run in successful) / len(successful)
        avg_time = sum(run.processing_time for run in successful) / len(successful)

        print(f"  {r.protocol_id:<8} {r.complexity_tier:>4} {avg_tables:>7.0f} {avg_cells:>7.0f} {avg_fn:>9.0f} {avg_time:>6.0f}s", end="")
        if is_repeat:
            print(f" {r.stable_cells_pct:>9.1f}% {len(r.unstable_cells):>8} {r.error_rate:>5.0%}", end="")
        print()

    # Aggregate by tier
    print(f"\n{'--- By Complexity Tier ---':^{55 + (25 if is_repeat else 0)}}")
    tiers = sorted(set(r.complexity_tier for r in results))
    for tier in tiers:
        tier_results = [r for r in results if r.complexity_tier == tier]
        successful_runs = [run for r in tier_results for run in r.runs if not run.error]
        if not successful_runs:
            continue
        avg_tables = sum(run.tables_found for run in successful_runs) / len(successful_runs)
        avg_cells = sum(run.total_cells for run in successful_runs) / len(successful_runs)
        error_rate = sum(1 for r in tier_results for run in r.runs if run.error) / sum(r.num_runs for r in tier_results)

        line = f"  Tier {tier}: {len(tier_results)} protocols | avg {avg_tables:.0f} tables, {avg_cells:.0f} cells | {error_rate:.0%} error rate"
        if is_repeat:
            stable_pcts = [r.stable_cells_pct for r in tier_results if r.cell_variances]
            if stable_pcts:
                line += f" | {sum(stable_pcts)/len(stable_pcts):.1f}% stability"
        print(line)

    # Repeatability-specific report
    if is_repeat:
        print(f"\n{'--- Repeatability Analysis ---':^90}")

        all_variances = [cv for r in results for cv in r.cell_variances]
        total_cells = len(all_variances)
        stable = sum(1 for cv in all_variances if cv.is_stable)
        unstable = total_cells - stable

        print(f"  Total cells tracked:    {total_cells}")
        print(f"  Stable (identical):     {stable} ({stable/total_cells*100:.1f}%)" if total_cells else "")
        print(f"  Unstable (varied):      {unstable} ({unstable/total_cells*100:.1f}%)" if total_cells else "")

        if all_variances:
            avg_ratio = sum(cv.stability_ratio for cv in all_variances) / len(all_variances)
            print(f"  Avg stability ratio:    {avg_ratio:.1%}")

        # Worst offenders — most unstable cells
        unstable_cells = [cv for cv in all_variances if not cv.is_stable]
        if unstable_cells:
            worst = sorted(unstable_cells, key=lambda cv: cv.stability_ratio)[:10]
            print(f"\n  Top 10 most unstable cells:")
            for cv in worst:
                unique = sorted(set(cv.values))
                print(f"    Table {cv.table_idx} ({cv.row},{cv.col}): "
                      f"{cv.unique_values} variants, stability={cv.stability_ratio:.0%} "
                      f"— values: {unique[:5]}")

        # Table count stability
        print(f"\n  Table count consistency:")
        for r in results:
            counts = [run.tables_found for run in r.runs if not run.error]
            if counts:
                stable_str = "STABLE" if len(set(counts)) == 1 else f"VARIES ({min(counts)}-{max(counts)})"
                print(f"    {r.protocol_id}: {stable_str} ({counts})")

    print("=" * 90)


def save_results(results: list[RepeatabilityResult], tag: str = ""):
    """Save evaluation results to JSON for tracking over time."""
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"eval_{timestamp}{'_' + tag if tag else ''}.json"
    path = RESULTS_DIR / filename

    data = {
        "timestamp": timestamp,
        "tag": tag,
        "num_protocols": len(results),
        "protocols": [],
    }

    for r in results:
        proto_data = {
            "protocol_id": r.protocol_id,
            "complexity_tier": r.complexity_tier,
            "num_runs": r.num_runs,
            "avg_tables": r.avg_tables,
            "avg_cells": r.avg_cells,
            "stable_cells_pct": r.stable_cells_pct,
            "avg_stability_ratio": r.avg_stability_ratio,
            "unstable_cell_count": len(r.unstable_cells),
            "error_rate": r.error_rate,
            "avg_processing_time": r.avg_processing_time,
            "runs": [
                {
                    "run_number": run.run_number,
                    "tables_found": run.tables_found,
                    "total_cells": run.total_cells,
                    "total_footnotes": run.total_footnotes,
                    "processing_time": run.processing_time,
                    "error": run.error,
                }
                for run in r.runs
            ],
        }
        data["protocols"].append(proto_data)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Results saved to {path}")
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Golden Set Evaluation with Repeatability Testing")
    parser.add_argument("--protocol", nargs="*", help="Protocol IDs (e.g., P-01 P-03)")
    parser.add_argument("--all", action="store_true", help="Evaluate all protocols")
    parser.add_argument("--tier", type=int, help="Evaluate protocols in a specific tier")
    parser.add_argument("--repeat", type=int, default=1, help="Number of runs per protocol (default: 1)")
    parser.add_argument("--report", action="store_true", help="Print summary report")
    parser.add_argument("--save", action="store_true", help="Save results to JSON")
    parser.add_argument("--tag", default="", help="Tag for saved results (e.g., 'v0.2_sonnet')")
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

    results = asyncio.run(run_evaluation(protocol_ids, num_runs=args.repeat))

    if args.report:
        print_report(results)

    if args.save:
        save_results(results, args.tag)
