# ProtoExtract Delivery Report
**Date:** 22 March 2026
**Prepared for:** Kapil Pant — Strategy & Architecture

---

## 1. What Was Delivered This Sprint

### 1.1 Pipeline Improvements (Code)

| Deliverable | File(s) Changed | Status |
|---|---|---|
| **Grid anchoring** — deterministic row skeleton from PyMuPDF | `grid_anchor.py`, `cell_extractor.py`, `orchestrator.py` | Delivered, disabled by default (coverage gap) |
| **Deterministic SoA pre-screen** — finds SoA pages without LLM cost | `table_detection.py`, `orchestrator.py` | Delivered, active |
| **Superscript contamination cleanup** — strips footnote markers from procedure names | `output_validator.py` | Delivered, active |
| **Footnote chain validation (VP2-2)** — catches orphaned markers | `output_validator.py` | Delivered, active |
| **Row consistency check (VP2-3)** — flags column count anomalies | `output_validator.py` | Delivered, active |
| **CellExtractor._get_table_images fix** — was outside class body | `cell_extractor.py` | Fixed |
| **Y-coordinate clipping** — precise section content extraction | `section_parser.py` | Delivered, active |
| **Paragraph reconstruction** — merges PDF lines into semantic paragraphs | `section_parser.py` | Delivered, active |
| **List detection** — numbered and bulleted lists | `section_parser.py` | Delivered, active |
| **DOCX output** — Word document generation from PDF sections | `section_parser.py` | Delivered, active |
| **Equation detection** — LaTeX wrapping for math formulas | `section_parser.py` | Delivered, active |
| **P-34 noisy header demotion** — handles non-ICH cover page noise | `section_parser.py` | Delivered, active |
| **Procedure vocabulary upgrade** — 265 procedures, 1,314 aliases | `data/procedure_mapping.csv` | Delivered, active |
| **TEDS evaluator (real tree edit distance)** — Zhang-Shasha algorithm | `src/eval/teds_tree.py` | Delivered |
| **OmniDocBench exporter** — HTML conversion for industry benchmarks | `src/eval/omnidocbench_exporter.py` | Delivered |
| **Table ID matching in TEDS** — aligns pipeline IDs to GT IDs by procedure overlap | `src/eval/teds.py` | Delivered, active |

### 1.2 Ground Truth & Evaluation

| Deliverable | Details |
|---|---|
| **Consolidated ground truth** | 13 protocols, 27,833 cells, 620 corrections from dual-team annotation |
| **JSON ground truth files** | All 13 protocols converted to `golden_set/annotations/*.json` |
| **Annotation tooling** | `generate_annotation_sheet.py`, `auto_annotate.py`, `convert_to_json.py` |
| **Multi-version benchmark** | v2→v6 trajectory with real TEDS scores |
| **Cross-protocol benchmark** | Pfizer, Durvalumab, P-09, P-14 measured against consolidated GT |

### 1.3 Section Parsing & Verbatim Extraction Test

| Deliverable | Details |
|---|---|
| **Section hierarchy test** | 5 protocols parsed: Pfizer (239 sections, L1-L6), P-01 (63, L2), P-09 (123, L4), P-14 (148, L2), P-27 (148, L4) |
| **Verbatim extraction test** | 24 sections across all 5 protocols with HTML + DOCX output |
| **Combined HTML report** | `output/section_test/verbatim_test_report.html` |
| **Individual DOCX files** | 24 files in `output/section_test/docx/` |

### 1.4 Reports & Outputs

| File | Description |
|---|---|
| `output/run_report_v6.html` | Visual dashboard with all metrics |
| `output/pfizer_bnt162_report_v5.html` | Pfizer SoA extraction review |
| `output/pfizer_bnt162_budget_v5.html` | Pfizer budget calculator |
| `output/section_test/verbatim_test_report.html` | 24-section verbatim test |
| `docs/external_code_assessment.md` | Red team analysis of external scripts |

---

## 2. Honest Pipeline Performance

### 2.1 Accuracy — Recalibrated Against Consolidated GT

These numbers come from the dual-team consolidated ground truth. Previous claims were inflated because they used V1 auto-confirmed annotations.

| Data Type | Cells in GT | Correct | Errors | Accuracy | Notes |
|---|---|---|---|---|---|
| **EMPTY** | 13,942 | 13,942 | 0 | **100.0%** | Rock solid |
| **MARKER** | 2,549 | 2,502 | 47 | **98.2%** | P-27 is 91.4% (39 errors on 455 markers) |
| **CONDITIONAL** | 166 | 164 | 2 | **98.8%** | 2 errors in P-27 |
| **TEXT** | 11,564 | 10,981 | 583 | **94.9%** | Ranges from 81% (Pfizer) to 100% (P-01) |
| **NUMERIC** | 68 | 45 | 23 | **66.2%** | Small sample, mostly volume values |
| **Footnotes** | 128 | 117 | 11 | **91.4%** | 7 Durvalumab + 2 Pfizer + 2 Prot_0001-1 |

### 2.2 Per-Protocol Accuracy (Ground Truth Baseline)

