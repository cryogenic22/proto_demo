# ProtoExtract — Structured Implementation Plan

## Principles

Every change follows:
1. **Spec first** — define what success looks like before writing code
2. **Test first** — write the failing test before the implementation
3. **Measure first** — establish baseline metric before changing anything
4. **Evidence after** — every change produces a before/after comparison

---

## Phase 0: Establish Measurement Baseline (Week 1)

**Goal:** Before changing anything, measure exactly where we are today so every
future improvement has a quantifiable delta.

### 0.1 Implement TEDS Metric

**Spec:** A function that takes two table representations (extracted vs ground truth)
and returns a Tree Edit Distance Similarity score between 0.0 and 1.0.

**Test first:**
```
test_teds_identical_tables → TEDS = 1.0
test_teds_completely_different → TEDS < 0.1
test_teds_one_cell_wrong → TEDS > 0.95
test_teds_wrong_structure → TEDS < 0.7
test_teds_empty_vs_populated → TEDS = 0.0
```

**Deliverable:** `src/eval/teds.py` with the Zhang-Shasha tree edit distance
algorithm adapted for our `ExtractedTable` schema.

### 0.2 Create Gold-Standard Annotations

**Start with ONE protocol — Pfizer BNT162.** Annotate it fully. Compute actual
TEDS. That single real number anchors everything else. Then add 2 more.

Three fully annotated protocols are more valuable than five partial ones.

| Priority | Protocol | Why | Estimated Effort |
|---|---|---|---|
| **First** | P-13 Pfizer BNT162 | Best understood, most data, anchors all baselines | 12-16 hours |
| **Second** | P-08 Etrasimod UC | Multiple SoA sections, tests multi-table handling | 8-10 hours |
| **Third** | P-01 Brivaracetam | Simple protocol, establishes easy-case ceiling | 4-6 hours |

**Format per table:**
```json
{
  "protocol_id": "P-13",
  "table_id": "soa_phase2_3",
  "ground_truth_cells": [
    {"row": 0, "col": 0, "value": "Physical Examination", "type": "TEXT"},
    {"row": 0, "col": 1, "value": "X", "type": "MARKER", "footnotes": ["a"]},
    ...
  ],
  "ground_truth_footnotes": [
    {"marker": "a", "text": "Only if clinically indicated", "type": "CONDITIONAL",
     "applies_to": [{"row": 0, "col": 1}, {"row": 0, "col": 3}]}
  ],
  "attributes": {
    "border_type": "full",
    "merged_cells": true,
    "footnote_count": 18,
    "column_count": 20,
    "multi_page": true,
    "sponsor_format": "pfizer"
  }
}
```

**Deliverable:** `golden_set/annotations/P-01.json` through `P-18.json`

### 0.3 Implement Cost-Weighted Accuracy Metric

**Spec:** A metric that weights cell errors by their financial impact on the
site budget — not all errors are equal.

**Test first:**
```
test_high_cost_error_weighted_heavily → PET scan wrong = high penalty
test_low_cost_error_weighted_lightly → Vital signs wrong = low penalty
test_perfect_extraction → cost_weighted_accuracy = 1.0
test_all_high_cost_wrong → cost_weighted_accuracy < 0.5
```

**Formula:**
```
Weighted Cell Error = Σ (cell_error × visit_frequency × cost_tier_weight)
where cost_tier_weight = {LOW: 1, MEDIUM: 3, HIGH: 10, VERY_HIGH: 25}
```

**Deliverable:** `src/eval/cost_weighted.py`

### 0.4 Baseline Benchmark Run

**Spec:** Run the current pipeline (v4) on all 5 annotated protocols, compute
TEDS, cell accuracy, footnote coverage, and section accuracy. Save as the
baseline that all future changes are measured against.

**Test first:**
```
test_baseline_produces_all_metrics → report has TEDS, cell_accuracy, footnote_coverage
test_baseline_saved_to_file → .benchmarks/baseline_v4.json exists
test_baseline_attribute_stratified → metrics broken down by sponsor, complexity, etc.
```

**Deliverable:** `src/eval/baseline.py`, `.benchmarks/baseline_v4.json`

### 0.3 Success Criteria for Phase 0

