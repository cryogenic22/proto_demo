# Cathedral Keeper Report

- Root: `C:/Users/kapil/Documents/Proto_Demo`
- Created: `2026-03-20T18:28:42.649656`
- Findings: `68`

## Summary

- Blockers: `0`
- High: `1`
- Medium: `3`
- Low: `64`

## Top Findings

### 1. HIGH (high) - Layer violation: llm → models
- Policy: `CK-ARCH-LAYER-DIRECTION`
- Why: Layer 'llm' imports from 'models' which is above it in the architecture.  Upward imports collapse layer separation and create hidden coupling.
- Evidence: `src/llm/client.py:18` - import src.models.schema
- Fix: Move the shared code to a lower layer or create an interface in 'models'.
- Verify: `python -m compileall -q src/llm/client.py`

### 2. MEDIUM (medium) - Untested boundary interface: src/models/schema.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: 'src/models/schema.py' is imported by 36 modules across different directories, making it a boundary interface. Boundary modules are higher-risk and should have dedicated test coverage.
- Evidence: `src/models/schema.py:1` - Imported across 36 directory boundaries
- Fix: Create test_schema.py with tests for this interface.
- Verify: `grep -rn 'import.*schema' --include='*.py' .`

### 3. MEDIUM (medium) - Untested boundary interface: src/llm/client.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: 'src/llm/client.py' is imported by 8 modules across different directories, making it a boundary interface. Boundary modules are higher-risk and should have dedicated test coverage.
- Evidence: `src/llm/client.py:1` - Imported across 8 directory boundaries
- Fix: Create test_client.py with tests for this interface.
- Verify: `grep -rn 'import.*client' --include='*.py' .`

### 4. MEDIUM (medium) - Untested boundary interface: src/pipeline/section_parser.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: 'src/pipeline/section_parser.py' is imported by 2 modules across different directories, making it a boundary interface. Boundary modules are higher-risk and should have dedicated test coverage.
- Evidence: `src/pipeline/section_parser.py:1` - Imported across 2 directory boundaries
- Fix: Create test_section_parser.py with tests for this interface.
- Verify: `grep -rn 'import.*section_parser' --include='*.py' .`

### 5. LOW (high) - Direct env access: FRONTEND_URL in api/main.py
- Policy: `CK-ARCH-CONFIG-SPRAWL`
- Why: 'FRONTEND_URL' is accessed via os.environ/os.getenv directly in application code instead of through a settings class. Scattered env access makes it impossible to know what configuration a service actually needs.
- Evidence: `api/main.py:46` - os.environ/getenv("FRONTEND_URL")
- Fix: Move this access into a centralised settings/config module.
- Verify: `grep -n 'FRONTEND_URL' api/main.py`

### 6. LOW (high) - Direct env access: LLM_PROVIDER in api/main.py
- Policy: `CK-ARCH-CONFIG-SPRAWL`
- Why: 'LLM_PROVIDER' is accessed via os.environ/os.getenv directly in application code instead of through a settings class. Scattered env access makes it impossible to know what configuration a service actually needs.
- Evidence: `api/main.py:131` - os.environ/getenv("LLM_PROVIDER")
- Fix: Move this access into a centralised settings/config module.
- Verify: `grep -n 'LLM_PROVIDER' api/main.py`

### 7. LOW (high) - Direct env access: ANTHROPIC_API_KEY in api/main.py
- Policy: `CK-ARCH-CONFIG-SPRAWL`
- Why: 'ANTHROPIC_API_KEY' is accessed via os.environ/os.getenv directly in application code instead of through a settings class. Scattered env access makes it impossible to know what configuration a service actually needs.
- Evidence: `api/main.py:132` - os.environ/getenv("ANTHROPIC_API_KEY")
- Fix: Move this access into a centralised settings/config module.
- Verify: `grep -n 'ANTHROPIC_API_KEY' api/main.py`

### 8. LOW (high) - Direct env access: OPENAI_API_KEY in api/main.py
- Policy: `CK-ARCH-CONFIG-SPRAWL`
- Why: 'OPENAI_API_KEY' is accessed via os.environ/os.getenv directly in application code instead of through a settings class. Scattered env access makes it impossible to know what configuration a service actually needs.
- Evidence: `api/main.py:133` - os.environ/getenv("OPENAI_API_KEY")
- Fix: Move this access into a centralised settings/config module.
- Verify: `grep -n 'OPENAI_API_KEY' api/main.py`

