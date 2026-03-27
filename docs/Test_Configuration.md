# Test Configuration — ProtoExtract

Recommended settings for the testing team before running protocol extractions.

## Recommended Test Config

| Setting        | Value                                        | Notes                                      |
|---------------|----------------------------------------------|---------------------------------------------|
| Preset         | `thorough`                                   | Enables dual-pass + consensus (3-way vote)  |
| Header mode    | `TreeThinker`                                | Automatic when multi-level headers detected |
| Stitcher       | Content-continuity scoring                   | Default — no config needed                  |
| Confidence     | 0.85 (standard), 0.95 (high-cost procedures) | Pipeline defaults                          |

## Environment Variables

```bash
EXTRACTION_PRESET=thorough
```

Setting the preset to `thorough` activates:
- Dual-pass extraction (two independent LLM passes)
- Challenger agent (cross-checks extracted values against source)
- 3-way consensus voting (pass3 runs only when passes 1+2 disagree)
- Superscript normalization in consensus (X, X4, Xa treated as same base marker)

## Running the Test Suite

### Backend (pytest)

```bash
# Full suite (excluding slow integration tests)
python -m pytest tests/ --ignore=tests/test_orchestrator.py --ignore=tests/test_pdf_ingestion.py --ignore=tests/test_table_detection.py --ignore=tests/test_ocr_grounding.py -q

# With coverage
python -m pytest tests/ --cov=src -q

# Single file
python -m pytest tests/test_consensus.py -v
```

### Validation

Header tree and stitcher validation are covered by the test suite:
```bash
python -m pytest tests/test_header_tree.py tests/test_stitcher_continuity.py -v
```

### Frontend (vitest)

```bash
cd web && npx vitest run --reporter=verbose
```

### E2E (Playwright)

```bash
cd web && npx playwright test --reporter=list
```

## Procedure Exclusions

Exclusion logic uses two layers:
1. **Exact exclusions** (`_EXACT_EXCLUSIONS`): Match the full lowercased label. "monitoring" excludes standalone "Monitoring" but NOT "AE Monitoring".
2. **Pattern exclusions** (`data/procedure_exclusions.json`): Substring match. "efficacy assessment" excludes any label containing that phrase.

To add new exclusions, edit `data/procedure_exclusions.json` (no code change needed).

## Known Stored Protocols

| Protocol ID                | Tables | Multi-page | Notes                            |
|---------------------------|--------|------------|-----------------------------------|
| pfizer_bnt162             | 1      | Yes (2pp)  | Vaccine, flat headers             |
| p14                       | 10     | Yes        | Complex multi-level headers       |
| p_14_690eb522             | 9      | Yes        | Variant of P-14                   |
| p09                       | 1      | Yes (2pp)  | Standard SoA                      |
| p01_brivaracetam          | 2      | Yes (4pp)  | Epilepsy, two distinct SoA tables |
| p17_durvalumab            | 1      | Yes (2pp)  | Missing headers (needs re-extract)|
| p17_durvalumab_bb172274   | 2      | Yes        | Oncology                          |
| p08                       | 2      | Yes        | Missing headers (needs re-extract)|
| prot_0001_1_3a3bae33      | 4      | Yes        | Large protocol, 10+ page SoA      |
