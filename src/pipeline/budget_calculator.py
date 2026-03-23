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

import logging
import re

from src.models.schema import ExtractedTable, FootnoteType, PipelineOutput

logger = logging.getLogger(__name__)

# Regex for footnote-embedded markers: X followed by footnote ref letters
# Matches: Xr, Xm, Xf, Xb, X^a, Xa,b  but NOT "Xray" or random text
_EMBEDDED_MARKER_RE = re.compile(
    r'^[X✓✔√Yy]'              # Starts with a marker character
    r'[a-g,\d\s\^]*$',         # Followed by optional footnote refs (a-g, digits, ^)
    re.IGNORECASE,
)

# Arrow/span patterns indicating continuous daily procedures
_SPAN_PATTERNS = ['←→', '↔', '←', '→', '⟵', '⟶', '⟷', '──', '———']

# Conditional text patterns in cells (not firm visits)
_CONDITIONAL_CELL_RE = re.compile(
    r'as clinically indicated|'
    r'if (?:clinically )?(?:appropriate|indicated|needed)|'
    r'as needed|per investigator|at discretion|'
    r'\bprn\b|may be performed',
    re.IGNORECASE,
)

# Minimum term length for compound row splitting (avoid splitting on short noise)
_MIN_COMPOUND_TERM_LEN = 3


def _split_compound_row(proc_name: str) -> list[str]:
    """Split compound SoA rows like 'ICF, demographics, concomitant medications'.

    Only splits when there are 2+ comma-separated terms, each at least
    _MIN_COMPOUND_TERM_LEN characters. Returns a list of cleaned terms,
    or the original name in a single-element list if no split is warranted.
    """
    # Only split on commas that are not inside parentheses
    # e.g., "Recording of MAAEs, AE leading to withdrawal..." stays as one
    # but "ICF, demographics, concomitant medications" splits
    if "," not in proc_name:
        return [proc_name]

    terms = [t.strip() for t in proc_name.split(",")]
    # Filter out very short terms (footnote markers like "8" or empty)
    valid_terms = [t for t in terms if len(t) >= _MIN_COMPOUND_TERM_LEN]

    if len(valid_terms) < 2:
        return [proc_name]

    # Heuristic: if any term is very long (>60 chars), it's probably a
    # descriptive procedure name, not a compound list
    if any(len(t) > 60 for t in valid_terms):
        return [proc_name]

    # Heuristic: if terms share common phrasing patterns like "AE leading to",
    # "concomitant medications relevant to" — it's a single complex procedure
    connectors = ["leading to", "relevant to", "and ", "or "]
    if any(any(c in t.lower() for c in connectors) for t in valid_terms[1:]):
        return [proc_name]

    return valid_terms


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
    firm_occurrences: int = 0  # Visits without CONDITIONAL footnotes
    conditional_occurrences: int = 0  # Visits with CONDITIONAL footnotes
    is_phone_call: bool = False  # Detected as phone-based from footnotes
    cycle_multiplier: float = 1.0  # Cycle multiplication factor for oncology
    cycle_source: str = ""  # Where cycle count came from
    has_frequency_modifier: bool = False  # Visit frequency modified by footnote
    frequency_modifier_notes: str = ""  # The modifier text
    source_pages: list[int] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
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
    "PHONE_CALL": 35,
    "EDIARY": 10,
    "INFUSION": 2500,
    "BIOPSY": 4000,
}


def _infer_cycle_multiplier(
    visit_windows: list,
    domain_config: dict,
) -> tuple[int, int, str]:
    """Detect representative cycles in SoA and return multiplier.

    For oncology cycle-based protocols, the SoA often shows only
    3-4 representative cycles while treatment lasts 6-17+ cycles.

    Args:
        visit_windows: VisitWindow objects from temporal extraction
        domain_config: Domain YAML config

    Returns:
        (represented_cycles, expected_total_cycles, source_description)
    """
    # Check if domain is cycle-based
    visit_structure = domain_config.get("domain", {}).get(
        "visit_structure", "fixed_duration"
    )
    if visit_structure != "cycle_based":
        return 1, 1, "fixed_duration — no multiplication"

    # Count unique cycles in visit windows
    cycles_seen = set()
    for vw in visit_windows:
        cycle = getattr(vw, "cycle", None)
        if cycle is not None:
            cycles_seen.add(cycle)

    if not cycles_seen:
        return 1, 1, "no cycle metadata detected"

    represented = len(cycles_seen)

    # If only 1 cycle shown, could be single-cycle protocol — don't multiply
    if represented <= 1:
        return 1, 1, "single cycle — conservative (no multiplication)"

    # Get expected total cycles from config
    ta_specific = domain_config.get("ta_specific", {})
    treat_to_prog = ta_specific.get("treat_to_progression", {})

    if treat_to_prog.get("enabled"):
        # Use median from treat-to-progression config
        expected = treat_to_prog.get("default_median_months", 9)
        cycle_days = ta_specific.get("cycle_length_days", 21)
        if cycle_days > 0:
            total = int(expected * 30 / cycle_days)
        else:
            total = ta_specific.get("default_cycles", 6)
        source = f"treat-to-progression ({expected} months median)"
    else:
        total = ta_specific.get("default_cycles", 6)
        source = f"domain default ({total} cycles)"

    # Don't apply multiplier if represented >= expected
    if represented >= total:
        return represented, represented, "all cycles visible"

    return represented, total, source


