# ProtoExtract — Technical Overview

## Protocol Table Extraction Pipeline for Site Budgeting

---

## 1. What It Does

ProtoExtract takes a clinical trial protocol PDF as input and produces a
structured, machine-readable representation of every table in the document —
with per-cell confidence scores, resolved footnotes, normalized procedures,
and a human review queue for ambiguous extractions.

**Input:** Protocol PDF (any sponsor format, any phase, up to 500 pages)
**Output:** Structured JSON with cell-level data, footnotes, procedures, visit windows

---

## 2. Pipeline Architecture — 12 Stages

```
 ┌──────────────────────────────────────────────────────────┐
 │                    PDF UPLOAD                             │
 └──────────────────────┬───────────────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────────────┐
 │  STAGE 1: PDF Ingestion                                  │
 │  PDF → high-resolution page images (150 DPI)             │
 │  Memory-managed rendering with garbage collection        │
 └──────────────────────┬───────────────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────────────┐
 │  STAGE 2: Table Detection                                │
 │  Vision LLM scans each page to identify table regions    │
 │  Parallel processing (5 pages concurrently)              │
 │  Classifies: SOA, Demographics, Lab Params, Dosing, etc. │
 └──────────────────────┬───────────────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────────────┐
 │  STAGE 3: Multi-Page Table Stitching                     │
 │  Detects tables spanning multiple pages                  │
 │  Matches by title, "continued" markers, page adjacency   │
 │  Merges into single logical tables                       │
 └──────────────────────┬───────────────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────────────┐
 │  STAGE 4: Structural Analysis (Pass 1 — Schema)          │
 │  Vision LLM reads table at gestalt level                 │
 │  Extracts: column headers, row groups, merged regions    │
 │  Catalogs all footnote markers (a, b, *, †, etc.)        │
 │  Output: TableSchema (structure, not values)             │
 └──────────────────────┬───────────────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────────────┐
 │  STAGE 5: Cell Extraction (Pass 2 — Values)              │
 │  Two independent extraction passes with different prompts│
 │  Semantic decomposition by row groups                    │
 │  Each cell: value, type, footnote markers, coordinates   │
 │  Pass A and Pass B compared for consistency              │
 └──────────────────────┬───────────────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────────────┐
 │  STAGE 6: Footnote Extraction                            │
 │  Dedicated vision pass reads footnote blocks             │
 │  Extracts marker → definition mappings                   │
 │  Handles multi-page footnotes (merges across pages)      │
 └──────────────────────┬───────────────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────────────┐
 │  STAGE 7: Footnote Resolution                            │
 │  Anchors footnote definitions to specific cells          │
 │  Classifies: Conditional, Exception, Clarification, Ref  │
 │  Result: cell-level metadata ("only if QTc > 450ms")     │
 └──────────────────────┬───────────────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────────────┐
 │  STAGE 8: Procedure Normalization                        │
 │  Maps free-text names → canonical vocabulary             │
 │  40+ procedures with CPT/SNOMED codes                    │
 │  Assigns cost tiers: LOW ($) to VERY_HIGH ($$$$)         │
 │  "12-lead ECG" = "ECG (12L)" = "Electrocardiogram"      │
 └──────────────────────┬───────────────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────────────┐
 │  STAGE 9: Temporal Extraction                            │
 │  Parses visit headers → structured windows               │
 │  Handles: Day N, Week N (±3d), C1D1, Month 3, ET        │
 │  Identifies unscheduled/follow-up/early termination      │
 └──────────────────────┬───────────────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────────────┐
 │  STAGE 10: Challenger Agent (Adversarial Validation)     │
 │  Independent vision LLM pass re-examines the source      │
 │  Compares extracted data against what it sees in image   │
 │  Hunts for: hallucinated values, missing cells,          │
 │  structural mismatches, unresolved footnotes             │
 └──────────────────────┬───────────────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────────────┐
 │  STAGE 11: Multi-Pass Reconciliation                     │
 │  Compares Pass A vs Pass B cell-by-cell                  │
 │  Incorporates challenger findings                        │
 │  Agreement → high confidence (95%)                       │
 │  Disagreement → low confidence (50%) → flagged           │
 │  Cost-weighted thresholds: MRI stricter than vitals      │
 └──────────────────────┬───────────────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────────────┐
 │  STAGE 12: Output Validation (Hard Gate)                 │
 │  Rejects NONE/NULL hallucinated values                   │
 │  Blocks impossible coordinates, impossible column counts │
 │  Detects duplicate cells, structural inconsistencies     │
 │  Cleans malformed values → EMPTY with tanked confidence  │
 │  NOTHING reaches downstream without passing this gate    │
 └──────────────────────┬───────────────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────────────┐
 │                  STRUCTURED OUTPUT                        │
 │                                                          │
 │  Per table:                                              │
 │  ├── Cell grid with confidence scores (0-100%)           │
 │  ├── Resolved footnotes anchored to cells                │
 │  ├── Normalized procedures with CPT codes + cost tiers   │
 │  ├── Visit windows with temporal logic                   │
 │  ├── Flagged cells for human review                      │
 │  └── Extraction metadata (passes, conflicts, time)       │
 │                                                          │
 │  Human review queue:                                     │
 │  ├── Cost-weighted (PET scan reviewed before vitals)     │
 │  ├── Categorized: Local Resolution / Structural / System │
 │  └── Full provenance trail per cell                      │
 └──────────────────────────────────────────────────────────┘
```

