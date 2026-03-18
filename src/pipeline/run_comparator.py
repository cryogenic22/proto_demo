"""
Run Comparator — compares extraction results across pipeline versions.

Loads previous run results and compares against current results to
measure improvement or regression at the cell level.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

OUTPUTS_DIR = Path(__file__).parent.parent.parent / "output"


@dataclass
class CellDelta:
    row: int
    col: int
    table_id: str
    previous_value: str
    current_value: str
    change_type: str  # "added", "removed", "changed", "unchanged"
    previous_confidence: float = 0.0
    current_confidence: float = 0.0


@dataclass
class ComparisonResult:
    previous_file: str
    current_run: str
    tables_previous: int = 0
    tables_current: int = 0
    cells_previous: int = 0
    cells_current: int = 0
    cells_unchanged: int = 0
    cells_changed: int = 0
    cells_added: int = 0
    cells_removed: int = 0
    footnotes_previous: int = 0
    footnotes_current: int = 0
    avg_conf_previous: float = 0.0
    avg_conf_current: float = 0.0
    deltas: list[CellDelta] = field(default_factory=list)

    @property
    def stability_pct(self) -> float:
        total = self.cells_unchanged + self.cells_changed
        return self.cells_unchanged / max(total, 1) * 100

    def to_html_section(self) -> str:
        """Render comparison as HTML for the report."""
        conf_delta = self.avg_conf_current - self.avg_conf_previous
        conf_icon = "&#9650;" if conf_delta > 0 else "&#9660;" if conf_delta < 0 else "&#8212;"
        conf_color = "#059669" if conf_delta > 0 else "#dc2626" if conf_delta < 0 else "#64748b"

        html = f"""