def generate_budget_from_output(
    output: PipelineOutput,
    domain_config: dict | None = None,
) -> list[BudgetLine]:
    """Generate budget line items from pipeline output."""
    all_lines: list[BudgetLine] = []

    for table in output.tables:
        lines = _extract_budget_lines(table, domain_config=domain_config)
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


def _extract_budget_lines(
    table: ExtractedTable,
    domain_config: dict | None = None,
) -> list[BudgetLine]:
    """Extract budget lines from one SoA table.

    Handles:
    - Standard markers (X, ✓, Y)
    - Footnote-embedded markers (Xr, Xm, Xf — P0-3)
    - Arrow/span indicators for continuous procedures (P0-4)
    - Conditional text in cells ("as clinically indicated" — P0-5)
    - FREQUENCY_MODIFIER footnotes that adjust visit counts
    - Oncology cycle multiplication
    """
    from src.pipeline.procedure_normalizer import ProcedureNormalizer

    lines: list[BudgetLine] = []
    normalizer = ProcedureNormalizer()

    # Build visit header map from schema
    visit_names: dict[int, str] = {}
    for h in table.schema_info.column_headers:
        visit_names[h.col_index] = h.text

    # Build procedure map
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

    # Load domain config for TA-specific rules
    from src.domain.config import (
        load_domain_config,
        get_marker_patterns,
        get_text_indicators,
        get_procedure_cost_override,
        get_cpt_overrides,
        is_phone_call,
        get_cost_tiers,
    )
    if domain_config is None:
        domain_config = load_domain_config()

    marker_patterns = get_marker_patterns(domain_config)
    text_indicators = get_text_indicators(domain_config)
    cost_tier_map = get_cost_tiers(domain_config)
    COST_TIER_ESTIMATES.update(cost_tier_map)

    # Build footnote type lookup for conditional / frequency modifier detection
    footnote_types: dict[str, str] = {}
    footnote_texts: dict[str, str] = {}
    for fn in table.footnotes:
        fn_type = fn.footnote_type
        # Handle both enum and string values
        if hasattr(fn_type, "value"):
            fn_type = fn_type.value
        for ref in fn.applies_to:
            key = f"{ref.row}-{ref.col}"
            footnote_types[key] = fn_type
            footnote_texts[key] = fn.text

    # ── Cycle multiplier (P0-1) ──────────────────────────────────────
    rep_cycles, total_cycles, cycle_source = _infer_cycle_multiplier(
        table.visit_windows, domain_config
    )
    cycle_multiplier = total_cycles / rep_cycles if rep_cycles > 0 else 1.0
    if cycle_multiplier > 1:
        logger.info(
            f"Cycle multiplier {cycle_multiplier:.1f}x "
            f"({rep_cycles} shown → {total_cycles} expected, {cycle_source})"
        )

    # For each procedure row, count visits where it's required
    for row_num, proc_name in sorted(row_headers.items()):
        if normalizer.is_not_procedure(proc_name):
            logger.debug(f"Skipping non-procedure: '{proc_name}'")
            continue

        # ── Compound row splitting ───────────────────────────────────
        # "ICF, demographics, concomitant medications" → 3 budget lines
        sub_procedures = _split_compound_row(proc_name)
        if len(sub_procedures) > 1:
            logger.info(
                f"Splitting compound row '{proc_name[:50]}' → "
                f"{len(sub_procedures)} sub-procedures"
            )

        cells_in_row = row_cells.get(row_num, [])

        # Find visits with markers
        firm_visits = []
        conditional_visits = []
        frequency_modifier_visits = []
        frequency_modifier_notes_list: list[str] = []
        has_span = False
        span_col_range: tuple[int, int] | None = None

        for cell in cells_in_row:
            if cell.col == 0:
                continue
            val = cell.raw_value.strip()
            val_upper = val.upper()

            # ── P0-4: Arrow/span detection ───────────────────────────
            if any(p in val for p in _SPAN_PATTERNS):
                has_span = True
                if span_col_range is None:
                    span_col_range = (cell.col, cell.col)
                else:
                    span_col_range = (
                        min(span_col_range[0], cell.col),
                        max(span_col_range[1], cell.col),
                    )
                continue

            # ── P0-5: Conditional text detection ─────────────────────
            if _CONDITIONAL_CELL_RE.search(val):
                visit = visit_names.get(
                    cell.col, cell.col_header or f"Visit {cell.col}"
                )
                conditional_visits.append(visit)
                continue

            # ── Standard marker check ────────────────────────────────
            is_marker = any(
                p == val_upper or p in val_upper
                for p in marker_patterns
            )

            # ── P0-3: Footnote-embedded marker check (Xr, Xm, etc.) ─
            if not is_marker and val and _EMBEDDED_MARKER_RE.match(val):
                is_marker = True

            # Check text indicators
            is_text = any(
                ind.lower() in val.lower()
                for ind in text_indicators
            ) if not is_marker and val else False

            if is_marker or is_text:
                visit = visit_names.get(
                    cell.col, cell.col_header or f"Visit {cell.col}"
                )
                cell_key = f"{cell.row}-{cell.col}"
                fn_type = footnote_types.get(cell_key, "")

                if fn_type == "CONDITIONAL":
                    conditional_visits.append(visit)
                elif fn_type == "FREQUENCY_MODIFIER":
                    # P0-2: Track separately — these visits have modified frequency
                    frequency_modifier_visits.append(visit)
                    fn_text = footnote_texts.get(cell_key, "")
                    if fn_text and fn_text not in frequency_modifier_notes_list:
                        frequency_modifier_notes_list.append(fn_text)
                else:
                    firm_visits.append(visit)

        # Handle span-based visits (e-diary, continuous procedures)
        if has_span and span_col_range:
            start_col, end_col = span_col_range
            start_visit = visit_names.get(start_col, f"Visit {start_col}")
            end_visit = visit_names.get(end_col, f"Visit {end_col}")
            firm_visits.append(f"{start_visit}→{end_visit} (continuous)")

        required_visits = firm_visits + conditional_visits + frequency_modifier_visits
        if not required_visits:
            continue

        # Build footnote notes (shared across sub-procedures)
        notes_parts = []
        for cell in cells_in_row:
            if cell.resolved_footnotes:
                for fn in cell.resolved_footnotes:
                    if fn not in notes_parts:
                        notes_parts.append(fn)

        # Calculate average confidence (shared)
        row_confs = [c.confidence for c in cells_in_row if c.col > 0]
        avg_conf = sum(row_confs) / len(row_confs) if row_confs else 0.5

        # ── P0-1: Apply cycle multiplier to total occurrences ────────
        base_occurrences = len(firm_visits) + len(conditional_visits)
        freq_mod_occurrences = len(frequency_modifier_visits)
        if cycle_multiplier > 1:
            total_occ = int(base_occurrences * cycle_multiplier) + freq_mod_occurrences
        else:
            total_occ = base_occurrences + freq_mod_occurrences

        has_freq_mod = bool(frequency_modifier_visits)
        freq_mod_notes = "; ".join(frequency_modifier_notes_list[:2])

        # Emit one BudgetLine per sub-procedure (compound row splitting)
        for sub_proc in sub_procedures:
            # Skip sub-procedures that are themselves noise
            if normalizer.is_not_procedure(sub_proc):
                continue

            # Look up procedure info per sub-procedure
            normalized = normalizer.normalize(sub_proc)
            canonical = normalized.canonical_name
            cpt = normalized.code or ""
            category = normalized.category
            cost_tier = normalized.estimated_cost_tier.value

            # Build issues per sub-procedure
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
                issues.append(f"Procedure '{sub_proc[:30]}' not in vocabulary — verify mapping")
            if notes_parts:
                issues.append(f"Conditional: {'; '.join(notes_parts[:2])}")
            if has_span:
                issues.append("Continuous/span procedure — verify daily count")
            if len(sub_procedures) > 1:
                issues.append(f"Split from compound row: '{proc_name[:40]}'")

            # ── Domain-aware CPT override ────────────────────────────
            cpt_overrides = get_cpt_overrides(domain_config)
            if canonical in cpt_overrides:
                override = cpt_overrides[canonical]
                if isinstance(override, dict):
                    cpt = override.get("cpt", cpt)
                    canonical = override.get("canonical", canonical)
                else:
                    cpt = str(override)

            # Check for domain-specific cost override
            override_tier = get_procedure_cost_override(domain_config, canonical)
            if override_tier:
                cost_tier = override_tier

            # Detect phone call procedures from footnote text
            is_phone = False
            for note in notes_parts:
                if is_phone_call(domain_config, note):
                    is_phone = True
                    cost_tier = "PHONE_CALL"
                    break

            if cycle_multiplier > 1:
                issues.append(
                    f"Cycle multiplier {cycle_multiplier:.1f}x applied ({cycle_source})"
                )

            lines.append(BudgetLine(
                procedure=sub_proc,
                canonical_name=canonical,
                cpt_code=cpt,
                category=category,
                cost_tier=cost_tier,
                visits_required=required_visits,
                total_occurrences=total_occ,
                firm_occurrences=len(firm_visits),
                conditional_occurrences=len(conditional_visits),
                is_phone_call=is_phone,
                cycle_multiplier=cycle_multiplier if cycle_multiplier > 1 else 1.0,
                cycle_source=cycle_source if cycle_multiplier > 1 else "",
                has_frequency_modifier=has_freq_mod,
                frequency_modifier_notes=freq_mod_notes,
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
