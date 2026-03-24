# ProtoExtract

AI-powered clinical trial protocol extraction platform. Extracts Schedule of Activities (SoA) tables from protocol PDFs/DOCX, builds structured protocol models, maps procedures to CPT codes, and generates site budget worksheets.

## Architecture

```
PDF/DOCX → [Extraction Pipeline] → Cells → [Structured Model Builder] → Protocol Model → [Budget Calculator] → Budget
                                                      ↓
                                              Knowledge Graph
                                    (Visits × Procedures × Footnotes)
```

| Layer | Purpose |
|-------|---------|
| **Extraction Pipeline** | 14-stage PDF processing: table detection, dual-pass cell extraction, OCR grounding, adversarial validation |
| **Structured Model Builder (SMB)** | Transforms cells into typed entities + relationships. YAML-driven, document-type agnostic |
| **Trust Module** | 3-tier confidence: Cell → Row → Protocol. Evidence chain preserved from extraction passes |
| **Procedure Vocabulary** | 552 canonical procedures, 3,400+ aliases, 187 CPT codes. 100% mapping across 9 test protocols |
| **Budget Calculator** | Visit counting with cycle multiplication, span parsing, footnote modifiers, domain-aware cost tiers |
| **Verbatim Extractor** | Zero-hallucination copy-paste: LLM locates, PyMuPDF/python-docx copies exact text |

## Key Metrics

| Metric | Value |
|--------|-------|
| Procedure mapping accuracy | 100% (408/408 across 9 protocols) |
| CPT + effort-based coverage | 85% |
| Formatting fidelity (PDF) | 79/100 (0 critical issues) |
| DOCX formatting fidelity | 100% (native XML parsing) |
| Test suite | 415+ tests |
| Protocols tested | 9 stored + 10 PDFs available |

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Configure
cp .env.example .env  # Set ANTHROPIC_API_KEY or OPENAI_API_KEY

# Run backend
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Run frontend
cd web && npm install && npm run dev

# Open http://localhost:3000
```

## API Endpoints

### Core
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/extract` | POST | Upload PDF, start extraction |
| `/api/jobs/{id}` | GET | Check extraction status |
| `/api/protocols` | GET | List stored protocols |
| `/api/protocols/{id}` | GET | Get full protocol data |
| `/api/protocols/{id}/trust` | GET | Protocol trust dashboard |
| `/api/protocols/{id}/review` | POST | Accept/correct/flag a cell |

### Structured Model Builder
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/smb/build/{id}` | POST | Build structured model from protocol |
| `/api/smb/model/{id}` | GET | Get model summary + validation |
| `/api/smb/model/{id}/schedule` | GET | Visit × Procedure matrix for budget |
| `/api/smb/model/{id}/graph` | GET | Entity-relationship graph for visualization |

### Verbatim & Sections
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sections` | POST | Parse document outline |
| `/api/verbatim` | POST | Zero-hallucination content extraction |
| `/api/protocols/{id}/verbatim` | POST | Extract from stored protocol's PDF |
| `/api/protocols/{id}/page-image/{page}` | GET | Render PDF page as PNG |

