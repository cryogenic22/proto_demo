# ProtoExtract

AI-powered clinical trial protocol extraction pipeline for site budgeting.

Extracts Schedule of Activities (SoA) tables from protocol PDFs/DOCX, maps procedures
to CPT codes, resolves footnotes, and generates interactive site budget worksheets —
with confidence scoring, adversarial validation, and OCR grounding to minimize hallucination.

## What It Does

| Capability | Description |
|-----------|-------------|
| **SoA Table Extraction** | Extracts Schedule of Activities tables from protocol PDFs with 90% confidence |
| **Site Budget Worksheet** | Auto-generates editable budget with procedures, CPT codes, frequencies, cost estimates, confidence colors, and review guidance |
| **Procedure Normalization** | Maps 840+ aliases → 180 canonical procedures with CPT codes across 15 categories |
| **Footnote Resolution** | Extracts and classifies footnotes (conditional/exception/reference) anchored to cells |
| **Section Parser** | Deterministic extraction of document outline with LLM fallback (PDF + DOCX) |
| **Verbatim Extraction** | Zero-hallucination copy-paste — LLM locates content, PyMuPDF extracts exact text |
| **Equation Preservation** | Detects formulas, outputs as LaTeX or OMML XML (editable in Word/MathType) |
| **Clinical Domain Intelligence** | Auto-classifies therapeutic area, applies domain-specific extraction hints |
| **Repeatability Testing** | Run N times, measure cell-level variance, track stability over time |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Edit .env: set your API key(s)

# 3. Start the API
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# 4. Start the frontend (optional)
cd web && npm install && npm run dev

# 5. Open http://localhost:3000
```

## LLM Provider Configuration

Supports **Anthropic Claude**, **OpenAI GPT**, and **Azure OpenAI**:

```env
# Anthropic (default)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Azure OpenAI
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Optional model overrides
LLM_MODEL=claude-sonnet-4-6
VISION_MODEL=gpt-4.1
```

### Performance Tuning

```env
# Concurrent LLM calls (default: 10)
MAX_CONCURRENT_LLM_CALLS=10

# OpenAI Batch Mode — 50% cheaper, async processing (minutes not seconds)
OPENAI_BATCH_MODE=true
```

## API Endpoints

### Core Pipeline

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/extract` | POST | Upload PDF → start SoA extraction |
| `/api/jobs/{id}` | GET | Check extraction status |
| `/api/jobs/{id}/result` | GET | Get raw extraction JSON |
| `/api/jobs/{id}/review?format=html` | GET | Extraction report with narrative analysis |
| `/api/jobs/{id}/review?format=budget` | GET | Interactive site budget worksheet |
| `/api/jobs/{id}/review?format=markdown` | GET | Medical writer review document |

### Section Parser & Verbatim Extraction

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sections` | POST | Parse document outline (PDF or DOCX) |
| `/api/verbatim?instruction=...` | POST | Extract verbatim content (zero hallucination) |

```bash
# Parse all sections
curl -X POST -F "file=@protocol.pdf" http://localhost:8000/api/sections

# Copy Section 5.1 verbatim (instant, no LLM needed)
curl -X POST -F "file=@protocol.pdf" \
  "http://localhost:8000/api/verbatim?instruction=Section 5.1"

# Find and copy inclusion criteria (one LLM call to locate)
curl -X POST -F "file=@protocol.pdf" \
  "http://localhost:8000/api/verbatim?instruction=Copy the inclusion criteria"

# Extract with LaTeX equations
curl -X POST -F "file=@protocol.pdf" \
  "http://localhost:8000/api/verbatim?instruction=Section 9.1&output_format=latex"
```

### Domain Library

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/procedures/mapping` | GET | Export full procedure → CPT mapping table |
| `/api/procedures/check` | POST | Test specific procedure names against vocabulary |

## Pipeline Architecture (14 Stages)

```
PDF → Page Images → Protocol Synopsis → SOA Detection (2-phase) →
Multi-Page Stitching → Structural Analysis → Cell Extraction (dual-pass) →
Footnote Extraction → Footnote Resolution → Procedure Normalization →
Temporal Extraction → Challenger Agent → OCR Grounding → Reconciliation →
Output Validation → Budget Worksheet
```

## Validation Results

Tested on Pfizer BNT162b2 COVID-19 vaccine protocol (252 pages):