---

## 3. Why This Architecture

### Problem: LLM Hallucination in Table Extraction

Single-pass LLM extraction is fundamentally unreliable for clinical data.
Research shows GPT-4 with retrieval fails or hallucinates on 81% of complex
document table questions (FinanceBench, 2024). The failure mode is subtle:
values that look correct but are fabricated.

### Our Defense-in-Depth Approach

| Layer | What It Catches | How |
|-------|----------------|-----|
| Dual-pass extraction | Values the model is uncertain about | Two prompts, compare outputs |
| Challenger agent | Plausible-sounding hallucinations | Independent adversarial review |
| Output validator | NONE/NULL propagation, impossible values | Hard gate with rejection rules |
| Confidence scoring | Everything above, aggregated | Per-cell 0-100% with cost weighting |
| Human review queue | Anything below threshold | Triaged by financial impact |

### Key Design Decisions

- **Vision-first, not text-first.** We never extract text from the PDF. Every
  table is read directly from the page image by the vision LLM. This preserves
  spatial relationships that text extraction destroys.

- **Temperature 0 everywhere.** All LLM calls use temperature=0 to minimize
  run-to-run variability.

- **Fail loud, not fail silent.** Malformed LLM outputs are caught and routed
  to human review rather than silently propagated into budget calculations.

- **Cost-weighted review.** A hallucinated PET scan costs $50,000 per patient.
  A hallucinated vital signs check costs $50. Review thresholds reflect this.

---

## 4. Test Harnesses

### 4.1 Unit Tests (91 tests, run in seconds)

Every pipeline module has isolated tests with mocked LLM calls.

```
tests/
├── test_models.py              # 35 tests — Pydantic schema validation
├── test_pdf_ingestion.py       # 5 tests  — PDF rendering, DPI, empty docs
├── test_table_detection.py     # 6 tests  — Detection parsing, type guards
├── test_table_stitcher.py      # 8 tests  — Multi-page merging logic
├── test_footnote_resolver.py   # 7 tests  — Marker→definition anchoring
├── test_procedure_normalizer.py# 11 tests — Name matching, CPT codes, cost tiers
├── test_temporal_extractor.py  # 15 tests — Visit window parsing (Day/Week/Cycle/ET)
├── test_reconciler.py          # 7 tests  — Multi-pass agreement, cost weighting
└── test_orchestrator.py        # 3 tests  — End-to-end coordination, error handling
```

Run: `python -m pytest tests/ -v`

### 4.2 Golden Set Regression (35 protocols)

A curated set of 35 publicly available clinical trial protocols spanning:

| Dimension | Coverage |
|-----------|----------|
| Therapeutic areas | 14 (Oncology, Cardiology, Neurology, Rare Disease, Vaccines, Autoimmune, Hematology, Dermatology, Ophthalmology, Infectious Disease, Respiratory, Psychiatry, Endocrinology, Gene Therapy) |
| Complexity tiers | 5 levels (Simple → Extreme) |
| Sponsor formats | 15 (Pfizer, Moderna, Lilly, AbbVie, AstraZeneca, Merck, Novartis, Roche, Gilead, Janssen, Novo Nordisk, etc.) |
| Trial phases | I through IV, including adaptive/platform designs |
| Table features | Multi-page SoA, dense footnotes, merged cells, cycle-based, multi-arm, nested sub-tables, pediatric |

Run: `python -m golden_set.evaluate --all --report`

### 4.3 Repeatability Testing (the critical test)

