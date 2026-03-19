# ProtoExtract

AI-powered clinical trial protocol extraction pipeline for site budgeting.

Extracts Schedule of Activities (SoA) tables from protocol PDFs, maps procedures
to CPT codes, resolves footnotes, and generates interactive site budget worksheets —
with confidence scoring, adversarial validation, and OCR grounding to minimize hallucination.

## What It Does

| Capability | Description |
|-----------|-------------|
| **SoA Table Extraction** | Extracts all Schedule of Activities tables from protocol PDFs with 90% confidence |
| **Site Budget Worksheet** | Auto-generates editable budget with procedures, CPT codes, frequencies, and cost estimates |
| **Procedure Normalization** | Maps 840+ aliases → 180 canonical procedures with CPT codes across 15 categories |
| **Footnote Resolution** | Extracts and classifies footnotes (conditional/exception/reference) anchored to cells |
| **Section Parser** | Deterministic extraction of document outline (239 sections from a 252-page protocol) |
| **Verbatim Extraction** | Zero-hallucination copy-paste from protocols — LLM locates, PyMuPDF extracts exact text |
| **Repeatability Testing** | Run N times, measure cell-level variance, track stability over time |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY or OPENAI_API_KEY

# 3. Start the API
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# 4. Start the frontend (optional)
cd web && npm install && npm run dev

# 5. Upload a protocol at http://localhost:3000
```

## LLM Provider Configuration

Supports both **Anthropic Claude** and **OpenAI GPT**:

```env
# Anthropic (default)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Optional model overrides
LLM_MODEL=claude-sonnet-4-6
VISION_MODEL=gpt-4.1
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
| `/api/verbatim?instruction=...` | POST | Extract verbatim content by section or keyword |

```bash
# Parse all sections from a protocol
curl -X POST -F "file=@protocol.pdf" http://localhost:8000/api/sections

# Copy Section 5.1 verbatim (no LLM needed — instant)
curl -X POST -F "file=@protocol.pdf" \
  "http://localhost:8000/api/verbatim?instruction=Section 5.1"

# Find and copy inclusion criteria (one LLM call to locate)
curl -X POST -F "file=@protocol.pdf" \
  "http://localhost:8000/api/verbatim?instruction=Copy the inclusion criteria"
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

See [Pipeline Efficacy Report](docs/pipeline_efficacy_report.md) for detailed
step-by-step explanation with rationale and evidence.

## Validation Results

Tested on Pfizer BNT162b2 COVID-19 vaccine protocol (252 pages):

| Metric | Value |
|--------|-------|
| SoA tables extracted | 8 |
| Total cells | 1,634 |
| Footnotes resolved | 27 |
| Procedures mapped | 20 (100%) |
| Average confidence | 90% |
| Processing time | 26 minutes |
| Cost per protocol | ~$3 |

### Pipeline Version Progression

| Version | Confidence | Flagged | Time | Cost |
|---------|-----------|---------|------|------|
| v1 (all tables) | 82% | 28% | 93 min | $14 |
| v2 (SOA + footnotes) | 85% | 20% | 28 min | $3 |
| v3 (+ synopsis + OCR) | 84% | 23% | 27 min | $3 |
| **v4 (OCR calibrated)** | **90%** | **17%** | **26 min** | **$3** |

## Test Suite

```bash
python -m pytest tests/ -v     # 212+ tests
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

35 publicly available clinical trial protocols across 14 therapeutic areas
with repeatability testing support.

```bash
# Single run
python -m golden_set.evaluate --protocol P-01 --report

# Repeatability test (5 runs)
python -m golden_set.evaluate --protocol P-13 --repeat 5 --report --save
```

## SME Corrections

Clinical experts can extend the procedure vocabulary without code changes:

```bash
# Add corrections as JSON files
golden_set/sme_inputs/my_corrections.json
```

See `golden_set/sme_inputs/example_corrections.json` for format.

## Project Structure

```
src/
├── pipeline/              # Extraction pipeline (14 stages)
│   ├── pdf_ingestion.py
│   ├── protocol_synopsis.py
│   ├── table_detection.py
│   ├── table_stitcher.py
│   ├── structural_analyzer.py
│   ├── cell_extractor.py
│   ├── footnote_extractor.py
│   ├── footnote_resolver.py
│   ├── procedure_normalizer.py
│   ├── temporal_extractor.py
│   ├── challenger_agent.py
│   ├── ocr_grounding.py
│   ├── reconciler.py
│   ├── output_validator.py
│   ├── section_parser.py     # Deterministic document outline
│   ├── verbatim_extractor.py # Zero-hallucination copy-paste
│   ├── clinical_domain.py    # Therapeutic area intelligence
│   ├── budget_calculator.py  # Site budget worksheet
│   ├── html_report.py        # Extraction report generator
│   ├── review_exporter.py    # Medical writer review docs
│   └── run_comparator.py     # Cross-version comparison
├── domain/                # Standalone clinical domain library
│   ├── procedures.py      # Procedure vocabulary (180 procs, 840 aliases)
│   └── sme_corrections.py # Expert correction mechanism
├── models/
│   └── schema.py          # Pydantic data models
└── llm/
    └── client.py          # Multi-provider LLM client (Anthropic + OpenAI)

api/main.py               # FastAPI backend
web/                      # Next.js frontend
data/procedure_mapping.csv # Reviewable procedure vocabulary
golden_set/               # 35-protocol evaluation set
docs/                     # Technical documentation
```

## Documentation

- [Pipeline Efficacy Report](docs/pipeline_efficacy_report.md) — 14-step walkthrough with evidence
- [Technical Overview](docs/technical_overview.md) — Architecture and test harnesses
- [Section & Verbatim Test Report](docs/section_verbatim_test_report.md) — Comprehensive testing results

## License

Proprietary. All rights reserved.
