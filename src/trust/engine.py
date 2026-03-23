"""
Trust Computation Engine — pure functions for computing trust scores.

No I/O, no LLM calls. Takes evidence data in, returns scores out.
Any pipeline can use these functions regardless of document type.
"""

from __future__ import annotations

from src.trust.models import (
    CellEvidence,
    ProtocolTrust,
    RowTrust,
    VerificationStep,
)

# ── Default weights (overridable via domain YAML) ────────────────────────

DEFAULT_WEIGHTS = {
    "dual_pass_agreement": 0.35,
    "ocr_grounding": 0.20,
    "challenger_clear": 0.20,
    "procedure_mapping": 0.15,
    "footnote_resolution": 0.10,
}

DEFAULT_THRESHOLDS = {
    "high": 0.90,
    "medium": 0.75,
}

REVIEW_MINUTES_PER_FLAGGED_CELL = 0.5
REVIEW_MINUTES_PER_UNMAPPED_PROCEDURE = 2.0


# ── Cell-level trust ─────────────────────────────────────────────────────

def compute_cell_trust(evidence: CellEvidence) -> float:
    """Compute final confidence from an evidence chain.

    Returns a score between 0 and 1.
    """
    # Manual override = full confidence
    if evidence.resolution_method == "manual":
        return 1.0

    score = 0.0
    weight_total = 0.0

    # 1. Dual-pass agreement (weight: 0.35)
    w = DEFAULT_WEIGHTS["dual_pass_agreement"]
    if evidence.pass2_value is not None:
        if evidence.passes_agree:
            score += w * 1.0
        else:
            score += w * 0.30  # Significant penalty for disagreement
        weight_total += w
    else:
        # Single pass — moderate baseline
        score += w * 0.65
        weight_total += w

    # 2. OCR grounding (weight: 0.20)
    w = DEFAULT_WEIGHTS["ocr_grounding"]
    if evidence.ocr_grounded is not None:
        score += w * (1.0 if evidence.ocr_grounded else 0.40)
        weight_total += w
    # If OCR not available, redistribute weight to other factors

    # 3. Challenger (weight: 0.20)
    w = DEFAULT_WEIGHTS["challenger_clear"]
    if evidence.challenger_issues:
        max_severity = max(
            (i.get("severity", 0.5) for i in evidence.challenger_issues),
            default=0.0,
        )
        score += w * (1.0 - max_severity)
    else:
        score += w * 1.0
    weight_total += w

    # Normalize if some checks were skipped (redistribute weight)
    if weight_total > 0:
        return min(1.0, max(0.0, score / weight_total))
    return 0.5  # No evidence at all


def build_cell_evidence(
    pass1_value: str = "",
    pass1_conf: float = 1.0,
    pass2_value: str | None = None,
    pass2_conf: float | None = None,
    ocr_value: str | None = None,
    ocr_grounded: bool | None = None,
    challenger_issues: list[dict] | None = None,
) -> CellEvidence:
    """Build a CellEvidence from pipeline stage results.

    This is the bridge function called by the reconciler/orchestrator
    to construct evidence from raw stage outputs.
    """
    steps: list[VerificationStep] = []

    # Dual-pass check
    if pass2_value is not None:
        agrees = pass1_value.strip().lower() == pass2_value.strip().lower()
        steps.append(VerificationStep(
            method="DUAL_PASS",
            status="PASS" if agrees else "FAIL",
            detail=(
                f"Both passes agree: '{pass1_value}'"
                if agrees
                else f"Disagreement: pass1='{pass1_value}' vs pass2='{pass2_value}'"
            ),
            value=pass2_value,
            confidence=0.95 if agrees else 0.50,
        ))
        resolution = "both_agree" if agrees else "pass1_preferred"
    else:
        steps.append(VerificationStep(
            method="DUAL_PASS",
            status="SKIPPED",
            detail="Single-pass mode — no second extraction",
            confidence=0.70,
        ))
        resolution = "single_pass"

    # OCR grounding
    if ocr_grounded is not None:
        steps.append(VerificationStep(
            method="OCR_GROUNDING",
            status="PASS" if ocr_grounded else "FAIL",
            detail=(
                f"OCR confirmed: '{ocr_value}'"
                if ocr_grounded
                else f"OCR mismatch: expected '{pass1_value}', found '{ocr_value}'"
            ),
            value=ocr_value or "",
            confidence=1.0 if ocr_grounded else 0.60,
        ))

    # Challenger
    issues = challenger_issues if challenger_issues is not None else None
    if issues is not None:
        if issues:
            max_sev = max(i.get("severity", 0.5) for i in issues)
            steps.append(VerificationStep(
                method="CHALLENGER_CLEAR",
                status="FAIL",
                detail=f"{len(issues)} issue(s) found (max severity {max_sev:.1f})",
                confidence=1.0 - max_sev * 0.5,
            ))
        else:
            steps.append(VerificationStep(
                method="CHALLENGER_CLEAR",
                status="PASS",
                detail="No issues found by adversarial review",
                confidence=1.0,
            ))

    # Update resolution if OCR confirms pass1 on disagreement
    if resolution == "pass1_preferred" and ocr_grounded:
        resolution = "pass1_ocr_confirmed"

    return CellEvidence(
        pass1_value=pass1_value,
        pass1_confidence=pass1_conf,
        pass2_value=pass2_value,
        pass2_confidence=pass2_conf,
        passes_agree=(
            pass2_value is not None
            and pass1_value.strip().lower() == pass2_value.strip().lower()
        ) if pass2_value is not None else True,
        ocr_value=ocr_value,
        ocr_grounded=ocr_grounded,
        challenger_issues=challenger_issues or [],
        resolution_method=resolution,
        verification_steps=steps,
    )