| Version | Confidence | Flagged | Footnotes | Time | Cost |
|---------|-----------|---------|-----------|------|------|
| v1 (all tables) | 82% | 28% | 0 | 93 min | $14 |
| v2 (SOA + footnotes) | 85% | 20% | 28 | 28 min | $3 |
| v3 (+ synopsis + OCR) | 84% | 23% | 27 | 27 min | $3 |
| **v4 (OCR calibrated)** | **90%** | **17%** | **27** | **26 min** | **$3** |

### Section Parser Results

Tested on 11 protocols across 8 therapeutic areas:

| Metric | Result |
|--------|--------|
| Protocols parsed | 11/11 (100%) |
| Deterministic | 11/11 (100%) |
| Pfizer BNT162b2 | 239 sections, 19/19 tests pass |
| Verbatim extraction | 9/10 instructions correct |

## Test Suite

```bash
python -m pytest tests/ -v     # 231+ tests
```

| Category | Tests |
|----------|-------|
| Models & schemas | 35 |
| Pipeline modules | 50+ |
| Procedure normalization | 23 |
| Footnote classification | 17 |
| Visit header parsing | 20 |
| Output validation | 12 |
| OCR grounding | 9 |
| Clinical domain | 12 |
| Section parser | 19 |
| Regression content | 30+ |

## Golden Evaluation Set

35 publicly available protocols across 14 therapeutic areas with repeatability testing:

```bash
# Single run
python -m golden_set.evaluate --protocol P-01 --report

# Repeatability test (5 runs)
python -m golden_set.evaluate --protocol P-13 --repeat 5 --report --save

# Full golden set with batch mode
python -m golden_set.evaluate --all --repeat 3 --report --save --tag "v4"
```

## SME Corrections

Clinical experts extend the procedure vocabulary without code changes:

```json
// golden_set/sme_inputs/my_corrections.json
{
  "expert_name": "Dr. Smith",
  "procedure_corrections": [
    {
      "action": "update_aliases",
      "canonical_name": "Electrocardiogram, 12-lead",
      "add_aliases": ["ecg with qtcf", "12-lead with rhythm strip"]
    }
  ]
}
```

## Project Structure

```
src/
├── pipeline/                # 14-stage extraction pipeline
│   ├── pdf_ingestion.py     # PDF → page images
│   ├── protocol_synopsis.py # Study design extraction
│   ├── table_detection.py   # SOA-only 2-phase detection
│   ├── table_stitcher.py    # Multi-page table merging
│   ├── structural_analyzer.py # Table schema extraction
│   ├── cell_extractor.py    # Dual-pass cell extraction
│   ├── footnote_extractor.py # Footnote definition extraction
│   ├── footnote_resolver.py # Marker → cell anchoring
│   ├── procedure_normalizer.py # 180 procedures, 840 aliases
│   ├── temporal_extractor.py # Visit window parsing
│   ├── challenger_agent.py  # Adversarial validation
│   ├── ocr_grounding.py     # Cross-modal verification (docTR)
│   ├── reconciler.py        # Multi-pass confidence scoring
│   ├── output_validator.py  # Hallucination blocking gate
│   ├── section_parser.py    # Document outline (PDF + DOCX + LLM fallback)
│   ├── verbatim_extractor.py # Zero-hallucination copy-paste
│   ├── clinical_domain.py   # Therapeutic area intelligence
│   ├── budget_calculator.py # Site budget worksheet
│   ├── html_report.py       # Extraction report generator
│   ├── review_exporter.py   # Medical writer review docs
│   └── run_comparator.py    # Cross-version comparison
├── domain/                  # Standalone clinical domain library
│   ├── procedures.py        # Procedure vocabulary with SME overlay
│   └── sme_corrections.py   # Expert correction mechanism
├── models/
│   └── schema.py            # Pydantic data models
└── llm/
    └── client.py            # Multi-provider (Anthropic + OpenAI + Azure)

api/main.py                  # FastAPI backend
web/                         # Next.js frontend
data/procedure_mapping.csv   # Reviewable procedure vocabulary
golden_set/                  # 35-protocol evaluation set
docs/                        # Technical documentation
```

## Documentation

- [Pipeline Efficacy Report](docs/pipeline_efficacy_report.md) — 14-step walkthrough with evidence
- [Technical Overview](docs/technical_overview.md) — Architecture and test harnesses
- [Section & Verbatim Test Report](docs/section_verbatim_test_report.md) — Testing results
- [Cathedral Keeper Analysis](docs/cathedral_keeper_analysis.md) — Architecture governance

## License

Proprietary. All rights reserved.
