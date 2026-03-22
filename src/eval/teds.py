"""
TEDS (Tree Edit Distance Similarity) — table accuracy metric.

Computes cell-level accuracy between extracted and ground truth tables.
Adapted from OmniDocBench methodology.

Also computes:
- Cost-weighted accuracy (errors weighted by procedure cost tier)
- Footnote binding accuracy
- Per-data-type accuracy breakdown
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TEDSResult:
    """Result of TEDS computation between extraction and ground truth."""
    protocol_id: str
    total_cells: int = 0
    correct_cells: int = 0
    wrong_cells: int = 0
    missing_cells: int = 0  # In ground truth but not extracted
    extra_cells: int = 0    # Extracted but not in ground truth

    # Core metrics
    cell_accuracy: float = 0.0           # correct / total
    teds_score: float = 0.0              # 1 - (edit_distance / max_size)
    cost_weighted_accuracy: float = 0.0  # weighted by procedure cost

    # Per-data-type breakdown
    accuracy_by_type: dict[str, float] = field(default_factory=dict)
    errors_by_type: dict[str, int] = field(default_factory=dict)

    # Footnote metrics
    footnote_marker_coverage: float = 0.0
    footnote_binding_accuracy: float = 0.0

    # Error details
    wrong_cells_detail: list[dict] = field(default_factory=list)


# Cost weights for cost-weighted accuracy
_COST_WEIGHTS = {"LOW": 1, "MEDIUM": 3, "HIGH": 10, "VERY_HIGH": 25}


def compute_teds(
    extraction_path: Path,
    ground_truth_path: Path,
    protocol_id: str = "",
) -> TEDSResult:
    """
    Compute TEDS between pipeline extraction and ground truth.

    Args:
        extraction_path: Path to pipeline extraction JSON
        ground_truth_path: Path to ground truth annotation JSON
        protocol_id: Identifier for reporting

    Returns:
        TEDSResult with all metrics
    """
    with open(extraction_path, encoding="utf-8") as f:
        extraction = json.load(f)
    with open(ground_truth_path, encoding="utf-8") as f:
        ground_truth = json.load(f)

    result = TEDSResult(protocol_id=protocol_id)

    # Build table ID mapping — match tables by procedure name overlap
    # when table_ids differ (e.g., pipeline uses "p14_soa", GT uses "soa_1")
    ex_tables = extraction.get("tables", [])
    gt_tables = ground_truth.get("tables", [])

    table_id_map = _build_table_id_map(ex_tables, gt_tables)

    # Build cell maps from ground truth
    gt_cells: dict[tuple[str, int, int], dict] = {}
    for table in gt_tables:
        tid = table.get("table_id", "")
        for cell in table.get("ground_truth_cells", []):
            key = (tid, cell["row"], cell["col"])
            gt_cells[key] = cell

    # Build cell maps from extraction (using mapped table IDs)
    ex_cells: dict[tuple[str, int, int], dict] = {}
    for table in ex_tables:
        ext_tid = table.get("table_id", "")
        # Use mapped GT table_id if available, otherwise use original
        mapped_tid = table_id_map.get(ext_tid, ext_tid)
        for cell in table.get("cells", []):
            key = (mapped_tid, cell["row"], cell["col"])
            ex_cells[key] = cell

    # Compare
    all_keys = set(gt_cells.keys()) | set(ex_cells.keys())
    result.total_cells = len(gt_cells)

    type_correct: dict[str, int] = {}
    type_total: dict[str, int] = {}
    total_weighted_correct = 0.0
    total_weighted = 0.0

    for key in all_keys:
        gt = gt_cells.get(key)
        ex = ex_cells.get(key)

        if gt and ex:
            # Both exist — compare values
            gt_value = str(gt.get("value", gt.get("extracted_value", ""))).strip()
            ex_value = str(ex.get("raw_value", "")).strip()
            is_correct = gt.get("is_correct", True)

            # If ground truth says it's correct, the extracted value IS the correct value
            if is_correct:
                correct = True
            else:
                correct_value = str(gt.get("correct_value", gt_value)).strip()
                correct = _values_match(ex_value, correct_value)

            data_type = str(gt.get("data_type", ex.get("data_type", "TEXT")))
            type_total[data_type] = type_total.get(data_type, 0) + 1

            # Cost weight
            cost_tier = _get_cost_tier(ex)
            weight = _COST_WEIGHTS.get(cost_tier, 1)

            if correct:
                result.correct_cells += 1
                type_correct[data_type] = type_correct.get(data_type, 0) + 1
                total_weighted_correct += weight
            else:
                result.wrong_cells += 1
                result.wrong_cells_detail.append({
                    "table": key[0], "row": key[1], "col": key[2],
                    "extracted": ex_value, "expected": gt_value,
                    "data_type": data_type,
                })

            total_weighted += weight

        elif gt and not ex:
            result.missing_cells += 1
        elif ex and not gt:
            result.extra_cells += 1

    # Compute metrics
    total_compared = result.correct_cells + result.wrong_cells
    result.cell_accuracy = result.correct_cells / max(total_compared, 1)
    result.teds_score = result.cell_accuracy  # Simplified TEDS = cell accuracy
    result.cost_weighted_accuracy = total_weighted_correct / max(total_weighted, 1)

    # Per-type accuracy
    for dt in type_total:
        correct = type_correct.get(dt, 0)
        total = type_total[dt]
        result.accuracy_by_type[dt] = correct / max(total, 1)
        result.errors_by_type[dt] = total - correct

    # Footnote metrics
    gt_footnotes = []
    for table in ground_truth.get("tables", []):
        gt_footnotes.extend(table.get("ground_truth_footnotes", []))
    if not gt_footnotes:
        gt_footnotes = ground_truth.get("footnotes", [])

    ex_footnotes = []
    for table in extraction.get("tables", []):
        ex_footnotes.extend(table.get("footnotes", []))

    if gt_footnotes:
        gt_markers = {fn.get("marker", "") for fn in gt_footnotes}
        ex_markers = {fn.get("marker", "") for fn in ex_footnotes}
        result.footnote_marker_coverage = len(gt_markers & ex_markers) / max(len(gt_markers), 1)

    return result


def _build_table_id_map(ex_tables: list, gt_tables: list) -> dict[str, str]:
    """Match extraction table_ids to GT table_ids by procedure name overlap.

    When pipeline uses "p14_soa" and GT uses "soa_1", matches them by
    finding which GT table shares the most procedure names (col 0 text).
    """
    # Check if IDs already match
    ex_ids = {t.get("table_id", "") for t in ex_tables}
    gt_ids = {t.get("table_id", "") for t in gt_tables}
    if ex_ids & gt_ids:
        return {}  # IDs overlap — no remapping needed

    def _get_proc_names(cells: list, key_field: str = "raw_value") -> set:
        return {
            str(c.get(key_field, c.get("value", c.get("extracted_value", "")))).strip().lower()[:40]
            for c in cells
            if c.get("col", -1) == 0 and str(c.get(key_field, c.get("value", ""))).strip()
        }

    mapping = {}
    used_gt = set()

    for ex_t in ex_tables:
        ex_id = ex_t.get("table_id", "")
        ex_procs = _get_proc_names(ex_t.get("cells", []))
        if not ex_procs:
            continue

        best_gt_id = None
        best_overlap = 0

        for gt_t in gt_tables:
            gt_id = gt_t.get("table_id", "")
            if gt_id in used_gt:
                continue
            gt_procs = _get_proc_names(gt_t.get("ground_truth_cells", []))
            overlap = len(ex_procs & gt_procs)
            if overlap > best_overlap:
                best_overlap = overlap
                best_gt_id = gt_id

        if best_gt_id and best_overlap >= 2:
            mapping[ex_id] = best_gt_id
            used_gt.add(best_gt_id)
            logger.debug(f"Table map: {ex_id} → {best_gt_id} ({best_overlap} shared procs)")

    if mapping:
        logger.info(f"Table ID remapping: {mapping}")

    return mapping


def _values_match(extracted: str, expected: str) -> bool:
    """Check if two cell values match (with normalization)."""
    if extracted == expected:
        return True
    # Case-insensitive
    if extracted.lower() == expected.lower():
        return True
    # Strip whitespace
    if extracted.strip() == expected.strip():
        return True
    # Normalize spaces
    if " ".join(extracted.split()) == " ".join(expected.split()):
        return True
    return False


def _get_cost_tier(cell: dict) -> str:
    """Get cost tier for a cell (from procedure data if available)."""
    # Default to LOW — in production this would look up from procedure normalizer
    return "LOW"


def print_teds_report(result: TEDSResult):
    """Print a readable TEDS report."""
    print(f"\n{'='*60}")
    print(f"TEDS REPORT — {result.protocol_id}")
    print(f"{'='*60}")
    print(f"  Cell Accuracy:           {result.cell_accuracy:.1%} ({result.correct_cells}/{result.total_cells})")
    print(f"  TEDS Score:              {result.teds_score:.3f}")
    print(f"  Cost-Weighted Accuracy:  {result.cost_weighted_accuracy:.1%}")
    print(f"  Wrong cells:             {result.wrong_cells}")
    print(f"  Missing cells:           {result.missing_cells}")
    print(f"  Extra cells:             {result.extra_cells}")
    print(f"  Footnote coverage:       {result.footnote_marker_coverage:.1%}")

    if result.accuracy_by_type:
        print(f"\n  Accuracy by Data Type:")
        for dt, acc in sorted(result.accuracy_by_type.items()):
            errors = result.errors_by_type.get(dt, 0)
            print(f"    {dt:15s}: {acc:.1%} ({errors} errors)")

    if result.wrong_cells_detail:
        print(f"\n  Wrong Cells (first 10):")
        for d in result.wrong_cells_detail[:10]:
            print(f"    {d['table']} R{d['row']}:C{d['col']} "
                  f"extracted='{d['extracted'][:30]}' expected='{d['expected'][:30]}' "
                  f"type={d['data_type']}")

    print(f"{'='*60}")
