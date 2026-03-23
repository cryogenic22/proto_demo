"""
Trust data models — document-agnostic evidence and confidence structures.

These models define the contract for trust data across any extraction pipeline
(SoA, CMC, CSR, ICF, etc.). The specific verification methods vary per pipeline,
but the trust framework is universal.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VerificationStep(BaseModel):
    """One check in the evidence chain.

    Matches the frontend VerificationStep type in web/src/lib/api.ts.
    Pipeline stages emit these; the UI renders them as a CI/CD-style chain.
    """

    method: str = ""
    """Verification method identifier. Standard methods:
    - DUAL_PASS: Two independent extraction passes compared
    - OCR_GROUNDING: Cross-modal verification against OCR text
    - CHALLENGER_CLEAR: Adversarial agent found no issues
    - TEXT_MATCH: Value matches PDF text layer
    - FORMAT_CHECK: Value matches expected format
    Pipelines may define additional methods (e.g., CROSS_REF_CHECK for CSR).
    """

    status: str = "SKIPPED"
    """PASS, FAIL, or SKIPPED."""

    detail: str = ""
    """Human-readable explanation (e.g., 'Both passes agree: X')."""

    value: str = ""
    """What this check found (e.g., the pass2 value, or OCR text)."""

    confidence: float = 1.0
    """Confidence from this specific check (0-1)."""


class CellEvidence(BaseModel):
    """Per-cell provenance bundle.

    Stored as a dict on ExtractedCell.evidence for backward compatibility.
    Captures what each pipeline stage found for this cell, enabling
    full audit trail from extraction to final value.
    """

    pass1_value: str = ""
    pass1_confidence: float = 1.0
    pass2_value: str | None = None
    pass2_confidence: float | None = None
    passes_agree: bool = True

    ocr_value: str | None = None
    ocr_grounded: bool | None = None  # None = OCR not available

    challenger_issues: list[dict] = Field(default_factory=list)
    """Serialized ChallengeIssue dicts (avoids circular import)."""

    resolution_method: str = ""
    """How the final value was chosen:
    - both_agree: Pass 1 and 2 agreed
    - pass1_preferred: Disagreement, pass 1 chosen (default)
    - pass1_ocr_confirmed: Disagreement, OCR confirmed pass 1
    - single_pass: Only one pass ran
    - manual: Human override
    """

    verification_steps: list[VerificationStep] = Field(default_factory=list)
    """Ordered list of checks performed on this cell."""


class RowTrust(BaseModel):
    """Composite trust for a row entity (procedure, CMC attribute, etc.).

    Aggregates cell-level confidence with procedure mapping quality
    and footnote resolution to give a single row-level score.
    """

    procedure_name: str = ""
    row_index: int = 0

    match_method: str = ""
    """How the procedure was matched: exact, alias, starts_with, fuzzy, unmatched."""

    match_score: float = 1.0
    """Match confidence (1.0 for exact, 0.5-0.9 for fuzzy, 0.0 for unmatched)."""

    cpt_status: str = "missing"
    """CPT code status: mapped, effort_based (N/A is correct), missing."""

    cell_count: int = 0
    avg_cell_confidence: float = 0.0
    flagged_cells: int = 0

    footnote_markers_total: int = 0
    footnote_markers_resolved: int = 0

    @property
    def footnote_resolution_rate(self) -> float:
        if self.footnote_markers_total == 0:
            return 1.0
        return self.footnote_markers_resolved / self.footnote_markers_total

    composite_score: float = 0.0


class ProtocolTrust(BaseModel):
    """Protocol-level trust dashboard.

    Aggregated from all tables in a protocol. Computed server-side,
    cached per protocol, invalidated on cell review actions.
    """

    overall_score: float = 0.0

    # ── Extraction quality ──
    total_cells: int = 0
    high_confidence_cells: int = 0
    medium_confidence_cells: int = 0
    low_confidence_cells: int = 0
    dual_pass_agreement_rate: float = 0.0
    ocr_match_rate: float | None = None
    challenger_issues_total: int = 0
    challenger_issues_resolved: int = 0

    # ── Procedure mapping ──
    procedures_total: int = 0
    procedures_mapped: int = 0
    procedures_with_cpt: int = 0
    noise_rows_filtered: int = 0

    # ── Budget readiness ──
    conditional_footnotes_resolved: int = 0
    conditional_footnotes_total: int = 0
    budget_confidence: str = "LOW"

    # ── Human review ──
    flagged_cells: int = 0
    reviewed_cells: int = 0
    estimated_review_minutes: int = 0

    # ── Row breakdown ──
    row_trusts: list[RowTrust] = Field(default_factory=list)

    # ── Metadata ──
    tables_count: int = 0
    passes_run: int = 1
    has_ocr_grounding: bool = False
    has_challenger: bool = False
