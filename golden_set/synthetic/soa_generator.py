"""
Synthetic SoA Table Generator — creates test tables with known ground truth.

Generates SoA tables as HTML→PNG images with parameterized complexity.
Every cell value is known, so extraction accuracy can be measured exactly.

Complexity parameters:
- num_procedures: 5-30
- num_visits: 4-20
- footnote_density: 0-20 footnotes
- merged_headers: True/False
- multi_page: True/False (simulated via very tall tables)
"""

from __future__ import annotations

import html
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SyntheticCell:
    row: int
    col: int
    value: str
    data_type: str  # MARKER, TEXT, EMPTY, CONDITIONAL
    footnote_markers: list[str] = field(default_factory=list)


@dataclass
class SyntheticFootnote:
    marker: str
    text: str
    footnote_type: str


@dataclass
class SyntheticSoA:
    """A synthetic SoA table with known ground truth."""
    name: str
    procedures: list[str]
    visits: list[str]
    cells: list[SyntheticCell]
    footnotes: list[SyntheticFootnote]
    complexity_tier: int
    html: str = ""
    ground_truth: dict[str, Any] = field(default_factory=dict)


# Procedure pools by domain
ONCOLOGY_PROCEDURES = [
    "Informed Consent", "Medical History", "Physical Examination",
    "Vital Signs", "ECOG Performance Status", "12-lead ECG",
    "CT Scan (chest/abdomen/pelvis)", "Bone Scan", "Brain MRI",
    "Complete Blood Count", "Comprehensive Metabolic Panel",
    "Coagulation Panel", "Urinalysis", "Pregnancy Test",
    "Tumor Biopsy", "ctDNA Sample", "PK Blood Sample",
    "ADA Sample", "Study Drug Administration",
    "Adverse Event Assessment", "Concomitant Medications",
    "RECIST Assessment", "QoL Questionnaire (EQ-5D)",
]

VACCINE_PROCEDURES = [
    "Informed Consent", "Medical History", "Physical Examination",
    "Vital Signs", "12-lead ECG", "Complete Blood Count",
    "Comprehensive Metabolic Panel", "Pregnancy Test",
    "Vaccination", "Immunogenicity Blood Draw",
    "Serology/Neutralizing Antibody", "Reactogenicity Assessment",
    "e-Diary Distribution", "e-Diary Review",
    "Adverse Event Assessment", "Concomitant Medications",
    "Telephone Contact", "Nasal Swab", "HIV Test",
]

GENERAL_PROCEDURES = [
    "Informed Consent", "Medical History", "Demographics",
    "Physical Examination", "Vital Signs", "Body Weight",
    "12-lead ECG", "Complete Blood Count",
    "Comprehensive Metabolic Panel", "Liver Function Tests",
    "Urinalysis", "Pregnancy Test", "Study Drug Administration",
    "Adverse Event Assessment", "Concomitant Medications",
    "Drug Accountability", "Compliance Assessment",
]

# Visit pools
DAY_VISITS = ["Screening", "Day 1", "Day 8", "Day 15", "Day 29", "Day 57",
              "Day 85", "Day 113", "Day 169", "Day 197"]
WEEK_VISITS = ["Screening", "Day 1", "Week 2", "Week 4", "Week 8", "Week 12",
               "Week 16", "Week 24", "Week 36", "Week 52", "ET", "Follow-up"]
CYCLE_VISITS = ["Screening", "C1D1", "C1D8", "C1D15", "C2D1", "C3D1",
                "C4D1", "C5D1", "C6D1", "EOT", "Follow-up"]

# Footnote templates
FOOTNOTE_TEMPLATES = [
    ("Only if clinically indicated", "CONDITIONAL"),
    ("At screening visit only", "CONDITIONAL"),
    ("Every 4 weeks after Week 12", "CONDITIONAL"),
    ("Per investigator judgment", "CONDITIONAL"),
    ("If female of childbearing potential", "CONDITIONAL"),
    ("Except at the early termination visit", "EXCEPTION"),
    ("Not required for participants in Cohort B", "EXCEPTION"),
    ("Unless already performed within 28 days", "EXCEPTION"),
    ("See Section 8.1 for detailed procedures", "REFERENCE"),
    ("Refer to the laboratory manual for sample handling", "REFERENCE"),
    ("Administered as IV infusion over 30 minutes", "CLARIFICATION"),
    ("Blood samples collected in EDTA tubes", "CLARIFICATION"),
    ("Within 72 hours of study drug administration", "CONDITIONAL"),
    ("Pre-dose and 2 hours post-dose", "CONDITIONAL"),
    ("At visits where study drug is administered", "CONDITIONAL"),
]