### 9. LOW (high) - Direct env access: LLM_PROVIDER in api/main.py
- Policy: `CK-ARCH-CONFIG-SPRAWL`
- Why: 'LLM_PROVIDER' is accessed via os.environ/os.getenv directly in application code instead of through a settings class. Scattered env access makes it impossible to know what configuration a service actually needs.
- Evidence: `api/main.py:326` - os.environ/getenv("LLM_PROVIDER")
- Fix: Move this access into a centralised settings/config module.
- Verify: `grep -n 'LLM_PROVIDER' api/main.py`

### 10. LOW (high) - Direct env access: LLM_MODEL in api/main.py
- Policy: `CK-ARCH-CONFIG-SPRAWL`
- Why: 'LLM_MODEL' is accessed via os.environ/os.getenv directly in application code instead of through a settings class. Scattered env access makes it impossible to know what configuration a service actually needs.
- Evidence: `api/main.py:327` - os.environ/getenv("LLM_MODEL")
- Fix: Move this access into a centralised settings/config module.
- Verify: `grep -n 'LLM_MODEL' api/main.py`

### 11. LOW (high) - Direct env access: VISION_MODEL in api/main.py
- Policy: `CK-ARCH-CONFIG-SPRAWL`
- Why: 'VISION_MODEL' is accessed via os.environ/os.getenv directly in application code instead of through a settings class. Scattered env access makes it impossible to know what configuration a service actually needs.
- Evidence: `api/main.py:328` - os.environ/getenv("VISION_MODEL")
- Fix: Move this access into a centralised settings/config module.
- Verify: `grep -n 'VISION_MODEL' api/main.py`

### 12. LOW (high) - Direct env access: ANTHROPIC_API_KEY in api/main.py
- Policy: `CK-ARCH-CONFIG-SPRAWL`
- Why: 'ANTHROPIC_API_KEY' is accessed via os.environ/os.getenv directly in application code instead of through a settings class. Scattered env access makes it impossible to know what configuration a service actually needs.
- Evidence: `api/main.py:329` - os.environ/getenv("ANTHROPIC_API_KEY")
- Fix: Move this access into a centralised settings/config module.
- Verify: `grep -n 'ANTHROPIC_API_KEY' api/main.py`

### 13. LOW (high) - Direct env access: OPENAI_API_KEY in api/main.py
- Policy: `CK-ARCH-CONFIG-SPRAWL`
- Why: 'OPENAI_API_KEY' is accessed via os.environ/os.getenv directly in application code instead of through a settings class. Scattered env access makes it impossible to know what configuration a service actually needs.
- Evidence: `api/main.py:330` - os.environ/getenv("OPENAI_API_KEY")
- Fix: Move this access into a centralised settings/config module.
- Verify: `grep -n 'OPENAI_API_KEY' api/main.py`

### 14. LOW (high) - Direct env access: PORT in api/main.py
- Policy: `CK-ARCH-CONFIG-SPRAWL`
- Why: 'PORT' is accessed via os.environ/os.getenv directly in application code instead of through a settings class. Scattered env access makes it impossible to know what configuration a service actually needs.
- Evidence: `api/main.py:388` - os.environ/getenv("PORT")
- Fix: Move this access into a centralised settings/config module.
- Verify: `grep -n 'PORT' api/main.py`

### 15. LOW (medium) - Dead module: api/__init__.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `api/__init__.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*__init__' --include='*.py' .`

### 16. LOW (medium) - Dead module: api/main.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `api/main.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*main' --include='*.py' .`

### 17. LOW (medium) - Dead module: golden_set/__init__.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `golden_set/__init__.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*__init__' --include='*.py' .`

### 18. LOW (medium) - Dead module: golden_set/evaluate.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `golden_set/evaluate.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*evaluate' --include='*.py' .`

### 19. LOW (medium) - Dead module: golden_set/synthetic/soa_generator.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `golden_set/synthetic/soa_generator.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*soa_generator' --include='*.py' .`

### 20. LOW (medium) - Dead module: src/__init__.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `src/__init__.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*__init__' --include='*.py' .`

### 21. LOW (medium) - Dead module: src/domain/__init__.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `src/domain/__init__.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*__init__' --include='*.py' .`

### 22. LOW (medium) - Dead module: src/llm/__init__.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `src/llm/__init__.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*__init__' --include='*.py' .`

### 23. LOW (medium) - Dead module: src/models/__init__.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `src/models/__init__.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*__init__' --include='*.py' .`

### 24. LOW (medium) - Dead module: src/pipeline/__init__.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `src/pipeline/__init__.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*__init__' --include='*.py' .`

### 25. LOW (medium) - Dead module: tests/__init__.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/__init__.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*__init__' --include='*.py' .`

