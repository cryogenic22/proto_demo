"""
HTML Report Generator — produces a self-contained, printable extraction report.

Generates a single HTML file with:
- Executive summary with KPIs
- Interactive table grids with confidence heat-mapping
- Procedure mapping table with CPT codes
- Footnote list with type badges
- Review queue sorted by cost impact
- Visit schedule timeline
- OCR grounding results
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.models.schema import ExtractedTable, PipelineOutput


def generate_html_report(
    output: PipelineOutput,
    path: Path | None = None,
) -> str:
    """Generate a self-contained HTML report."""
    total_cells = sum(len(t.cells) for t in output.tables)
    total_flagged = sum(len(t.flagged_cells) for t in output.tables)
    total_footnotes = sum(len(t.footnotes) for t in output.tables)
    total_procs = sum(len(t.procedures) for t in output.tables)
    avg_conf = (
        sum(t.overall_confidence for t in output.tables) / len(output.tables)
        if output.tables else 0
    )

    tables_html = "\n".join(_render_table_section(t) for t in output.tables)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ProtoExtract Report — {_esc(output.document_name)}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; color: #1e293b; background: #f8fafc; line-height: 1.5; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
h1 {{ font-size: 22px; font-weight: 700; color: #0f172a; margin-bottom: 4px; }}
h2 {{ font-size: 17px; font-weight: 600; color: #0f172a; margin: 32px 0 12px; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
h3 {{ font-size: 14px; font-weight: 600; color: #334155; margin: 20px 0 8px; }}
.subtitle {{ font-size: 13px; color: #64748b; margin-bottom: 24px; }}
.meta {{ display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: #64748b; margin-bottom: 24px; }}
.meta span {{ background: #f1f5f9; padding: 4px 10px; border-radius: 6px; }}

/* KPI Cards */
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 28px; }}
.kpi {{ background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; }}
.kpi-value {{ font-size: 28px; font-weight: 700; }}
.kpi-label {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }}
.kpi-good {{ color: #059669; }}
.kpi-warn {{ color: #d97706; }}
.kpi-bad {{ color: #dc2626; }}
.kpi-info {{ color: #0284c7; }}

/* Tables */
.data-table {{ width: 100%; border-collapse: collapse; font-size: 11px; margin: 8px 0 20px; }}
.data-table th {{ background: #f1f5f9; color: #475569; font-weight: 600; text-align: left; padding: 8px 10px; border: 1px solid #e2e8f0; white-space: nowrap; }}
.data-table td {{ padding: 6px 10px; border: 1px solid #e2e8f0; vertical-align: top; }}
.data-table tr:hover {{ background: #f8fafc; }}
.data-table .sticky {{ position: sticky; left: 0; background: white; z-index: 1; font-weight: 500; }}

/* Cell confidence coloring */
.conf-high {{ background: #ecfdf5; }}
.conf-mid {{ background: #fefce8; }}
.conf-low {{ background: #fef2f2; }}
.flagged {{ outline: 2px solid #f59e0b; outline-offset: -2px; }}

/* Badges */
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; }}
.badge-soa {{ background: #dbeafe; color: #1d4ed8; }}
.badge-cond {{ background: #fef3c7; color: #92400e; }}
.badge-exc {{ background: #fecaca; color: #991b1b; }}
.badge-ref {{ background: #dbeafe; color: #1e40af; }}
.badge-clar {{ background: #e2e8f0; color: #475569; }}
.badge-cost-low {{ background: #f1f5f9; color: #64748b; }}
.badge-cost-med {{ background: #e0f2fe; color: #0369a1; }}
.badge-cost-high {{ background: #fef3c7; color: #92400e; }}
.badge-cost-vhigh {{ background: #fecaca; color: #991b1b; }}

/* Table section */
.table-section {{ background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
.table-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
.table-meta {{ font-size: 12px; color: #64748b; }}
.conf-bar {{ display: inline-block; width: 60px; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; vertical-align: middle; }}
.conf-fill {{ height: 100%; border-radius: 4px; }}
.grid-scroll {{ overflow-x: auto; margin: 0 -20px; padding: 0 20px; }}

/* Procedure mapping */
.proc-table td:nth-child(3) {{ font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 10px; }}

/* Review queue */
.review-item {{ display: flex; gap: 12px; padding: 10px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; margin-bottom: 8px; font-size: 12px; }}
.review-icon {{ width: 28px; height: 28px; background: #fef3c7; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}

/* Narrative */
.narrative {{ background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 24px; margin-bottom: 24px; }}
.narrative h2 {{ margin-top: 0; }}
.narrative-section {{ margin-bottom: 16px; }}
.narrative-section h3 {{ color: #0f172a; font-size: 13px; margin-bottom: 6px; }}
.narrative-section p {{ font-size: 12px; color: #475569; line-height: 1.6; }}
.finding {{ display: flex; gap: 10px; padding: 8px 12px; border-radius: 6px; margin-bottom: 6px; font-size: 12px; }}
.finding-good {{ background: #ecfdf5; color: #065f46; }}
.finding-warn {{ background: #fffbeb; color: #92400e; }}
.finding-bad {{ background: #fef2f2; color: #991b1b; }}
.finding-info {{ background: #eff6ff; color: #1e40af; }}
.finding-icon {{ font-size: 14px; flex-shrink: 0; }}

/* Print */
@media print {{
  body {{ background: white; }}
  .container {{ max-width: 100%; padding: 12px; }}
  .table-section {{ break-inside: avoid; }}
  .grid-scroll {{ overflow: visible; }}
}}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<h1>Protocol Table Extraction Report</h1>
<p class="subtitle">{_esc(output.document_name)}</p>
<div class="meta">
  <span>{output.total_pages} pages</span>
  <span>{len(output.tables)} SOA tables</span>
  <span>{output.processing_time_seconds:.0f}s processing</span>
  <span>Pipeline v{output.pipeline_version}</span>
  <span>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</span>
</div>

<!-- KPIs -->
<div class="kpis">
  <div class="kpi">
    <div class="kpi-value kpi-info">{len(output.tables)}</div>
    <div class="kpi-label">SOA Tables</div>
  </div>
  <div class="kpi">
    <div class="kpi-value kpi-info">{total_cells:,}</div>
    <div class="kpi-label">Cells Extracted</div>
  </div>
  <div class="kpi">
    <div class="kpi-value {'kpi-good' if avg_conf >= 0.85 else 'kpi-warn' if avg_conf >= 0.7 else 'kpi-bad'}">{avg_conf:.0%}</div>
    <div class="kpi-label">Avg Confidence</div>
  </div>
  <div class="kpi">
    <div class="kpi-value kpi-info">{total_footnotes}</div>
    <div class="kpi-label">Footnotes Resolved</div>
  </div>
  <div class="kpi">
    <div class="kpi-value {'kpi-good' if total_flagged == 0 else 'kpi-warn'}">{total_flagged}</div>
    <div class="kpi-label">Cells for Review</div>
  </div>
  <div class="kpi">
    <div class="kpi-value kpi-info">{total_procs}</div>
    <div class="kpi-label">Procedures Mapped</div>
  </div>
</div>

{"".join(f'<div style="background:#fefce8;border:1px solid #fde68a;border-radius:8px;padding:10px 16px;margin-bottom:12px;font-size:12px;color:#92400e;">{_esc(w)}</div>' for w in output.warnings) if output.warnings else ""}

<!-- Narrative Analysis -->
{_render_narrative_analysis(output)}

<!-- Tables -->
{tables_html}

</div>
</body>
</html>"""

    if path:
        path.write_text(html, encoding="utf-8")

    return html


