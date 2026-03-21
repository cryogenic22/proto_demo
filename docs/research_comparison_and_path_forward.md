# ProtoExtract vs Research Landscape — Gap Analysis & Path Forward

## Purpose

This document compares our current pipeline against the research findings in
rough_notes.md, identifies where we are ahead, where we have gaps, and proposes
a complexity-adaptive multi-step architecture to achieve near-deterministic
accuracy on complex protocols.

---

## Part 1: Problem Statement Comparison

The rough_notes identify four reasons protocols are exceptionally hard. Here is
where we stand on each.

### 1. Document Length and "Lost in the Middle"

**Research finding:** LLMs degrade when relevant information is in the middle of
long contexts. Naive full-document injection is architecturally broken for
150-300 page protocols.

**Our status: MITIGATED (not fully solved).**
We never inject the full document into an LLM context. Our pipeline:
- Renders pages as images (isolated page context)
- SOA pre-screening processes one page at a time
- Protocol synopsis reads only the first 12 pages
- Cell extraction works on one table chunk at a time
- No stage ever sees more than 5-6 pages of context

**Remaining risk:** Page-level isolation solves context window degradation
but creates a different problem: **long-range semantic dependencies**. A
footnote on page 47 may reference a term defined in Section 3 on page 12.
A conditional eligibility criterion in the SoA may only make sense if
you've read the inclusion/exclusion section. The synopsis reading the
first 12 pages is a heuristic — it will break on protocols where the
design rationale is buried in amendment addenda. "Mitigated for the
common case" keeps us honest about the remaining failure modes.

### 2. Multi-Level Heading Hierarchies

**Research finding:** MinerU only supports first-level headings. Docling outputs
uniform heading levels. All tools struggle with 4-5 level deep ICH structure
(1, 1.1, 1.1.1, 1.1.1.1).

**Our status: PARTIALLY SOLVED.**
Our section parser handles 4+ heading levels via TOC text parsing with regex
for numbered sections. On the Pfizer protocol: 78 sections across 5 levels
(1 through 19, with 1.3.8.x sub-sub-subsections).

**Gaps:**
- TOC text parsing fails when the TOC is on page 24+ (fixed: now scans 30 pages)
- Page offset calibration needed for protocols with cover pages (fixed)
- Font-based heading detection needed for protocols without numbered sections (added)
- Bundled amendment PDFs (P-03) confuse the parser — no clear protocol boundary
- Protocols that use bold-without-heading-styles are partially covered but noisy

**What research suggests we should add:**
ICH E6/TransCelerate numbering conventions as explicit parser hints. We currently
use generic regex. A domain-aware parser that KNOWS the expected section structure
(1=Introduction, 2=Background, 3=Objectives, 4=Design, 5=Population, etc.) could
validate and correct heading detection against the standard.

### 3. SoA Table Complexity

**Research finding:** SoA tables are dense sparse matrices with merged headers,
grouped rows, conditional footnotes, and cross-page spanning. "Arguably harder
than financial tables."

**Our status: SUBSTANTIALLY ADDRESSED but not fully solved.**

What we do well:
- Vision-first extraction preserves spatial relationships
- Multi-page table stitching via title/continuation matching
- Dual-pass extraction with adversarial challenger
- Footnote extraction and cell-level anchoring (27 footnotes on Pfizer)
- OCR grounding for cross-modal verification
- Output validation gate blocking hallucinated values

**Gaps we have vs research recommendations:**

| Research Recommendation | Our Status | Gap |
|---|---|---|
| Table-to-HTML structural parse (MinerU/Docling) | We skip this — go direct from image to cell values | No intermediate HTML representation to validate against |
| Iterative critique-refinement loop | We have the challenger agent (single pass) | Not iterative — one adversarial pass, not N cycles of refine-and-verify |
| Spanning-cell detection (TATR/TABLET) | VLM detects merged regions in structural analysis | No dedicated TSR model — we rely on VLM visual understanding |
| Table continuity across pages | Table stitcher handles this | Works well for standard cases, untested on 6+ page tables |

