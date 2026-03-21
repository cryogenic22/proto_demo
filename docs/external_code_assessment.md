# External Code Assessment — Red Team Analysis

## Files Reviewed

| File | Purpose | Quality |
|---|---|---|
| `fix_validation_issues.py` | Post-annotation fixes (CPT codes, superscript cleanup, low-conf flagging) | Good — catches real issues |
| `validation_pass2_3.py` | Structural and integrity validation (table dimensions, footnote chains, row consistency) | Excellent — we should adopt this |
| `protocol_section_parser (1).py` | Pfizer-specific section parser with Y-coordinate tracking | Good but protocol-specific |
| `protoextract_parser.py` | Universal three-layer parser (bookmark → font → regex) with reconciler | **Excellent — architecturally superior to our current parser** |
| `annotate_soa_v2.py` | Domain-specific cell annotation with volume verification | Very good — deep protocol knowledge |
| `pfizer_bnt162_annotation_final.xlsx` | Complete ground truth: 1,634 cells, 21 errors found | **Critical asset — our first real baseline** |

---

## Key Findings

### 1. The Annotated Excel Is Real Ground Truth

`pfizer_bnt162_annotation_final.xlsx` has:
- **1,634 cells fully annotated** (zero blank)
- **1,613 Y** (correct), **21 N** (errors found)
- **Error rate: 1.3%** — the pipeline is 98.7% accurate on cell values
- Every annotation has an audit trail method in the notes column
- 75 procedures annotated, 27 footnotes annotated

**This is the real TEDS baseline we've been trying to get.** We should
immediately convert this to our ground truth JSON format and compute
actual TEDS.

### 2. The Universal Parser (`protoextract_parser.py`) Is Better Than Ours

**Three-layer architecture with confidence-scored reconciliation:**

```
Layer 1 (Bookmarks):  confidence=0.95 — fastest, most reliable when available
Layer 2 (Font):       confidence=0.50-0.90 — bold detection with font size scoring
Layer 3 (Regex):      confidence=0.55 — fallback for documents without bookmarks
```

**What it does that ours doesn't:**

| Feature | Their Parser | Our Parser |
|---|---|---|
| **Per-section confidence** | Yes — each section has a confidence score | No |
| **Multi-method reconciliation** | Merges all three layers, boosts confidence when methods agree | Picks one strategy winner |
| **Y-coordinate tracking** | Stores exact Y position of heading on page | No — we just store page number |
| **Header/footer auto-detection** | Samples 15 pages, finds repeating lines, builds regex patterns | Hardcoded patterns |
| **SoA table detection** | Pattern matching + page clustering | Separate VLM-based detection |
| **Batch processing** | Built-in `--batch` mode for multiple protocols | Not built in |

**The Y-coordinate tracking is the critical difference.** When extracting
section content, knowing the exact Y position of the heading on the page
means you start extraction at the right line — not at the top of the page
(which includes headers, previous section endings, etc.). This is why
our Section 6.1 extraction returned pregnancy test footnotes instead of
the actual overview content.

### 3. The Validation Scripts Catch Issues We Don't

`validation_pass2_3.py` performs 9 checks we should integrate:

| Check | What It Does | Do We Have This? |
|---|---|---|
| VP2-1: Table dimensions | Verify row/col coverage, find missing rows | No |
| VP2-2: Footnote chain | Verify every footnote marker binds to existing cells | No |
| VP2-3: Row consistency | Each row should have same number of columns | No |
| VP3-1: Field completeness | No null required fields | Partial (output validator) |
| VP3-2: Data type distribution | Count by type, flag anomalies | No |
| VP3-3: MARKER value validation | Verify markers are standard (X, ✓) | Partial |
| VP3-4: Procedure cross-reference | Procedures in cells match procedures sheet | No |
| VP3-5: Confidence distribution | Bucket and report confidence scores | No |
| VP3-7: CPT consistency | CPT code + code_system alignment | No |

### 4. The Annotation Script Has Deep Domain Knowledge

`annotate_soa_v2.py` has something we completely lack: **table-specific
volume expectations derived from reading the actual PDF.**

