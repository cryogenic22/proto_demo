# Commit Conventions — ProtoExtract

Use Conventional Commits format:

```
type(scope): description
```

## Types
- `feat` — New feature (new page, new endpoint, new component)
- `fix` — Bug fix (extraction accuracy, UI rendering, data issue)
- `refactor` — Code change that doesn't add features or fix bugs
- `docs` — Documentation only
- `test` — Test additions or fixes
- `chore` — Build, config, dependency changes
- `perf` — Performance improvement

## Scopes
- `pipeline` — Extraction pipeline (orchestrator, cell extractor, challenger)
- `soa-filter` — Non-SoA table rejection logic
- `section-parser` — Document structure parsing
- `verbatim` — Verbatim content extraction
- `budget` — Site budget calculation
- `procedures` — Procedure vocabulary / normalization
- `ui` — Frontend (Next.js pages, components)
- `api` — FastAPI endpoints
- `persistence` — Data storage (JSON store, protocol bridge)
- `domain` — Domain config (therapeutic area YAML)

## Examples
```
feat(budget): add XLSX export with formatted headers
fix(soa-filter): reject tables with >80% flagged cells
fix(ui): remove duplicate procedure column from SoA grid
refactor(persistence): add singleton pattern to KE store
test(pipeline): add section parser boundary tests
```

## Rules
- One commit per logical change
- Reference the feedback entry ID if applicable: `fix(ui): ... [FB-042]`
- Never force-push to main
- Co-author tag for Claude-assisted commits