def _render_narrative_analysis(output: PipelineOutput) -> str:
    """Generate narrative analysis of extraction quality."""
    if not output.tables:
        return '<div class="narrative"><h2>Analysis</h2><p>No tables were extracted.</p></div>'

    total_cells = sum(len(t.cells) for t in output.tables)
    total_flagged = sum(len(t.flagged_cells) for t in output.tables)
    total_footnotes = sum(len(t.footnotes) for t in output.tables)
    total_procs = sum(len(t.procedures) for t in output.tables)
    avg_conf = sum(t.overall_confidence for t in output.tables) / len(output.tables)

    # Analyze what's working and what's not
    findings: list[tuple[str, str, str]] = []  # (icon_class, icon, text)

    # Overall confidence assessment
    if avg_conf >= 0.90:
        findings.append(("finding-good", "&#10003;",
            f"<strong>High extraction confidence.</strong> Average confidence across all tables is {avg_conf:.0%}. "
            f"The majority of cell values are consistent across dual-pass extraction."))
    elif avg_conf >= 0.80:
        findings.append(("finding-warn", "&#9888;",
            f"<strong>Moderate extraction confidence.</strong> Average confidence is {avg_conf:.0%}. "
            f"Some cells showed disagreement between extraction passes, indicating potential ambiguity in the source document."))
    else:
        findings.append(("finding-bad", "&#10007;",
            f"<strong>Low extraction confidence.</strong> Average confidence is only {avg_conf:.0%}. "
            f"Significant disagreement between extraction passes — manual review of flagged cells is strongly recommended."))

    # Flagged cells analysis
    if total_flagged == 0:
        findings.append(("finding-good", "&#10003;",
            "No cells flagged for review. All extracted values passed confidence thresholds."))
    else:
        flag_pct = total_flagged / max(total_cells, 1) * 100
        # Break down by table
        worst_table = max(output.tables, key=lambda t: len(t.flagged_cells))
        findings.append(("finding-warn", "&#9888;",
            f"<strong>{total_flagged} cells ({flag_pct:.0f}%) require human review.</strong> "
            f"These cells either showed disagreement between extraction passes, were flagged by the "
            f"adversarial challenger, or fell below confidence thresholds. "
            f"The table with the most flagged cells is \"{_esc(worst_table.title or worst_table.table_id)}\" "
            f"({len(worst_table.flagged_cells)} flagged)."))

    # Footnotes analysis
    if total_footnotes > 0:
        fn_types: dict[str, int] = {}
        for t in output.tables:
            for fn in t.footnotes:
                fn_types[fn.footnote_type.value] = fn_types.get(fn.footnote_type.value, 0) + 1
        type_desc = ", ".join(f"{v} {k.lower()}" for k, v in sorted(fn_types.items(), key=lambda x: -x[1]))
        findings.append(("finding-good", "&#10003;",
            f"<strong>{total_footnotes} footnotes extracted and classified.</strong> "
            f"Types found: {type_desc}. Footnotes are anchored to specific cells "
            f"and displayed as superscripts in the grid view."))
    else:
        findings.append(("finding-info", "&#9432;",
            "<strong>No footnotes were extracted.</strong> "
            "This may indicate the SoA tables in this document have no footnotes, or the "
            "footnote extraction pass did not find definitions matching the markers detected in cells. "
            "Check the source PDF to verify."))

    # Procedure mapping analysis
    if total_procs > 0:
        unmapped = sum(
            1 for t in output.tables for p in t.procedures
            if p.code is None and p.category == "Unknown"
        )
        mapped_with_code = sum(
            1 for t in output.tables for p in t.procedures if p.code
        )
        if unmapped == 0:
            findings.append(("finding-good", "&#10003;",
                f"<strong>All {total_procs} procedures mapped successfully.</strong> "
                f"{mapped_with_code} have CPT codes assigned."))
        else:
            findings.append(("finding-warn", "&#9888;",
                f"<strong>{unmapped} of {total_procs} procedures could not be mapped</strong> to the "
                f"canonical vocabulary. These are shown as their raw extracted names in the procedure "
                f"mapping tables below. {mapped_with_code} procedures have CPT codes. "
                f"Unmapped procedures may be protocol-specific assessments or novel procedures "
                f"not yet in the mapping database."))

    # Per-table confidence variation
    confs = [t.overall_confidence for t in output.tables]
    if len(confs) >= 2:
        min_conf = min(confs)
        max_conf = max(confs)
        weakest = min(output.tables, key=lambda t: t.overall_confidence)
        if max_conf - min_conf > 0.15:
            findings.append(("finding-info", "&#9432;",
                f"<strong>Confidence varies significantly across tables</strong> "
                f"(range: {min_conf:.0%} to {max_conf:.0%}). "
                f"The lowest-confidence table is \"{_esc(weakest.title or weakest.table_id)}\" "
                f"at {weakest.overall_confidence:.0%}. This table may have complex structure "
                f"(multi-level headers, dense footnotes, or spanning cells) that is harder to extract reliably."))

    # Multi-page table detection
    multi_page = [t for t in output.tables if len(t.source_pages) > 1]
    if multi_page:
        findings.append(("finding-info", "&#9432;",
            f"<strong>{len(multi_page)} table(s) span multiple pages.</strong> "
            f"These were automatically stitched from continuation pages. "
            f"Multi-page tables are more prone to extraction errors at page boundaries — "
            f"pay special attention to rows near page breaks."))

    # Build HTML
    html_parts = ['<div class="narrative">', '<h2>Extraction Analysis</h2>']

    # Summary paragraph
    html_parts.append(
        f'<div class="narrative-section"><p>'
        f'This report contains the extraction results for <strong>{_esc(output.document_name)}</strong> '
        f'({output.total_pages} pages). The pipeline identified <strong>{len(output.tables)} SOA '
        f'(Schedule of Activities) table(s)</strong> and extracted <strong>{total_cells:,} cells</strong> '
        f'with an average confidence of <strong>{avg_conf:.0%}</strong>. '
        f'Each cell was extracted twice using different prompts, cross-checked by an adversarial '
        f'validation agent, and verified against OCR output where available. '
        f'Cells highlighted in <span style="background:#fef2f2;padding:2px 4px;border-radius:3px;">red</span> '
        f'have low confidence; cells with <span style="outline:2px solid #f59e0b;padding:2px 4px;border-radius:3px;">orange outlines</span> '
        f'are flagged for human review.'
        f'</p></div>'
    )

    # Individual findings
    html_parts.append('<div class="narrative-section"><h3>Key Findings</h3>')
    for cls, icon, text in findings:
        html_parts.append(
            f'<div class="finding {cls}">'
            f'<span class="finding-icon">{icon}</span>'
            f'<div>{text}</div>'
            f'</div>'
        )
    html_parts.append('</div>')

    # Reviewer guidance
    html_parts.append(
        '<div class="narrative-section"><h3>Reviewer Guidance</h3>'
        '<p>When reviewing this extraction:</p>'
        '<ul style="font-size:12px;color:#475569;margin:6px 0 0 20px;line-height:1.8;">'
        '<li><strong>Flagged cells (orange outline)</strong> — These require verification against the source PDF. '
        'The pipeline was not confident in the extracted value.</li>'
        '<li><strong>Red-background cells</strong> — Low confidence (&lt;70%). The two extraction passes disagreed, '
        'or the adversarial checker found a potential error.</li>'
        '<li><strong>Procedure mapping</strong> — Verify that raw procedure names are correctly mapped to canonical names. '
        '"Unknown" category procedures need manual mapping.</li>'
        '<li><strong>Footnotes</strong> — Verify that footnote markers (superscripts) are anchored to the correct cells '
        'and that the footnote text matches the source document.</li>'
        '<li><strong>Visit windows</strong> — Confirm that Day/Week/Month calculations and window ranges match the protocol.</li>'
        '</ul></div>'
    )

    html_parts.append('</div>')
    return "\n".join(html_parts)


