"""
Site Budget Calculator — generates a budget worksheet from extracted SoA data.

Takes the extraction output and produces:
- Procedure × Visit frequency matrix
- CPT code mapping for each procedure
- Cost input fields (pre-filled with tier estimates)
- Auto-calculated per-patient budget
- Export as interactive HTML with editable cost fields
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.models.schema import ExtractedTable, PipelineOutput


@dataclass
class BudgetLine:
    """One line item in the site budget."""
    procedure: str
    canonical_name: str
    cpt_code: str
    category: str
    cost_tier: str
    visits_required: list[str]  # Visit names where this procedure is required
    total_occurrences: int
    estimated_unit_cost: float  # Pre-filled from cost tier
    avg_confidence: float = 1.0  # Average confidence across cells for this procedure
    source_pages: list[int] = field(default_factory=list)  # Protocol pages where this appears
    issues: list[str] = field(default_factory=list)  # Specific issues for hover tooltip
    notes: str = ""

    @property
    def confidence_color(self) -> str:
        if self.avg_confidence >= 0.90:
            return "green"
        elif self.avg_confidence >= 0.75:
            return "amber"
        return "red"


COST_TIER_ESTIMATES = {
    "LOW": 75,
    "MEDIUM": 350,
    "HIGH": 1200,
    "VERY_HIGH": 3500,
}


def generate_budget_from_output(output: PipelineOutput) -> list[BudgetLine]:
    """Generate budget line items from pipeline output."""
    all_lines: list[BudgetLine] = []

    for table in output.tables:
        lines = _extract_budget_lines(table)
        all_lines.extend(lines)

    # Deduplicate procedures across tables (keep highest occurrence count)
    merged: dict[str, BudgetLine] = {}
    for line in all_lines:
        key = line.canonical_name or line.procedure
        if key in merged:
            existing = merged[key]
            # Merge visits
            all_visits = list(set(existing.visits_required + line.visits_required))
            existing.visits_required = all_visits
            existing.total_occurrences = max(existing.total_occurrences, line.total_occurrences)
        else:
            merged[key] = line

    return sorted(merged.values(), key=lambda l: (l.category, l.procedure))


def _extract_budget_lines(table: ExtractedTable) -> list[BudgetLine]:
    """Extract budget lines from one SoA table."""
    from src.pipeline.procedure_normalizer import ProcedureNormalizer

    lines: list[BudgetLine] = []
    # Use current normalizer (with SME corrections) for live re-mapping
    normalizer = ProcedureNormalizer()

    # Build visit header map from schema
    visit_names: dict[int, str] = {}
    for h in table.schema_info.column_headers:
        visit_names[h.col_index] = h.text

    # Build procedure map — RE-NORMALIZE using current vocabulary
    proc_map: dict[str, dict] = {}
    for p in table.procedures:
        proc_map[p.raw_name.lower()] = {
            "canonical": p.canonical_name,
            "cpt": p.code or "",
            "category": p.category,
            "cost_tier": p.estimated_cost_tier.value,
        }

    # Group cells by row (procedure)
    row_cells: dict[int, list] = defaultdict(list)
    row_headers: dict[int, str] = {}
    for cell in table.cells:
        row_cells[cell.row].append(cell)
        if cell.col == 0 and cell.raw_value.strip():
            row_headers[cell.row] = cell.raw_value.strip()
        elif cell.row_header and cell.row not in row_headers:
            row_headers[cell.row] = cell.row_header

    # For each procedure row, count visits where it's required
    for row_num, proc_name in sorted(row_headers.items()):
        cells_in_row = row_cells.get(row_num, [])

        # Find visits with markers (X, checkmark, etc.)
        required_visits = []
        for cell in cells_in_row:
            if cell.col == 0:
                continue
            val = cell.raw_value.strip().upper()
            if val in ("X", "Y", "YES") or "X" in val or "\u2713" in val or "\u2714" in val:
                visit = visit_names.get(cell.col, cell.col_header or f"Visit {cell.col}")
                required_visits.append(visit)

        if not required_visits:
            continue

        # Look up procedure info — use LIVE normalizer for best mapping
        normalized = normalizer.normalize(proc_name)
        canonical = normalized.canonical_name
        cpt = normalized.code or ""
        category = normalized.category
        cost_tier = normalized.estimated_cost_tier.value

        # Build footnote notes
        notes_parts = []
        for cell in cells_in_row:
            if cell.resolved_footnotes:
                for fn in cell.resolved_footnotes:
                    if fn not in notes_parts:
                        notes_parts.append(fn)

        # Calculate average confidence for this procedure's cells
        row_confs = [c.confidence for c in cells_in_row if c.col > 0]
        avg_conf = sum(row_confs) / len(row_confs) if row_confs else 0.5

        # Build detailed issues for hover tooltips
        issues = []
        low_conf_visits = []
        for c in cells_in_row:
            if c.col > 0 and c.confidence < 0.85 and c.raw_value.strip():
                v_name = visit_names.get(c.col, f"Col {c.col}")
                low_conf_visits.append(f"{v_name} ({c.confidence:.0%})")
        if low_conf_visits:
            issues.append(f"Low confidence at: {', '.join(low_conf_visits[:5])}")
        if not cpt:
            issues.append("No CPT code mapped — needs manual assignment")
        if category == "Unknown":
            issues.append(f"Procedure '{proc_name[:30]}' not in vocabulary — verify mapping")
        if notes_parts:
            issues.append(f"Conditional: {'; '.join(notes_parts[:2])}")

        lines.append(BudgetLine(
            procedure=proc_name,
            canonical_name=canonical,
            cpt_code=cpt,
            category=category,
            cost_tier=cost_tier,
            visits_required=required_visits,
            total_occurrences=len(required_visits),
            estimated_unit_cost=COST_TIER_ESTIMATES.get(cost_tier, 100),
            avg_confidence=avg_conf,
            source_pages=table.source_pages,
            issues=issues,
            notes="; ".join(notes_parts[:3]),
        ))

    return lines


def generate_budget_html(output: PipelineOutput, path: Path | None = None) -> str:
    """Generate an interactive HTML budget worksheet."""
    lines = generate_budget_from_output(output)
    total_estimated = sum(l.estimated_unit_cost * l.total_occurrences for l in lines)

    rows_html = ""
    for i, line in enumerate(lines):
        visits_str = ", ".join(line.visits_required)

        tier_class = {
            "LOW": "tier-low", "MEDIUM": "tier-med",
            "HIGH": "tier-high", "VERY_HIGH": "tier-vhigh",
        }.get(line.cost_tier, "tier-low")
        tier_label = {"LOW": "$", "MEDIUM": "$$", "HIGH": "$$$", "VERY_HIGH": "$$$$"}.get(line.cost_tier, "?")

        guidance = _build_review_guidance(line)
        conf_class = f"conf-{line.confidence_color}"

        tooltip_parts = [f"Source: Protocol pages {', '.join(str(p) for p in line.source_pages)}"]
        tooltip_parts.extend(line.issues)
        tooltip = "&#10;".join(_esc(t) for t in tooltip_parts)
        page_ref = f"(p.{', '.join(str(p) for p in line.source_pages[:3])})" if line.source_pages else ""

        cpt_cell = f'<span class="mono">{line.cpt_code}</span>' if line.cpt_code else '<span class="needs-input">Enter CPT</span>'

        rows_html += f"""
        <tr class="{conf_class}" title="{tooltip}">
          <td class="proc-name">
            <div class="proc-primary">{_esc(line.procedure)}</div>
            <div class="proc-canonical">{_esc(line.canonical_name)} <span class="page-ref">{page_ref}</span></div>
          </td>
          <td class="center">{cpt_cell}</td>
          <td>{_esc(line.category)}</td>
          <td class="center"><span class="{tier_class}">{tier_label}</span></td>
          <td class="center freq">{line.total_occurrences}</td>
          <td class="visits-cell">{_esc(visits_str)}</td>
          <td class="center">
            <span class="conf-dot conf-dot-{line.confidence_color}"></span>
            {line.avg_confidence:.0%}
          </td>
          <td class="cost-cell">
            <span class="currency">$</span>
            <input type="number" class="cost-input" id="cost_{i}"
              value="{line.estimated_unit_cost:.0f}"
              onchange="recalculate()" min="0" step="10"
              placeholder="Enter cost">
          </td>
          <td class="line-total" id="total_{i}">
            ${line.estimated_unit_cost * line.total_occurrences:,.0f}</td>
          <td class="guidance">{guidance}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Site Budget Worksheet — {_esc(output.document_name)}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; color: #1e293b; background: #f8fafc; }}
