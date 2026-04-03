"""
Generate a benchmark PDF containing diverse formula text for formula-detection testing.

Sections cover chemical, dosing/PK, statistical, mathematical, clinical/pharma,
and mixed stress-test formulas. Normal prose paragraphs are interspersed to test
for false positives.

Usage:
    python tests/fixtures/create_formula_benchmark.py       # standalone
    from tests.fixtures.create_formula_benchmark import generate; generate()
"""
from __future__ import annotations

import os
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------

_OUTPUT_DIR = Path(__file__).resolve().parent
_OUTPUT_PATH = _OUTPUT_DIR / "formula_benchmark.pdf"


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

_SECTIONS: list[tuple[str, list[str]]] = [
    # ---- Section 1: Chemical ----
    (
        "Section 1: Chemical Formulas",
        [
            "The following chemical species were measured during the study:",
            "CO2, H2O, O2, N2, HbA1c, PO4, Ca2+, Na+, K+, Cl-.",
            "Dissolved oxygen (O2) levels were monitored continuously. "
            "CO2 partial pressure and H2O content were recorded at each visit.",
        ],
    ),

    # ---- Prose interlude (false-positive bait) ----
    (
        "Study Design",
        [
            "This protocol describes a randomized, double-blind study. "
            "Subjects were enrolled across multiple sites. The study was "
            "conducted in accordance with GCP guidelines.",
            "Informed consent was obtained from all participants prior to "
            "any study-related procedures. The protocol was reviewed and "
            "approved by the institutional review board.",
        ],
    ),

    # ---- Section 2: Dosing & PK ----
    (
        "Section 2: Dosing and Pharmacokinetic Parameters",
        [
            "The recommended dose was 200 mg/m2 administered intravenously.",
            "Cell viability was assessed at x10^6 cells/mL before infusion.",
            "Primary PK parameters included AUC0-inf, AUC0-t, Cmax, Cmin, "
            "t1/2, tmax, and Vd.",
            "Apparent oral clearance (CL/F) was derived from the model.",
        ],
    ),

    # ---- Prose interlude ----
    (
        "Eligibility Criteria",
        [
            "Eligible subjects were adults aged 18 to 75 years with a "
            "confirmed diagnosis. Exclusion criteria included prior organ "
            "transplant, active infection, or pregnancy.",
        ],
    ),

    # ---- Section 3: Statistical ----
    (
        "Section 3: Statistical Notation",
        [
            "The primary analysis showed p < 0.001 with HR 0.67.",
            "The 95% CI: 0.45-0.99 was reported for the hazard ratio.",
            "Variability was expressed as %RSD and %CV.",
            "Immunogenicity endpoints included GMT, GMFR, and log10 Titer.",
            "Descriptive statistics included SD and SEM for continuous variables.",
        ],
    ),

    # ---- Section 4: Mathematical ----
    (
        "Section 4: Mathematical Expressions",
        [
            "Variance was expressed as sigma^2 with sample size sqrt(n).",
            "The natural logarithm ln(x) was used for transformation.",
            "The expression 10^ln(10) was evaluated numerically.",
            "Factorial notation: n! denotes the product of integers 1 through n.",
            "Summation: sum_{i=1}^{n} and product: prod_{i=1}^{n} were used.",
            "The limiting behavior was examined via lim_{x->0}.",
        ],
    ),

    # ---- Prose interlude ----
    (
        "Data Management",
        [
            "Data were collected using an electronic data capture system. "
            "All data management activities followed the pre-specified plan. "
            "Queries were generated automatically and resolved by the site.",
        ],
    ),

    # ---- Section 5: Clinical / Pharma ----
    (
        "Section 5: Clinical and Pharmaceutical Formulas",
        [
            "Vaccine efficacy was defined as VE = 100 x (1 - IRR).",
            "Number needed to treat was computed as NNT = 1/ARR.",
            "The one-compartment PK model used dC/dt = -k*C.",
            "Renal function was estimated by CrCl = ((140-age)*weight)/(72*SCr).",
            "The limit of detection was determined as LOD = 3.3*sigma/S.",
            "Kaplan-Meier survival was estimated as S(t) = prod(1-di/ni).",
        ],
    ),

    # ---- Section 6: Mixed Stress Test ----
    (
        "Section 6: Mixed Stress Test",
        [
            "The primary endpoint was met (p < 0.001, HR 0.67). "
            "AUC0-inf was 245.3 with Cmax of 45.2 ng/mL. The %RSD was "
            "2.1% and log10 Titer showed GMT of 256.0.",
            "CO2 levels remained stable throughout the infusion of 200 mg/m2. "
            "The t1/2 of 12.4 hours was consistent with prior studies.",
        ],
    ),
]


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def generate(output_path: str | Path | None = None) -> Path:
    """Generate the formula benchmark PDF and return its path.

    Args:
        output_path: Override the default output location.

    Returns:
        Path to the generated PDF file.
    """
    dest = Path(output_path) if output_path else _OUTPUT_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(dest),
        pagesize=letter,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "BenchTitle",
        parent=styles["Title"],
        fontSize=18,
        spaceAfter=24,
    )
    heading_style = ParagraphStyle(
        "BenchHeading",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=18,
        spaceAfter=10,
    )
    body_style = ParagraphStyle(
        "BenchBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
    )

    story: list = []

    # Title page
    story.append(Paragraph("Formula Detection Benchmark Document", title_style))
    story.append(Paragraph(
        "Protocol XYZ-2026-001 &mdash; Comprehensive Formula Coverage Test",
        body_style,
    ))
    story.append(Spacer(1, 0.3 * inch))

    # Sections
    for heading, paragraphs in _SECTIONS:
        story.append(Paragraph(heading, heading_style))
        for text in paragraphs:
            story.append(Paragraph(text, body_style))
        story.append(Spacer(1, 0.15 * inch))

    doc.build(story)
    return dest


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    path = generate()
    print(f"Benchmark PDF generated: {path}")
    print(f"Size: {os.path.getsize(path):,} bytes")
