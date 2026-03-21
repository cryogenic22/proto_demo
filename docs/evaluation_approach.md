# ProtoExtract — Evaluation Approach Using OmniDocBench Methodology

## Purpose

Define a rigorous, evidence-based evaluation framework for the ProtoExtract
pipeline, adapting the OmniDocBench benchmark methodology (CVPR 2025) to
clinical protocol table extraction.

---

## Part 1: What OmniDocBench Teaches Us

OmniDocBench is the most comprehensive document parsing benchmark available:
1,355 pages, 9 document types, 15 block-level annotation categories, and
multi-metric evaluation across text, tables, formulas, and layout.

### Key Metrics We Should Adopt

| OmniDocBench Metric | What It Measures | Our Application |
|---|---|---|
| **TEDS** (Tree Edit Distance Similarity) | Structural + content accuracy of table extraction | Compare our extracted cell grid against ground truth SoA tables |
| **TEDS-S** | Structure-only accuracy (ignoring cell values) | Measure whether we get the right number of rows/columns/merged cells |
| **Normalized Edit Distance** | Text-level accuracy per cell | Compare each cell's extracted value against ground truth |
| **CDM** (Cross-modal Distance Metric) | Formula extraction accuracy | Measure LaTeX/equation extraction quality in statistical sections |
| **BLEU / METEOR** | Text generation quality | Measure verbatim extraction accuracy against source text |

### Key Evaluation Approach: Attribute-Based Subsetting

OmniDocBench doesn't just produce one accuracy number — it breaks results down
by document attributes. We should do the same:

| Attribute | Values | Why It Matters |
|---|---|---|
| **Table border type** | Full / Partial / Three-line / Borderless | SoA tables vary — some have clear borders, others are borderless |
| **Merged cells** | Yes / No | Merged headers are the hardest case |
| **Footnote density** | Low (<5) / Medium (5-15) / High (15+) | More footnotes = more potential for misresolution |
| **Column count** | Low (<10) / Medium (10-20) / High (20+) | Wide tables are harder to extract accurately |
| **Multi-page** | Yes / No | Cross-page tables have unique failure modes |
| **Image-rendered** | Yes / No | Text-based vs image-based SoA tables |
| **Sponsor format** | Pfizer / Lilly / AbbVie / Roche / etc. | Different sponsors format protocols differently |

---

## Part 2: Our Evaluation Framework

### Level 1: Cell-Level Accuracy (TEDS Equivalent)

Measure each extracted cell against ground truth using Tree Edit Distance.

**Implementation:**

```python
def compute_teds(extracted_table, ground_truth_table):
    """
    Compute Tree Edit Distance Similarity.

    1. Convert both tables to tree representation
       (root → rows → cells, with cell content as leaf values)
    2. Compute tree edit distance using Zhang-Shasha algorithm
    3. TEDS = 1 - (edit_distance / max(|T1|, |T2|))

    TEDS = 1.0 means perfect extraction
    TEDS = 0.0 means completely wrong
    """
```

**What we measure:**
- **TEDS (full):** Structure + content accuracy
- **TEDS-S (structure):** Did we get the right grid dimensions?
- **Cell-level edit distance:** Per-cell text accuracy

### Level 2: Footnote Resolution Accuracy

No existing benchmark measures this. We define our own:

| Metric | Formula | Target |
|---|---|---|
| **Marker coverage** | (markers resolved / markers in ground truth) × 100 | ≥ 90% |
| **Binding accuracy** | (correctly bound / total bindings) × 100 | ≥ 85% |
| **Type classification** | (correct type / total footnotes) × 100 | ≥ 80% |

### Level 3: Procedure Mapping Accuracy

| Metric | Formula | Target |
|---|---|---|
| **Mapping rate** | (procedures mapped / total procedures) × 100 | ≥ 95% |
| **Mapping correctness** | (correctly mapped / mapped) × 100 | ≥ 98% |
| **CPT code accuracy** | (correct CPT / assigned CPT) × 100 | ≥ 95% |
| **False positive rate** | (wrong mappings / total) × 100 | ≤ 2% |

### Level 4: Section Parsing Accuracy

| Metric | Formula | Target |
|---|---|---|
| **Section completeness** | (sections found / sections in protocol) × 100 | ≥ 90% |
| **Page number accuracy** | (correct pages / total sections) × 100 | ≥ 95% |
| **Hierarchy accuracy** | (correct level / total sections) × 100 | ≥ 90% |
| **Verbatim fidelity** | 1 - edit_distance(extracted, source) | ≥ 0.95 |

### Level 5: Repeatability (Our Unique Metric)

| Metric | Formula | Target |
|---|---|---|
| **Cell stability** | (identical cells across N runs / total cells) × 100 | ≥ 90% |
| **Table count stability** | Same table count every run | 100% |
| **Confidence variance** | std_dev(confidence across N runs) | ≤ 0.05 |

---

## Part 3: Building the Ground Truth

### Approach 1: Manual Annotation (Highest Quality, Highest Cost)

For 5 protocols (one per complexity tier), manually annotate:
- Every cell in every SoA table (value, type, footnote markers)
- Every footnote with its cell bindings
- Every section with its page number
- Every procedure with its correct canonical name and CPT code

**Cost:** ~4 hours per protocol × 5 = 20 hours of expert time.