def _render_table_section(table: ExtractedTable) -> str:
    """Render one table as an HTML section."""
    conf = table.overall_confidence
    conf_color = "#059669" if conf >= 0.85 else "#d97706" if conf >= 0.7 else "#dc2626"

    grid_html = _render_grid(table)
    procs_html = _render_procedures(table)
    footnotes_html = _render_footnotes(table)
    review_html = _render_review_queue(table)
    visits_html = _render_visits(table)

    return f"""
<div class="table-section">
  <div class="table-header">
    <div>
      <h2 style="margin:0;border:none;padding:0;">{_esc(table.title) or table.table_id}</h2>
      <div class="table-meta">
        <span class="badge badge-soa">{table.table_type.value}</span>
        Pages {', '.join(str(p) for p in table.source_pages)} &middot;
        {len(table.cells)} cells &middot;
        {len(table.flagged_cells)} flagged &middot;
        {len(table.footnotes)} footnotes
      </div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:24px;font-weight:700;color:{conf_color};">{conf:.0%}</div>
      <div class="conf-bar"><div class="conf-fill" style="width:{conf*100:.0f}%;background:{conf_color};"></div></div>
    </div>
  </div>

  <h3>Extracted Grid</h3>
  <div class="grid-scroll">
    {grid_html}
  </div>

  {procs_html}
  {footnotes_html}
  {visits_html}
  {review_html}
</div>"""


