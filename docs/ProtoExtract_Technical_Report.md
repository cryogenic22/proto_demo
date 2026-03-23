# ProtoExtract — Technical Architecture Report

**Version:** 1.0 | **Date:** 2026-03-23 | **Status:** Production (Railway)

---

## Executive Summary

ProtoExtract is an AI-powered clinical trial protocol extraction pipeline that digitizes Schedule of Activities (SoA) tables from protocol PDFs, normalizes procedures to canonical vocabulary with CPT codes, and generates site budget worksheets. The system uses a hybrid deterministic + LLM architecture across 11 pipeline stages, with multi-pass extraction, adversarial validation, and a 5-layer noise filter.

**Key metrics:**
- 99.1% cell extraction accuracy (13-protocol benchmark)
- 542-procedure vocabulary with 2,900+ aliases and 415 CPT codes
- 100% procedure mapping rate across stored protocols
- 5-layer SoA filter: zero false-positive tables reaching users

**Architecture:** FastAPI backend (Python 3.12) + Next.js 16 frontend (React 19, TypeScript) | Deployed on Railway

---

## 1. Pipeline Architecture Overview

```
PDF Upload
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 1: PDF Ingestion                                       │
│   PyMuPDF renders pages at 150 DPI → PageImage objects       │
├─────────────────────────────────────────────────────────────┤
│ Stage 1b: Protocol Synopsis                                  │
│   Reads first 20 pages → therapeutic area, phase, indication │
├─────────────────────────────────────────────────────────────┤
│ Stage 2: Table Detection (Hybrid)                            │
│   Deterministic text scan (free) + VLM validation (paid)     │
│   X-mark counting, continuation detection, Y-band matching   │
├─────────────────────────────────────────────────────────────┤
│ Stage 3: Table Stitching                                     │
│   Multi-page fragments → logical tables (gap ≤2 pages)      │
├─────────────────────────────────────────────────────────────┤
│ Stage 3b: SoA Validation (5-Layer Filter)                    │
│   Layer 1: Section parser page-range gate                    │
│   Layer 2: Title rejection (45+ keywords)                    │
│   Layer 3: Post-extraction marker validation                 │
│   Layer 4: High-flagged-rate rejection (>80%)                │
│   Layer 5: Column header validation (visit patterns)         │
├─────────────────────────────────────────────────────────────┤
│ Stage 4: Structural Analysis                                 │
│   VLM infers schema: column headers, row groups, merged cells│
├─────────────────────────────────────────────────────────────┤
│ Stage 4b: Grid Anchoring (Optional)                          │
│   Deterministic row skeleton from PyMuPDF text layer         │
├─────────────────────────────────────────────────────────────┤
│ Stage 5: Cell Extraction (Dual-Pass)                         │
│   Pass 1: VLM extracts all cells with prompt variant A       │
│   Pass 2: VLM re-extracts with prompt variant B              │
│   Agreement → high confidence | Disagreement → flagged       │
├─────────────────────────────────────────────────────────────┤
│ Stage 6: Footnote Resolution                                 │
│   6a: Extract footnote definitions (VLM)                     │
│   6b: Match markers to cells (deterministic)                 │
│   6c: Classify: CONDITIONAL | EXCEPTION | REFERENCE | CLAR.  │
├─────────────────────────────────────────────────────────────┤
│ Stage 7: Procedure Normalization                             │
│   542-procedure vocabulary + 2,900 aliases                   │
│   6-step matching: exact → starts_with → word → fuzzy        │
│   CPT code + category + cost tier assignment                 │
├─────────────────────────────────────────────────────────────┤
│ Stage 8: Temporal Extraction                                 │
│   Visit windows: Day/Week/Month/Cycle parsing                │
├─────────────────────────────────────────────────────────────┤
│ Stage 9: Challenger Validation (Adversarial)                 │
│   Independent VLM reviews extraction for errors              │
│   + OCR grounding cross-verification                         │
├─────────────────────────────────────────────────────────────┤
│ Stage 10: Reconciliation                                     │
│   Merge dual-pass results + challenger findings              │
│   Cost-weighted confidence thresholds                        │
│   Flag cells below threshold for human review                │
├─────────────────────────────────────────────────────────────┤
│ Stage 11: Output Validation (Hard Gate)                      │
│   Schema sanity, cell value sanity, structural consistency   │
│   Rejects malformed tables before they leave the pipeline    │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
Protocol Persistence → Protocol Library → UI Review
```