# ── Row-level trust ──────────────────────────────────────────────────────

def compute_row_trust(
    procedure_name: str,
    cell_confidences: list[float],
    match_method: str = "exact",
    match_score: float = 1.0,
    cpt_code: str | None = None,
    footnotes_total: int = 0,
    footnotes_resolved: int = 0,
    is_effort_based: bool = False,
    flagged_count: int = 0,
    row_index: int = 0,
) -> RowTrust:
    """Compute composite row trust from components."""
    cell_count = len(cell_confidences)
    avg_conf = sum(cell_confidences) / max(cell_count, 1)

    # CPT status
    if cpt_code:
        cpt_status = "mapped"
        cpt_score = 1.0
    elif is_effort_based:
        cpt_status = "effort_based"
        cpt_score = 0.8  # No CPT needed — still good
    else:
        cpt_status = "missing"
        cpt_score = 0.3

    # Footnote resolution
    fn_rate = footnotes_resolved / max(footnotes_total, 1) if footnotes_total > 0 else 1.0

    # Mapping quality
    if match_method == "unmatched":
        map_score = 0.0
    elif match_method == "exact":
        map_score = 1.0
    elif match_method == "alias":
        map_score = 0.95
    elif match_method.startswith("starts_with"):
        map_score = 0.85
    elif match_method.startswith("fuzzy"):
        map_score = match_score
    else:
        map_score = match_score

    # Flagged cell penalty
    flag_penalty = flagged_count * 0.05

    # Composite: weighted average
    w = DEFAULT_WEIGHTS
    composite = (
        avg_conf * (w["dual_pass_agreement"] + w["ocr_grounding"] + w["challenger_clear"])
        + map_score * w["procedure_mapping"]
        + fn_rate * w["footnote_resolution"]
        + cpt_score * 0.05  # Small CPT bonus
    )
    composite = max(0.0, min(1.0, composite - flag_penalty))

    return RowTrust(
        procedure_name=procedure_name,
        row_index=row_index,
        match_method=match_method,
        match_score=match_score,
        cpt_status=cpt_status,
        cell_count=cell_count,
        avg_cell_confidence=avg_conf,
        flagged_cells=flagged_count,
        footnote_markers_total=footnotes_total,
        footnote_markers_resolved=footnotes_resolved,
        composite_score=composite,
    )


# ── Protocol-level trust ─────────────────────────────────────────────────

