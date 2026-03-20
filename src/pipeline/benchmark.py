"""
Benchmark Reporter — consolidates extraction results across protocols
into a single comparative report.

Tracks key dimensions:
- Section parsing accuracy
- SoA table detection
- Cell extraction volume
- Footnote resolution
- Procedure mapping coverage
- Confidence scores
- Processing time and cost
- Failures and warnings

Produces a single HTML benchmark report showing success/failure across
all tested protocols with trend analysis.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BENCHMARK_DIR = Path(".benchmarks")


@dataclass
class ProtocolBenchmark:
    """Results from one protocol extraction run."""
    protocol_id: str
    protocol_name: str
    therapeutic_area: str = ""
    phase: str = ""
    pages: int = 0
    # Section parsing
    sections_found: int = 0
    section_method: str = ""  # "fitz_toc", "toc_text", "header_scan", "llm_fallback"
    # SoA extraction
    tables_found: int = 0
    total_cells: int = 0
    footnotes_resolved: int = 0
    procedures_mapped: int = 0
    procedures_unmapped: int = 0
    avg_confidence: float = 0.0
    cells_flagged: int = 0
    cells_flagged_pct: float = 0.0
    # Budget
    budget_lines: int = 0
    cpt_codes_mapped: int = 0
    # Performance
    processing_time_s: float = 0.0
    estimated_cost_usd: float = 0.0
    # Quality
    warnings: int = 0
    errors: list[str] = field(default_factory=list)
    status: str = "success"  # "success", "partial", "failed"
    timestamp: str = ""


def load_benchmark(path: Path | None = None) -> list[ProtocolBenchmark]:
    """Load existing benchmark data."""
    p = path or (BENCHMARK_DIR / "benchmark.json")
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return [ProtocolBenchmark(**item) for item in data.get("protocols", [])]


def save_benchmark(benchmarks: list[ProtocolBenchmark], path: Path | None = None):
    """Save benchmark data."""
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    p = path or (BENCHMARK_DIR / "benchmark.json")
    data = {
        "version": "1.0",
        "updated": datetime.now(timezone.utc).isoformat(),
        "protocol_count": len(benchmarks),
        "protocols": [_to_dict(b) for b in benchmarks],
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_benchmark(
    benchmark: ProtocolBenchmark,
    path: Path | None = None,
):
    """Add or update a protocol benchmark result."""
    existing = load_benchmark(path)
    # Replace if same protocol_id exists
    existing = [b for b in existing if b.protocol_id != benchmark.protocol_id]
    existing.append(benchmark)
    save_benchmark(existing, path)
    logger.info(f"Benchmark saved for {benchmark.protocol_id}: {benchmark.status}")


def from_pipeline_output(
    result: dict,
    protocol_id: str,
    therapeutic_area: str = "",
    phase: str = "",
) -> ProtocolBenchmark:
    """Create a benchmark entry from pipeline output JSON."""
    tables = result.get("tables", [])
    total_cells = sum(len(t.get("cells", [])) for t in tables)
    total_fn = sum(len(t.get("footnotes", [])) for t in tables)
    total_flagged = sum(len(t.get("flagged_cells", [])) for t in tables)
    confs = [t.get("overall_confidence", 0) for t in tables]
    avg_conf = sum(confs) / len(confs) if confs else 0

    total_procs = sum(len(t.get("procedures", [])) for t in tables)
    unmapped = sum(
        1 for t in tables for p in t.get("procedures", [])
        if p.get("category") == "Unknown"
    )
    cpt = sum(
        1 for t in tables for p in t.get("procedures", [])
        if p.get("code")
    )

    warnings = result.get("warnings", [])
    errors = [w for w in warnings if "failed" in w.lower()]

    status = "success"
    if not tables:
        status = "failed"
    elif errors:
        status = "partial"

    return ProtocolBenchmark(
        protocol_id=protocol_id,
        protocol_name=result.get("document_name", ""),
        therapeutic_area=therapeutic_area,
        phase=phase,
        pages=result.get("total_pages", 0),
        tables_found=len(tables),
        total_cells=total_cells,
        footnotes_resolved=total_fn,
        procedures_mapped=total_procs - unmapped,
        procedures_unmapped=unmapped,
        avg_confidence=round(avg_conf, 3),
        cells_flagged=total_flagged,
        cells_flagged_pct=round(total_flagged / max(total_cells, 1) * 100, 1),
        budget_lines=total_procs,
        cpt_codes_mapped=cpt,
        processing_time_s=round(result.get("processing_time_seconds", 0), 1),
        estimated_cost_usd=round(result.get("processing_time_seconds", 0) / 60 * 0.12, 2),
        warnings=len(warnings),
        errors=errors,
        status=status,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def generate_benchmark_html(benchmarks: list[ProtocolBenchmark] | None = None,
                             path: Path | None = None) -> str:
    """Generate an HTML benchmark comparison report."""
    if benchmarks is None:
        benchmarks = load_benchmark()

    if not benchmarks:
        return "<html><body><h1>No benchmark data yet</h1></body></html>"

    # Sort by protocol_id
    benchmarks = sorted(benchmarks, key=lambda b: b.protocol_id)

    # Compute aggregates
    total = len(benchmarks)
    success = sum(1 for b in benchmarks if b.status == "success")
    partial = sum(1 for b in benchmarks if b.status == "partial")
    failed = sum(1 for b in benchmarks if b.status == "failed")
    avg_conf = sum(b.avg_confidence for b in benchmarks) / total if total else 0
    avg_time = sum(b.processing_time_s for b in benchmarks) / total if total else 0
    total_cells = sum(b.total_cells for b in benchmarks)
    total_fn = sum(b.footnotes_resolved for b in benchmarks)

    # Build rows
    rows = ""
    for b in benchmarks:
        status_class = {"success": "st-pass", "partial": "st-warn", "failed": "st-fail"}.get(b.status, "")
        status_icon = {"success": "&#10003;", "partial": "&#9888;", "failed": "&#10007;"}.get(b.status, "?")
        conf_class = "c-good" if b.avg_confidence >= 0.85 else "c-warn" if b.avg_confidence >= 0.7 else "c-bad"

        rows += f"""<tr>