### 26. LOW (medium) - Dead module: tests/test_clinical_domain.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_clinical_domain.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_clinical_domain' --include='*.py' .`

### 27. LOW (medium) - Dead module: tests/test_footnote_resolver.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_footnote_resolver.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_footnote_resolver' --include='*.py' .`

### 28. LOW (medium) - Dead module: tests/test_models.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_models.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_models' --include='*.py' .`

### 29. LOW (medium) - Dead module: tests/test_ocr_grounding.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_ocr_grounding.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_ocr_grounding' --include='*.py' .`

### 30. LOW (medium) - Dead module: tests/test_orchestrator.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_orchestrator.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_orchestrator' --include='*.py' .`

### 31. LOW (medium) - Dead module: tests/test_output_validator.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_output_validator.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_output_validator' --include='*.py' .`

### 32. LOW (medium) - Dead module: tests/test_pdf_ingestion.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_pdf_ingestion.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_pdf_ingestion' --include='*.py' .`

### 33. LOW (medium) - Dead module: tests/test_procedure_normalizer.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_procedure_normalizer.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_procedure_normalizer' --include='*.py' .`

### 34. LOW (medium) - Dead module: tests/test_reconciler.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_reconciler.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_reconciler' --include='*.py' .`

### 35. LOW (medium) - Dead module: tests/test_regression_content.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_regression_content.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_regression_content' --include='*.py' .`

### 36. LOW (medium) - Dead module: tests/test_section_parser_comprehensive.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_section_parser_comprehensive.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_section_parser_comprehensive' --include='*.py' .`

### 37. LOW (medium) - Dead module: tests/test_table_detection.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_table_detection.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_table_detection' --include='*.py' .`

### 38. LOW (medium) - Dead module: tests/test_table_stitcher.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_table_stitcher.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_table_stitcher' --include='*.py' .`

### 39. LOW (medium) - Dead module: tests/test_temporal_extractor.py
- Policy: `CK-ARCH-DEAD-MODULES`
- Why: This file is never imported by any other module and doesn't match known entry-point patterns.  Dead modules confuse developers, mislead AI tools, and increase maintenance burden.
- Evidence: `tests/test_temporal_extractor.py:1` - (no incoming imports)
- Fix: Delete the file if it is genuinely unused.
- Verify: `grep -r 'import.*test_temporal_extractor' --include='*.py' .`

### 40. LOW (medium) - Missing test file for: api/main.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: Source module 'api/main.py' has no corresponding test file. Gaps in test architecture tend to cluster at the exact points where bugs are most expensive.
- Evidence: `api/main.py:1` - Expected: test_main.py
- Fix: Create a test file: test_main.py
- Verify: `find . -name 'test_main.py'`

### 41. LOW (medium) - Missing test file for: golden_set/evaluate.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: Source module 'golden_set/evaluate.py' has no corresponding test file. Gaps in test architecture tend to cluster at the exact points where bugs are most expensive.
- Evidence: `golden_set/evaluate.py:1` - Expected: test_evaluate.py
- Fix: Create a test file: test_evaluate.py
- Verify: `find . -name 'test_evaluate.py'`

### 42. LOW (medium) - Missing test file for: src/domain/procedures.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: Source module 'src/domain/procedures.py' has no corresponding test file. Gaps in test architecture tend to cluster at the exact points where bugs are most expensive.
- Evidence: `src/domain/procedures.py:1` - Expected: test_procedures.py
- Fix: Create a test file: test_procedures.py
- Verify: `find . -name 'test_procedures.py'`

### 43. LOW (medium) - Missing test file for: src/domain/sme_corrections.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: Source module 'src/domain/sme_corrections.py' has no corresponding test file. Gaps in test architecture tend to cluster at the exact points where bugs are most expensive.
- Evidence: `src/domain/sme_corrections.py:1` - Expected: test_sme_corrections.py
- Fix: Create a test file: test_sme_corrections.py
- Verify: `find . -name 'test_sme_corrections.py'`

### 44. LOW (medium) - Missing test file for: src/llm/client.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: Source module 'src/llm/client.py' has no corresponding test file. Gaps in test architecture tend to cluster at the exact points where bugs are most expensive.
- Evidence: `src/llm/client.py:1` - Expected: test_client.py
- Fix: Create a test file: test_client.py
- Verify: `find . -name 'test_client.py'`

### 45. LOW (medium) - Missing test file for: src/models/schema.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: Source module 'src/models/schema.py' has no corresponding test file. Gaps in test architecture tend to cluster at the exact points where bugs are most expensive.
- Evidence: `src/models/schema.py:1` - Expected: test_schema.py
- Fix: Create a test file: test_schema.py
- Verify: `find . -name 'test_schema.py'`