- [ ] TEDS computation works on synthetic tables with known ground truth
- [ ] 5 protocols have cell-level annotations
- [ ] Baseline metrics saved: TEDS, cell accuracy, footnote coverage per protocol
- [ ] Attribute-stratified report generated

---

## Phase 1: ICH Structure Validator as Router (Week 2)

**Goal:** Detect structural anomalies BEFORE extraction and route documents
to the appropriate complexity path.

### 1.1 ICH Section Standard

**Spec:** A validator that knows the expected ICH E6/TransCelerate section
structure and compares the parsed outline against it.

**Test first:**
```
test_standard_protocol_passes → Pfizer protocol matches ICH structure
test_nonstandard_section3_flags → Section 3 = "DOSING" instead of "OBJECTIVES" → flag
test_missing_section_flags → No Section 5 (Population) → flag
test_amendment_bundle_detected → Multiple "Section 1" entries → flag
test_complexity_score_computed → Returns score 1-12
```

**Implementation:**
```python
class ICHValidator:
    EXPECTED = {
        "1": ["summary", "synopsis", "protocol"],
        "2": ["introduction", "background"],
        "3": ["objectives", "endpoints"],
        "4": ["design", "study design"],
        "5": ["population", "eligibility"],
        "6": ["intervention", "treatment"],
        "7": ["discontinuation", "withdrawal"],
        "8": ["assessments", "procedures", "schedule"],
        "9": ["statistical"],
        "10": ["supporting", "documentation", "appendix"],
    }

    def validate(self, sections) -> ICHValidationResult:
        """Returns match score, anomalies, and recommended extraction path."""
```

**Deliverable:** `src/pipeline/ich_validator.py`, integrated into orchestrator
as Stage 0.5 (after synopsis, before SoA detection).

### 1.2 Complexity Scorer

**Spec:** Compute a document complexity score from SoA-specific dimensions
to route to Path A/B/C.

**Test first:**
```
test_simple_protocol_path_A → P-01 → Path A (score 4-6)
test_moderate_protocol_path_A → P-08 → Path A or B (score 6-8)
test_complex_protocol_path_B → P-13 → Path B (score 8-10)
test_extreme_protocol_path_C → P-18 → Path C (score 10+)
```

**Dimensions scored after pre-screening:**
- Page count (1-3)
- SoA column count from pre-screen (1-3)
- Footnote density from pre-screen (1-3)
- Heading quality from section parser (1-3)
- Amendment indicators detected (0 or 3)

**Deliverable:** `src/pipeline/complexity_scorer.py`

### 1.3 Eval Gate

After implementation, re-run baseline:
- [ ] TEDS unchanged (no regression from adding router)
- [ ] Complexity scores match expected tiers for all 5 annotated protocols
- [ ] ICH anomalies detected on P-03 (amendment bundle) and P-05 (non-standard numbering)

---

## Phase 2: Directed Challenger Correction Loop (Week 3)

**Goal:** The challenger currently flags errors but doesn't fix them. Make it
produce specific corrections, then re-extract ONLY the flagged cells.

### 2.1 Challenger Correction Output

**Spec:** Challenger returns structured corrections, not just issue descriptions.

**Test first:**
```
test_challenger_returns_corrections → output has cell_ref + suggested_value
test_correction_is_specific → correction targets one cell, not full table
test_empty_correction_list_when_correct → no corrections when extraction is right
```

**Implementation change to `challenger_agent.py`:**
```python
# Current output:
ChallengeIssue(description="Cell R14/C7 appears incorrect")

# New output:
ChallengeCorrection(
    cell_ref=CellRef(row=14, col=7),
    current_value="X",
    suggested_value="",
    confidence=0.8,
    reasoning="Source image shows empty cell at this position"
)
```

### 2.2 Targeted Re-Extraction

**Spec:** A re-extraction pass that takes a list of flagged cells, crops each
cell region from the source image, and re-reads at higher resolution.

**Test first:**
```
test_targeted_reextract_only_touches_flagged → 300 cells untouched, 3 re-extracted
test_correction_accepted_when_agrees → new read agrees with suggestion → accepted
test_correction_rejected_when_disagrees → new read disagrees → route to human review
test_no_regression_on_correct_cells → correct cells unchanged after correction loop
```

**Implementation:** New module `src/pipeline/correction_loop.py`

### 2.3 Eval Gate

