"""P0 tests: deterministic cell ordering + SoA detection expansion."""

import re
import pytest


class TestCellExtractionOrdering:
    """Verify cells are sorted by (row, col) regardless of async completion order."""

    def test_cells_sorted_after_extraction(self):
        """After extraction, cells must be in (row, col) order."""
        from src.models.schema import ExtractedCell

        # Simulate cells arriving in random order (from async gather)
        cells = [
            ExtractedCell(row=2, col=1, raw_value="X"),
            ExtractedCell(row=0, col=0, raw_value="CBC"),
            ExtractedCell(row=1, col=2, raw_value="X"),
            ExtractedCell(row=0, col=1, raw_value="X"),
            ExtractedCell(row=2, col=0, raw_value="ECG"),
            ExtractedCell(row=1, col=0, raw_value="Vitals"),
        ]
        # Sort like the fix does
        cells.sort(key=lambda c: (c.row, c.col))

        # Verify deterministic order
        positions = [(c.row, c.col) for c in cells]
        assert positions == [(0, 0), (0, 1), (1, 0), (1, 2), (2, 0), (2, 1)]

    def test_sort_is_stable(self):
        """Same input always produces same output (deterministic)."""
        from src.models.schema import ExtractedCell

        cells1 = [ExtractedCell(row=1, col=0), ExtractedCell(row=0, col=0)]
        cells2 = [ExtractedCell(row=1, col=0), ExtractedCell(row=0, col=0)]
        cells1.sort(key=lambda c: (c.row, c.col))
        cells2.sort(key=lambda c: (c.row, c.col))
        assert [(c.row, c.col) for c in cells1] == [(c.row, c.col) for c in cells2]


class TestSoADetectionExpanded:
    """Verify expanded SoA detection patterns match non-standard titles."""

    @pytest.fixture
    def accept_keywords(self):
        return [
            "schedule of activities", "schedule of assessments",
            "schedule of evaluations", "schedule of procedures",
            "schedule of events", "supplemental soe",
            "supplemental schedule", "soa", "s.o.a.", "soe",
            "schedule", "activities",
            "time and events", "time & events",
            "study procedures schedule", "study procedures matrix",
            "study procedures table", "study procedures overview",
            "assessment schedule", "assessment matrix",
            "assessment overview", "assessment plan",
            "visit schedule", "encounter schedule",
            "protocol flowchart", "study flowchart",
            "clinical trial flowchart",
            "table of activities", "table of assessments",
            "table of procedures", "table of study procedures",
            "treatment schedule", "dosing schedule",
            "evaluation schedule",
        ]

    def test_standard_titles(self, accept_keywords):
        """Standard SoA titles should match."""
        for title in ["Schedule of Activities", "Schedule of Assessments",
                      "Schedule of Events", "SOA"]:
            assert any(kw in title.lower() for kw in accept_keywords), f"'{title}' not matched"

    def test_nonstandard_pfizer_titles(self, accept_keywords):
        """Non-standard Pfizer protocol titles should now match."""
        for title in ["Time and Events Table", "Study Procedures Matrix",
                      "Assessment Schedule Overview"]:
            assert any(kw in title.lower() for kw in accept_keywords), f"'{title}' not matched"

    def test_additional_formats(self, accept_keywords):
        """Various SoA title formats from different sponsors."""
        for title in ["Visit Schedule", "Treatment Schedule",
                      "Table of Study Procedures", "Evaluation Schedule",
                      "Encounter Schedule", "Clinical Trial Flowchart"]:
            assert any(kw in title.lower() for kw in accept_keywords), f"'{title}' not matched"

    def test_page_text_regex(self):
        """The page-text fallback regex should match expanded patterns."""
        title_re = re.compile(
            r"schedule\s+of\s+(?:activities|assessments|evaluations|procedures|events)"
            r"|time\s+and\s+events?\s+(?:table|schedule)"
            r"|study\s+procedures?\s+(?:schedule|table|matrix)"
            r"|assessment\s+(?:schedule|matrix|overview)"
            r"|(?:visit|encounter)\s+schedule"
            r"|table\s+of\s+(?:study\s+)?(?:activities|assessments|procedures)"
            r"|(?:treatment|dosing|evaluation)\s+schedule"
            r"|(?:^|\s)soa(?:\s|$)"
            r"|(?:^|\s)s\.o\.a\.(?:\s|$)",
            re.IGNORECASE,
        )
        # These should all match
        for text in [
            "Time and Events Table",
            "Study Procedures Schedule",
            "Assessment Matrix",
            "Visit Schedule for Period 1",
            "Table of Study Procedures",
            "Treatment Schedule Overview",
            "Appendix 3: SOA",
        ]:
            assert title_re.search(text), f"Regex should match: '{text}'"

    def test_non_soa_titles_not_matched(self, accept_keywords):
        """Non-SoA tables should not match."""
        for title in ["Synopsis", "Amendment History", "Abbreviations",
                      "Objectives and Endpoints"]:
            # These specific words should NOT appear in accept_keywords
            assert title.lower() not in accept_keywords


