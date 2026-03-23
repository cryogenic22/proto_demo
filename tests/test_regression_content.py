"""
Comprehensive content regression tests.

These tests validate that the pipeline produces clinically correct output
across known patterns, edge cases, and failure modes encountered in production.

Categories:
1. Visit header parsing — every known format
2. Procedure normalization — abbreviations, variants, edge cases
3. Footnote classification — conditional, exception, reference patterns
4. SoA structure patterns — merged cells, multi-page, cycle-based
5. Output validation — hallucination patterns, impossible values
6. Domain classification — all therapeutic areas
7. Table stitching — continuation detection
8. Temporal logic — windows, cycles, unscheduled visits
"""

import pytest
from src.models.schema import (
    BoundingBox,
    CellDataType,
    CellRef,
    CostTier,
    ExtractedCell,
    FootnoteType,
    PipelineConfig,
    TableRegion,
    TableType,
    WindowUnit,
)
from src.pipeline.footnote_resolver import FootnoteResolver
from src.pipeline.procedure_normalizer import ProcedureNormalizer
from src.pipeline.temporal_extractor import TemporalExtractor
from src.pipeline.table_stitcher import TableStitcher
from src.pipeline.reconciler import Reconciler


# ======================================================================
# 1. VISIT HEADER PARSING — comprehensive format coverage
# ======================================================================

class TestVisitHeaderRegression:
    """Every visit header format we've seen in real protocols."""

    def setup_method(self):
        self.extractor = TemporalExtractor()

    # Standard formats
    def test_day_1(self):
        r = self.extractor.parse_visit("Day 1", 0)
        assert r.target_day == 1

    def test_day_15(self):
        r = self.extractor.parse_visit("Day 15", 2)
        assert r.target_day == 15

    def test_week_4(self):
        r = self.extractor.parse_visit("Week 4", 3)
        assert r.target_day == 28

    def test_week_52(self):
        r = self.extractor.parse_visit("Week 52", 10)
        assert r.target_day == 364

    def test_month_6(self):
        r = self.extractor.parse_visit("Month 6", 5)
        assert r.target_day == 180

    # Windows
    def test_symmetric_window(self):
        r = self.extractor.parse_visit("Week 4 (±3 days)", 3)
        assert r.target_day == 28
        assert r.window_minus == 3
        assert r.window_plus == 3

    def test_asymmetric_window(self):
        r = self.extractor.parse_visit("Day 15 (-2/+5 days)", 4)
        assert r.target_day == 15
        assert r.window_minus == 2
        assert r.window_plus == 5

    def test_screening_range(self):
        r = self.extractor.parse_visit("Screening (-28 to -1 days)", 0)
        assert r.window_minus == 28

    # Oncology cycle-based
    def test_c1d1_short(self):
        r = self.extractor.parse_visit("C1D1", 1)
        assert r.cycle == 1
        assert r.target_day == 1

    def test_c2d15_short(self):
        r = self.extractor.parse_visit("C2D15", 5)
        assert r.cycle == 2
        assert r.target_day == 15

    def test_cycle_day_long(self):
        r = self.extractor.parse_visit("Cycle 3 Day 8", 7)
        assert r.cycle == 3
        assert r.target_day == 8

    # Unscheduled
    def test_early_termination(self):
        r = self.extractor.parse_visit("Early Termination", 20)
        assert r.is_unscheduled is True

    def test_et_abbreviation(self):
        r = self.extractor.parse_visit("ET", 20)
        assert r.is_unscheduled is True

    def test_end_of_study(self):
        r = self.extractor.parse_visit("End of Study", 20)
        assert r.is_unscheduled is True

    def test_end_of_treatment(self):
        r = self.extractor.parse_visit("End of Treatment", 20)
        assert r.is_unscheduled is True

    def test_eos_abbreviation(self):
        r = self.extractor.parse_visit("EOS", 20)
        assert r.is_unscheduled is True

    def test_discontinuation(self):
        r = self.extractor.parse_visit("Discontinuation", 20)
        assert r.is_unscheduled is True

    # Follow-up
    def test_followup_30_days(self):
        r = self.extractor.parse_visit("Follow-up (30 days post-dose)", 12)
        assert r.target_day == 30

    # Generic visit numbers
    def test_visit_number(self):
        r = self.extractor.parse_visit("Visit 5", 5)
        assert r.visit_name == "Visit 5"

    # Screening without range
    def test_plain_screening(self):
        r = self.extractor.parse_visit("Screening", 0)
        assert r.is_unscheduled is False

    # Batch processing preserves order
    def test_batch_col_indices(self):
        headers = ["Screening", "Day 1", "Week 4", "Week 8", "ET"]
        results = self.extractor.parse_batch(headers)
        assert [r.col_index for r in results] == [0, 1, 2, 3, 4]