---

## 2. Stage Details

### 2.1 PDF Ingestion

**Module:** `src/pipeline/pdf_ingestion.py`

- Converts PDF bytes → PageImage objects using PyMuPDF
- Renders at configurable DPI (default: 150, range: 72-600)
- Each PageImage carries: page number, image bytes, width, height
- Handles both digitally-created and scanned PDFs

### 2.2 Protocol Synopsis Extraction

**Module:** `src/pipeline/protocol_synopsis.py`

- Reads first 20 pages to extract protocol metadata
- Identifies: therapeutic area, indication, study type, phase, arms
- Non-fatal: pipeline continues if extraction fails
- Downstream use: informs domain classifier for extraction hints

### 2.3 Table Detection (Hybrid Deterministic + VLM)

**Module:** `src/pipeline/table_detection.py`

**Deterministic Pre-Screen** (zero LLM cost):
1. Scans PDF text layer for SoA keywords ("Schedule of Activities", etc.)
2. X-mark density counting per page (≥3 X marks = likely SoA)
3. Continuation marker detection ("(continued)", "(cont'd)")
4. Y-band similarity scoring (matching row spacing to known SoA pages)
5. Iterative expansion: search ±10 pages from known SoA pages

**VLM Validation** (only for ambiguous pages):
- Vision LLM confirms/rejects deterministic candidates
- In SOA-only mode, pre-screen reduces VLM calls by ~90%

**Output:** TableRegion objects with pages, bounding boxes, table type, title

### 2.4 Table Stitching

**Module:** `src/pipeline/table_stitcher.py`

- Merges table fragments spanning multiple pages
- Merge criteria: consecutive pages (gap ≤2) + continuation markers OR matching titles
- Preserves original table ID from first fragment
- Handles interleaved text pages between SoA table pages

### 2.5 SoA Validation (5-Layer Filter)

**Module:** `src/pipeline/orchestrator.py`

| Layer | Check | Cost | Catches |
|-------|-------|------|---------|
| 1 | Section parser page-range gate | $0 | Amendment history, synopsis, appendices |
| 2 | Title rejection (45+ keywords) | $0 | Statistical methods, objectives, grading scales |
| 3 | Marker validation (0 MARKER = reject) | After extraction | Objective tables, all-text tables |
| 4 | Flagged rate (>80% = reject) | After extraction | Amendment tables (98% flagged) |
| 5 | Column header validation | After extraction | Tables without visit/time columns |

**Default behavior:** Ambiguous tables are REJECTED (conservative — no false positives)

### 2.6 Structural Analysis

**Module:** `src/pipeline/structural_analyzer.py`

- VLM analyzes table images to infer logical structure
- Output: TableSchema with column headers (multi-level), row groups, merged regions
- Handles complex headers: Phase → Visit → Day nesting

### 2.7 Grid Anchoring (Optional)

**Module:** `src/pipeline/grid_anchor.py`

- Extracts deterministic row/column structure from PDF text layer
- PyMuPDF `find_tables()` detects table boundaries
- Produces GridSkeleton with procedure names + Y-positions
- VLM fills values against fixed row indices (no structural drift)
- Disabled by default — can be enabled per-protocol

### 2.8 Cell Extraction (Dual-Pass)

**Module:** `src/pipeline/cell_extractor.py`

**Pass 1:** VLM extracts all cells with prompt variant A
**Pass 2:** Independent extraction with prompt variant B (different framing)

**3 prompt strategies:**
1. **Anchored** (with GridSkeleton): row indices locked from PyMuPDF
2. **Standard** (no anchor): VLM infers structure visually
3. **Text-layout** (no grid lines): alignment-based column detection

**Cell data type classification:**
- MARKER (X, ✓, ✔) — procedure performed at this visit
- TEXT — descriptive content
- NUMERIC — measurements, counts
- EMPTY — no content
- CONDITIONAL — marker with qualifying footnote

**Chunking:** Tables >5 pages extracted per-page with headers repeated

### 2.9 Footnote Resolution

**Module A:** `src/pipeline/footnote_extractor.py` — VLM reads footnote blocks
**Module B:** `src/pipeline/footnote_resolver.py` — Deterministic matching + classification