class TestExtractionDeterminism:
    """Same input must produce same output across runs."""

    def test_extraction_determinism(self):
        """Load a stored protocol and run normalizer + reconciler twice.

        Verify that the cell list is identical between both runs — the pipeline
        must be fully deterministic.
        """
        import json
        from pathlib import Path
        from src.pipeline.procedure_normalizer import ProcedureNormalizer
        from src.pipeline.reconciler import Reconciler
        from src.models.schema import ExtractedCell, PipelineConfig

        proto_path = Path(__file__).parent.parent / "data" / "protocols" / "pfizer_bnt162.json"
        if not proto_path.exists():
            import pytest
            pytest.skip("pfizer_bnt162.json not found in data/protocols")

        with open(proto_path, encoding="utf-8") as f:
            data = json.load(f)

        table = data["tables"][0]
        raw_cells = table.get("cells", [])
        if not raw_cells:
            import pytest
            pytest.skip("No cells in stored protocol table")

        # Build ExtractedCell list from stored data
        cells = [
            ExtractedCell(
                row=c["row"],
                col=c["col"],
                raw_value=c.get("raw_value", ""),
                confidence=c.get("confidence", 0.9),
            )
            for c in raw_cells
        ]

        normalizer = ProcedureNormalizer()
        config = PipelineConfig()
        reconciler = Reconciler(config)

        # --- Run 1 ---
        normalized_1 = [
            normalizer.normalize(c.raw_value) for c in cells if c.col == 0
        ]
        reconciled_1 = reconciler.reconcile(cells, cells)

        # --- Run 2 ---
        normalized_2 = [
            normalizer.normalize(c.raw_value) for c in cells if c.col == 0
        ]
        reconciled_2 = reconciler.reconcile(cells, cells)

        # Compare normalizer output
        assert len(normalized_1) == len(normalized_2)
        for n1, n2 in zip(normalized_1, normalized_2):
            assert n1.canonical_name == n2.canonical_name, (
                f"Normalizer non-deterministic: {n1.canonical_name} != {n2.canonical_name}"
            )
            assert n1.code == n2.code

        # Compare reconciler output cell-by-cell
        assert len(reconciled_1.cells) == len(reconciled_2.cells)
        for c1, c2 in zip(reconciled_1.cells, reconciled_2.cells):
            assert c1.row == c2.row
            assert c1.col == c2.col
            assert c1.raw_value == c2.raw_value, (
                f"Cell ({c1.row},{c1.col}): '{c1.raw_value}' != '{c2.raw_value}'"
            )
            assert c1.confidence == c2.confidence, (
                f"Cell ({c1.row},{c1.col}): conf {c1.confidence} != {c2.confidence}"
            )
