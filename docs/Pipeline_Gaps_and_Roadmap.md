# Pipeline Gaps & Roadmap — From Technical Review

**Date:** 2026-03-23 | **Source:** Technical review of ProtoExtract_Technical_Report.md

---

## Critical Corrections to Technical Report

### 1. Accuracy Claim Context
**Current:** "99.1% cell extraction accuracy (13-protocol benchmark)"
**Should be:** "99.1% cell accuracy on matched cells after SoA filtering. Prior to the 5-layer filter, production correction rate was 29.7% due to noise table contamination."

### 2. Grid Anchoring Recommendation
**Current:** "Disabled by default"
**Should be:** "Enable by default, fall back to standard extraction if grid detection fails"
- Grid Anchoring achieved 100% procedure match in v4
- When disabled in v5, row numbering broke and correction rate spiked
- Works well on clean PDF text layers; breaks on image-rendered pages

### 3. Cost Tier Disclosure
**Current:** Presents tiers as the costing model
**Should be:** "Cost tiers are the current fallback. FMV Rate Store (spec complete) will replace with per-procedure Medicare-derived rates. GrantPlan import is the target for production FMV data."

---

## P0 — Must Fix (blocks oncology accuracy)

### Gap 1: Oncology Cycle Counting Model
**Impact:** 60-80% budget underestimation for cycle-based protocols
**Problem:** Pipeline counts visible X-marks. Oncology SoA shows 3-4 representative cycles, not full treatment. A protocol with 13 median cycles shows 4 X-marks → budget is 3x too low.

**Fix:**
- Detect cycle-based column headers (C1D1 pattern) in Stage 2
- Parse cycle length from headers (Q3W = 21 days) in Stage 8
- New Stage 8b: Cycle Model Inference — read protocol text for treatment duration, cycle caps, phase transitions
- Budget Calculator: multiply X-marks by expected cycle count

**Domain YAML additions:**
```yaml
cycle_model:
  type: "cycle_based"
  cycle_length_days: 21
  treatment_phases:
    induction: { cycles: 4 }
    maintenance: { type: "treat_to_progression", expected_cycles: { p25: 6, p50: 9, p75: 14 } }
  procedure_frequency_overrides:
    "CT Scan": "every_2_cycles"
    "Drug Administration": "every_cycle"
```

**Effort:** ~3 days

### Gap 2: FREQUENCY_MODIFIER Footnote Type
**Impact:** 15-20% of footnotes mishandled, ~$495/patient cost difference
**Problem:** "CBC Day 1 and Day 8 of Cycles 1-2, then Day 1 only" → without parsing: 26 CBCs; with parsing: 15 CBCs

**Fix:**
- Add FREQUENCY_MODIFIER to footnote classification
- Regex patterns for frequency modifier detection
- Budget calculator accepts `visits_formula` not just flat count

```yaml
frequency_modifier_patterns:
  - pattern: "Day 1 and Day \\d+ of Cycle[s]? (\\d+)[-–](\\d+) only"
    action: "split_by_cycle_range"
  - pattern: "every (\\d+) (?:cycles?|visits?)"
    action: "divide_frequency"
  - pattern: "(?:first|initial) (\\d+) cycles? only"
    action: "cap_at_cycle"
```

**Effort:** ~2 days

---

## P1 — High Priority (budget accuracy)

### Gap 3: SUBSET Footnote Type
**Impact:** Patient count wrong for subset procedures
**Example:** "Immunogenicity samples in reactogenicity subset (1,000 of 4,000)" → $1.8M cost difference

**Fix:** Add `patient_fraction` field to BudgetLine. Parse subset ratios from footnote text.

**Effort:** ~1 day

### Gap 4: OPTIONAL Footnote Type (distinct from CONDITIONAL)
**Impact:** Over-budgeting optional procedures
**Fix:** OPTIONAL → budget at 30% probability. CONDITIONAL → 50-70% probability. Separate from current CONDITIONAL catch-all.

**Effort:** ~1 day

### Gap 5: Screen Failure + Early Discontinuation Rates
**Impact:** Missing cost components
**Fix:** Add to domain YAML defaults:
```yaml
screen_failure_rates:
  oncology: 0.45
  vaccines: 0.20
  cns: 0.35
  default: 0.30

early_discontinuation_rates:
  oncology_immuno: 0.25
  oncology_chemo: 0.35
  vaccines: 0.05
  default: 0.20

footnote_probabilities:
  CONDITIONAL: 0.60
  OPTIONAL: 0.30
  SUBSET: null  # Extracted from footnote
  DISCONTINUED_EARLY: 0.25
```

