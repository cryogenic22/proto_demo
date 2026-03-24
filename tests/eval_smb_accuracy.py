"""
SMB Accuracy Evaluation Script.

Builds SMB models for all stored protocols, reports entity counts,
inference rules fired, schedule entry breakdown, and compares
the SMB schedule output against the existing budget calculator output.

Usage:
    python -m tests.eval_smb_accuracy
    # or
    pytest tests/eval_smb_accuracy.py -v -s
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ── Ensure project root on sys.path ──────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def get_stored_protocol_ids() -> list[str]:
    """Find all stored protocol JSON files."""
    protocol_dir = ROOT / "data" / "protocols"
    if not protocol_dir.exists():
        return []
    return [p.stem for p in sorted(protocol_dir.glob("*.json"))]


def load_protocol_data(protocol_id: str) -> dict[str, Any] | None:
    """Load stored protocol JSON."""
    path = ROOT / "data" / "protocols" / f"{protocol_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_smb_model(protocol_data: dict[str, Any]) -> dict[str, Any]:
    """Build SMB model and return analysis dict."""
    from src.smb.core.engine import SMBEngine
    from src.smb.core.query import (
        get_budget_schedule,
        get_visit_timeline,
        get_procedure_frequency,
    )

    engine = SMBEngine(domain="protocol")
    start = time.time()
    result = engine.build_from_protocol_json(protocol_data)
    elapsed = time.time() - start

    model = result.model
    summary = model.summary()
    schedule = get_budget_schedule(model)
    timeline = get_visit_timeline(model)

    # Gather procedure frequencies
    proc_freqs = []
    for proc in model.get_entities("Procedure"):
        freq = get_procedure_frequency(model, proc.name)
        proc_freqs.append(freq)

    # Schedule entry breakdown
    entries = model.get_schedule_entries()
    firm_count = sum(1 for e in entries if e.get_property("mark_type") in ("firm", "span"))
    conditional_count = sum(1 for e in entries if e.get_property("mark_type") == "conditional")
    excluded_count = sum(1 for e in entries if e.get_property("mark_type") == "excluded")

    return {
        "protocol_id": protocol_data.get("protocol_id", "unknown"),
        "document_name": protocol_data.get("document_name", ""),
        "build_time_seconds": round(elapsed, 3),
        "summary": summary,
        "entity_counts": summary.get("entity_types", {}),
        "relationship_counts": summary.get("relationship_types", {}),
        "total_entities": summary.get("total_entities", 0),
        "total_relationships": summary.get("total_relationships", 0),
        "schedule_entries": len(entries),
        "firm_entries": firm_count,
        "conditional_entries": conditional_count,
        "excluded_entries": excluded_count,
        "visits": len(timeline),
        "procedures": len(model.get_entities("Procedure")),
        "footnotes": len(model.get_entities("Footnote")),
        "inference_rules_fired": result.inference_rules_fired,
        "inference_rules_count": len(result.inference_rules_fired),
        "validation_passed": result.validation_passed,
        "validation_errors": result.validation_errors,
        "validation_warnings": result.validation_warnings,
        "budget_schedule_rows": len(schedule),
        "budget_schedule": schedule,
        "timeline": timeline,
        "procedure_frequencies": proc_freqs,
    }


def compare_with_budget_lines(
    smb_schedule: list[dict[str, Any]],
    protocol_data: dict[str, Any],
) -> dict[str, Any]:
    """Compare SMB schedule output against existing budget_lines in the protocol."""
    budget_lines = protocol_data.get("budget_lines", [])
    if not budget_lines:
        return {"has_existing_budget": False}

    # Build lookup by canonical_name
    existing = {bl.get("canonical_name", ""): bl for bl in budget_lines}
    smb_lookup = {s["canonical_name"]: s for s in smb_schedule}

    matched = 0
    occ_match = 0
    occ_mismatch = 0
    only_in_budget = []
    only_in_smb = []

    for name, bl in existing.items():
        if name in smb_lookup:
            matched += 1
            bl_total = bl.get("total_occurrences", 0)
            smb_total = smb_lookup[name]["total_occurrences"]
            if bl_total == smb_total:
                occ_match += 1
            else:
                occ_mismatch += 1
        else:
            only_in_budget.append(name)

    for name in smb_lookup:
        if name not in existing:
            only_in_smb.append(name)

    return {
        "has_existing_budget": True,
        "existing_budget_rows": len(budget_lines),
        "smb_schedule_rows": len(smb_schedule),
        "matched_procedures": matched,
        "occurrence_match": occ_match,
        "occurrence_mismatch": occ_mismatch,
        "only_in_existing_budget": only_in_budget,
        "only_in_smb_schedule": only_in_smb,
    }


def run_evaluation() -> dict[str, Any]:
    """Run full evaluation across all stored protocols."""
    protocol_ids = get_stored_protocol_ids()
    print(f"\n{'='*70}")
    print(f"SMB Accuracy Evaluation -- {len(protocol_ids)} protocols")
    print(f"{'='*70}\n")

    results: list[dict[str, Any]] = []
    totals = {
        "total_entities": 0,
        "total_relationships": 0,
        "total_schedule_entries": 0,
        "total_firm": 0,
        "total_conditional": 0,
        "total_inferences": 0,
        "total_build_time": 0.0,
        "validation_pass_count": 0,
    }

    for pid in protocol_ids:
        protocol_data = load_protocol_data(pid)
        if not protocol_data:
            print(f"  SKIP {pid} -- could not load")
            continue

        print(f"  Building: {pid}...", end=" ", flush=True)
        try:
            result = build_smb_model(protocol_data)
            comparison = compare_with_budget_lines(
                result["budget_schedule"], protocol_data
            )
            result["budget_comparison"] = comparison

            print(
                f"OK -- {result['total_entities']} entities, "
                f"{result['schedule_entries']} schedule entries, "
                f"{result['inference_rules_count']} rules, "
                f"{result['build_time_seconds']:.2f}s"
            )

            totals["total_entities"] += result["total_entities"]
            totals["total_relationships"] += result["total_relationships"]
            totals["total_schedule_entries"] += result["schedule_entries"]
            totals["total_firm"] += result["firm_entries"]
            totals["total_conditional"] += result["conditional_entries"]
            totals["total_inferences"] += result["inference_rules_count"]
            totals["total_build_time"] += result["build_time_seconds"]
            if result["validation_passed"]:
                totals["validation_pass_count"] += 1

            results.append(result)
        except Exception as e:
            print(f"FAILED -- {e}")
            results.append({
                "protocol_id": pid,
                "error": str(e),
            })

    # Print summary
    n = len([r for r in results if "error" not in r])
    print(f"\n{'='*70}")
    print(f"Summary: {n}/{len(protocol_ids)} protocols built successfully")
    print(f"{'='*70}")
    print(f"  Total entities:         {totals['total_entities']}")
    print(f"  Total relationships:    {totals['total_relationships']}")
    print(f"  Total schedule entries:  {totals['total_schedule_entries']}")
    print(f"    Firm:                 {totals['total_firm']}")
    print(f"    Conditional:          {totals['total_conditional']}")
    print(f"  Total inference rules:  {totals['total_inferences']}")
    print(f"  Total build time:       {totals['total_build_time']:.2f}s")
    print(f"  Validation passed:      {totals['validation_pass_count']}/{n}")

    # Budget comparison summary
    print(f"\n{'-'*70}")
    print("Budget Comparison:")
    for r in results:
        if "error" in r:
            continue
        comp = r.get("budget_comparison", {})
        if not comp.get("has_existing_budget"):
            print(f"  {r['protocol_id']}: no existing budget lines")
            continue
        print(
            f"  {r['protocol_id']}: "
            f"matched={comp['matched_procedures']}, "
            f"occ_match={comp['occurrence_match']}, "
            f"occ_mismatch={comp['occurrence_mismatch']}, "
            f"only_budget={len(comp['only_in_existing_budget'])}, "
            f"only_smb={len(comp['only_in_smb_schedule'])}"
        )

    # Save report
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "protocols_evaluated": len(protocol_ids),
        "protocols_success": n,
        "totals": totals,
        "results": results,
    }

    report_dir = ROOT / ".quality-reports"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"smb_eval_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to: {report_path}")

    return report


# ── Pytest test function ─────────────────────────────────────────────────────


def test_smb_builds_all_protocols():
    """Test that SMB can build models for all stored protocols."""
    report = run_evaluation()
    n_success = report["protocols_success"]
    n_total = report["protocols_evaluated"]
    assert n_success > 0, "No protocols built successfully"
    assert n_success == n_total, (
        f"Only {n_success}/{n_total} protocols built successfully"
    )


# ── Direct execution ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_evaluation()
