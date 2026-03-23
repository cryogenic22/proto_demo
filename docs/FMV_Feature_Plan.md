# FMV (Fair Market Value) Pricing Module — Tech Spec v2

## Context

Site budget calculations currently use cost tier estimates (LOW=$75, MEDIUM=$350, HIGH=$1,200, VERY_HIGH=$3,500). Real site budgets need Fair Market Value (FMV) rates — actual per-procedure costs that vary by country, region, site type, and therapeutic area. This feature lets clients maintain their own FMV benchmarks, import from GrantPlan/Medidata, and reduce dependency on IQVIA pricing.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│ FMV Data Sources                                         │
│                                                          │
│  CMS PFS 2026    GrantPlan    Manual Entry    IQVIA      │
│  (17K codes)     (CSV import) (UI editor)    (future)   │
│  + research      + P25/P50/   + per-site     + API      │
│    multiplier      P75 ranges   overrides               │
│        │              │            │              │      │
│        └──────────────┴────────────┴──────────────┘      │
│                        │                                  │
│              ┌─────────▼──────────┐                      │
│              │  FMV Rate Store    │                      │
│              │  CPT × region ×    │                      │
│              │  site_type × TA    │                      │
│              └─────────┬──────────┘                      │
│                        │                                  │
│         ┌──────────────┼──────────────┐                  │
│         ▼              ▼              ▼                  │
│   Budget Wizard   Rate Comparison  XLSX Export           │
│   (auto-fill +    (CMS vs Grant   (negotiation-         │
│    percentile     Plan vs custom)  ready format)         │
│    ranges)                                               │
└──────────────────────────────────────────────────────────┘
```

## Data Model (v2 — incorporating feedback)

### FMV Rate Entry
```python
@dataclass
class FMVRate:
    cpt_code: str = ""               # CPT/HCPCS code (can be empty for non-billable)
    canonical_name: str = ""         # For procedures without CPT codes
    region: str = "US"               # US, EU, UK, APAC, Global
    site_type: str = "any"           # academic, community, standalone, any
    therapeutic_area: str = "any"    # oncology, vaccines, cns, rare_disease, any
    rate_type: str = "medicare"      # medicare, commercial, fmv, custom, grant_plan

    # Percentile pricing (GrantPlan-style ranges)
    p25: float = 0.0                 # 25th percentile
    p50: float = 0.0                 # Median (primary display)
    p75: float = 0.0                 # 75th percentile
    unit_cost: float = 0.0           # Single rate when percentiles unavailable

    currency: str = "USD"
    source: str = ""                 # "CMS PFS 2026", "GrantPlan Q1 2026", "Site XYZ"
    effective_date: str = ""         # When this rate was set
    expiry_months: int = 24          # After which rate is flagged as stale
    inflation_rate: float = 0.04     # Annual inflation for aged rates

    confidence: str = "low"          # low (single source), medium (2), high (3+)
    sample_size: int = 0             # How many data points behind this rate
    notes: str = ""
```

### Key Design Decisions

1. **Lookup key is canonical_name OR cpt_code** — 116 procedures (22%) have no CPT, they still need FMV rates
2. **CMS rates × research multiplier** — raw Medicare rates are 50-75% below research costs. Multiplier configurable per category in domain YAML
3. **Percentile ranges** — P25/P50/P75 for negotiation (GrantPlan's value prop)
4. **Rate aging** — 24-month expiry + 4% annual inflation. Budget wizard warns on stale rates
5. **Batch lookup** — one API call for all procedures in a protocol
6. **Postgres migration in Phase 2** — JSON works for MVP, 17K rates × dimensions needs a proper DB

### Research Markup Multipliers (in domain YAML)
```yaml
fmv_settings:
  cms_research_multiplier:
    Laboratory: 2.0
    Imaging: 2.5
    Physical Examination: 1.5
    Procedure: 3.0
    Drug Administration: 2.0
    Cardiology: 2.0
    Biopsy: 3.0
    default: 2.0

  stale_rate_months: 24
  annual_inflation: 0.04