def generate_synthetic_soa(
    name: str = "synthetic_soa",
    domain: str = "general",
    num_procedures: int = 12,
    num_visits: int = 8,
    num_footnotes: int = 5,
    marker_density: float = 0.4,
    seed: int = 42,
) -> SyntheticSoA:
    """Generate a synthetic SoA table with known ground truth."""
    rng = random.Random(seed)

    # Select procedures and visits
    proc_pool = {
        "oncology": ONCOLOGY_PROCEDURES,
        "vaccine": VACCINE_PROCEDURES,
    }.get(domain, GENERAL_PROCEDURES)

    visit_pool = {
        "oncology": CYCLE_VISITS,
        "vaccine": DAY_VISITS,
    }.get(domain, WEEK_VISITS)

    procedures = proc_pool[:min(num_procedures, len(proc_pool))]
    visits = visit_pool[:min(num_visits, len(visit_pool))]

    # Generate footnotes
    fn_templates = rng.sample(FOOTNOTE_TEMPLATES, min(num_footnotes, len(FOOTNOTE_TEMPLATES)))
    markers = list("abcdefghijklmnop"[:num_footnotes])
    footnotes = [
        SyntheticFootnote(marker=m, text=t, footnote_type=ft)
        for m, (t, ft) in zip(markers, fn_templates)
    ]

    # Generate cells
    cells: list[SyntheticCell] = []
    for r, proc in enumerate(procedures):
        for c, visit in enumerate(visits):
            # Procedure name in col 0
            if c == 0:
                cells.append(SyntheticCell(row=r, col=c, value=proc, data_type="TEXT"))
                continue

            # Determine cell value
            roll = rng.random()
            if roll < marker_density:
                # Mark as required
                fn_markers = []
                if footnotes and rng.random() < 0.2:
                    fn_markers = [rng.choice(markers)]
                cells.append(SyntheticCell(
                    row=r, col=c, value="X",
                    data_type="CONDITIONAL" if fn_markers else "MARKER",
                    footnote_markers=fn_markers,
                ))
            else:
                cells.append(SyntheticCell(row=r, col=c, value="", data_type="EMPTY"))

    # Build ground truth
    ground_truth = {
        "table_id": name,
        "procedures": procedures,
        "visits": visits,
        "cells": [
            {
                "row": c.row, "col": c.col,
                "value": c.value, "data_type": c.data_type,
                "footnote_markers": c.footnote_markers,
            }
            for c in cells
        ],
        "footnotes": [
            {"marker": f.marker, "text": f.text, "type": f.footnote_type}
            for f in footnotes
        ],
        "num_rows": len(procedures),
        "num_cols": len(visits),
    }

    # Generate HTML
    table_html = _render_html(procedures, visits, cells, footnotes)

    # Determine complexity tier
    if num_procedures <= 8 and num_footnotes <= 2:
        tier = 1
    elif num_procedures <= 15 and num_footnotes <= 5:
        tier = 2
    elif num_procedures <= 20 and num_footnotes <= 10:
        tier = 3
    else:
        tier = 4

    return SyntheticSoA(
        name=name,
        procedures=procedures,
        visits=visits,
        cells=cells,
        footnotes=footnotes,
        complexity_tier=tier,
        html=table_html,
        ground_truth=ground_truth,
    )


