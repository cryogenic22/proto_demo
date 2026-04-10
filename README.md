# ProtoExtract

AI-powered clinical trial protocol extraction and document digitization platform. Extracts Schedule of Activities (SoA) tables from protocol documents, builds structured protocol models, maps procedures to CPT codes, generates site budget worksheets, and provides format-preserving document conversion across 7 input and 7 output formats.

## Architecture

```
                ┌──────────────────────────────────────────────────────────┐
                │  Layer 1: Document Digitization (DocumentDigitizer)     │
                │  PDF · DOCX · HTML · PPTX · XLSX · MD · TXT · JSON     │
                │      ↓ FormattedDocument + Sections + Table Classes     │
                │      ↓ Formula Enrichment ↓ Fidelity Check              │
                │  IR → HTML · DOCX · PDF · PPTX · MD · TXT · JSON       │
                └──────────────────────────────────────────────────────────┘
                                         ↓ DigitizedDocument
                ┌──────────────────────────────────────────────────────────┐
                │  Layer 2: Targeted Extraction (configurable)            │
                │  ├── SoA Extractor → cells, procedures, visits, budget  │
                │  ├── Eligibility Extractor → inclusion/exclusion KEs    │
                │  └── Endpoints Extractor → objectives, endpoints KEs    │
                └──────────────────────────────────────────────────────────┘
                                         ↓
        [Structured Model Builder] → Protocol Model → [Budget Calculator] → Budget
                      ↓
              Knowledge Graph (Visits × Procedures × Footnotes)
```

| Layer | Purpose |
|-------|---------|
| **Layer 1: Digitization** | Full document extraction: text, tables, formulas, sections, formatting. Table classification (SOA/OTHER). Format-preserving rendering (8 input, 7 output formats) |
| **Layer 2: Extraction** | Targeted extractors operating on Layer 1 output. Configurable via UI: Full / SoA Only / SoA + Protocol Elements |
| **Structured Model Builder (SMB)** | Transforms cells into typed entities + relationships. YAML-driven, document-type agnostic |
| **Trust Module** | 3-tier confidence: Cell → Row → Protocol. Evidence chain preserved from extraction passes |
| **Procedure Vocabulary** | 552 canonical procedures, 3,400+ aliases, 187 CPT codes. 100% mapping across 9 test protocols |
| **Budget Calculator** | Visit counting with cycle multiplication, span parsing, footnote modifiers, domain-aware cost tiers |
| **Verbatim Extractor** | Zero-hallucination copy-paste: LLM locates, PyMuPDF/python-docx copies exact text |

## Document Digitization Pipeline

Format-preserving document conversion built on a universal intermediate representation (IR). Any supported input format can be converted to any supported output format while preserving formatting, structure, and formulas.

### Supported Formats

| Direction | Formats |
|-----------|---------|
| **Input (Ingest)** | PDF, DOCX, HTML, PPTX, XLSX, Markdown, Plain Text, JSON (auto-detected) |
| **Output (Render)** | HTML, DOCX, PDF, PPTX, Markdown, Plain Text, JSON |

### JSON Ingest — Auto-Detecting Schema Framework

The JSON ingestor automatically detects the schema of incoming JSON files and routes to the appropriate parser. No hard-coding — new schemas are added as plugins.

| Schema | Detection | Output |
|--------|-----------|--------|
| **USDM** (CDISC Unified Study Definitions Model) | `study` + `studyDesigns` keys | Protocol + KEs + SMB Structured Model + FormattedDocument |
| **Protocol IR** (ProtoExtract native) | `protocol_id` + `metadata` + `tables`/`sections` | Protocol + KEs |
| **FormattedDocument IR** (JSONRenderer round-trip) | `pages` + `total_pages` | FormattedDocument (full format fidelity) |

```python
from src.formatter import DocHandler

handler = DocHandler()

# Auto-detects USDM, Protocol IR, or FormattedDocument IR
doc = handler.ingest(json_string, format="json", filename="study.json")
html = handler.render(doc, format="html")

# USDM → SMB Structured Model (for knowledge graph + budget)
from src.smb.adapters.usdm import USDMAdapter
adapter = USDMAdapter()
protocol = adapter.to_protocol(usdm_data)       # → persistence + KE graph
extraction = adapter.to_extraction_input(usdm_data)  # → SMB engine
```