**Classification patterns:**
| Type | Triggers | Budget Impact |
|------|----------|---------------|
| CONDITIONAL | "only if", "as needed", "clinically indicated" | Reduces visit frequency (range) |
| EXCEPTION | "except", "unless", "not required" | Excludes visit |
| REFERENCE | "see section", "refer to" | Informational |
| CLARIFICATION | Everything else | Informational |

### 2.10 Procedure Normalization

**Module:** `src/pipeline/procedure_normalizer.py`

**6-step matching algorithm:**
1. Clean input (strip footnote markers, normalize case)
2. Exact match against 2,900+ aliases
3. Starts-with match (handles long SoA descriptions)
4. Whole-word alias match
5. Fuzzy match (Levenshtein ≥80%)
6. Not-procedure check (84 exclusion patterns)

**Vocabulary:** 542 canonical procedures, 415 with CPT codes, 59 categories
**Exclusions:** 84 patterns in `data/procedure_exclusions.json`
**Hierarchy:** 5 procedure families with site-specific children (Biopsy, CT, Endoscopy, Drug Admin, Ultrasound)

### 2.11 Temporal Extraction

**Module:** `src/pipeline/temporal_extractor.py`

- Parses visit/column headers to extract timing
- Handles: Day N, Week N, Month N, Cycle N, Screening, Baseline, Follow-up
- Extracts visit windows: target_day ± window_minus/window_plus
- Detects unscheduled visits

### 2.12 Challenger Validation

**Module:** `src/pipeline/challenger_agent.py`

- Independent VLM reviews extraction for errors
- Looks for: hallucinated values, missing cells, structural mismatches
- Produces ChallengeIssue with severity score (0-1)
- Design: VLM asked to find ERRORS (adversarial framing)

### 2.13 OCR Grounding

**Module:** `src/pipeline/ocr_grounding.py`

- Cross-verifies VLM extraction against independent OCR reading
- Backends: docTR (preferred) or Tesseract (fallback)
- Flags disagreements between VLM and OCR
- Conservative: only flags clear mismatches

### 2.14 Reconciliation

**Module:** `src/pipeline/reconciler.py`

**Multi-pass reconciliation:**
- Both passes agree → confidence = 0.95
- Passes disagree → confidence = 0.50, flagged for review
- Single pass only → confidence = 0.70

**Cost-weighted thresholds:**
- LOW tier: confidence ≥ 0.85 to pass
- MEDIUM: ≥ 0.90
- HIGH/VERY_HIGH: ≥ 0.95

### 2.15 Output Validation

**Module:** `src/pipeline/output_validator.py`

Hard validation gate — rejects malformed tables:
- Schema sanity (num_cols < 200)
- Cell value sanity (no NONE/NULL patterns)
- Structural consistency (no impossible row/col indices)
- Footnote chain validation
- Duplicate detection

---

## 3. Verbatim Extraction System

**Module:** `src/pipeline/verbatim_extractor.py`

### Architecture: LLM-as-Locator, PyMuPDF-as-Copier

```
User instruction: "Extract the inclusion criteria"
    │
    ├─── Direct match? ──→ Regex: "Section 5.1" → section_parser.find("5.1")
    │    (deterministic, $0)
    │
    └─── LLM Locator ──→ Sends outline to LLM → {"target_sections": ["5.1"]}
         ($0.001)        LLM never sees the PDF content
    │
    ▼
PyMuPDF Extraction (deterministic)
    │
    ├─── Y-coordinate clipping (start_y → end_y)
    ├─── Paragraph reconstruction (Y-gap analysis)
    ├─── List detection (bullet chars + indentation)
    ├─── Table detection (find_tables())
    ├─── Bold/italic from font metadata
    └─── Section heading stripped (body content only)
    │
    ▼
Semantic HTML output with formatting integrity
```

### Section Boundary Detection

**Same-page boundaries:** Sibling section number lookup (`_next_section_number()`)
- 2.2.1 → 2.2.2: find 2.2.2's heading Y on the same page
- Cross-page: scan each page from declared_end for sibling heading

**Page-range buffer:** +2 pages beyond end_page, with iterative boundary scanning

---

## 4. Section Parser

**Module:** `src/pipeline/section_parser.py`

### 100% Deterministic — No LLM Required