def save_synthetic_set(
    output_dir: Path,
    count: int = 10,
    seed: int = 42,
) -> list[dict]:
    """Generate a set of synthetic SoA tables with varying complexity."""
    output_dir.mkdir(parents=True, exist_ok=True)

    configs = [
        {"name": "simple_general", "domain": "general", "num_procedures": 8, "num_visits": 6, "num_footnotes": 2},
        {"name": "simple_vaccine", "domain": "vaccine", "num_procedures": 10, "num_visits": 7, "num_footnotes": 3},
        {"name": "moderate_general", "domain": "general", "num_procedures": 15, "num_visits": 10, "num_footnotes": 5},
        {"name": "moderate_oncology", "domain": "oncology", "num_procedures": 15, "num_visits": 8, "num_footnotes": 6},
        {"name": "complex_vaccine", "domain": "vaccine", "num_procedures": 18, "num_visits": 10, "num_footnotes": 8},
        {"name": "complex_oncology", "domain": "oncology", "num_procedures": 20, "num_visits": 11, "num_footnotes": 10},
        {"name": "dense_general", "domain": "general", "num_procedures": 17, "num_visits": 12, "num_footnotes": 7, "marker_density": 0.6},
        {"name": "sparse_general", "domain": "general", "num_procedures": 12, "num_visits": 8, "num_footnotes": 4, "marker_density": 0.2},
        {"name": "many_footnotes", "domain": "oncology", "num_procedures": 15, "num_visits": 8, "num_footnotes": 12},
        {"name": "wide_table", "domain": "general", "num_procedures": 10, "num_visits": 12, "num_footnotes": 5},
    ]

    manifest = []
    for i, cfg in enumerate(configs[:count]):
        soa = generate_synthetic_soa(seed=seed + i, **cfg)

        # Save HTML
        html_path = output_dir / f"{soa.name}.html"
        html_path.write_text(soa.html, encoding="utf-8")

        # Save ground truth
        gt_path = output_dir / f"{soa.name}_ground_truth.json"
        gt_path.write_text(json.dumps(soa.ground_truth, indent=2), encoding="utf-8")

        manifest.append({
            "name": soa.name,
            "html_file": html_path.name,
            "ground_truth_file": gt_path.name,
            "complexity_tier": soa.complexity_tier,
            "procedures": len(soa.procedures),
            "visits": len(soa.visits),
            "footnotes": len(soa.footnotes),
            "total_cells": len(soa.cells),
        })

    # Save manifest
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return manifest


def _render_html(procedures, visits, cells, footnotes) -> str:
    """Render SoA table as HTML."""
    cell_map = {(c.row, c.col): c for c in cells}

    rows = ['<html><head><style>',
            'table { border-collapse: collapse; font-family: Arial, sans-serif; font-size: 11px; }',
            'th { background: #f0f0f0; padding: 6px 8px; border: 1px solid #ccc; font-weight: bold; }',
            'td { padding: 4px 8px; border: 1px solid #ccc; text-align: center; }',
            'td.proc { text-align: left; font-weight: 500; }',
            'sup { color: #0066cc; font-size: 9px; }',
            '.footnotes { margin-top: 12px; font-size: 10px; color: #333; }',
            '</style></head><body>',
            '<h3>Schedule of Activities</h3>',
            '<table>',
            '<thead><tr><th>Procedure</th>']

    for v in visits[1:]:  # Skip first (procedure name column)
        rows.append(f'<th>{html.escape(v)}</th>')
    rows.append('</tr></thead><tbody>')

    for r, proc in enumerate(procedures):
        rows.append('<tr>')
        rows.append(f'<td class="proc">{html.escape(proc)}</td>')
        for c in range(1, len(visits)):
            cell = cell_map.get((r, c))
            if cell and cell.value:
                fn_sup = "".join(f'<sup>{m}</sup>' for m in cell.footnote_markers)
                rows.append(f'<td>{html.escape(cell.value)}{fn_sup}</td>')
            else:
                rows.append('<td></td>')
        rows.append('</tr>')

    rows.append('</tbody></table>')

    if footnotes:
        rows.append('<div class="footnotes">')
        for fn in footnotes:
            rows.append(f'<p><sup>{fn.marker}</sup> {html.escape(fn.text)}</p>')
        rows.append('</div>')

    rows.append('</body></html>')
    return '\n'.join(rows)


if __name__ == "__main__":
    output = Path(__file__).parent / "generated"
    manifest = save_synthetic_set(output, count=10)
    print(f"Generated {len(manifest)} synthetic SoA tables in {output}")
    for m in manifest:
        print(f"  {m['name']}: {m['procedures']} procedures × {m['visits']} visits, {m['footnotes']} footnotes (tier {m['complexity_tier']})")