def compute_protocol_trust(
    tables: list,
    domain_config: dict | None = None,
) -> ProtocolTrust:
    """Aggregate protocol-level trust from all tables.

    Args:
        tables: list of ExtractedTable objects.
        domain_config: Optional domain YAML config with trust weight overrides.
    """
    if not tables:
        return ProtocolTrust()

    total_cells = 0
    high_cells = 0
    medium_cells = 0
    low_cells = 0
    all_confidences: list[float] = []
    total_conflicts = 0
    total_challenger_issues = 0
    total_procedures = 0
    mapped_procedures = 0
    cpt_procedures = 0
    total_footnote_markers = 0
    resolved_footnote_markers = 0
    flagged_set: set[tuple[int, int]] = set()
    reviewed_count = 0
    passes = 1

    for table in tables:
        meta = getattr(table, "extraction_metadata", None)
        if meta:
            total_conflicts += getattr(meta, "reconciliation_conflicts", 0)
            total_challenger_issues += getattr(meta, "challenger_issues_found", 0)
            passes = max(passes, getattr(meta, "passes_run", 1))

        for cell in getattr(table, "cells", []):
            total_cells += 1
            conf = getattr(cell, "confidence", 0.5)
            all_confidences.append(conf)

            if conf >= DEFAULT_THRESHOLDS["high"]:
                high_cells += 1
            elif conf >= DEFAULT_THRESHOLDS["medium"]:
                medium_cells += 1
            else:
                low_cells += 1

            if getattr(cell, "human_reviewed", False):
                reviewed_count += 1

        for ref in getattr(table, "flagged_cells", []):
            flagged_set.add((getattr(ref, "row", 0), getattr(ref, "col", 0)))

        for proc in getattr(table, "procedures", []):
            total_procedures += 1
            cn = getattr(proc, "canonical_name", "")
            rn = getattr(proc, "raw_name", "")
            if cn and cn != rn:
                mapped_procedures += 1
            code = getattr(proc, "code", None)
            if code:
                cpt_procedures += 1

        for fn in getattr(table, "footnotes", []):
            markers = getattr(fn, "applies_to", [])
            total_footnote_markers += len(markers)
            if getattr(fn, "text", ""):
                resolved_footnote_markers += len(markers)

    # Dual-pass agreement rate
    agree_cells = total_cells - total_conflicts if total_cells > 0 else 0
    agreement_rate = agree_cells / max(total_cells, 1)

    # Budget confidence
    mapping_rate = mapped_procedures / max(total_procedures, 1)
    if mapping_rate >= 0.90 and agreement_rate >= 0.95:
        budget_conf = "HIGH"
    elif mapping_rate >= 0.70 and agreement_rate >= 0.80:
        budget_conf = "MEDIUM"
    else:
        budget_conf = "LOW"

    # Overall score: weighted average of components
    avg_conf = sum(all_confidences) / max(len(all_confidences), 1)
    overall = (
        avg_conf * 0.40
        + agreement_rate * 0.25
        + mapping_rate * 0.20
        + (resolved_footnote_markers / max(total_footnote_markers, 1)) * 0.15
    )

    pt = ProtocolTrust(
        overall_score=round(min(1.0, overall), 4),
        total_cells=total_cells,
        high_confidence_cells=high_cells,
        medium_confidence_cells=medium_cells,
        low_confidence_cells=low_cells,
        dual_pass_agreement_rate=round(agreement_rate, 4),
        challenger_issues_total=total_challenger_issues,
        procedures_total=total_procedures,
        procedures_mapped=mapped_procedures,
        procedures_with_cpt=cpt_procedures,
        conditional_footnotes_total=total_footnote_markers,
        conditional_footnotes_resolved=resolved_footnote_markers,
        budget_confidence=budget_conf,
        flagged_cells=len(flagged_set),
        reviewed_cells=reviewed_count,
        tables_count=len(tables),
        passes_run=passes,
        has_challenger=total_challenger_issues > 0 or passes >= 2,
    )
    pt.estimated_review_minutes = estimate_review_minutes(pt)
    return pt


def estimate_review_minutes(trust: ProtocolTrust) -> int:
    """Estimate human review time in minutes."""
    flagged_time = trust.flagged_cells * REVIEW_MINUTES_PER_FLAGGED_CELL
    unmapped = max(0, trust.procedures_total - trust.procedures_mapped)
    unmapped_time = unmapped * REVIEW_MINUTES_PER_UNMAPPED_PROCEDURE
    return int(flagged_time + unmapped_time)
