"""
Formula benchmark tests — validates detection coverage across formula types.

Generates a benchmark PDF with diverse pharma formulas, ingests it through the
DocHandler pipeline, runs the formula detection system, and asserts minimum
coverage thresholds per formula type.

Run:
    python -m pytest tests/test_formula_benchmark.py -v
    python tests/test_formula_benchmark.py            # standalone summary
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path


class TestFormulaBenchmark:
    """End-to-end formula detection benchmark against a generated PDF."""

    @classmethod
    def setup_class(cls):
        # 1. Generate the benchmark PDF
        from tests.fixtures.create_formula_benchmark import generate
        generate()

        # 2. Ingest with DocHandler
        from src.formatter import DocHandler
        handler = DocHandler()
        pdf_path = Path(__file__).resolve().parent / "fixtures" / "formula_benchmark.pdf"
        content = pdf_path.read_bytes()
        cls.doc = handler.ingest(content, "pdf", "formula_benchmark.pdf")

        # 3. Run formula detection across all paragraphs
        from src.formatter.formula.factory import create_formula_system
        cls.orchestrator = create_formula_system()
        cls.all_formulas = []
        cls.para_texts = []
        for page in cls.doc.pages:
            for para in page.paragraphs:
                text = para.text
                cls.para_texts.append(text)
                spans = cls.orchestrator.process_text(text)
                cls.all_formulas.extend(spans)

    # ------------------------------------------------------------------
    # Coverage thresholds
    # ------------------------------------------------------------------

    def test_total_formulas_detected(self):
        """At least 30 distinct formulas should be detected across all sections."""
        assert len(self.all_formulas) >= 30, (
            f"Only {len(self.all_formulas)} formulas detected, expected >= 30"
        )

    def test_chemical_count(self):
        """At least 5 chemical formulas (CO2, H2O, O2, N2, HbA1c, etc.)."""
        chems = [f for f in self.all_formulas
                 if f.formula.formula_type.value == "chemical"]
        assert len(chems) >= 5, (
            f"Only {len(chems)} chemical formulas detected, expected >= 5. "
            f"Found: {[f.original_text for f in chems]}"
        )

    def test_pk_count(self):
        """At least 5 PK formulas (AUC0-inf, AUC0-t, Cmax, Cmin, t1/2, etc.)."""
        pks = [f for f in self.all_formulas
               if f.formula.formula_type.value == "pk"]
        assert len(pks) >= 5, (
            f"Only {len(pks)} PK formulas detected, expected >= 5. "
            f"Found: {[f.original_text for f in pks]}"
        )

    def test_statistical_count(self):
        """At least 5 statistical formulas (p-values, HR, CI, %RSD, etc.)."""
        stats = [f for f in self.all_formulas
                 if f.formula.formula_type.value == "statistical"]
        assert len(stats) >= 5, (
            f"Only {len(stats)} statistical formulas detected, expected >= 5. "
            f"Found: {[f.original_text for f in stats]}"
        )

    def test_mathematical_count(self):
        """At least 3 mathematical formulas (sigma^2, sqrt, log10, etc.)."""
        maths = [f for f in self.all_formulas
                 if f.formula.formula_type.value == "mathematical"]
        assert len(maths) >= 3, (
            f"Only {len(maths)} mathematical formulas detected, expected >= 3. "
            f"Found: {[f.original_text for f in maths]}"
        )

    def test_no_unknown_types(self):
        """No formula should be classified as 'unknown'."""
        unknowns = [f for f in self.all_formulas
                    if f.formula.formula_type.value == "unknown"]
        assert len(unknowns) == 0, (
            f"{len(unknowns)} formulas classified as unknown: "
            f"{[f.original_text for f in unknowns]}"
        )

    def test_latex_for_transforms(self):
        """Every formula with an HTML transform must also have LaTeX."""
        with_html = [f for f in self.all_formulas
                     if f.formula.html and f.formula.html != f.original_text]
        for f in with_html:
            assert f.formula.latex, (
                f"Missing LaTeX for transformed formula: '{f.original_text}' "
                f"-> html='{f.formula.html}'"
            )

    def test_prose_no_false_positives(self):
        """Normal prose words like 'protocol' or 'randomized' must not trigger."""
        prose_hits = [f for f in self.all_formulas
                      if "protocol" in f.original_text.lower()
                      or "randomized" in f.original_text.lower()
                      or "subjects" in f.original_text.lower()]
        assert len(prose_hits) == 0, (
            f"False positives in prose: {[f.original_text for f in prose_hits]}"
        )

    def test_mixed_section_detects_multiple_types(self):
        """The mixed stress-test paragraph should yield at least 3 formula types."""
        # Find mixed section paragraphs (contain both "p < 0.001" and "AUC")
        mixed_formulas = []
        for page in self.doc.pages:
            for para in page.paragraphs:
                text = para.text
                if "primary endpoint was met" in text.lower():
                    spans = self.orchestrator.process_text(text)
                    mixed_formulas.extend(spans)
        types_found = {f.formula.formula_type.value for f in mixed_formulas}
        assert len(types_found) >= 3, (
            f"Mixed section only detected {len(types_found)} types: {types_found}, "
            f"expected >= 3"
        )

    def test_dosing_count(self):
        """At least 2 dosing formulas (mg/m2, cells/mL multiplier, etc.)."""
        dosing = [f for f in self.all_formulas
                  if f.formula.formula_type.value == "dosing"]
        assert len(dosing) >= 2, (
            f"Only {len(dosing)} dosing formulas detected, expected >= 2. "
            f"Found: {[f.original_text for f in dosing]}"
        )

    def test_efficacy_count(self):
        """At least 1 efficacy formula (VE=, NNT=, ARR)."""
        efficacy = [f for f in self.all_formulas
                    if f.formula.formula_type.value == "efficacy"]
        assert len(efficacy) >= 1, (
            f"No efficacy formulas detected. "
            f"All types: {Counter(f.formula.formula_type.value for f in self.all_formulas)}"
        )


# ---------------------------------------------------------------------------
# Standalone benchmark summary
# ---------------------------------------------------------------------------

def _run_benchmark_summary():
    """Print a detailed summary table — useful outside pytest."""
    from tests.fixtures.create_formula_benchmark import generate
    generate()

    from src.formatter import DocHandler
    handler = DocHandler()
    pdf_path = Path(__file__).resolve().parent / "fixtures" / "formula_benchmark.pdf"
    content = pdf_path.read_bytes()
    doc = handler.ingest(content, "pdf", "formula_benchmark.pdf")

    from src.formatter.formula.factory import create_formula_system
    orchestrator = create_formula_system()

    all_formulas = []
    for page in doc.pages:
        for para in page.paragraphs:
            spans = orchestrator.process_text(para.text)
            all_formulas.extend(spans)

    # Summary
    type_counts = Counter(f.formula.formula_type.value for f in all_formulas)
    source_counts = Counter(f.formula.source.value for f in all_formulas)
    complexity_counts = Counter(f.formula.complexity.value for f in all_formulas)

    print("\n" + "=" * 72)
    print("  FORMULA BENCHMARK SUMMARY")
    print("=" * 72)
    print(f"  Total formulas detected: {len(all_formulas)}")
    print(f"  Total paragraphs:        {doc.total_paragraphs}")
    print()

    print("  BY TYPE:")
    print("  " + "-" * 40)
    for ftype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        bar = "#" * count
        print(f"    {ftype:<15} {count:>3}  {bar}")
    print()

    print("  BY SOURCE:")
    print("  " + "-" * 40)
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"    {src:<15} {count:>3}")
    print()

    print("  BY COMPLEXITY:")
    print("  " + "-" * 40)
    for cplx, count in sorted(complexity_counts.items(), key=lambda x: -x[1]):
        print(f"    {cplx:<15} {count:>3}")
    print()

    # Detail listing
    print("  DETAILED DETECTIONS:")
    print("  " + "-" * 68)
    print(f"  {'Original':<30} {'Type':<15} {'Source':<10} {'LaTeX'}")
    print("  " + "-" * 68)
    for f in sorted(all_formulas, key=lambda x: (x.formula.formula_type.value, x.original_text)):
        latex_preview = (f.formula.latex[:30] + "...") if len(f.formula.latex) > 30 else f.formula.latex
        print(f"  {f.original_text:<30} {f.formula.formula_type.value:<15} "
              f"{f.formula.source.value:<10} {latex_preview}")

    print("=" * 72)
    print()

    # Quick pass/fail summary
    thresholds = {
        "chemical": 5,
        "pk": 5,
        "statistical": 5,
        "mathematical": 3,
        "dosing": 2,
        "efficacy": 1,
    }
    all_pass = True
    for ftype, minimum in thresholds.items():
        actual = type_counts.get(ftype, 0)
        status = "PASS" if actual >= minimum else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}] {ftype:<15} {actual:>3} / {minimum} minimum")

    unknowns = type_counts.get("unknown", 0)
    unk_status = "PASS" if unknowns == 0 else "FAIL"
    if unknowns > 0:
        all_pass = False
    print(f"  [{unk_status}] {'no unknowns':<15} {unknowns:>3} (should be 0)")

    total_status = "PASS" if len(all_formulas) >= 30 else "FAIL"
    if len(all_formulas) < 30:
        all_pass = False
    print(f"  [{total_status}] {'total >= 30':<15} {len(all_formulas):>3}")

    print()
    if all_pass:
        print("  >>> ALL BENCHMARKS PASSED <<<")
    else:
        print("  >>> SOME BENCHMARKS FAILED <<<")
    print()


if __name__ == "__main__":
    # Ensure the project root is on sys.path for direct script execution
    _project_root = str(Path(__file__).resolve().parent.parent)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    _run_benchmark_summary()