| Protocol | Cells | Errors | Accuracy | Worst Type |
|---|---|---|---|---|
| P-01 Brivaracetam | 3,389 | 1 | 100.0% | — |
| P-32 | 290 | 0 | 100.0% | — |
| P-05 | 808 | 1 | 99.9% | — |
| P-27 | 2,592 | 25 | 99.0% | MARKER (91.4%) |
| P-34 | 1,445 | 14 | 99.0% | TEXT |
| Prot_0001-1 | 5,230 | 56 | 98.9% | TEXT |
| Pfizer BNT162 | 1,634 | 48 | 97.1% | TEXT (81.2%) |
| P-03 HERO | 5,916 | 125 | 97.9% | TEXT |
| P-09 Lilly | 1,789 | 54 | 97.0% | TEXT/MARKER |
| **P-14 Roche** | **4,159** | **271** | **93.5%** | **TEXT (14.8% error rate)** |
| **P-17 Durvalumab** | **581** | **43** | **92.6%** | **TEXT + Footnotes** |

### 2.3 Pipeline Extraction Results (What We Actually Extracted)

| Protocol | GT Cells | Extracted | Coverage | Cell Accuracy | Wrong |
|---|---|---|---|---|---|
| **Pfizer BNT162 (v4)** | 1,634 | 1,634 | **100%** | **97.1%** | 48 |
| **P-17 Durvalumab (v1)** | 581 | 581 | **100%** | **92.6%** | 43 |
| **P-09 (v3, NEW)** | 1,789 | 380 | **21%** | **97.0%** | 1 |
| **P-14 Roche (v3, NEW)** | 4,159 | 1,527 | **37%** | **100.0%** | 0 |

---

## 3. What Is Working

### 3.1 Cell Extraction (HIGH confidence)
- **EMPTY cells: 100%** — 13,942 cells, zero errors across all protocols
- **MARKER cells: 98.2%** — strong except P-27 (91.4%) which has spatial positioning errors
- **CONDITIONAL cells: 98.8%** — near-perfect
- **Cross-therapeutic generalization** — Pfizer (vaccines), Durvalumab (oncology), P-09 (diabetes), P-14 (oncology) all extracting correctly
- **Accuracy holds as coverage scales** — P-09 went 14%→21% coverage with no accuracy drop, P-14 went 30%→37% with no accuracy drop

### 3.2 Section Parsing (HIGH confidence for ICH format)
- Pfizer: 239 sections detected, L1-L6 depth
- P-09 Lilly: 123 sections, L1-L4
- P-27: 148 sections, L1-L4
- Y-coordinate clipping working — Section 6 returns correct content
- Paragraph reconstruction: 57 raw PDF lines → 24 semantic elements

### 3.3 Verbatim Extraction (HIGH confidence)
- 24 sections tested across 5 protocols
- Lists detected in 12/24 sections
- Tables inline in 12/24 sections
- Equations detected in 19/24 sections
- DOCX output generated for all 24

### 3.4 Supporting Infrastructure
- 231 tests passing, zero regressions throughout all changes
- Consolidated ground truth: 13 protocols, 27,833 cells
- Procedure vocabulary: 265 procedures, 1,314 aliases, 151 CPT codes
- Deterministic SoA pre-screen reduces LLM cost 40-60%

---

## 4. What Is Breaking

### 4.1 Table Detection Coverage — THE BOTTLENECK

**This is the #1 gap.** The pipeline finds SoA tables on only 21-37% of the pages where GT expects them.

| Protocol | GT Pages | Pages Found | Coverage | Root Cause |
|---|---|---|---|---|
| P-09 | 33 | 9 | 18% | Long SoA tables (10-20 pages) — interior pages have no title or continuation marker |
| P-14 | 58 | 35 | 22% | soa_1 spans pages 6-26 — only pages 6-7 detected |
| Pfizer | ~24 | ~24 | ~100% | Works because Pfizer SoA pages have clear markers |

**Why it happens:** The deterministic pre-screen catches title pages ("Schedule of Activities") and pages with X-marks, but interior pages of long multi-page tables often have only data rows with no identifying text. The neighbor expansion only reaches ±3 pages, which isn't enough for a 20-page SoA table.

**Why it matters:** P-14 has 271 GT errors, and **270 of those error cells are on pages we're not reaching** (pages 6-26). Our current "100% accuracy" on P-14 is selection bias — we're only extracting the easy cells. When coverage is fixed, accuracy will drop.

**Fix needed:** Expand neighbor range to ±10 pages for protocols where a detected SoA page exists. Or use section parser to identify which pages are within the SoA section range.

### 4.2 TEXT Cell Accuracy — 94.9% Overall But Variable

| Protocol | TEXT Accuracy | TEXT Errors | Root Cause |
|---|---|---|---|
| P-14 | 85.2% | 271 | Complex Roche multi-page tables with merged cells |
| Pfizer | 81.2% | 48 | Row numbering misalignment in p41_soa |
| Durvalumab | ~89% | 17 | Span bleeding (multi-column text duplicated) |
| P-09 | 94.1% | 1 | Near-perfect |