<div style="background:white;border:1px solid #e2e8f0;border-radius:10px;padding:20px;margin-bottom:24px;">
  <h2 style="margin-top:0;border:none;">Comparison with Previous Run</h2>
  <p style="font-size:12px;color:#64748b;">Previous: {self.previous_file}</p>

  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0;">
    <div style="background:#f8fafc;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:24px;font-weight:700;color:#0284c7;">{self.tables_previous} → {self.tables_current}</div>
      <div style="font-size:11px;color:#64748b;">Tables</div>
    </div>
    <div style="background:#f8fafc;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:24px;font-weight:700;color:#0284c7;">{self.cells_previous} → {self.cells_current}</div>
      <div style="font-size:11px;color:#64748b;">Cells</div>
    </div>
    <div style="background:#f8fafc;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:24px;font-weight:700;color:{conf_color};">{conf_icon} {abs(conf_delta):.1%}</div>
      <div style="font-size:11px;color:#64748b;">Confidence Delta</div>
    </div>
    <div style="background:#f8fafc;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:24px;font-weight:700;color:#059669;">{self.stability_pct:.0f}%</div>
      <div style="font-size:11px;color:#64748b;">Cell Stability</div>
    </div>
  </div>

  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0;">
    <div style="background:#ecfdf5;border-radius:6px;padding:8px;text-align:center;font-size:12px;">
      <strong>{self.cells_unchanged}</strong> unchanged
    </div>
    <div style="background:#fefce8;border-radius:6px;padding:8px;text-align:center;font-size:12px;">
      <strong>{self.cells_changed}</strong> changed
    </div>
    <div style="background:#eff6ff;border-radius:6px;padding:8px;text-align:center;font-size:12px;">
      <strong>{self.cells_added}</strong> new
    </div>
    <div style="background:#fef2f2;border-radius:6px;padding:8px;text-align:center;font-size:12px;">
      <strong>{self.cells_removed}</strong> removed
    </div>
  </div>

  <div style="font-size:12px;color:#64748b;margin-top:12px;">
    <strong>Footnotes:</strong> {self.footnotes_previous} → {self.footnotes_current}
    ({'+' if self.footnotes_current > self.footnotes_previous else ''}{self.footnotes_current - self.footnotes_previous})
  </div>"""

        # Show top changed cells
        changed = [d for d in self.deltas if d.change_type == "changed"]
        if changed:
            html += """
  <h3 style="font-size:13px;margin:16px 0 8px;">Changed Cells (Top 10)</h3>
  <table style="width:100%;border-collapse:collapse;font-size:11px;">
  <thead><tr>
    <th style="background:#f1f5f9;padding:6px;border:1px solid #e2e8f0;text-align:left;">Table</th>
    <th style="background:#f1f5f9;padding:6px;border:1px solid #e2e8f0;">Row,Col</th>
    <th style="background:#f1f5f9;padding:6px;border:1px solid #e2e8f0;text-align:left;">Previous</th>
    <th style="background:#f1f5f9;padding:6px;border:1px solid #e2e8f0;text-align:left;">Current</th>
  </tr></thead><tbody>"""
            for d in changed[:10]:
                html += f"""
  <tr>
    <td style="padding:4px 6px;border:1px solid #e2e8f0;">{d.table_id[:20]}</td>
    <td style="padding:4px 6px;border:1px solid #e2e8f0;text-align:center;">{d.row},{d.col}</td>
    <td style="padding:4px 6px;border:1px solid #e2e8f0;background:#fef2f2;">{d.previous_value[:30]}</td>
    <td style="padding:4px 6px;border:1px solid #e2e8f0;background:#ecfdf5;">{d.current_value[:30]}</td>
  </tr>"""
            html += "</tbody></table>"

        html += "</div>"
        return html


def compare_runs(
    current_result: dict,
    previous_file: str | Path | None = None,
) -> ComparisonResult | None:
    """Compare current extraction result against a previous run."""
    if previous_file is None:
        # Auto-find the most recent previous output
        previous_file = _find_latest_output()
    if previous_file is None:
        return None

    previous_path = Path(previous_file)
    if not previous_path.exists():
        logger.warning(f"Previous output not found: {previous_path}")
        return None

    with open(previous_path, encoding="utf-8") as f:
        previous = json.load(f)

    result = ComparisonResult(
        previous_file=previous_path.name,
        current_run="current",
    )

    prev_tables = previous.get("tables", [])
    curr_tables = current_result.get("tables", [])

    result.tables_previous = len(prev_tables)
    result.tables_current = len(curr_tables)

    # Build cell maps
    prev_cells: dict[tuple[str, int, int], dict] = {}
    curr_cells: dict[tuple[str, int, int], dict] = {}

    for t in prev_tables:
        tid = t.get("table_id", "")
        for c in t.get("cells", []):
            prev_cells[(tid, c["row"], c["col"])] = c

    for t in curr_tables:
        tid = t.get("table_id", "")
        for c in t.get("cells", []):
            curr_cells[(tid, c["row"], c["col"])] = c

    result.cells_previous = len(prev_cells)
    result.cells_current = len(curr_cells)

    # Footnotes
    result.footnotes_previous = sum(len(t.get("footnotes", [])) for t in prev_tables)
    result.footnotes_current = sum(len(t.get("footnotes", [])) for t in curr_tables)

    # Confidence
    prev_confs = [t.get("overall_confidence", 0) for t in prev_tables]
    curr_confs = [t.get("overall_confidence", 0) for t in curr_tables]
    result.avg_conf_previous = sum(prev_confs) / max(len(prev_confs), 1)
    result.avg_conf_current = sum(curr_confs) / max(len(curr_confs), 1)

    # Compare cells
    all_keys = set(prev_cells.keys()) | set(curr_cells.keys())
    for key in sorted(all_keys):
        tid, row, col = key
        prev = prev_cells.get(key)
        curr = curr_cells.get(key)

        if prev and curr:
            pv = (prev.get("raw_value") or "").strip()
            cv = (curr.get("raw_value") or "").strip()
            if pv == cv:
                result.cells_unchanged += 1
                change = "unchanged"
            else:
                result.cells_changed += 1
                change = "changed"
            result.deltas.append(CellDelta(
                row=row, col=col, table_id=tid,
                previous_value=pv, current_value=cv,
                change_type=change,
                previous_confidence=prev.get("confidence", 0),
                current_confidence=curr.get("confidence", 0),
            ))
        elif curr and not prev:
            result.cells_added += 1
            result.deltas.append(CellDelta(
                row=row, col=col, table_id=tid,
                previous_value="", current_value=(curr.get("raw_value") or "").strip(),
                change_type="added",
                current_confidence=curr.get("confidence", 0),
            ))
        elif prev and not curr:
            result.cells_removed += 1
            result.deltas.append(CellDelta(
                row=row, col=col, table_id=tid,
                previous_value=(prev.get("raw_value") or "").strip(), current_value="",
                change_type="removed",
                previous_confidence=prev.get("confidence", 0),
            ))

    return result


def _find_latest_output() -> Path | None:
    """Find the most recent extraction output JSON."""
    if not OUTPUTS_DIR.exists():
        return None
    jsons = sorted(OUTPUTS_DIR.glob("*extraction*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return jsons[0] if jsons else None