**Effort:** ~0.5 day

### Gap 6: Reconciler Threshold Validation
**Impact:** Thresholds are design targets, not empirically validated
**Fix:** Run reconciler on 13 GT protocols, plot false-positive rate vs threshold per cost tier, set thresholds from ROC curve.

**Effort:** ~1 day

---

## P2 — Important (completeness)

### Gap 7: Multi-Arm Budget Separation
**Impact:** Combined budget hides per-arm differences
**Fix:** Add `arm` field to BudgetLine, `visits_by_arm` dict. Budget wizard toggle: "All arms" / "Per-arm breakdown."

**Effort:** ~2 days

### Gap 8: TIMING_WINDOW + DISCONTINUED_EARLY Footnotes
**Impact:** Site burden underestimation
**Fix:** Parse timing constraints, flag tight windows. Budget early termination at discontinuation rate.

**Effort:** ~1 day

### Gap 9: Table-Level Error Isolation
**Impact:** One failed table kills entire extraction
**Fix:** Per-table try/catch with graceful degradation. Show successful tables, flag failed ones. Already partially implemented (checkpoint system) but not fully exposed in UI.

**Effort:** ~1 day

---

## P3 — Strategic (infrastructure)

### Gap 10: Railway Volume Backup
**Impact:** Single point of failure for all data
**Fix:** Scheduled export of protocols + annotations + vocabulary to S3 or equivalent.

**Effort:** ~1 day

### Gap 11: Integration Test Suite (13-Protocol Benchmark)
**Impact:** Can't measure accuracy impact of pipeline changes
**Fix:** CI pipeline that uploads known protocols, asserts extraction matches GT ± tolerance.

**Effort:** ~2 days

### Gap 12: Domain YAML Architecture (_defaults.yaml + per-TA overrides)
**Impact:** Only 3 configs exist, need comprehensive hierarchy
**Fix:** Create `_defaults.yaml` + TA-specific overrides + sponsor overrides. Extend configs for chemoradiation, immunotherapy, TKI regimens.

**Effort:** ~2 days

### Gap 13: Grid Anchoring Auto-Enable
**Impact:** Accuracy gain on clean PDFs left on the table
**Fix:** Enable by default, auto-detect clean text layer, fall back if grid detection fails.

**Effort:** ~1 day

---

## Extended Footnote Classification (Complete)

| Type | % of Footnotes | Budget Impact | Implementation |
|------|---------------|---------------|----------------|
| CONDITIONAL | ~30% | Reduces firm visits → cost range | Probability × cost (current: 60%) |
| FREQUENCY_MODIFIER | ~15% | Changes per-cycle count | Parse formula, adjust multiplier |
| EXCEPTION | ~10% | Excludes visits | Remove from budget |
| SUBSET | ~10% | Reduces patient denominator | Apply patient_fraction |
| OPTIONAL | ~10% | Budget at reduced probability | 30% probability |
| TIMING_WINDOW | ~10% | Scheduling, not direct cost | Flag for site burden |
| REFERENCE | ~10% | Informational | No cost impact |
| CLARIFICATION | ~5% | Informational | No cost impact |
| DISCONTINUED_EARLY | — | Early termination procedures | 25% discontinuation rate |

---

## New Domain YAMLs Needed

| File | Protocol/TA | Key Addition |
|------|-------------|-------------|
| `_defaults.yaml` | All | Cycle defaults, footnote probabilities, screen failure rates |
| `oncology_chemoradiation.yaml` | Durvalumab-type | Phased model (CRT + consolidation) |
| `oncology_immunotherapy.yaml` | Pembrolizumab-type | Treat-to-progression + irAE monitoring |
| `oncology_chemo.yaml` | Fixed-cycle chemo | 4-8 cycle models |
| `oncology_tki.yaml` | Oral TKI | Continuous until progression |

---

## Priority Summary

| Priority | Items | Total Effort |
|----------|-------|-------------|
| **P0** | Cycle counting + FREQUENCY_MODIFIER | ~5 days |
| **P1** | SUBSET + OPTIONAL + screen failure + threshold validation | ~3.5 days |
| **P2** | Multi-arm + TIMING_WINDOW + error isolation | ~4 days |
| **P3** | Backup + integration tests + domain YAML + grid anchor | ~6 days |
| **Total** | 13 gaps | ~18.5 days |