After implementation, re-run baseline:
- [ ] TEDS improves on at least 3/5 protocols
- [ ] No TEDS regression on any protocol
- [ ] Flagged cell count decreases (corrections resolved)
- [ ] Save as `baseline_v5.json`, compare against v4

---

## Phase 3: Amendment Detection (Week 4)

**Goal:** Detect protocol amendments that modify SoA tables partially, and
flag them for human review.

### 3.1 Amendment Detector

**Spec:** Scan the document for amendment indicators near SoA tables.

**Test first:**
```
test_detects_amendment_keyword → "Amendment 3" near SoA → flagged
test_detects_version_history → "Protocol Version 5.0" → metadata captured
test_detects_partial_soa → SoA table with fewer rows than expected → warning
test_no_false_positive_on_original → Original protocol without amendments → clean
test_p03_amendment_bundle_detected → P-03 (4 amendments bundled) → flagged
```

**Implementation:** `src/pipeline/amendment_detector.py`

Patterns to detect:
- "Amendment N" / "Protocol Amendment"
- "Summary of Changes"
- Version history tables
- Partial SoA tables (fewer rows than schema expects)
- Multiple SoA sections with different visit counts

### 3.2 Adversarial Test Set

**Spec:** 3-5 deliberately unusual protocols that test graceful degradation.
No full annotations needed — just confirm the pipeline doesn't silently
produce wrong output with high confidence.

| Protocol | Why It's Adversarial |
|---|---|
| Landscape SoA table | Non-standard orientation breaks column detection |
| Phase I FIH with single-row visits | Minimal SoA, tests edge case of too-few-cells |
| Amendment with footnote-only SoA change | No table to extract, only text modifications |
| Non-English protocol (German/Japanese) | Tests cross-language robustness |
| Scanned protocol with no text layer | Tests pure vision-only extraction |

**Critical check:** Does confidence correlate with actual accuracy? A cell
marked 95% confident that's actually wrong is more dangerous than a cell
marked 50% that's wrong.

### 3.3 Eval Gate

- [ ] P-03 correctly flagged as amendment bundle
- [ ] Pfizer protocol amendments 1-15 detected in version history
- [ ] No false positives on clean protocols (P-27, P-32)
- [ ] Adversarial protocols degrade gracefully (low confidence, not wrong with high confidence)

---

## Phase 4: Docling Pre-Parse for Path B (Weeks 5-6)

**Goal:** Add a structural pre-parse layer that produces HTML intermediate
representation before VLM extraction.

### 4.1 Docling Integration

**Spec:** When complexity score routes to Path B, run Docling first to produce
an HTML table, then have the VLM verify and correct it.

**Test first:**
```
test_docling_produces_html → Input PDF → output HTML table with rows/cols
test_docling_html_has_correct_structure → Row count and col count match
test_vlm_verification_catches_docling_error → Docling misses merged cell → VLM fixes
test_path_b_teds_higher_than_path_a → TEDS improvement on complex protocols
test_path_a_unchanged → Simple protocols still use Path A, no regression
```

**Implementation:**
```python
class PathBExtractor:
    """Enhanced extraction with structural pre-parse."""

    async def extract(self, region, pages):
        # Step 1: Docling produces initial HTML
        html = self.docling.parse_table(pages)

        # Step 2: VLM verifies HTML against source image
        verification = await self.vlm.verify_html(html, pages)

        # Step 3: Correct structural errors
        corrected_html = self.apply_corrections(html, verification)

        # Step 4: Extract cells from corrected HTML
        cells = self.html_to_cells(corrected_html)
        return cells
```

### 4.2 Iterative Refinement (2-3 Cycles)

**Spec:** Run the VLM verification cycle 2-3 times, each time feeding back
the specific errors from the previous cycle.

**Test first:**
```
test_refinement_improves_teds → TEDS increases with each cycle (diminishing returns)
test_refinement_stops_when_stable → If cycle N = cycle N-1, stop early
test_max_3_cycles → Never runs more than 3 cycles regardless
```

### 4.3 Eval Gate

- [ ] TEDS on complex protocols (P-08, P-13) improves ≥5% with Path B
- [ ] TEDS on simple protocols (P-01, P-27) unchanged (still using Path A)
- [ ] Cost increase for Path B is ≤ 2x (acceptable for complex documents)
- [ ] Save as `baseline_v6.json`, compare against v4 and v5

