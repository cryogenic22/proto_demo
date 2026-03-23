# Test Requirements — ProtoExtract

## Backend Tests (pytest)
- Location: `tests/`
- Framework: pytest + pytest-asyncio
- Coverage minimum: 40% (ratchet — only goes up)
- Async mode: auto

### Naming
- Files: `test_<feature>.py`
- Classes: `class Test<Feature>:`
- Methods: `def test_<scenario>(self):`

### Patterns
- Use `setup_method` for per-test setup
- Use `unittest.mock.patch()` for external dependencies
- Use `AsyncMock()` for async functions
- Use helper factories: `_make_page()`, `_cell()`, `_table()`
- Use `conftest.py` for shared fixtures

### Running
```bash
pytest tests/ -v                    # All tests
pytest tests/test_models.py -v      # Single file
pytest tests/ --cov=src             # With coverage
```

## Frontend Tests (vitest)
- Location: `web/src/__tests__/`
- Framework: vitest + @testing-library/react
- Config: `web/vitest.config.ts`

### Naming
- Files: `<feature>.test.tsx` or `<feature>.test.ts`

### Patterns
- Mock API calls with `vi.mock('@/lib/api')`
- Mock next/navigation with `vi.mock('next/navigation')`
- Use `render()`, `screen`, `fireEvent` from @testing-library

### Running
```bash
cd web && npx vitest run             # All tests
cd web && npx vitest run --reporter=verbose  # Verbose
```

## E2E Tests (Playwright)
- Location: `web/e2e/`
- Config: `web/playwright.config.ts`
- Base URL: https://protocolx.up.railway.app

```bash
cd web && npx playwright test --reporter=list
```

## TDD Discipline
1. Write test first (it should FAIL)
2. Implement the fix (minimal code)
3. Run test (it should PASS)
4. Run ALL tests (zero regressions)
5. Run Quality Gate
