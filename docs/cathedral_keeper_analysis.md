# Cathedral Keeper Analysis — ProtoExtract Pipeline

## Run Summary

| Metric | Value |
|--------|-------|
| Files analyzed | 51 |
| Total findings | 68 |
| Blockers | 0 |
| High | 1 |
| Medium | 3 |
| Low | 64 |

**Verdict: No blockers, one architecture layer violation, three untested boundary interfaces.**

---

## Findings by Policy

| Policy | Count | Severity | Assessment |
|--------|-------|----------|------------|
| CK-ARCH-DEAD-MODULES | 25 | LOW | Most are entry points (CLI scripts, test files) — correctly not imported |
| CK-ARCH-TEST-ALIGNMENT | 21 | LOW/MEDIUM | Real gaps: 3 boundary interfaces lack dedicated tests |
| CK-ARCH-CONFIG-SPRAWL | 10 | LOW | Valid: env vars scattered across api/main.py instead of settings class |
| CK-ARCH-DEPENDENCY-HEALTH | 6 | LOW | Expected: pip dependencies vs requirements.txt alignment |
| CK-ARCH-ENV-PARITY | 5 | LOW | Valid: some env vars in code but not in .env.example |
| CK-ARCH-LAYER-DIRECTION | 1 | HIGH | Real: llm layer imports from models layer (upward dependency) |

---

## Critical Findings & Action Items

### HIGH: Layer Violation — `llm` imports from `models`

**Finding:** `src/llm/client.py` imports `src.models.schema.PipelineConfig`.

**Why CK flagged it:** In the layer hierarchy (api → pipeline → models → llm), the LLM layer is below models. Importing upward creates coupling between layers.

**Assessment:** This is a **legitimate architectural concern**. The LLM client depends on `PipelineConfig` for API keys, model names, and provider selection. If `PipelineConfig` changes, the LLM client breaks.

**Fix:** Extract an `LLMConfig` interface that the LLM layer owns, and have `PipelineConfig` extend or compose it. This inverts the dependency:
```
Before: llm/client.py → models/schema.py (upward)
After:  llm/config.py defines LLMConfig
        models/schema.py imports LLMConfig (downward)
        llm/client.py uses its own LLMConfig (same layer)
```

**Priority:** Medium — not causing bugs today, but will make the LLM layer harder to extract as a standalone package.

---

### MEDIUM: Untested Boundary Interfaces (3)

**Finding:** Three high-fan-in modules lack dedicated test files:

| Module | Imported By | Risk |
|--------|------------|------|
| `src/models/schema.py` | 36 modules | Change here breaks everything |
| `src/llm/client.py` | 8 modules | Provider switching logic is critical |
| `src/pipeline/section_parser.py` | 2 modules | New module, integration tests exist but no unit tests |

**Assessment:** `schema.py` is tested indirectly by `test_models.py` (35 tests). `client.py` is tested via pipeline integration tests. `section_parser.py` has 19 comprehensive tests. CK flagged these because the test files don't follow the naming convention exactly.

**Fix:** Create dedicated test files matching the module names:
- `tests/test_schema.py` (or rename `test_models.py` → `test_schema.py`)
- `tests/test_llm_client.py`
- Already have `tests/test_section_parser_comprehensive.py` — CK may not detect the non-standard name

**Priority:** Low — coverage exists, just naming/alignment.

---

### LOW: Config Sprawl (10 findings)

**Finding:** `api/main.py` has 10 direct `os.environ.get()` calls scattered across the file:
- `FRONTEND_URL`, `LLM_PROVIDER`, `LLM_MODEL`, `VISION_MODEL`
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `PORT`

**Assessment:** CK is correct — this is a real code smell. If someone asks "what environment variables does this service need?", you have to grep the entire file instead of looking at one settings class.

**Fix:** Create a `Settings` class:
```python
# api/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    port: int = 8000

    class Config:
        env_file = ".env"
```

**Priority:** Medium — improves maintainability and makes configuration auditable.

---

### LOW: Dead Modules (25 findings)