### 46. LOW (medium) - Missing test file for: src/pipeline/budget_calculator.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: Source module 'src/pipeline/budget_calculator.py' has no corresponding test file. Gaps in test architecture tend to cluster at the exact points where bugs are most expensive.
- Evidence: `src/pipeline/budget_calculator.py:1` - Expected: test_budget_calculator.py
- Fix: Create a test file: test_budget_calculator.py
- Verify: `find . -name 'test_budget_calculator.py'`

### 47. LOW (medium) - Missing test file for: src/pipeline/cell_extractor.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: Source module 'src/pipeline/cell_extractor.py' has no corresponding test file. Gaps in test architecture tend to cluster at the exact points where bugs are most expensive.
- Evidence: `src/pipeline/cell_extractor.py:1` - Expected: test_cell_extractor.py
- Fix: Create a test file: test_cell_extractor.py
- Verify: `find . -name 'test_cell_extractor.py'`

### 48. LOW (medium) - Missing test file for: src/pipeline/challenger_agent.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: Source module 'src/pipeline/challenger_agent.py' has no corresponding test file. Gaps in test architecture tend to cluster at the exact points where bugs are most expensive.
- Evidence: `src/pipeline/challenger_agent.py:1` - Expected: test_challenger_agent.py
- Fix: Create a test file: test_challenger_agent.py
- Verify: `find . -name 'test_challenger_agent.py'`

### 49. LOW (medium) - Missing test file for: src/pipeline/footnote_extractor.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: Source module 'src/pipeline/footnote_extractor.py' has no corresponding test file. Gaps in test architecture tend to cluster at the exact points where bugs are most expensive.
- Evidence: `src/pipeline/footnote_extractor.py:1` - Expected: test_footnote_extractor.py
- Fix: Create a test file: test_footnote_extractor.py
- Verify: `find . -name 'test_footnote_extractor.py'`

### 50. LOW (medium) - Missing test file for: src/pipeline/html_report.py
- Policy: `CK-ARCH-TEST-ALIGNMENT`
- Why: Source module 'src/pipeline/html_report.py' has no corresponding test file. Gaps in test architecture tend to cluster at the exact points where bugs are most expensive.
- Evidence: `src/pipeline/html_report.py:1` - Expected: test_html_report.py
- Fix: Create a test file: test_html_report.py
- Verify: `find . -name 'test_html_report.py'`

## Hotspots (Files)

- `api/main.py` - `18` findings
- `src/llm/client.py` - `3` findings
- `golden_set/evaluate.py` - `3` findings
- `src/pipeline/section_parser.py` - `3` findings
- `golden_set/synthetic/soa_generator.py` - `2` findings
- `src/domain/__init__.py` - `2` findings
- `tests/test_clinical_domain.py` - `2` findings
- `tests/test_footnote_resolver.py` - `2` findings
- `tests/test_models.py` - `2` findings
- `src/models/schema.py` - `2` findings
- `src/pipeline/verbatim_extractor.py` - `2` findings
- `requirements.txt` - `2` findings
- `api/__init__.py` - `1` findings
- `golden_set/__init__.py` - `1` findings
- `src/__init__.py` - `1` findings
- `src/llm/__init__.py` - `1` findings
- `src/models/__init__.py` - `1` findings
- `src/pipeline/__init__.py` - `1` findings
- `tests/__init__.py` - `1` findings
- `tests/test_ocr_grounding.py` - `1` findings
- `tests/test_orchestrator.py` - `1` findings
- `tests/test_output_validator.py` - `1` findings
- `tests/test_pdf_ingestion.py` - `1` findings
- `tests/test_procedure_normalizer.py` - `1` findings
- `tests/test_reconciler.py` - `1` findings
- `tests/test_regression_content.py` - `1` findings
- `tests/test_section_parser_comprehensive.py` - `1` findings
- `tests/test_table_detection.py` - `1` findings
- `tests/test_table_stitcher.py` - `1` findings
- `tests/test_temporal_extractor.py` - `1` findings

## Policy Breakdown

- `CK-ARCH-DEAD-MODULES` - `25`
- `CK-ARCH-TEST-ALIGNMENT` - `21`
- `CK-ARCH-CONFIG-SPRAWL` - `10`
- `CK-ARCH-DEPENDENCY-HEALTH` - `6`
- `CK-ARCH-ENV-PARITY` - `5`
- `CK-ARCH-LAYER-DIRECTION` - `1`