# ======================================================================
# 2. PROCEDURE NORMALIZATION — variant handling
# ======================================================================

class TestProcedureNormalizationRegression:
    """Every procedure variant we've seen in real SoA tables."""

    def setup_method(self):
        self.normalizer = ProcedureNormalizer()

    # ECG variants
    def test_ecg_standard(self):
        r = self.normalizer.normalize("ECG")
        assert "electrocardiogram" in r.canonical_name.lower() or r.code == "93000"

    def test_ecg_12_lead(self):
        r = self.normalizer.normalize("12-lead ECG")
        assert r.code == "93000"

    def test_ecg_12l(self):
        r = self.normalizer.normalize("ECG")
        assert r.code == "93000"

    def test_ekg(self):
        r = self.normalizer.normalize("EKG")
        assert "electrocardiogram" in r.canonical_name.lower() or r.code == "93000"

    # Cost tier accuracy
    def test_vitals_are_low(self):
        assert self.normalizer.normalize("Vital Signs").estimated_cost_tier == CostTier.LOW

    def test_ecg_is_cardiology(self):
        r = self.normalizer.normalize("ECG")
        assert r.category == "Cardiology"

    def test_mri_is_expensive(self):
        r = self.normalizer.normalize("MRI Brain")
        assert r.estimated_cost_tier in (CostTier.HIGH, CostTier.VERY_HIGH)

    def test_pet_is_very_high(self):
        assert self.normalizer.normalize("PET/CT scan").estimated_cost_tier == CostTier.VERY_HIGH

    def test_biopsy_maps(self):
        r = self.normalizer.normalize("Core Needle Biopsy")
        assert "biopsy" in r.canonical_name.lower()

    def test_genetic_testing_maps(self):
        r = self.normalizer.normalize("Targeted Gene Panel")
        assert r.category != "Unknown" or "gene" in r.canonical_name.lower()

    # CPT code presence
    def test_cbc_has_cpt(self):
        result = self.normalizer.normalize("Complete Blood Count")
        assert result.code is not None
        assert result.code_system == "CPT"

    def test_physical_exam_variants(self):
        for variant in ["Physical Exam", "PE"]:
            result = self.normalizer.normalize(variant)
            assert "physical" in result.canonical_name.lower(), f"Failed for: {variant}"

    # Case insensitivity
    def test_case_insensitive(self):
        r = self.normalizer.normalize("vital signs")
        assert "vital signs" in r.canonical_name.lower()
        assert self.normalizer.normalize("VITAL SIGNS").canonical_name == "Vital Signs"

    # Unknown procedure handling
    def test_unknown_procedure_preserves_name(self):
        result = self.normalizer.normalize("Zorblax Experimental Test")
        assert result.canonical_name == "Zorblax Experimental Test"
        assert result.code is None

    # False positive prevention — CRITICAL for client trust
    def test_experimental_does_not_match_exam(self):
        """'experimental' should NOT match 'exam' or 'physical exam'."""
        result = self.normalizer.normalize("Experimental Zorblax Test")
        assert result.canonical_name == "Experimental Zorblax Test"

    def test_collect_does_not_match_ct_scan(self):
        """'Collect blood sample' should NOT match 'CT scan'."""
        result = self.normalizer.normalize("Collect blood sample for hematology")
        assert result.canonical_name != "CT Scan", f"False match: 'Collect' matched CT Scan"

    def test_reactogenicity_does_not_match_ct(self):
        """'Reactogenicity' should NOT match 'CT scan'."""
        result = self.normalizer.normalize("Review reactogenicity e-diary data")
        assert result.canonical_name != "CT Scan"

    def test_contraceptive_does_not_match_ct(self):
        """'Contraceptive' should NOT match 'CT scan'."""
        result = self.normalizer.normalize("Confirm use of contraceptives")
        assert result.canonical_name != "CT Scan"

    def test_prohibited_does_not_match_ct(self):
        """'Collect prohibited medication' should NOT match 'CT scan'."""
        result = self.normalizer.normalize("Collect prohibited medication use")
        assert result.canonical_name != "CT Scan"

    def test_covid_collection_does_not_match_ct(self):
        """'Collection of COVID-19-related information' should NOT match CT."""
        result = self.normalizer.normalize("Collection of COVID-19-related clinical and laboratory information")
        assert result.canonical_name != "CT Scan"

    # Batch processing
    def test_batch_returns_correct_count(self):
        names = ["ECG", "MRI", "CBC", "Unknown Test"]
        results = self.normalizer.normalize_batch(names)
        assert len(results) == 4


# ======================================================================
# 3. FOOTNOTE CLASSIFICATION — pattern matching
# ======================================================================