The most important test for production readiness. Runs the same protocol
N times and measures whether the pipeline produces identical results.

**What it measures:**

| Metric | What It Tells You |
|--------|-------------------|
| **Cell stability %** | % of cells that are identical across all N runs |
| **Stability ratio** | For each cell, what fraction of runs agree with the majority |
| **Table count consistency** | Does the pipeline find the same number of tables every time? |
| **Top unstable cells** | Which specific cells vary between runs (targets for improvement) |
| **Error rate** | % of runs that crash (should be 0%) |

**Why it matters:**

A pipeline that produces 90% accuracy on one run but different results each
time is not production-ready. The repeatability test catches the failure mode
that standard accuracy testing misses: "worked Tuesday, failed Thursday."

Run:
```bash
# 5 runs on one protocol — quick stability check
python -m golden_set.evaluate --protocol P-13 --repeat 5 --report --save

# Full suite — 35 protocols, 3 runs each
python -m golden_set.evaluate --all --repeat 3 --report --save --tag "v1.0"
```

**Sample output:**
```
==========================================
GOLDEN SET EVALUATION REPORT — 5 protocols, 3 run(s) each
==========================================

Protocol   Tier  Tables   Cells  Footnotes   Time  Stability  Unstable  Errors
  P-01        1       2      48         3     45s      98.2%        1      0%
  P-03        2       4     156        12    120s      94.5%        9      0%
  P-07        3       6     342        18    240s      91.2%       30      0%
  P-13        4      63    3006        45    900s      87.3%      382      0%
  P-18        5      12     890        25    480s      84.1%      141      0%

--- Repeatability Analysis ---
  Total cells tracked:    4442
  Stable (identical):     4009 (90.2%)
  Unstable (varied):       433 (9.8%)
  Avg stability ratio:    95.1%

  Top 10 most unstable cells:
    Table 3 (12,5): 3 variants, stability=33% — values: ["X", "", "Xa"]
    Table 3 (14,7): 2 variants, stability=67% — values: ["X", ""]
    ...
==========================================
```

### 4.4 Longitudinal Tracking

Every evaluation run saves results to `golden_set/results/` as timestamped JSON.
This creates a performance history that shows:

- Accuracy trends over time (are we getting better or worse?)
- Impact of model changes (Sonnet 4.5 → 4.6 comparison)
- Impact of prompt changes (before/after for each modification)
- Regression detection (immediate alert if a change degrades results)

---

## 5. Production Confidence Criteria

Before production deployment, the pipeline must meet:

| Criterion | Threshold | How Measured |
|-----------|-----------|--------------|
| **Cell stability** | ≥ 90% across 5 runs | Repeatability test on golden set |
| **Table count consistency** | 100% (same count every run) | Repeatability test |
| **Error rate** | 0% (no crashes) | Repeatability test |
| **SoA table confidence** | ≥ 85% average | Extraction confidence scores |
| **High-cost procedure accuracy** | ≥ 95% | Manual validation on golden set |
| **Footnote resolution rate** | ≥ 80% of markers resolved | Extraction metadata |
| **Processing time** | < 2 min for typical protocol (50 pages) | Benchmark |

---

## 6. Technology Stack

| Component | Technology |
|-----------|-----------|
| Vision LLM | Claude Sonnet 4.6 (temperature=0) |
| PDF rendering | PyMuPDF (150 DPI, PNG) |
| Data models | Pydantic v2 (strict validation) |
| Backend API | FastAPI (async, background jobs) |
| Frontend | Next.js 16 + Tailwind CSS |
| Testing | pytest + pytest-asyncio (91 tests) |
| Evaluation | Custom golden set runner with repeatability |

---

## 7. What Happens When It's Wrong

Every extraction error falls into one of three categories, each with a
different resolution path:

| Type | Example | Resolution |
|------|---------|------------|
| **Type 1: Locally resolvable** | Footnote text partially cut off by PDF rendering | Human sees source PDF, types correct value → writes to KE directly |
| **Type 2: Structural interpretation** | Merged cell spans 3 visits — applies to all or only first? | Human selects from pipeline-surfaced options → pipeline re-applies rule to all affected cells |
| **Type 3: Systematic pattern** | Model consistently misreads "except at" footnotes | Triggers prompt/schema update → re-run all affected documents |

The review queue is sorted by **financial impact** — high-cost procedures
(PET scans, biopsies, genetic testing) are reviewed first regardless of
confidence score.