### Usage

```python
from src.formatter import DocHandler

handler = DocHandler()

# Ingest any format into universal IR
doc = handler.ingest(pdf_bytes, format="pdf", filename="protocol.pdf")
doc = handler.ingest(docx_bytes, format="docx")
doc = handler.ingest(html_string, format="html")

# Render to any output format
html = handler.render(doc, format="html")      # str
docx = handler.render(doc, format="docx")      # bytes
pdf  = handler.render(doc, format="pdf")       # bytes
json_str = handler.render(doc, format="json")  # str (IR dump)

# One-shot conversion
html = handler.convert(pdf_bytes, "pdf", "html")
```

### Intermediate Representation (IR)

The IR preserves full document structure and formatting:

```
FormattedDocument
├── pages[]
│   ├── paragraphs[] — style, alignment, indent, spacing
│   │   └── lines[]
│   │       └── spans[] — text, font, size, color, bold/italic/underline,
│   │                      superscript/subscript, strikethrough, coordinates,
│   │                      formula annotations
│   └── tables[] — rows × cols with header flags, rowspan/colspan
├── font_inventory — font usage counts
├── color_inventory — color usage counts
└── style_inventory — paragraph style counts
```

### Formula Detection

4-tier formula detection pipeline that identifies and annotates mathematical, chemical, and pharmacokinetic notation:

| Tier | Method | Coverage |
|------|--------|----------|
| **Tier 1–2** | Regex detector — chemical formulas (CO₂, H₂O), dosing (mg/m²), PK parameters (AUC₀₋ᵢₙf), statistics (p<0.05) | Inline formulas |
| **Tier 3** | Structured parser — partial derivatives, integrals, summations, factorials, named pharma formulas, PK differential equations | Complex notation |
| **OMML** | Office MathML extractor — fractions, radicals, n-ary operators, super/subscript from DOCX | DOCX-native math |
| **Tier 4** | Image classifier + OCR — equation-like images detected by aspect ratio/histogram analysis | Image-rendered formulas |

The **Formula Enricher** runs post-ingestion, mapping detected formula offsets back to individual IR spans with HTML and LaTeX representations.

### Quality Assurance

| Tool | Purpose |
|------|---------|
| **Fidelity Checker** | Measures formatting conformance: spacing, fonts, alignment, run-on word detection, strikethrough analysis |
| **Span Forensics** | Three-level diff (source → IR → output) identifying exactly where formatting is lost and why |
| **Template Generator** | Applies blueprint template formatting to extracted content, producing CKEditor-compatible HTML |
| **Site Contract Generator** | Fills CTSA template PDFs with protocol-specific data while preserving template formatting |

## Key Metrics