### Budget & Procedures
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/protocols/{id}/budget/lines` | GET | Budget line items with CPT codes |
| `/api/protocols/{id}/budget/export-xlsx` | GET | Export budget as Excel |
| `/api/procedures/library` | GET | Full 552-procedure vocabulary |

## Project Structure

```
src/
├── pipeline/                    # 14-stage extraction pipeline
│   ├── orchestrator.py          # Main pipeline with 5-layer SoA filter
│   ├── cell_extractor.py        # Dual-pass VLM cell extraction
│   ├── reconciler.py            # Multi-pass reconciliation + evidence
│   ├── challenger_agent.py      # Adversarial validation
│   ├── ocr_grounding.py         # Cross-modal OCR verification
│   ├── procedure_normalizer.py  # 552 procedures, 100% mapping
│   ├── footnote_resolver.py     # 5-type footnote classification
│   ├── budget_calculator.py     # Site budget with cycle/span/conditional
│   ├── section_parser.py        # Section parsing (PDF + DOCX + LLM fallback)
│   └── verbatim_extractor.py    # Zero-hallucination copy-paste
├── smb/                         # Structured Model Builder (standalone)
│   ├── core/
│   │   ├── engine.py            # SMBEngine — build pipeline orchestrator
│   │   ├── entity.py            # Entity model with provenance
│   │   ├── relationship.py      # Typed directed relationships
│   │   ├── model.py             # StructuredModel knowledge graph
│   │   ├── inference.py         # 7 inference rules (Cycle, Span, Conditional...)
│   │   ├── validator.py         # Model completeness checking
│   │   ├── context.py           # ProtocolContextExtractor (whole-protocol)
│   │   └── query.py             # Semantic query engine
│   ├── domains/
│   │   ├── protocol/            # Protocol domain schema + builder
│   │   └── ta_profiles/         # TA-specific YAML configs (oncology, vaccines...)
│   ├── adapters/
│   │   └── protoextract.py      # Pipeline output → SMB input adapter
│   └── storage/                 # In-memory + Neo4j backends
├── trust/                       # Trust module (cell → row → protocol)
│   ├── models.py                # CellEvidence, RowTrust, ProtocolTrust
│   └── engine.py                # Confidence computation
├── domain/config/               # Domain YAML rules (oncology, vaccines, general)
├── models/                      # Pydantic data models
└── persistence/                 # Protocol storage (JSON + Neo4j)

api/main.py                      # FastAPI backend (30+ endpoints)
web/                             # Next.js 16 frontend
data/procedure_mapping.csv       # 552 canonical procedures with CPT codes
data/procedure_exclusions.json   # Noise row exclusion patterns
```

## Frontend Features

| Feature | Location |
|---------|----------|
| Protocol Workspace | Select protocol → SoA tables, procedures, overview |
| Trust Dashboard | Protocol-level trust score, extraction quality, budget readiness |
| Knowledge Graph | Interactive protocol intelligence hub with agent chat |
| SoA Review Assistant | 3-layer review: Overview → Smart Grid → Cell Detail with evidence |
| Verbatim Extract | Side-by-side PDF comparison with formatting fidelity indicators |
| Source PDF Viewer | View source PDF alongside extracted content |
| Site Budget Wizard | 4-step budget workflow with CPT lookup |
| Procedure Library | 552 procedures, searchable, editable aliases |

## Known Limitations

| Issue | Impact | Status |
|-------|--------|--------|
| Transposed SoA tables | Procedures as columns, visits as rows — produces incorrect output | Planned |
| Image-rendered SoA pages | Tables as images without text layer — requires VLM-only extraction | Detected, warns user |
| 200+ page protocols | Performance degrades, higher variability | Optimization planned |
| Low-confidence section parsing | 2 of 10 test protocols have parser failures | LLM fallback (`parse_auto`) available |
| Occurrence count accuracy | SMB vs budget calculator counts may differ | Under investigation |

## Running Tests

```bash
# Full suite (415+ tests)
pytest tests/ -v

# Formatting fidelity eval
python -m tests.eval_formatting_fidelity

# SMB accuracy eval
python -m tests.eval_smb_accuracy

# Quick check
pytest tests/ --ignore=tests/test_orchestrator.py --ignore=tests/test_pdf_ingestion.py -q
```

## Deployment

Railway: Backend + Frontend as separate services.
- Backend: `docker/Dockerfile` or direct Python
- Frontend: `web/` with `NEXT_PUBLIC_API_URL` pointing to backend
- PDFs in `golden_set/cached_pdfs/` (committed for Railway access)

## Documentation

- [Pipeline Gaps & Roadmap](docs/Pipeline_Gaps_and_Roadmap.md)
- [Formatting Enhancement Plan](docs/Formatting_Enhancement_Plan.md)
- [Section Parsing Technical Review](docs/Section_Parsing_Verbatim_Technical_Review.md)
- [FMV Feature Plan](docs/FMV_Feature_Plan.md)

## License

Proprietary. All rights reserved.