def _render_grid(table: ExtractedTable) -> str:
    if not table.cells:
        return "<p style='color:#94a3b8;font-size:12px;'>No cells extracted</p>"

    row_headers: dict[int, str] = {}
    cell_map: dict[tuple[int, int], any] = {}
    flagged = {(f.row, f.col) for f in table.flagged_cells}

    for c in table.cells:
        if c.row_header and c.row not in row_headers:
            row_headers[c.row] = c.row_header
        cell_map[(c.row, c.col)] = c

    col_headers = [h.text for h in table.schema_info.column_headers] if table.schema_info.column_headers else []
    max_row = max(c.row for c in table.cells)
    max_col = max(c.col for c in table.cells)

    # Limit columns for readability
    show_cols = min(max_col + 1, 25)

    rows = ['<table class="data-table">']
    # Header
    rows.append('<thead><tr><th class="sticky">Procedure</th>')
    for c in range(show_cols):
        h = _esc(col_headers[c][:15]) if c < len(col_headers) else f"Col {c}"
        rows.append(f'<th>{h}</th>')
    rows.append('</tr></thead><tbody>')

    for r in range(max_row + 1):
        proc = _esc(row_headers.get(r, "")[:30])
        rows.append(f'<tr><td class="sticky">{proc}</td>')
        for c in range(show_cols):
            cell = cell_map.get((r, c))
            if cell:
                val = _esc(cell.raw_value[:15])
                conf_class = (
                    "conf-high" if cell.confidence >= 0.9
                    else "conf-mid" if cell.confidence >= 0.7
                    else "conf-low"
                )
                flag_class = " flagged" if (r, c) in flagged else ""
                fn_sup = ""
                if cell.footnote_markers:
                    fn_sup = f'<sup style="color:#0284c7">{",".join(cell.footnote_markers)}</sup>'
                title = f"Confidence: {cell.confidence:.0%}"
                if cell.resolved_footnotes:
                    title += "\n" + "\n".join(cell.resolved_footnotes)
                rows.append(
                    f'<td class="{conf_class}{flag_class}" title="{_esc(title)}">'
                    f'{val}{fn_sup}</td>'
                )
            else:
                rows.append('<td style="color:#cbd5e1">—</td>')
        rows.append('</tr>')

    rows.append('</tbody></table>')
    if show_cols < max_col + 1:
        rows.append(f'<p style="font-size:11px;color:#94a3b8;">Showing {show_cols} of {max_col+1} columns</p>')

    return "\n".join(rows)