**Use OmniDocBench annotation format:**
```json
{
  "page_id": "pfizer_bnt162_p41",
  "category": "table",
  "poly": [[x0,y0], [x1,y1], ...],
  "text": "",
  "html": "<table>...</table>",
  "attribute": {
    "border": "full",
    "merged_cells": true,
    "footnote_density": "high",
    "column_count": 18,
    "multi_page": true,
    "sponsor_format": "pfizer"
  }
}
```

### Approach 2: LLM-Assisted Annotation (Medium Quality, Medium Cost)

1. Run the pipeline on a protocol
2. Export the extraction as a review document
3. Have an expert spot-check 20% of cells and mark corrections
4. Use corrections as partial ground truth

**Cost:** ~1 hour per protocol.

### Approach 3: Synthetic Ground Truth (Automated, Free)

Already built — 10 synthetic SoA tables with known ground truth in
`golden_set/synthetic/generated/`. Expand to 50+ with:
- Different column counts (5-30)
- Different footnote densities (0-20)
- Different merged cell patterns
- Multi-page variants

---

## Part 4: Evaluation Protocol

### Pre-Release Evaluation (Run Before Every Deployment)

```bash
# Step 1: Run on synthetic tables (automated, 5 min)
python -m golden_set.synthetic.soa_generator --count 20
python -m golden_set.evaluate --synthetic --report

# Step 2: Run on golden set (10 protocols, 3 runs each, ~$30)
python -m golden_set.evaluate --tier 1 --tier 2 --repeat 3 --report --save

# Step 3: Compare against previous release
python -m golden_set.evaluate --compare-tag "v4" --report
```

### Quarterly Deep Evaluation

```bash
# Full golden set, 5 runs each, attribute-stratified metrics
python -m golden_set.evaluate --all --repeat 5 --report --save --tag "q1_2026"
```

### Per-Protocol Evaluation (When Testing a New Protocol)

```bash
# Single protocol, benchmark against golden set results
curl -X POST -F "file=@protocol.pdf" http://localhost:8000/api/extract
# Results auto-added to benchmark
curl http://localhost:8000/api/benchmark/report
```

---

## Part 5: Metrics Dashboard

### What to Track Over Time

| Metric Category | Specific Metric | Current Baseline | Target |
|---|---|---|---|
| **Table accuracy** | TEDS (full) | ~0.85 (estimated) | ≥ 0.92 |
| **Table structure** | TEDS-S | ~0.90 (estimated) | ≥ 0.95 |
| **Cell accuracy** | Edit distance | ~0.88 (from confidence) | ≥ 0.93 |
| **Footnotes** | Marker coverage | 85% (27/~32 on Pfizer) | ≥ 95% |
| **Procedures** | Mapping rate | 100% (with SME corrections) | ≥ 98% without SME |
| **Sections** | Completeness | 90% (78/~85 on P-05) | ≥ 95% |
| **Repeatability** | Cell stability (3 runs) | Not yet measured | ≥ 90% |
| **Cost** | Per protocol | $3 | ≤ $5 |
| **Time** | Per protocol | 26 min | ≤ 30 min |

### Attribute-Stratified Reporting

Following OmniDocBench's approach, report accuracy broken down by:

```
TEDS by Sponsor Format:
  Pfizer:      0.90
  Roche:       0.85
  Lilly:       0.88
  AstraZeneca: 0.87
  Novo Nordisk: 0.82  ← needs investigation

TEDS by Table Complexity:
  Single-page, <10 cols:  0.94
  Multi-page, 10-20 cols: 0.88
  Multi-page, 20+ cols:   0.78  ← Path C candidate
  Image-rendered:         0.72  ← fundamentally harder

TEDS by Footnote Density:
  Low (0-5):    0.93
  Medium (5-15): 0.87
  High (15+):   0.81
```

This immediately tells you WHERE to invest engineering effort — the attribute
with the lowest score is where the next improvement should focus.

---

## Part 6: Integration with OmniDocBench

### Can We Use OmniDocBench Directly?

**Partially.** OmniDocBench's 1,355 pages don't include clinical protocols
specifically, but:

1. **Table evaluation code** is reusable — the TEDS computation, matching
   algorithms, and attribute-based subsetting all apply to our tables
2. **Evaluation infrastructure** (YAML config, Docker, result organization)
   can be adapted
3. **The quick_match algorithm** for handling formula-text interchange is
   directly useful for protocols with inline statistical formulas

### What We Should Build On Top

```
OmniDocBench evaluation framework
  └── Clinical Protocol Extension
       ├── Protocol-specific attributes (sponsor, phase, amendment count)
       ├── SoA-specific metrics (footnote binding, procedure mapping)
       ├── Repeatability metrics (N-run variance)
       └── Budget accuracy metrics (frequency × cost correctness)
```

### Practical Steps

1. **Download OmniDocBench**: `huggingface-cli download opendatalab/OmniDocBench`
2. **Adapt TEDS computation** for our `ExtractedTable` schema
3. **Build protocol-specific annotation format** extending OmniDocBench JSON
4. **Create 5 gold-standard protocol annotations** using their format
5. **Run attribute-stratified evaluation** on every pipeline version

---

*This evaluation approach combines the rigor of OmniDocBench's academic
benchmarking methodology with the domain-specific metrics needed for clinical
protocol table extraction. The key principle: measure attribute-stratified
accuracy, not just aggregate numbers, so every engineering decision is
informed by WHERE the pipeline is weakest.*