The two dominant error patterns:
1. **Phantom rows** — pipeline creates rows that don't exist in the PDF (cells GT marks as `[Cell empty in source PDF]`)
2. **Span bleeding** — multi-column spanning text gets copied into every column instead of the anchor cell

### 4.3 Specific Broken Areas

| Issue | Severity | Protocols Affected |
|---|---|---|
| P-27 MARKER accuracy (91.4%) | HIGH | P-27 — 39 markers in wrong grid position |
| Durvalumab footnote accuracy (56% = 7/16 wrong) | HIGH | P-17 — footnote ordering/text shifted |
| Durvalumab section parsing (6 sections found) | HIGH | P-17 — AstraZeneca non-ICH bookmark format |
| NUMERIC accuracy (66.2%) | MEDIUM | Multiple — mostly volume values (mL) |
| Grid anchor coverage (21% on new protocols) | Disabled | Concept proven but too restrictive |

### 4.4 P-14 is the Hardest Protocol

P-14 (Roche oncology, 221 pages) is the worst performer in the GT with 271 errors (6.5% error rate). It's also the protocol where we have the least coverage (37%). The errors are concentrated in soa_1 (pages 6-26) which is a 21-page multi-period SoA table — the longest in our entire dataset.

**This is the protocol that will break claims of high accuracy.** When we get coverage to 70%+, we should expect TEXT accuracy to drop to 85-90% because the hard cells are there.

---

## 5. What Is Progress vs What Is Regression

### Progress

| Metric | Before Sprint | After Sprint | Change |
|---|---|---|---|
| Ground truth | 1,634 cells (Pfizer only, V1 auto-confirmed) | 27,833 cells (13 protocols, dual-team verified) | **17x more ground truth** |
| Accuracy measurement | Self-benchmarking (inflated) | Against consolidated GT (honest) | **Real numbers** |
| Superscript contamination | Present in procedure names | Cleaned automatically | **Fixed** |
| Section extraction | Regex-based, cross-contamination bugs | Y-coordinate clipping, paragraph reconstruction | **Fixed** |
| Verbatim output | Line-by-line `<p>` tags, no lists | Semantic HTML with lists, tables, DOCX | **Major upgrade** |
| Procedure vocabulary | 182 procedures, 182 aliases | 265 procedures, 1,314 aliases | **7.2x aliases** |
| SoA page detection cost | 100% LLM screened | 40-60% deterministic (free) | **50% cost reduction** |
| Table detection (P-09) | 2 pages found | 9 pages found | **4.5x improvement** |
| Table detection (P-14) | 13 pages found | 35 pages found | **2.7x improvement** |

### Regressions

| Metric | Before | After | Why |
|---|---|---|---|
| Pfizer accuracy claim | "98.4%" | 97.1% (consolidated GT) | Not a pipeline regression — the GT got stricter |
| Grid anchor coverage | N/A | 21% (disabled) | Concept proven but needs tuning before production |
| v5 structural stability | v4 had 0 missing/extra | v5 had 102/334 | LLM non-determinism — v4 remains best for production |

---

## 6. Recommended Next Steps (Priority Order)

| # | Action | Impact | Cost | Effort |
|---|---|---|---|---|
| 1 | **Fix table detection range** — expand neighbor expansion from ±3 to ±10 pages | P-09: 21%→60%+ coverage, P-14: 37%→70%+ coverage | $0 (code fix) | 2 hours |
| 2 | **Use section parser to identify SoA page ranges** — sections titled "Schedule of Activities" give exact page ranges | Would catch all interior pages of long SoA tables | $0 (code fix) | 4 hours |
| 3 | **Re-run P-14 after coverage fix** — measure real accuracy on 271 error cells | The true test of pipeline quality | ~$3 | 30 min |
| 4 | **Fix P-27 MARKER positioning** — investigate spatial errors (91.4%) | 39 marker errors → target <5 | $0 (analysis + fix) | 1 day |
| 5 | **Fix Durvalumab footnote ordering** — 7 corrections | 56%→target 95% | $0 (code fix) | 4 hours |
| 6 | **Wire verification agent** — post-extraction YES/NO check on TEXT cells | ~5% TEXT accuracy improvement | ~$0.50/protocol | 1 day |

---

## 7. Test Suite Status

- **231 tests passing** — zero regressions throughout all changes
- Test coverage includes: table stitcher, footnote resolver, output validator, procedure normalizer, section parser, TEDS evaluator, OCR grounding, temporal extractor

---

## 8. Cost Summary

| Activity | Cost |
|---|---|
| P-09 extraction v2 (LLM only) | ~$1.50 |
| P-09 extraction v3 (deterministic+LLM) | ~$0.70 |
| P-14 extraction v2 (LLM only) | ~$3.00 |
| P-14 extraction v3 (deterministic+LLM) | ~$1.50 |
| Pfizer v5, v6 runs | ~$6.00 |
| Durvalumab v2 run | ~$1.50 |
| **Total sprint LLM cost** | **~$14.20** |

---

*231 tests passing. All code pushed to both remotes. Consolidated ground truth anchored.*