---

## Phase 5: TEDS Dashboard and Continuous Evaluation (Week 7)

**Goal:** Make evaluation a living, continuous process — not a one-time check.

### 5.1 TEDS in Benchmark Report

**Spec:** The benchmark HTML report shows TEDS per protocol, stratified by
attributes, with trend lines across pipeline versions.

**Test first:**
```
test_benchmark_has_teds_column → HTML report shows TEDS for each protocol
test_attribute_stratification → Metrics broken by sponsor, complexity, footnote density
test_trend_comparison → v4 vs v5 vs v6 shown side by side
test_regression_alert → Red flag when any metric decreases
```

### 5.2 CI Integration

**Spec:** Every PR runs the synthetic table evaluation and blocks merge if
TEDS regresses.

```yaml
# .github/workflows/eval.yml
- name: Run Synthetic Table Eval
  run: python -m src.eval.synthetic_eval --fail-on-regression
- name: Run Section Parser Tests
  run: python -m pytest tests/test_section_parser_comprehensive.py
```

### 5.3 Eval Gate

- [ ] Benchmark report shows TEDS for all tested protocols
- [ ] Attribute-stratified view identifies weakest sponsor format
- [ ] CI blocks PRs that regress TEDS on synthetic tables
- [ ] Dashboard accessible at `/api/benchmark/report`

---

## Summary: What Gets Measured at Each Phase

| Phase | New Metric Added | Target | How Measured |
|---|---|---|---|
| 0 | TEDS baseline + cost-weighted accuracy | Real numbers from real ground truth | 3 fully annotated protocols (Pfizer first) |
| 1 | ICH match score | ≥80% on standard protocols | Section parser vs ICH template |
| 2 | Correction acceptance rate | ≥70% accepted, 0% regression | Directed re-extraction on flagged cells only |
| 3 | Amendment detection + adversarial degradation | ≥90% precision, graceful degradation | Known amendments + adversarial set |
| 4 | TEDS improvement (Path B) | ≥5% on complex, 0% regression on simple | Before/after comparison on all 3 annotated protocols |
| 5 | Continuous tracking + confidence calibration | No regression, confidence correlates with accuracy | CI automated eval + adversarial verification |

## Tracking Progress

Every phase produces:
1. **Spec document** (what success looks like)
2. **Test file** (tests written BEFORE code)
3. **Implementation** (code to pass the tests)
4. **Baseline comparison** (before/after metrics saved to `.benchmarks/`)
5. **Benchmark report update** (HTML report shows the improvement)

No phase is complete until the eval gate criteria are all checked.

---

## Escalation Policy for Human Review

The directed correction loop may produce a high disagreement rate. If the
challenger flags 15 cells and the re-reader disagrees on 8, that's 8 cells
in human review per table — at scale that becomes human-as-the-loop, not
human-in-the-loop.

**Policy:** If >20% of a table's cells require human review after the correction
loop, escalate the entire table to Path C rather than doing cell-by-cell review.
This prevents the review queue from becoming unmanageable.

---

## Timeline (Revised — Annotation Parallel, Not Sequential)

The critical insight: annotation must run IN PARALLEL with Sprint 1, not after
the development roadmap. Without a real TEDS baseline from real ground truth,
there is no way to measure whether improvements actually work.

| Week | Track A (Development) | Track B (Evaluation) |
|---|---|---|
| 1 | Phase 1: ICH structure validator as router | Pfizer BNT162 ground truth annotation (full, not spot-check) |
| 2 | Phase 1: Complexity scorer + routing logic | Continue annotation (12-16 hours total) |
| 3 | Phase 2: Directed challenger correction loop | TEDS computation against completed annotation — FIRST REAL BASELINE |
| 4 | Phase 3: Amendment detection + adversarial set | Measure correction loop improvement against real baseline |
| 5-6 | Phase 4: Docling integration for Path B | P-08 annotation + second TEDS measurement |
| 7 | Phase 5: Dashboard + CI integration | P-01 annotation + full attribute-stratified report |

**The constraint:** No improvement claim is valid until Sprint 3 delivers
the first real TEDS measurement. Everything before that is eyeballing.

**Total: 7 weeks, but real measurement starts at Week 3 — not Week 7.**