| Metric | Value |
|--------|-------|
| Procedure mapping accuracy | 100% (408/408 across 9 protocols) |
| CPT + effort-based coverage | 85% |
| Formatting fidelity (PDF) | 79/100 (0 critical issues) |
| DOCX formatting fidelity | 100% (native XML parsing) |
| Test suite | 916 tests |
| Protocols tested | 19 stored + 10 PDFs available |

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
| `/api/protocols/import` | POST | Import JSON (auto-detects USDM / Protocol IR / FormattedDoc IR) |
| `/api/protocols/import-batch` | POST | Batch import multiple JSON files |
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
├── formatter/                   # Document digitization pipeline
│   ├── extractor.py             # PDF ingestor (PyMuPDF) + IR data model
│   ├── docx_renderer.py         # DOCX output with borders, formulas, page breaks
│   ├── fidelity_checker.py      # Formatting conformance measurement
│   ├── site_contract_generator.py  # CTSA template PDF filler
│   ├── template_generator.py    # Blueprint template → CKEditor HTML
│   ├── ingest/                  # Format ingestors
│   │   ├── json_ingestor.py     # JSON → IR (auto-detecting framework)
│   │   ├── json_schemas/        # Pluggable JSON schema parsers
│   │   │   ├── usdm.py          # CDISC USDM detection + parsing
│   │   │   ├── protocol_ir.py   # Protocol JSON detection + parsing
│   │   │   └── formatted_doc_ir.py  # FormattedDocument round-trip
│   │   ├── docx_ingestor.py     # DOCX → IR
│   │   ├── html_ingestor.py     # HTML → IR
│   │   ├── markdown_ingestor.py # Markdown → IR
│   │   ├── text_ingestor.py     # Plain text → IR
│   │   ├── pptx_ingestor.py     # PowerPoint → IR
│   │   └── excel_ingestor.py    # Excel → IR
│   ├── render/                  # Format renderers
│   │   ├── html_renderer.py     # IR → HTML (centered, formula-aware)
│   │   ├── pdf_renderer.py      # IR → PDF
│   │   ├── pptx_renderer.py     # IR → PowerPoint
│   │   ├── markdown_renderer.py # IR → Markdown
│   │   ├── text_renderer.py     # IR → Plain text
│   │   └── json_renderer.py     # IR → JSON (full IR dump)
│   ├── formula/                 # Formula detection & annotation
│   │   ├── enricher.py          # Post-ingestion formula → span mapper
│   │   ├── orchestrator.py      # Multi-tier detection coordinator
│   │   ├── tools/
│   │   │   ├── regex_detector.py      # Tier 1-2: inline formula patterns
│   │   │   ├── structured_parser.py   # Tier 3: complex notation
│   │   │   ├── omml_extractor.py      # DOCX Office MathML extraction
│   │   │   ├── image_classifier.py    # Tier 4: equation image detection
│   │   │   ├── ocr_backends.py        # Tier 4: OCR for image formulas
│   │   │   └── renderers.py           # Formula rendering utilities
│   │   └── registry.py         # Detection tool registry
│   ├── analyze/                 # Quality analysis
│   │   └── span_forensics.py    # 3-level formatting loss diff
│   └── pipeline/                # Registry-based conversion routing
│       ├── orchestrator.py      # Format routing orchestrator
│       ├── registry.py          # Tool registry + metadata
│       ├── adapters.py          # Ingestor/renderer adapters
│       └── factory.py           # Tool factory
├── pipeline/                    # 14-stage extraction pipeline
│   ├── digitizer.py             # DocumentDigitizer — Layer 1 entry point
│   ├── orchestrator.py          # Main pipeline with soft SoA filter
│   ├── cell_extractor.py        # Dual-pass VLM cell extraction
│   ├── reconciler.py            # Multi-pass reconciliation + evidence
│   ├── challenger_agent.py      # Adversarial validation
│   ├── ocr_grounding.py         # Cross-modal OCR verification
│   ├── procedure_normalizer.py  # 552 procedures, 100% mapping
│   ├── footnote_resolver.py     # 5-type footnote classification
│   ├── budget_calculator.py     # Site budget with cycle/span/conditional
│   ├── section_parser.py        # Section parsing (PDF + DOCX + LLM fallback)
│   └── verbatim_extractor.py    # Zero-hallucination copy-paste
├── ingest/                      # Unified import routing
│   └── json_router.py           # Auto-detect JSON schema, dispatch, persist
├── models/
│   └── digitized.py             # DigitizedDocument + TableClassification (Layer 1↔2 contract)
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
│   │   ├── protoextract.py      # Pipeline output → SMB input adapter
│   │   └── usdm.py              # USDM JSON → Protocol + ExtractionInput + KEs
│   └── storage/                 # In-memory + Neo4j backends
├── trust/                       # Trust module (cell → row → protocol)
│   ├── models.py                # CellEvidence, RowTrust, ProtocolTrust
│   └── engine.py                # Confidence computation
├── domain/config/               # Domain YAML rules (oncology, vaccines, general)
├── models/                      # Pydantic data models
└── persistence/                 # Protocol storage (JSON + Neo4j)

api/main.py                      # FastAPI backend (58 endpoints)
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
# Full suite (916 tests)
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