def _render_procedures(table: ExtractedTable) -> str:
    if not table.procedures:
        return ""

    rows = ['<h3>Procedure Mapping</h3>', '<table class="data-table proc-table">',
            '<thead><tr><th>Raw Name</th><th>Canonical Name</th><th>CPT Code</th><th>Category</th><th>Cost</th></tr></thead><tbody>']

    cost_badges = {
        "LOW": "badge-cost-low", "MEDIUM": "badge-cost-med",
        "HIGH": "badge-cost-high", "VERY_HIGH": "badge-cost-vhigh",
    }
    cost_labels = {"LOW": "$", "MEDIUM": "$$", "HIGH": "$$$", "VERY_HIGH": "$$$$"}

    for p in table.procedures:
        code = f"{p.code} ({p.code_system})" if p.code else "—"
        tier = p.estimated_cost_tier.value
        rows.append(
            f'<tr><td>{_esc(p.raw_name[:40])}</td>'
            f'<td><strong>{_esc(p.canonical_name[:40])}</strong></td>'
            f'<td>{code}</td>'
            f'<td>{_esc(p.category)}</td>'
            f'<td><span class="badge {cost_badges.get(tier, "")}">{cost_labels.get(tier, tier)}</span></td></tr>'
        )
    rows.append('</tbody></table>')
    return "\n".join(rows)