```python
# p41_soa: Phase 1
# - Hematology/Chemistry: ~10 mL at Screening, V2, V3, V4, V5
# - Immunogenicity: V1=~50mL, V3=~50mL, V4=~50mL
#   V5,V6,V7=~50 mL + optional ~170 mL
#   V8,V8a,V8b,V8c,V9=~20 mL
```

This means the annotation script can VERIFY volume values against known
expectations — not just check if the text appears on the page, but check
if "~10 mL" is the RIGHT value for hematology samples in this specific
table and visit. This is domain-grounded verification.

### 5. The Fix Script Catches Superscript Contamination

`fix_validation_issues.py` addresses a bug we know about but haven't
systematically fixed: **footnote superscript markers contaminating
procedure names.** "assessmente" should be "assessment" + footnote marker
"e". The fix has a dictionary of known contaminated suffixes:

```python
contaminated_suffixes = {
    'assessmente': 'assessment',
    'appropriateb': 'appropriate',
    'informationd': 'information',
    'administrationf': 'administration',
    ...
}
```

We handle some of this in the SME corrections JSON, but the fix script
is more systematic — it strips Unicode superscripts (ᵃ, ᵇ, ᶜ) AND
known contaminated word endings.

---

## What We Should Incorporate

### Priority 1: Use the Annotated Excel as Ground Truth (Immediate)

Convert `pfizer_bnt162_annotation_final.xlsx` to our ground truth JSON
format and compute TEDS. This gives us the real baseline number.

```bash
python golden_set/annotation_tools/convert_to_json.py \
  pfizer_bnt162_annotation_final.xlsx \
  golden_set/annotations/P-13.json
```

### Priority 2: Replace Our Section Parser with the Three-Layer Architecture

The `protoextract_parser.py` universal parser should replace our current
`section_parser.py`. Key adoptions:

1. **Three-layer detection with reconciliation** — run all three, merge
   by confidence, boost when methods agree
2. **Y-coordinate tracking** — essential for correct verbatim extraction
3. **Auto header/footer detection** — adaptive, not hardcoded patterns
4. **Per-section confidence scores** — enables quality reporting

### Priority 3: Integrate the Validation Checks

Add the 9 validation checks from `validation_pass2_3.py` to our output
validator or as a new post-extraction validation stage:

- Table dimension verification (missing rows/columns)
- Footnote chain validation (all markers bind to cells)
- Row consistency (same column count per row)
- Procedure cross-reference (cells ↔ procedure sheet)
- Confidence distribution reporting

### Priority 4: Superscript Contamination Cleanup

Add the `fix_validation_issues.py` superscript stripping logic to our
cell extractor or output validator:

- Strip Unicode superscripts (ᵃ→a, ᵇ→b, etc.) from procedure names
- Move stripped characters to `footnote_markers` field
- Apply the contaminated suffix dictionary

### Priority 5: Volume Verification Knowledge (Future)

The table-specific volume expectations in `annotate_soa_v2.py` are
protocol-specific — not directly portable. But the PATTERN of encoding
domain expectations as structured rules is valuable. Consider building
a "protocol knowledge base" that stores expected values per table/row
for annotated protocols.

---

## Honest Assessment: How These Files Help Our Pipeline

| Aspect | Impact | Effort |
|---|---|---|
| **Ground truth Excel** | **Critical** — first real TEDS baseline | 1 hour (convert + compute) |
| **Universal parser** | **High** — fixes Section 6.1 and P-05 verbatim issues | 2-3 days (replace parser) |
| **Validation checks** | **High** — catches structural errors we currently miss | 1-2 days (integrate 9 checks) |
| **Superscript cleanup** | **Medium** — fixes known procedure name contamination | Half day |
| **Volume verification** | **Low (short-term)** — protocol-specific, not portable | Future knowledge base feature |

The annotated Excel alone is worth more than all the code combined.
It's the real anchor we've been missing — 1,634 cells of genuine ground
truth with a 1.3% error rate discovered. Everything else in the evaluation
framework now has a number to measure against.