<td class="{status_class}">{status_icon}</td>
<td><strong>{_h(b.protocol_id)}</strong><br><span class="sub">{_h(b.protocol_name[:40])}</span></td>
<td>{_h(b.therapeutic_area)}</td>
<td class="center">{b.pages}</td>
<td class="center">{b.tables_found}</td>
<td class="center">{b.total_cells}</td>
<td class="center">{b.footnotes_resolved}</td>
<td class="center {conf_class}">{b.avg_confidence:.0%}</td>
<td class="center">{b.cells_flagged_pct:.0f}%</td>
<td class="center">{b.procedures_mapped}/{b.procedures_mapped + b.procedures_unmapped}</td>
<td class="center">{b.cpt_codes_mapped}</td>
<td class="center">{b.processing_time_s:.0f}s</td>
<td class="center">${b.estimated_cost_usd:.2f}</td>
<td class="center">{b.warnings}</td>
</tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ProtoExtract Benchmark Report</title>
<style>
body {{ font-family: 'Segoe UI', system-ui, sans-serif; color: #1e293b; background: #f8fafc; margin: 0; padding: 20px; }}
.container {{ max-width: 1600px; margin: 0 auto; }}
h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; }}
.sub {{ font-size: 10px; color: #94a3b8; }}
.meta {{ font-size: 12px; color: #64748b; margin-bottom: 20px; }}
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 20px; }}
.kpi {{ background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; text-align: center; }}
.kpi-val {{ font-size: 24px; font-weight: 700; }}
.kpi-lbl {{ font-size: 10px; color: #64748b; text-transform: uppercase; }}
.k-blue {{ color: #0284c7; }} .k-green {{ color: #059669; }} .k-amber {{ color: #d97706; }} .k-red {{ color: #dc2626; }}
table {{ width: 100%; border-collapse: collapse; font-size: 11px; background: white; border: 1px solid #e2e8f0; border-radius: 8px; }}
th {{ background: #0f172a; color: white; padding: 8px 6px; text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 0.3px; position: sticky; top: 0; }}
td {{ padding: 6px; border-bottom: 1px solid #f1f5f9; }}
tr:hover {{ background: #f8fafc; }}
.center {{ text-align: center; }}
.st-pass {{ color: #059669; font-size: 14px; text-align: center; }}
.st-warn {{ color: #d97706; font-size: 14px; text-align: center; }}
.st-fail {{ color: #dc2626; font-size: 14px; text-align: center; }}
.c-good {{ color: #059669; font-weight: 600; }}
.c-warn {{ color: #d97706; font-weight: 600; }}
.c-bad {{ color: #dc2626; font-weight: 600; }}
.legend {{ margin-top: 16px; font-size: 11px; color: #64748b; }}
.legend span {{ margin-right: 16px; }}
@media print {{ body {{ background: white; }} th {{ background: #333; }} }}
</style>
</head>
<body>
<div class="container">
<h1>ProtoExtract — Benchmark Report</h1>
<p class="meta">{total} protocols tested | Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>

<div class="kpis">
<div class="kpi"><div class="kpi-val k-green">{success}</div><div class="kpi-lbl">Passed</div></div>
<div class="kpi"><div class="kpi-val k-amber">{partial}</div><div class="kpi-lbl">Partial</div></div>
<div class="kpi"><div class="kpi-val k-red">{failed}</div><div class="kpi-lbl">Failed</div></div>
<div class="kpi"><div class="kpi-val k-blue">{total_cells:,}</div><div class="kpi-lbl">Total Cells</div></div>
<div class="kpi"><div class="kpi-val k-blue">{total_fn}</div><div class="kpi-lbl">Footnotes</div></div>
<div class="kpi"><div class="kpi-val {'k-green' if avg_conf >= 0.85 else 'k-amber'}">{avg_conf:.0%}</div><div class="kpi-lbl">Avg Confidence</div></div>
<div class="kpi"><div class="kpi-val k-blue">{avg_time:.0f}s</div><div class="kpi-lbl">Avg Time</div></div>
</div>

<table>
<thead><tr>
<th></th><th>Protocol</th><th>Area</th><th>Pages</th><th>Tables</th><th>Cells</th>
<th>Foot-notes</th><th>Conf.</th><th>Flagged</th><th>Procs Mapped</th><th>CPT</th>
<th>Time</th><th>Cost</th><th>Warns</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>

<div class="legend">
<span><strong>Status:</strong> &#10003; = all tables extracted | &#9888; = some tables failed | &#10007; = no tables</span><br>
<span><strong>Conf.:</strong> green ≥85% | amber 70-85% | red &lt;70%</span>
</div>
</div>
</body>
</html>"""

    out = path or (BENCHMARK_DIR / "benchmark_report.html")
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return html


def _to_dict(b: ProtocolBenchmark) -> dict:
    return {
        "protocol_id": b.protocol_id,
        "protocol_name": b.protocol_name,
        "therapeutic_area": b.therapeutic_area,
        "phase": b.phase,
        "pages": b.pages,
        "sections_found": b.sections_found,
        "section_method": b.section_method,
        "tables_found": b.tables_found,
        "total_cells": b.total_cells,
        "footnotes_resolved": b.footnotes_resolved,
        "procedures_mapped": b.procedures_mapped,
        "procedures_unmapped": b.procedures_unmapped,
        "avg_confidence": b.avg_confidence,
        "cells_flagged": b.cells_flagged,
        "cells_flagged_pct": b.cells_flagged_pct,
        "budget_lines": b.budget_lines,
        "cpt_codes_mapped": b.cpt_codes_mapped,
        "processing_time_s": b.processing_time_s,
        "estimated_cost_usd": b.estimated_cost_usd,
        "warnings": b.warnings,
        "errors": b.errors,
        "status": b.status,
        "timestamp": b.timestamp,
    }


def _h(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