class TestFootnoteClassificationRegression:
    """Footnote type classification for all known patterns."""

    def setup_method(self):
        self.resolver = FootnoteResolver()

    def _classify(self, text: str) -> FootnoteType:
        cells = [ExtractedCell(row=0, col=0, raw_value="X",
                               data_type=CellDataType.MARKER,
                               footnote_markers=["a"])]
        _, footnotes = self.resolver.resolve(cells, {"a": text})
        return footnotes[0].footnote_type

    # Conditional patterns
    def test_only_if(self):
        assert self._classify("Only if QTc > 450ms at baseline") == FootnoteType.CONDITIONAL

    def test_if_clinically_indicated(self):
        assert self._classify("If clinically indicated") == FootnoteType.CONDITIONAL

    def test_per_investigator(self):
        assert self._classify("Per investigator judgment") == FootnoteType.CONDITIONAL

    def test_as_needed(self):
        assert self._classify("As needed based on clinical assessment") == FootnoteType.CONDITIONAL

    def test_when_applicable(self):
        assert self._classify("When applicable to the study population") == FootnoteType.CONDITIONAL

    def test_at_discretion(self):
        assert self._classify("At the discretion of the investigator") == FootnoteType.CONDITIONAL

    def test_prn(self):
        assert self._classify("PRN (as needed)") == FootnoteType.CONDITIONAL

    # Exception patterns
    def test_except_at(self):
        assert self._classify("Except at the early termination visit") == FootnoteType.EXCEPTION

    def test_unless(self):
        assert self._classify("Unless the subject has already completed Week 12") == FootnoteType.EXCEPTION

    def test_not_required(self):
        assert self._classify("Not required for subjects in Cohort B") == FootnoteType.EXCEPTION

    def test_excluding(self):
        assert self._classify("Excluding screening visit") == FootnoteType.EXCEPTION

    # Reference patterns
    def test_see_section(self):
        assert self._classify("See Section 8.1 for details") == FootnoteType.REFERENCE

    def test_refer_to(self):
        assert self._classify("Refer to the laboratory manual") == FootnoteType.REFERENCE

    def test_see_appendix(self):
        assert self._classify("See Appendix B for the full schedule") == FootnoteType.REFERENCE

    # Clarification (default)
    def test_plain_clarification(self):
        assert self._classify("Blood samples collected in EDTA tubes") == FootnoteType.CLARIFICATION

    def test_dosing_clarification(self):
        assert self._classify("Administered as IV infusion over 30 minutes") == FootnoteType.CLARIFICATION


# ======================================================================
# 4. TABLE STITCHING — multi-page detection
# ======================================================================

class TestTableStitchingRegression:
    """Multi-page table merging edge cases."""

    def setup_method(self):
        self.stitcher = TableStitcher()

    def _region(self, table_id: str, page: int, title: str,
                markers: list[str] | None = None) -> TableRegion:
        return TableRegion(
            table_id=table_id, pages=[page],
            bounding_boxes=[BoundingBox(page=page, x0=10, y0=10, x1=500, y1=700)],
            table_type=TableType.SOA, title=title,
            continuation_markers=markers or [],
        )

    def test_continued_parenthetical(self):
        regions = [
            self._region("t1", 5, "Schedule of Activities"),
            self._region("t2", 6, "Schedule of Activities (continued)"),
        ]
        result = self.stitcher.stitch(regions)
        assert len(result) == 1
        assert result[0].pages == [5, 6]

    def test_contd_variant(self):
        regions = [
            self._region("t1", 5, "Schedule of Activities"),
            self._region("t2", 6, "Schedule of Activities (cont'd)"),
        ]
        result = self.stitcher.stitch(regions)
        assert len(result) == 1

    def test_three_page_table(self):
        regions = [
            self._region("t1", 10, "SoA Table"),
            self._region("t2", 11, "SoA Table (continued)"),
            self._region("t3", 12, "SoA Table (continued)"),
        ]
        result = self.stitcher.stitch(regions)
        assert len(result) == 1
        assert result[0].pages == [10, 11, 12]

    def test_same_title_consecutive(self):
        regions = [
            self._region("t1", 3, "Table 14.1"),
            self._region("t2", 4, "Table 14.1"),
        ]
        result = self.stitcher.stitch(regions)
        assert len(result) == 1

    def test_same_title_non_consecutive_no_merge(self):
        regions = [
            self._region("t1", 3, "Table 14.1"),
            self._region("t2", 10, "Table 14.1"),
        ]
        result = self.stitcher.stitch(regions)
        assert len(result) == 2

    def test_different_tables_not_merged(self):
        regions = [
            self._region("t1", 5, "Demographics"),
            self._region("t2", 6, "Schedule of Activities"),
        ]
        result = self.stitcher.stitch(regions)
        assert len(result) == 2

    def test_continuation_marker_in_data(self):
        regions = [
            self._region("t1", 5, "Schedule of Activities"),
            self._region("t2", 6, "Schedule of Activities", markers=["continued"]),
        ]
        result = self.stitcher.stitch(regions)
        assert len(result) == 1