**3 detection strategies:**
1. Table of Contents parsing (regex on dotted leader lines)
2. Font-based heading detection (bold text at specific sizes)
3. Numbered section pattern matching (1., 1.1, 1.1.1, up to 6 levels)

**Content extraction:**
- Y-coordinate clipping for precise boundaries
- Paragraph reconstruction from Y-gap analysis (gap > 6pt = new paragraph)
- List classification: HEADING, SUBHEADING, BODY, LIST_ITEM, LIST_ITEM_L2, TABLE
- Header/footer stripping: auto-detected from repeated text in top/bottom 80pt

**Output:** Hierarchical section tree with `content_html` per section

---

## 5. Budget Calculation

**Module:** `src/pipeline/budget_calculator.py`

### Budget Line Generation

```
For each SoA table row (procedure):
    1. Skip if is_not_procedure() matches (84 exclusion patterns)
    2. Count MARKER cells → firm_visits
    3. Check CONDITIONAL footnotes → conditional_visits
    4. Detect phone-based procedures → PHONE_CALL cost tier
    5. Re-normalize with current vocabulary → CPT code + category
    6. Apply domain YAML cost overrides
    7. Generate BudgetLine with firm/conditional split
```

### Cost Tiers (configurable per domain)

| Tier | Default | Description |
|------|---------|-------------|
| LOW | $75 | Vitals, basic labs, consent |
| MEDIUM | $350 | ECG, physical exam, standard bloodwork |
| HIGH | $1,200 | CT, MRI, specialized labs |
| VERY_HIGH | $3,500 | PET/CT, cardiac cath |
| PHONE_CALL | $35 | Remote/phone follow-up |
| EDIARY | $10 | Per-prompt eDiary |
| INFUSION | $2,500 | IV drug administration |
| BIOPSY | $4,000 | Tissue biopsy + pathology |

### Conditional Footnote Handling

- FIRM visits: guaranteed (counted at full cost)
- CONDITIONAL visits: may not occur (shown as range: $X – $Y)
- Budget wizard shows both: "3 firm + 2 conditional" with cost range

---

## 6. Domain Configuration

**Path:** `src/domain/config/*.yaml`

### Configs Available

| File | Protocol | TA |
|------|----------|-----|
| `pfizer_vaccines.yaml` | BNT162b2 | Vaccines |
| `moderna_vaccines.yaml` | mRNA-1273-P301 | Vaccines |
| `oncology.yaml` | Generic | Oncology (cycle-based) |

### Config Capabilities

- Visit counting rules (marker patterns, text indicators)
- Cost tier definitions and overrides
- Footnote handling rules (conditional → range/exclude/include)
- Phone call detection keywords
- TA-specific rules (reactogenicity windows, cycle counting, treat-to-progression)

---

## 7. Data Layer

### Protocol Persistence

**Module:** `src/persistence/ke_store.py`

- **JsonKEStore** (default): `data/protocols/{id}.json`
- **Neo4jKEStore** (optional): Graph database for KE relationships
- Singleton pattern with `create_ke_store()` / `reset_ke_store()`
- Protocol bridge: `pipeline_output_to_protocol()` converts extraction results

### Procedure Vocabulary

**Module:** `src/domain/vocabulary/`

- `procedure_vocab.py`: 542-procedure CRUD with fuzzy search
- `procedure_hierarchy.py`: Parent-child families (5 hierarchies)
- `data/procedure_mapping.csv`: Canonical vocabulary
- `data/procedure_exclusions.json`: 84 exclusion patterns
- `data/procedure_hierarchies.json`: Site-specific CPT resolution

### Ground Truth Annotations

- Every cell accept/correct/flag → `data/annotations/{protocol_id}_annotations.csv`
- CSV format: timestamp, cell reference, action, old_value, new_value, confidence
- Feeds back into pipeline evaluation and accuracy benchmarking

---

## 8. API Endpoints

### Core Extraction
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/extract` | Upload PDF, start extraction job |
| GET | `/api/jobs/{id}` | Poll job status |
| GET | `/api/jobs/{id}/result` | Get extraction results |

### Protocol Management
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/protocols` | List all protocols |
| GET | `/api/protocols/{id}` | Get full protocol data |
| GET | `/api/protocols/{id}/sections` | Section tree |
| GET | `/api/protocols/{id}/budget/lines` | Budget lines (re-normalized) |
| GET | `/api/protocols/{id}/budget/export` | XLSX export |
| GET | `/api/protocols/{id}/page-image/{page}` | PDF page as PNG |
| POST | `/api/protocols/{id}/review` | Accept/correct/flag cell |
| POST | `/api/protocols/{id}/ask` | Q&A about protocol |
| POST | `/api/protocols/{id}/verbatim` | Server-side verbatim extraction |