def _render_footnotes(table: ExtractedTable) -> str:
    if not table.footnotes:
        return ""

    type_badges = {
        "CONDITIONAL": "badge-cond", "EXCEPTION": "badge-exc",
        "REFERENCE": "badge-ref", "CLARIFICATION": "badge-clar",
    }

    rows = ['<h3>Footnotes</h3>', '<table class="data-table">',
            '<thead><tr><th style="width:40px">Marker</th><th>Text</th><th>Type</th><th>Cells</th></tr></thead><tbody>']
    for fn in table.footnotes:
        badge = type_badges.get(fn.footnote_type.value, "badge-clar")
        rows.append(
            f'<tr><td><strong style="color:#0284c7;font-size:14px;">{_esc(fn.marker)}</strong></td>'
            f'<td>{_esc(fn.text)}</td>'
            f'<td><span class="badge {badge}">{fn.footnote_type.value}</span></td>'
            f'<td>{len(fn.applies_to)}</td></tr>'
        )
    rows.append('</tbody></table>')
    return "\n".join(rows)


def _render_visits(table: ExtractedTable) -> str:
    if not table.visit_windows:
        return ""

    rows = ['<h3>Visit Schedule</h3>', '<table class="data-table">',
            '<thead><tr><th>Visit</th><th>Target Day</th><th>Window</th><th>Cycle</th><th>Unscheduled</th></tr></thead><tbody>']
    for vw in table.visit_windows:
        day = str(vw.target_day) if vw.target_day is not None else "—"
        window = f"-{vw.window_minus}/+{vw.window_plus} {vw.window_unit.value.lower()}" if (vw.window_minus or vw.window_plus) else "—"
        cycle = str(vw.cycle) if vw.cycle else "—"
        unsched = "Yes" if vw.is_unscheduled else ""
        rows.append(f'<tr><td>{_esc(vw.visit_name[:25])}</td><td>{day}</td><td>{window}</td><td>{cycle}</td><td>{unsched}</td></tr>')
    rows.append('</tbody></table>')
    return "\n".join(rows)


def _render_review_queue(table: ExtractedTable) -> str:
    if not table.review_items:
        return '<h3>Review Queue</h3><p style="color:#059669;font-size:12px;">All cells passed validation — no review needed.</p>'

    cost_labels = {"LOW": "$", "MEDIUM": "$$", "HIGH": "$$$", "VERY_HIGH": "$$$$"}

    items = ['<h3>Review Queue</h3>']
    # Sort by cost tier (high cost first)
    cost_order = {"VERY_HIGH": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    sorted_items = sorted(table.review_items, key=lambda x: cost_order.get(x.cost_tier.value, 4))

    for ri in sorted_items[:20]:  # Show top 20
        cost = cost_labels.get(ri.cost_tier.value, "?")
        items.append(
            f'<div class="review-item">'
            f'<div class="review-icon">⚠</div>'
            f'<div style="flex:1;">'
            f'<div><strong>Row {ri.cell_ref.row}, Col {ri.cell_ref.col}</strong> '
            f'<span class="badge badge-cost-{"vhigh" if ri.cost_tier.value == "VERY_HIGH" else ri.cost_tier.value.lower()}">{cost}</span> '
            f'<span class="badge badge-clar">{ri.review_type.value.replace("_"," ")}</span></div>'
            f'<div style="color:#64748b;margin-top:2px;">{_esc(ri.reason[:80])}</div>'
            f'{"<div style=&quot;margin-top:2px;&quot;>Value: <code style=&quot;background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:11px;&quot;>" + _esc(ri.extracted_value[:30]) + "</code></div>" if ri.extracted_value else ""}'
            f'</div></div>'
        )
    if len(table.review_items) > 20:
        items.append(f'<p style="font-size:12px;color:#94a3b8;">... and {len(table.review_items) - 20} more items</p>')

    return "\n".join(items)


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;"))