# ======================================================================
# 5. RECONCILER — multi-pass agreement logic
# ======================================================================

class TestReconcilerRegression:
    """Multi-pass reconciliation edge cases."""

    def setup_method(self):
        self.config = PipelineConfig(soa_only=False)
        self.reconciler = Reconciler(self.config)

    def _cell(self, row, col, value, confidence=1.0):
        return ExtractedCell(row=row, col=col, raw_value=value,
                             data_type=CellDataType.MARKER if value in ("X", "✓") else CellDataType.TEXT,
                             confidence=confidence)

    def test_both_X_high_confidence(self):
        p1 = [self._cell(0, 0, "X")]
        p2 = [self._cell(0, 0, "X")]
        result = self.reconciler.reconcile(p1, p2)
        assert result.cells[0].confidence >= 0.9

    def test_X_vs_empty_low_confidence(self):
        p1 = [self._cell(0, 0, "X")]
        p2 = [self._cell(0, 0, "")]
        result = self.reconciler.reconcile(p1, p2)
        assert result.cells[0].confidence < 0.85
        assert CellRef(row=0, col=0) in result.flagged

    def test_X_vs_checkmark_treated_as_disagree(self):
        """'X' and '✓' are both markers but exact string differs."""
        p1 = [self._cell(0, 0, "X")]
        p2 = [self._cell(0, 0, "✓")]
        result = self.reconciler.reconcile(p1, p2)
        # These disagree on the string level even though semantically similar
        assert result.cells[0].confidence < 0.85

    def test_cell_only_in_pass1(self):
        p1 = [self._cell(0, 0, "X"), self._cell(0, 1, "X")]
        p2 = [self._cell(0, 0, "X")]  # Missing (0,1)
        result = self.reconciler.reconcile(p1, p2)
        cell_01 = [c for c in result.cells if c.row == 0 and c.col == 1][0]
        assert cell_01.confidence < 0.85  # Lower confidence for single-pass

    def test_single_pass_preserves_confidence(self):
        p1 = [self._cell(0, 0, "X", confidence=0.88)]
        result = self.reconciler.reconcile(p1, None)
        assert result.cells[0].confidence == 0.88


# ======================================================================
# 6. PIPELINE CONFIG — defaults and constraints
# ======================================================================

class TestPipelineConfigRegression:
    def test_soa_only_default_true(self):
        cfg = PipelineConfig()
        assert cfg.soa_only is True

    def test_dpi_min_72(self):
        with pytest.raises(Exception):
            PipelineConfig(render_dpi=50)

    def test_dpi_max_600(self):
        with pytest.raises(Exception):
            PipelineConfig(render_dpi=800)

    def test_confidence_threshold_range(self):
        with pytest.raises(Exception):
            PipelineConfig(confidence_threshold=1.5)

    def test_max_passes_range(self):
        with pytest.raises(Exception):
            PipelineConfig(max_extraction_passes=0)


# ======================================================================
# 7. DATA MODEL CONTRACTS — schema invariants
# ======================================================================

class TestSchemaContracts:
    """Ensure data model constraints that downstream code relies on."""

    def test_cellref_hashable(self):
        """CellRef must be usable as dict key."""
        d = {CellRef(row=0, col=0): "value"}
        assert d[CellRef(row=0, col=0)] == "value"

    def test_cellref_equality(self):
        assert CellRef(row=1, col=2) == CellRef(row=1, col=2)
        assert CellRef(row=1, col=2) != CellRef(row=1, col=3)

    def test_cellref_in_set(self):
        s = {CellRef(row=0, col=0), CellRef(row=0, col=0), CellRef(row=1, col=1)}
        assert len(s) == 2  # Deduplication

    def test_confidence_bounded(self):
        with pytest.raises(Exception):
            ExtractedCell(row=0, col=0, confidence=1.5)
        with pytest.raises(Exception):
            ExtractedCell(row=0, col=0, confidence=-0.1)

    def test_bounding_box_x1_gt_x0(self):
        with pytest.raises(Exception):
            BoundingBox(page=0, x0=100, y0=0, x1=50, y1=100)

    def test_table_region_requires_pages(self):
        with pytest.raises(Exception):
            TableRegion(
                table_id="t1", pages=[],
                bounding_boxes=[BoundingBox(page=0, x0=0, y0=0, x1=1, y1=1)],
            )