**Assessment:** Almost all are **false positives** — they're entry points or CLI scripts:
- `api/main.py` — FastAPI app (run by uvicorn, not imported)
- `golden_set/evaluate.py` — CLI script (run directly)
- `golden_set/synthetic/soa_generator.py` — CLI script
- Various `__init__.py` files
- Test files

**Fix:** Already added entry point patterns in config. CK correctly identified these as "never imported" — the pattern exclusions just need to cover all entry points.

**Priority:** None — these are correct dead module detections for non-imported scripts.

---

## What CK Found That Manual Review Would Miss

1. **The layer violation** — `llm` importing from `models` is the kind of dependency that accumulates silently. Today it's one import. In 6 months it's 5 imports and the LLM client can't be extracted.

2. **Config sprawl pattern** — 10 env vars scattered across one file. Each one was added individually during development (API key, then provider, then model override, then frontend URL). No single PR introduced "sprawl" — it accumulated.

3. **Test alignment gaps** — The test files exist but don't follow naming conventions. This means a CI script that checks "does every src/ module have a test?" would report false negatives.

---

## Feedback for Cathedral Keeper

Based on running CK on a real, rapidly-developed AI pipeline (51 files, 212 tests, built over 2 days), here are suggestions:

### What Works Well

1. **Dead module detection is useful** — even though many were false positives (entry points), the 3 genuine ones in the initial run (before config) were correct.

2. **Config sprawl detection is valuable** — it caught a real pattern that would have gotten worse over time.

3. **Layer direction is the highest-value check** — the one HIGH finding (llm → models) is a genuine architectural concern that no linter or test would catch.

4. **Evidence-first approach** — every finding has file:line + snippet. This makes triage fast.

### Suggestions for Improvement

1. **Entry point detection needs work.** CK flagged `api/main.py` as dead — but it contains a FastAPI `app` object and an `if __name__ == "__main__"` block. Both are strong entry point signals that CK should auto-detect. The `entry_point_patterns` config helps but requires manual setup.

   **Suggestion:** Auto-detect entry points by looking for:
   - `if __name__ == "__main__":`
   - FastAPI/Flask/Django `app` objects
   - `click.command()` / `argparse` patterns
   - Files named `main.py`, `cli.py`, `app.py`, `manage.py`

2. **Test alignment should support naming variants.** Our test for `section_parser.py` is named `test_section_parser_comprehensive.py`. CK expects `test_section_parser.py`. Support `test_<module>*.py` glob patterns.

3. **Async-blocking detection would be valuable.** Our pipeline mixes sync and async code — `ProcedureNormalizer` is sync but called from an async pipeline. CK could detect `sync_function()` called inside `async def` without `run_in_executor`.

4. **Import-time side effects detection.** Our `procedure_normalizer.py` loads a CSV at import time (inside `_load_vocabulary`). This is fine for a CLI tool but bad for serverless/Lambda. CK could flag modules that do I/O at import time.

5. **Circular dependency POTENTIAL detection.** We don't have cycles today, but `orchestrator.py` imports 15 pipeline modules. If any of those modules ever imports orchestrator (e.g., for a callback), we'd have a cycle. CK could warn about "near-cycle" modules with high mutual fan-in.

6. **AI-assisted coding patterns.** Since CK is designed for repos with AI coding:
   - Detect when an AI added a new `os.environ.get()` instead of using the existing Settings class
   - Detect when a new module was added without a corresponding test file
   - Detect when a new dependency was imported but not added to requirements.txt

7. **Pydantic model validation.** Our codebase uses Pydantic v2 extensively. CK could detect:
   - Models that shadow `BaseModel.schema` (we renamed ours to `schema_info`)
   - Fields without type annotations
   - Models used as dict keys without `frozen=True` (we had this bug with CellRef)

---

*Analysis run: Cathedral Keeper on ProtoExtract (51 files, 212 tests).
Zero import cycles. One layer violation. Three untested boundaries.
Ten config sprawl instances. 25 dead module false positives (entry points).*
