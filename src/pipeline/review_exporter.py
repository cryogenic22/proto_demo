"""
Review Exporter — generates human-readable output for medical writer review.

Produces a structured document showing:
- Each SoA table as a readable grid
- Procedure mappings with canonical names and CPT codes
- Resolved footnotes anchored to specific cells
- Flagged cells requiring human review
- Confidence scores with color coding
- Visit windows with temporal logic
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.models.schema import ExtractedTable, PipelineOutput


def export_review_document(
    output: PipelineOutput,
    path: Path | None = None,
) -> str:
    """
    Generate a Markdown review document for medical writer review.

    Returns the document as a string. Optionally writes to file.
    """
    lines: list[str] = []

    # Header
    lines.append(f"# Protocol Table Extraction — Medical Writer Review")
    lines.append(f"")
    lines.append(f"**Document:** {output.document_name}")
    lines.append(f"**Pages:** {output.total_pages}")
    lines.append(f"**Tables Extracted:** {len(output.tables)}")
    lines.append(f"**Pipeline Version:** {output.pipeline_version}")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"")

    # Summary stats
    total_cells = sum(len(t.cells) for t in output.tables)
    total_flagged = sum(len(t.flagged_cells) for t in output.tables)
    total_footnotes = sum(len(t.footnotes) for t in output.tables)
    total_procs = sum(len(t.procedures) for t in output.tables)
    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total cells extracted | {total_cells} |")
    lines.append(f"| Cells requiring review | {total_flagged} ({total_flagged/max(total_cells,1)*100:.0f}%) |")
    lines.append(f"| Footnotes resolved | {total_footnotes} |")
    lines.append(f"| Procedures normalized | {total_procs} |")
    lines.append(f"| Processing time | {output.processing_time_seconds:.0f}s |")
    lines.append(f"")

    # Warnings
    if output.warnings:
        lines.append(f"## Warnings")
        lines.append(f"")
        for w in output.warnings:
            lines.append(f"- {w}")
        lines.append(f"")

    # Each table
    for table in output.tables:
        lines.extend(_render_table(table))

    doc = "\n".join(lines)

    if path:
        path.write_text(doc, encoding="utf-8")

    return doc


def export_review_json(
    output: PipelineOutput,
    path: Path | None = None,
) -> dict:
    """
    Generate a structured JSON review document.
    Designed for programmatic consumption by review tools.
    """
    review = {
        "document": output.document_name,
        "pages": output.total_pages,
        "generated": datetime.now(timezone.utc).isoformat(),
        "pipeline_version": output.pipeline_version,
        "tables": [],
    }

    for table in output.tables:
        table_review = {
            "table_id": table.table_id,
            "title": table.title,
            "type": table.table_type.value,
            "pages": table.source_pages,
            "confidence": round(table.overall_confidence, 3),
            "cell_count": len(table.cells),
            "flagged_count": len(table.flagged_cells),
            "grid": _build_grid(table),
            "procedures": [
                {
                    "raw_name": p.raw_name,
                    "canonical_name": p.canonical_name,
                    "cpt_code": p.code,
                    "category": p.category,
                    "cost_tier": p.estimated_cost_tier.value,
                }
                for p in table.procedures
            ],
            "footnotes": [
                {
                    "marker": fn.marker,
                    "text": fn.text,
                    "type": fn.footnote_type.value,
                    "applies_to_cells": len(fn.applies_to),
                }
                for fn in table.footnotes
            ],
            "review_items": [
                {
                    "row": ri.cell_ref.row,
                    "col": ri.cell_ref.col,
                    "reason": ri.reason,
                    "extracted_value": ri.extracted_value,
                    "review_type": ri.review_type.value,
                    "cost_tier": ri.cost_tier.value,
                }
                for ri in table.review_items
            ],
        }
        review["tables"].append(table_review)

    if path:
        path.write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")

    return review


def _render_table(table: ExtractedTable) -> list[str]:
    """Render a single table as Markdown sections."""
    lines: list[str] = []
    conf_pct = f"{table.overall_confidence * 100:.0f}%"

    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## Table: {table.title or table.table_id}")
    lines.append(f"")
    lines.append(f"**Type:** {table.table_type.value} | "
                 f"**Pages:** {', '.join(str(p) for p in table.source_pages)} | "
                 f"**Confidence:** {conf_pct} | "
                 f"**Cells:** {len(table.cells)} | "
                 f"**Flagged:** {len(table.flagged_cells)}")
    lines.append(f"")

    # Grid
    if table.cells:
        lines.append(f"### Extracted Grid")
        lines.append(f"")
        lines.extend(_render_grid(table))
        lines.append(f"")

    # Procedures
    if table.procedures:
        lines.append(f"### Procedure Mapping")
        lines.append(f"")
        lines.append(f"| Raw Name | Canonical Name | CPT Code | Category | Cost |")
        lines.append(f"|----------|----------------|----------|----------|------|")
        for p in table.procedures:
            code = f"{p.code} ({p.code_system})" if p.code else "—"
            cost = {"LOW": "$", "MEDIUM": "$$", "HIGH": "$$$", "VERY_HIGH": "$$$$"}.get(
                p.estimated_cost_tier.value, "?")
            lines.append(f"| {p.raw_name} | **{p.canonical_name}** | {code} | {p.category} | {cost} |")
        lines.append(f"")

    # Footnotes
    if table.footnotes:
        lines.append(f"### Footnotes")
        lines.append(f"")
        for fn in table.footnotes:
            cell_count = len(fn.applies_to)
            lines.append(
                f"- **{fn.marker}** [{fn.footnote_type.value}]: {fn.text} "
                f"*(applies to {cell_count} cell{'s' if cell_count != 1 else ''})*"
            )
        lines.append(f"")

    # Review items
    if table.review_items:
        lines.append(f"### Items Requiring Review")
        lines.append(f"")
        lines.append(f"| Row | Col | Value | Reason | Type | Cost |")
        lines.append(f"|-----|-----|-------|--------|------|------|")
        for ri in table.review_items:
            cost = {"LOW": "$", "MEDIUM": "$$", "HIGH": "$$$", "VERY_HIGH": "$$$$"}.get(
                ri.cost_tier.value, "?")
            val = ri.extracted_value or "*(empty)*"
            lines.append(
                f"| {ri.cell_ref.row} | {ri.cell_ref.col} | `{val}` | "
                f"{ri.reason[:60]} | {ri.review_type.value} | {cost} |"
            )
        lines.append(f"")

    # Visit windows
    if table.visit_windows:
        lines.append(f"### Visit Schedule")
        lines.append(f"")
        lines.append(f"| Visit | Target Day | Window | Unscheduled |")
        lines.append(f"|-------|-----------|--------|-------------|")
        for vw in table.visit_windows:
            day = str(vw.target_day) if vw.target_day is not None else "—"
            window = ""
            if vw.window_minus or vw.window_plus:
                window = f"-{vw.window_minus}/+{vw.window_plus} {vw.window_unit.value.lower()}"
            unsched = "Yes" if vw.is_unscheduled else ""
            lines.append(f"| {vw.visit_name} | {day} | {window} | {unsched} |")
        lines.append(f"")

    return lines


def _render_grid(table: ExtractedTable) -> list[str]:
    """Render cell grid as a Markdown table."""
    if not table.cells:
        return ["*(no cells)*"]

    # Build maps
    row_headers: dict[int, str] = {}
    col_headers: list[str] = []
    cell_map: dict[tuple[int, int], str] = {}
    flagged_set = {(f.row, f.col) for f in table.flagged_cells}

    for cell in table.cells:
        if cell.row_header and cell.row not in row_headers:
            row_headers[cell.row] = cell.row_header
        cell_map[(cell.row, cell.col)] = cell.raw_value

    if table.schema_info.column_headers:
        col_headers = [h.text for h in table.schema_info.column_headers]

    max_row = max(c.row for c in table.cells) if table.cells else 0
    max_col = max(c.col for c in table.cells) if table.cells else 0

    # Limit to reasonable size for review document
    if max_col > 20:
        return [f"*(Table too wide for Markdown — {max_col + 1} columns. See JSON export.)*"]
    if max_row > 50:
        show_rows = 30
    else:
        show_rows = max_row + 1

    lines: list[str] = []

    # Header row
    header = "| Procedure |"
    sep = "|-----------|"
    for c in range(min(max_col + 1, 20)):
        h = col_headers[c] if c < len(col_headers) else f"Col {c}"
        header += f" {h[:12]} |"
        sep += "------|"
    lines.append(header)
    lines.append(sep)

    # Data rows
    for r in range(min(show_rows, max_row + 1)):
        proc = row_headers.get(r, "")[:25]
        row_str = f"| {proc:<25} |"
        for c in range(min(max_col + 1, 20)):
            val = cell_map.get((r, c), "")
            if (r, c) in flagged_set:
                val = f"**{val}?**"  # Mark flagged cells
            row_str += f" {val[:12]:^12} |"
        lines.append(row_str)

    if show_rows < max_row + 1:
        lines.append(f"| *(... {max_row + 1 - show_rows} more rows)* |")

    return lines


def _build_grid(table: ExtractedTable) -> list[list[dict]]:
    """Build a 2D grid structure for JSON export."""
    if not table.cells:
        return []

    flagged_set = {(f.row, f.col) for f in table.flagged_cells}
    max_row = max(c.row for c in table.cells)
    max_col = max(c.col for c in table.cells)

    cell_map = {}
    for c in table.cells:
        cell_map[(c.row, c.col)] = c

    grid = []
    for r in range(max_row + 1):
        row = []
        for c in range(max_col + 1):
            cell = cell_map.get((r, c))
            if cell:
                row.append({
                    "value": cell.raw_value,
                    "type": cell.data_type.value,
                    "confidence": round(cell.confidence, 2),
                    "flagged": (r, c) in flagged_set,
                    "footnotes": cell.footnote_markers,
                    "resolved_footnotes": cell.resolved_footnotes,
                })
            else:
                row.append({"value": "", "type": "EMPTY", "confidence": 0, "flagged": False})
        grid.append(row)

    return grid