```

## Implementation Plan

### Phase 1: Backend — FMV Rate Store (TDD)

**New file: `src/domain/vocabulary/fmv_store.py`**

```python
class FMVStore:
    def get_rate(self, cpt_code=None, canonical_name=None,
                 region="US", site_type="any", therapeutic_area="any") -> FMVRate | None
    def set_rate(self, rate: FMVRate) -> None
    def list_rates(self, region="US", limit=100) -> list[FMVRate]
    def batch_lookup(self, queries: list[dict]) -> list[FMVRate | None]
    def import_csv(self, csv_content: str) -> ImportResult
    def import_cms_pfs(self, xlsx_path: Path, multipliers: dict) -> ImportResult
    def export_csv(self) -> str
    def check_stale_rates(self) -> list[FMVRate]
```

**Tests first: `tests/test_fmv_store.py` (14 tests)**
```
test_get_rate_by_cpt
test_get_rate_by_canonical_name
test_get_rate_most_specific_match
test_set_rate_persists
test_list_rates_by_region
test_batch_lookup_returns_array
test_import_csv_adds_new_rates
test_import_csv_updates_existing
test_import_csv_handles_duplicates
test_cms_import_applies_research_multiplier
test_stale_rate_detection
test_inflation_adjustment
test_export_csv_format
test_percentile_ranges
```

### Phase 2: CMS PFS 2026 Seed + Postgres Migration

- Import 8,729 CT-relevant codes from reference library Excel
- Apply research multipliers from domain YAML
- Seed to Railway volume
- **Begin Postgres migration** — 17K rates × site types × regions

### Phase 3: API Endpoints

```
GET  /api/fmv/rates?cpt=93000&region=US       — single lookup
POST /api/fmv/rates/batch                      — batch lookup
POST /api/fmv/rates                            — set/update rate
GET  /api/fmv/rates/export                     — CSV export
POST /api/fmv/rates/import                     — CSV import
GET  /api/fmv/rates/stats                      — coverage stats
GET  /api/fmv/rates/stale                      — aged rates
```

**Tests: `tests/test_fmv_endpoints.py` (6 tests)**

### Phase 4: Budget Wizard Integration (highest value)

- Batch lookup FMV rates for all procedures in protocol
- Show P25/P50/P75 range bar per procedure
- Show rate source + stale warnings
- Rate comparison: CMS vs GrantPlan vs custom
- User override always wins

### Phase 5: Negotiation Export

- Rate comparison table in Budget Wizard Step 3
- Total budget at P25/P50/P75
- Negotiation-ready XLSX with all columns

### Phase 6: XLSX Export Enhancement

- FMV P25/P50/P75 columns
- Rate Source + Stale flag columns
- Tier Estimate column (for comparison)
- Summary: FMV total vs tier total

## Files to Create/Modify

| File | Action | Phase |
|------|--------|-------|
| `src/domain/vocabulary/fmv_store.py` | CREATE | 1 |
| `src/domain/config/*.yaml` | MODIFY (add fmv_settings) | 1 |
| `tests/test_fmv_store.py` | CREATE | 1 |
| `data/fmv_rates.json` | CREATE | 2 |
| `api/main.py` | MODIFY | 3 |
| `tests/test_fmv_endpoints.py` | CREATE | 3 |
| `web/src/lib/api.ts` | MODIFY | 4 |
| `web/src/app/protocols/[protocolId]/budget-wizard/page.tsx` | MODIFY | 4-5 |

## Estimated Scope

- Backend: ~500 lines (store + endpoints + tests)
- Frontend: ~250 lines (budget wizard + rate comparison)
- Data: CMS PFS import + domain YAML
- Tests: ~100 lines (20 test cases)
- Total: ~850 lines across 6 phases