### 4. Formula Parsing

**Research finding:** LaTeX formula misinterpretation is rampant. Mathematical
symbols get "destroyed." MinerU's LaTeX conversion is the best available option
but should be treated as first-pass draft requiring verification.

**Our status: BASIC.**
We have equation detection (math font + pattern matching) and LaTeX wrapping
in the section parser, but:
- No MinerU integration for formula-to-LaTeX conversion
- No formula verification step
- No round-trip validation (render LaTeX → compare to source image)
- OMML XML extraction for DOCX files works for Word equation editing

**Gap:** This is a real gap for protocols with dosing calculations and PK formulas.
Not critical for SoA extraction (tables don't contain formulas) but critical for
verbatim section extraction and protocol-as-code future.

---

## Part 2: Tool Landscape Comparison

### What We Built vs What's Available

| Tool/Approach | What It Does | Our Equivalent | Comparison |
|---|---|---|---|
| **Docling** (IBM) | PDF → structured DoclingDocument with provenance | PyMuPDF + VLM pipeline | We preserve less structural metadata but get better table accuracy via vision |
| **MinerU** (Shanghai AI Lab) | Layout analysis + OCR + formula + table recognition | Our 14-stage pipeline | MinerU is faster on CPU (1.26s/page vs our ~10s/page) but we have more validation layers |
| **LlamaParse** (commercial) | Custom-instructable table extraction | Our SOA-specific prompts | Similar capability but we're self-hosted, they're API-dependent |
| **TATR / Table Transformer** (Microsoft) | Dedicated table structure recognition model | Our VLM structural analyzer | TATR is specialized for cell detection; our VLM is general-purpose but less precise on spanning cells |
| **TABLET** (2025) | Sequence labeling for row/column splitting | Nothing equivalent | **Gap** — we have no dedicated TSR model |
| **DocAgent** (EMNLP 2025) | Multi-agent hierarchical document navigation | Our protocol synopsis + section parser | Architecturally similar — we have outline extraction before content retrieval |
| **MDocAgent** (2025) | 5 specialized agents (text, image, critical, summary) | Our pipeline stages as pseudo-agents | We have more stages but they're sequential, not truly multi-agent with dynamic routing |

### Key Insight: What We Have That They Don't

None of the research tools have:
1. **Clinical domain intelligence** — procedure normalization, CPT codes, therapeutic area detection
2. **Site budget output** — procedure → cost → budget worksheet
3. **Confidence scoring per cell** with cost-weighted thresholds
4. **SME correction mechanism** without code changes
5. **Repeatability testing framework** with cell-level variance tracking
6. **Cross-run comparison** showing improvement/regression

These are the features that make our pipeline production-ready for pharma site
budgeting specifically. The research tools are general-purpose document parsers.

---

## Part 3: The Four Unsolved Problems — Our Position

The rough_notes identify four failure modes "none of the above fully solves."

### 1. Footnote-to-Cell Resolution at Scale

**Research says:** Unsolved. Requires domain-aware post-processing.

**Our position:** We have a working implementation:
- FootnoteExtractor reads footnote blocks via VLM
- FootnoteResolver matches markers to cells
- Type classification (conditional/exception/reference)
- 27 footnotes resolved on Pfizer, 10 on P-08

**Remaining gap:** We don't verify that ALL footnote markers in cells have
definitions. If a cell has superscript "d" but no footnote "d" was extracted,
we silently miss it. Should add a completeness check.

### 2. Multi-Page SoA Tables

**Research says:** Breaks almost every tool. PubTables-v2 acknowledges the gap.

**Our position:** Table stitcher handles this:
- Title matching across consecutive pages
- Continuation markers ("continued", "cont'd")
- Tested on Pfizer (6-page main SoA table)

**Remaining gap:** Not tested on tables spanning 8+ pages. Column alignment
across pages is assumed but not verified — if page 2 has different column count
than page 1, stitching succeeds but extraction may misalign.

### 3. Heading Hierarchy Reconstruction

**Research says:** Requires domain knowledge. ICH E6 numbering as parser hint.

**Our position:** Section parser uses numbered regex + font detection + TOC parsing.
Page offset calibration handles cover pages. 78 sections parsed from P-05.

**Remaining gap:** We don't use ICH structure as validation. An ICH-aware validator
could check: "Section 5 should be STUDY POPULATION, you found DOSING DELAYS —
likely mislabeled or out of order."

### 4. Formula Parsing

**Research says:** Zero-tolerance risk for regulatory context.

**Our position:** Basic detection and LaTeX wrapping. No verification.

**Remaining gap:** Critical for verbatim extraction of statistical sections.
Not critical for SoA extraction.

---

## Part 4: Proposed Path Forward — Complexity-Adaptive Architecture

The key insight from the research is that a **single extraction strategy cannot
handle all document complexity levels**. Instead, the pipeline should assess
document complexity FIRST, then choose the appropriate extraction strategy.

### Document Complexity Assessment (New Stage 0)

Before any extraction, classify the document on five dimensions. The scoring
should be **table-specific, not document-level** — a protocol can have a high
image ratio from diagrams and flowcharts while having a perfectly clean text-based
SoA. The pre-screening pass already touches every page — use it to derive
SoA-specific complexity.

```
Complexity Score = f(page_count, soa_complexity, heading_quality, amendment_state, structure_match)
```

| Dimension | Low (1) | Medium (2) | High (3) |
|---|---|---|---|
| **Page count** | <50 | 50-150 | 150+ |
| **SoA complexity** | Single-page, <10 columns, <5 footnotes | Multi-page, 10-20 cols, 5-15 footnotes | Multi-page, 20+ cols, image-rendered, 15+ footnotes |
| **Heading quality** | PDF TOC metadata present | TOC in text, parseable | No TOC, bold-only headings |
| **Amendment state** | Original protocol, no amendments | 1-2 amendments, full SoA reproduced | 3+ amendments, partial SoA diffs |
| **ICH structure match** | Section numbers match ICH standard | Section numbers present but non-standard | No section numbers or anomalous structure |

### ICH Structure Validation (Route to Correct Path)

ICH E6 / TransCelerate defines a standard section structure:
- Section 1: Protocol Summary / Synopsis
- Section 2: Introduction / Background
- Section 3: Objectives / Endpoints
- Section 4: Study Design
- Section 5: Study Population
- Section 6: Study Intervention
- Section 7: Discontinuation
- Section 8: Assessments / Procedures (contains SoA)
- Section 9: Statistical Considerations
- Section 10: Supporting Documentation
- Section 11: References

**Use this as a ROUTER, not just a validator.** If the section parser labels
something "Section 3: DOSING DELAYS" and the ICH validator knows Section 3
should be OBJECTIVES, that's a bright red flag: the protocol structure is
unusual and should be routed to Path B or C, not Path A. Discovering structural
problems BEFORE extraction is architecturally more powerful than discovering
them during extraction and trying to fix downstream.

Composite score determines which extraction path to take:

### Path A: Standard (Score 4-6)
```
PDF → PyMuPDF render → VLM pre-screen → VLM extraction (current pipeline)
```
This is what we have now. Works for most Phase III protocols with standard
formatting: Pfizer (90% confidence), P-08 (87% confidence).

### Path B: Enhanced (Score 7-9)
```
PDF → MinerU/Docling structural parse → HTML intermediate → VLM verification
    → Iterative critique-refinement (2-3 cycles) → Footnote binding
```
Adds a structural parse layer BEFORE VLM extraction. The VLM's job changes from
"extract everything from the image" to "verify and correct the structural parse."
This is the iterative critique-refinement loop the research recommends.

**What to implement:**
1. Integrate Docling (Apache 2.0, no license issues) as a pre-parse step
2. Docling produces initial HTML table structure
3. VLM compares HTML against source image — flags structural errors
4. Second VLM pass corrects flagged cells
5. Footnote binding uses both HTML markers and VLM-detected superscripts

**Expected gain:** 5-10% accuracy improvement on complex tables with multi-tier
headers and dense footnotes.

### Path C: Maximum Fidelity (Score 10-12)
```
PDF → MinerU structural parse + Docling provenance → TATR/TABLET cell detection
    → VLM verification → Iterative refinement (3-5 cycles)
    → OCR grounding → Challenger agent → Human review for <85% cells
```
Adds a dedicated Table Structure Recognition model for cell-level detection before
any VLM extraction. This is the research frontier approach.

**What to implement:**
1. TATR or TABLET for cell-level bounding box detection
2. Each cell cropped and individually read by OCR + VLM
3. Structural validation: cell count matches grid dimensions
4. Multi-pass refinement with image comparison
5. Mandatory human review for cells below threshold

**Expected gain:** Targets 95%+ accuracy but at 3-5x cost and time.

### Missing Failure Mode: Amended SoA Tables

Protocol amendments that modify specific cells without reproducing the full table
are a critical gap not addressed in our pipeline or in the research. Amendment 3
might say "Visit 6 PK sampling is now optional — see updated SoA" and include
only a partial table or a diff-style change table.

This breaks:
- The stitcher (partial table doesn't match the base table format)
- The footnote resolver (amended footnotes may reference the original table)
- The budget output (frequency changes from amendments not captured)

**Worst case:** Confidence scores on the amendment section may look fine because
the partial table IS correctly extracted — it's just missing the context that
it's a DIFF, not a complete table.

**Mitigation:** Detect amendment patterns ("Amendment N", "Protocol Version X.Y",
"Summary of Changes") and flag the SoA as potentially incomplete. Route to human
review when amendment indicators are found near SoA tables.

### Implementation Priority (Revised)

| Phase | What to Build | Effort | Impact |
|---|---|---|---|
| **Now** | ICH structure validation as complexity ROUTER | 1 week | Catches anomalies before extraction, routes to correct path |
| **Now** | Directed challenger correction loop | 1 week | Highest-leverage accuracy improvement for existing pipeline |
| **Next** | Complexity assessment (auto-classify) | 1 week | Enables adaptive routing to Path A/B/C |
| **Next** | Docling integration as pre-parse for Path B | 2 weeks | 5-10% on complex tables |
| **Next** | Amendment detection and flagging | 1 week | Prevents silent failures on amended protocols |
| **Later** | TATR/TABLET integration for Path C | 3 weeks | Cell-level precision for hardest cases |
| **Later** | MinerU integration for formula extraction | 2 weeks | Unblocks formula-heavy sections |

---

## Part 5: Specific Research Techniques to Integrate

### 1. Iterative Critique-Refinement Loop (Highest Value)

The research describes a critic-refine cycle:

```
Round 1: VLM extracts table → produces initial cell values
Round 2: Critic VLM compares extraction against source image → lists errors
Round 3: Refiner VLM corrects listed errors → produces improved extraction
Round 4: Critic reviews corrections → confirms or flags remaining issues
```

**How this maps to our pipeline:**

Our current flow is: Extract (2 passes) → Challenge (1 pass) → Reconcile.

The research says: Extract (1 pass) → Critique (1 pass) → Refine (1 pass) →
Critique (1 pass) → final output.

**The difference:** Our challenger identifies errors but doesn't fix them — it
just lowers confidence. The critique-refinement approach feeds errors BACK to
the extractor with specific corrections. This closes the loop.

**Critical implementation detail:** The correction loop must be DIRECTED —
specific cells, not full re-extraction. When the challenger says "cell R14/C7
appears incorrect," the corrector re-examines that specific cell without
disturbing the 300 other cells it already got right. Undirected re-extraction
risks regressing correct cells while fixing incorrect ones. The research
critique-refinement loop works because it passes specific structural errors
as a structured list to the refiner.

**Implementation:**
1. Challenger produces a list of `{cell_ref, error_type, suggested_value}`
2. A targeted re-extraction pass crops ONLY the flagged cell regions from the image
3. VLM re-reads each flagged cell at higher resolution with the error context
4. Reconciler accepts the correction ONLY if the re-read agrees with the suggestion
   (if it disagrees, the cell goes to human review)

### 2. DocAgent-Style Hierarchical Navigation (Already Partially Built)

Our protocol synopsis extractor is the DocAgent "outline extraction" step.
Our section parser is the "interactive reading interface."

**What's missing:** The DocAgent "reviewer agent" that cross-checks responses
using complementary sources. We have the challenger agent for SoA tables but
no reviewer for section content — verbatim extraction is trusted without
verification.

**Implementation:** Add a verification step to verbatim extraction: after
extracting text, have a VLM read the source page image and confirm the
extracted text matches what's visible. This catches cases where PyMuPDF
text extraction fails (image-only pages, garbled encoding).

### 3. Structural Parse as Intermediate Representation

The research unanimously recommends an intermediate structural representation
(HTML, DoclingDocument, or similar) rather than going directly from image to
cell values. The intermediate representation can be validated, corrected, and
compared across extraction methods.

**What we currently do:** Image → VLM → JSON cells. No intermediate HTML.

**What research recommends:** Image → Structural Parse (HTML) → VLM Verification
→ Corrected HTML → Cell extraction from HTML.

**Why this matters:** HTML is inspectable. A human or automated test can look
at the HTML table and check: "Does this have the right number of rows? Are
the merged cells correct?" JSON cell values are harder to validate structurally.

**Implementation:** Use Docling or PyMuPDF's `find_tables()` to produce initial
HTML, then have the VLM verify and correct it before cell extraction.

---

## Part 6: Honest Assessment — Where We Are

### Strengths (Ahead of Research)

1. **Production-ready for site budgeting** — no research tool produces budget
   worksheets with CPT codes
2. **Multi-provider LLM support** — Anthropic, OpenAI, Azure (research tools
   are typically single-provider)
3. **Clinical domain intelligence** — 180 procedures, 840 aliases, 15 categories
4. **SME correction mechanism** — no code changes needed
5. **Telemetry and checkpointing** — production resilience
6. **Repeatability testing** — N-run variance measurement
7. **Cost optimization** — SOA pre-screening at 5x cheaper than full extraction

### Gaps (Behind Research)

1. **No intermediate structural representation** — we go image → cells with no
   inspectable intermediate step
2. **No iterative refinement** — challenger identifies errors but doesn't fix them
3. **No dedicated TSR model** — rely on VLM for structural understanding
4. **No formula extraction** — basic detection but no LaTeX conversion
5. **Image-only pages** — when SoA tables are rendered as images with no text
   layer, verbatim extraction fails and we can only use the VLM pipeline
6. **No ICH structural validation** — section parser doesn't know the expected
   protocol structure

### Bottom Line

Our pipeline is **production-grade for the common case** (standard protocols with
text-based SoA tables). It's ahead of research tools on domain-specific features
(procedure mapping, budgeting, footnote resolution, repeatability testing).

It's **behind research on the hard cases**: image-rendered tables, dense multi-tier
headers, complex merged cells, and formula-heavy sections. The path forward is
not to replace what we've built but to add the research-recommended layers
(structural pre-parse, iterative refinement, TSR model) as optional processing
stages that activate based on document complexity.

The complexity-adaptive architecture is the key insight: **don't run the expensive
path on simple documents, and don't run the simple path on complex ones.**

The risk isn't that the architecture is wrong — it's that "production-grade for
the common case" gets shipped as "production-grade," and the hard cases arrive
when the client least expects them. The ICH validator as a router, the directed
challenger correction loop, and amendment detection are the three changes that
close the gap between "works on standard protocols" and "works on real-world
protocols with all their messiness."