.container {{ max-width: 1600px; margin: 0 auto; padding: 20px; }}
h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; }}
.subtitle {{ font-size: 12px; color: #64748b; margin-bottom: 16px; }}
.summary {{ display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }}
.summary-card {{ background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 20px; min-width: 160px; }}
.summary-value {{ font-size: 24px; font-weight: 700; }}
.summary-label {{ font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }}
.budget-table {{ width: 100%; border-collapse: collapse; font-size: 11px; background: white; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }}
.budget-table th {{ background: #0f172a; color: white; padding: 8px 10px; text-align: left; font-weight: 600; font-size: 10px; text-transform: uppercase; letter-spacing: 0.3px; position: sticky; top: 0; z-index: 10; }}
.budget-table td {{ padding: 6px 10px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }}
.budget-table tr:hover {{ background: #f8fafc; }}
.proc-name {{ min-width: 260px; }}
.proc-primary {{ font-weight: 600; font-size: 12px; color: #0f172a; line-height: 1.4; }}
.proc-canonical {{ font-size: 10px; color: #64748b; margin-top: 2px; }}
.mono {{ font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 11px; color: #475569; }}
.center {{ text-align: center; }}
.freq {{ font-size: 14px; font-weight: 700; color: #0f172a; }}
.visits-cell {{ font-size: 10px; color: #64748b; max-width: 280px; line-height: 1.5; }}
.guidance {{ font-size: 10px; max-width: 260px; line-height: 1.6; }}
.cost-cell {{ white-space: nowrap; }}
.currency {{ color: #94a3b8; font-size: 11px; margin-right: 2px; }}
.needs-input {{ background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 500; }}
.conf-green {{ }}
.conf-amber {{ background: #fffbeb !important; }}
.conf-red {{ background: #fef2f2 !important; }}
.conf-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; }}
.conf-dot-green {{ background: #059669; }}
.conf-dot-amber {{ background: #d97706; }}
.conf-dot-red {{ background: #dc2626; }}
.hint-ok {{ color: #059669; font-weight: 500; }}
.hint-red {{ color: #dc2626; font-size: 10px; }}
.hint-amber {{ color: #d97706; font-size: 10px; }}
.hint-info {{ color: #0284c7; font-size: 10px; }}
.action-needed {{ color: #dc2626; font-weight: 600; font-size: 10px; }}
.page-ref {{ font-size: 9px; color: #94a3b8; font-style: italic; }}
.cost-input {{ width: 80px; padding: 4px 6px; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 11px; text-align: right; }}
.cost-input:focus {{ outline: 2px solid #0284c7; border-color: transparent; }}
.line-total {{ font-weight: 600; text-align: right; white-space: nowrap; }}
.tier-low {{ background: #f1f5f9; color: #64748b; padding: 2px 6px; border-radius: 3px; font-size: 9px; }}
.tier-med {{ background: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 3px; font-size: 9px; }}
.tier-high {{ background: #fef3c7; color: #92400e; padding: 2px 6px; border-radius: 3px; font-size: 9px; }}
.tier-vhigh {{ background: #fecaca; color: #991b1b; padding: 2px 6px; border-radius: 3px; font-size: 9px; }}
.grand-total {{ background: #0f172a; color: white; font-size: 14px; }}
.grand-total td {{ padding: 12px 10px; font-weight: 700; }}
.footer {{ margin-top: 16px; font-size: 11px; color: #94a3b8; }}
.footer p {{ margin-bottom: 4px; }}
@media print {{
  .cost-input {{ border: none; background: transparent; }}
  body {{ background: white; }}
}}
</style>
</head>
<body>
<div class="container">

<h1>Site Budget Worksheet</h1>
<p class="subtitle">{_esc(output.document_name)} | Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>

<div class="summary">
  <div class="summary-card">
    <div class="summary-value" style="color:#0284c7;">{len(lines)}</div>
    <div class="summary-label">Budget Line Items</div>
  </div>
  <div class="summary-card">
    <div class="summary-value" style="color:#0284c7;">{sum(l.total_occurrences for l in lines)}</div>
    <div class="summary-label">Total Procedure Visits</div>
  </div>
  <div class="summary-card">
    <div class="summary-value" style="color:#059669;" id="grand-total-display">${total_estimated:,.0f}</div>
    <div class="summary-label">Estimated Per-Patient Cost</div>
  </div>
  <div class="summary-card">
    <div class="summary-value" style="color:#64748b;">{sum(1 for l in lines if l.cpt_code)}/{len(lines)}</div>
    <div class="summary-label">Procedures with CPT Codes</div>
  </div>
</div>

<table class="budget-table">
<thead>
<tr>
  <th style="min-width:260px">Procedure / Canonical Name</th>
  <th>CPT</th>
  <th>Category</th>
  <th>Tier</th>
  <th>Freq</th>
  <th style="min-width:200px">Visits Required</th>
  <th>Conf.</th>
  <th style="min-width:100px">Unit Cost ($)</th>
  <th>Line Total</th>
  <th style="min-width:220px">Action Required</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
<tfoot>
<tr class="grand-total">
  <td colspan="8" style="text-align:right;">ESTIMATED PER-PATIENT TOTAL</td>
  <td></td>
  <td id="grand-total-cell" style="text-align:right;">${total_estimated:,.0f}</td>
  <td></td>
</tr>
</tfoot>
</table>

<div class="footer">
  <h3 style="font-size:13px;color:#0f172a;margin-bottom:8px;">How to Complete This Worksheet</h3>
  <ol style="font-size:12px;color:#475569;line-height:1.8;margin-left:20px;">
    <li><strong>Review the "Action Required" column</strong> — green rows are ready, amber/red rows need your attention.</li>
    <li><strong>Enter your site's unit costs</strong> in the cost column. Current values are estimates (LOW=$75, MEDIUM=$350, HIGH=$1,200, VERY_HIGH=$3,500). Line totals and the grand total will recalculate automatically.</li>
    <li><strong>Add CPT codes</strong> where marked "Enter CPT" — check your institution's fee schedule.</li>
    <li><strong>Verify amber/red rows</strong> against the source protocol (page numbers shown in parentheses after each procedure name).</li>
    <li><strong>Check conditional procedures</strong> — the "Action Required" column shows footnote conditions that may reduce the actual frequency.</li>
  </ol>
  <div style="margin-top:12px;padding:10px 16px;background:#eff6ff;border-radius:6px;font-size:11px;color:#1e40af;">
    <strong>Confidence Legend:</strong>
    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#059669;margin:0 4px;vertical-align:middle;"></span> Green (≥90%) = reliable, no action needed &nbsp;
    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#d97706;margin:0 4px;vertical-align:middle;"></span> Amber (75-90%) = spot-check recommended &nbsp;
    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#dc2626;margin:0 4px;vertical-align:middle;"></span> Red (<75%) = verify against source PDF
  </div>
</div>

</div>

<script>
const LINE_COUNT = {len(lines)};
const OCCURRENCES = [{','.join(str(l.total_occurrences) for l in lines)}];

function recalculate() {{
  let grand = 0;
  for (let i = 0; i < LINE_COUNT; i++) {{
    const input = document.getElementById('cost_' + i);
    const cost = parseFloat(input.value) || 0;
    const total = cost * OCCURRENCES[i];
    document.getElementById('total_' + i).textContent = '$' + total.toLocaleString('en-US', {{minimumFractionDigits: 0}});
    grand += total;
  }}
  document.getElementById('grand-total-cell').textContent = '$' + grand.toLocaleString('en-US', {{minimumFractionDigits: 0}});
  document.getElementById('grand-total-display').textContent = '$' + grand.toLocaleString('en-US', {{minimumFractionDigits: 0}});
}}
</script>
</body>
</html>"""

    if path:
        path.write_text(html, encoding="utf-8")
    return html


def _build_review_guidance(line: BudgetLine) -> str:
    """Generate specific review guidance for a budget line item."""
    hints: list[str] = []

    # Confidence-based guidance
    if line.avg_confidence < 0.75:
        hints.append('<span class="hint-red">LOW CONFIDENCE — verify frequency against source PDF</span>')
    elif line.avg_confidence < 0.90:
        hints.append('<span class="hint-amber">Check: some visit marks uncertain</span>')

    # CPT code guidance
    if not line.cpt_code:
        hints.append('<span class="hint-red">Missing CPT code — assign billing code</span>')
    elif line.category == "Unknown":
        hints.append('<span class="hint-amber">Verify procedure mapping is correct</span>')

    # Cost tier guidance
    if line.cost_tier == "VERY_HIGH":
        hints.append('<span class="hint-amber">High-cost item — verify frequency is correct</span>')

    # Footnote/conditional guidance
    if line.notes:
        hints.append(f'<span class="hint-info">Conditional: {_esc(line.notes[:50])}</span>')

    # Frequency sanity
    if line.total_occurrences > 20:
        hints.append('<span class="hint-amber">High frequency ({}) — confirm not over-counted</span>'.format(line.total_occurrences))

    if not hints:
        return '<span class="hint-ok">OK</span>'

    return "<br>".join(hints)


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))