### Procedure Library
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/procedures/library` | List procedures (filterable) |
| GET | `/api/procedures/library/search?q=` | Fuzzy search |
| GET | `/api/procedures/library/stats` | Vocabulary stats |
| GET | `/api/procedures/library/hierarchies` | Procedure families |
| GET | `/api/procedures/library/export` | CSV export |
| POST | `/api/procedures/library/import` | CSV import |
| PUT | `/api/procedures/{name}` | Update procedure |
| DELETE | `/api/procedures/{name}` | Delete procedure |

### Section Parsing & Verbatim
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/sections` | Parse sections from PDF |
| POST | `/api/verbatim` | Verbatim extraction (file upload) |

---

## 9. Frontend Architecture

### Pages (12 routes)

| Route | Purpose |
|-------|---------|
| `/` | Protocol upload |
| `/protocols` | Protocol library |
| `/protocols/{id}` | Protocol workspace (table-focused) |
| `/protocols/{id}/budget-wizard` | 4-step site budget wizard |
| `/budget` | Budget wizard landing |
| `/tools/sections` | Document Explorer |
| `/tools/verbatim` | Verbatim extraction |
| `/manage/procedures` | Procedure library management |
| `/history` | Extraction job history |
| `/how-it-works` | Pipeline documentation |
| `/login` | Password-protected access |

### Key UI Components

- **SoA Review Assistant**: 3-layer progressive review (Overview → Smart Grid → Cell Detail)
- **Critique Engine**: 6 automated analyzers (confidence, footnotes, CPT gaps, flagged rate, pass disagreements, cost risk)
- **CPT Lookup Widget**: Search + hierarchy browser + add-to-library
- **Document Explorer**: Section tree + verbatim extraction + PDF viewer
- **Budget Wizard**: 4 steps (SoA Review → Costs & CPT → Preview → Validate & Export)

---

## 10. Quality & Testing

### Test Suite
- 228 backend tests (pytest + pytest-asyncio)
- 17 frontend tests (Vitest + Testing Library)
- 18 E2E tests (Playwright)

### Quality Gate Integration
- KP_SDLC Quality Gate with PRS scoring
- Cathedral Keeper architecture governance
- Feedback loop with `/triage-feedback` and `/process-feedback` commands

### Ground Truth
- Cell-level annotations (accept/correct/flag) logged to CSV
- Protocol-level linkage for procedure vocabulary enrichment
- 100% procedure mapping rate across stored protocols

---

## 11. Deployment

### Railway (Production)
- **Backend**: Python 3.12, FastAPI, Nixpacks builder
- **Frontend**: Next.js 16 standalone, separate service
- **Volume**: Persistent disk at `/app/data` for protocols, procedures, annotations
- **Seed**: Startup script copies seed data from `data_seed/` to volume on deploy
- **Password**: Next.js middleware, configurable via `SITE_PASSWORD` env var

### Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | LLM API key for extraction |
| `PORT` | Auto | Set by Railway |
| `NEXT_PUBLIC_API_URL` | Frontend | Backend URL |
| `SITE_PASSWORD` | Optional | Frontend password |
| `NEO4J_URI` | Optional | Neo4j for KE graph |

---

## 12. Known Limitations & Roadmap

### Current Limitations
1. **Image-based SoA pages**: Tables rendered as images (not text) cannot be extracted via text layer — VLM-only extraction required
2. **Cycle-based oncology**: Budget calculator counts visible X-marks, doesn't multiply by expected cycle count
3. **Treatment-to-progression**: No duration model for open-ended treatment protocols
4. **FMV pricing**: Cost tiers are estimates — FMV module planned (see `docs/FMV_Feature_Plan.md`)
5. **Multi-arm budgets**: All arms merged into one total — per-arm separation needed

### Planned Features
- FMV Pricing Module (6-phase plan, spec complete)
- Postgres migration (when scale requires it)
- Per-arm budget separation
- Cycle-based visit counting for oncology
- GrantPlan CSV import for FMV rates
