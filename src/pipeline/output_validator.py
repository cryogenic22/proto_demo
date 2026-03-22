"""
Output Validator — hard gate between LLM extraction and downstream processing.

Validates structural integrity of extracted tables before they're
returned to consumers. Rejects tables with impossible/malformed values
rather than letting them propagate silently.

This addresses the core failure mode described in production incidents:
LLM hallucinations propagating unchecked into sorting/calculation logic.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from src.models.schema import (
    CellDataType,
    ExtractedCell,
    ExtractedTable,
    TableSchema,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cells_rejected: int = 0
    cells_cleaned: int = 0


# Patterns that indicate hallucinated/malformed values
_NONE_PATTERNS = re.compile(
    r"\bNONE\b|\bNULL\b|\bN/A\b|\bNaN\b|\bundefined\b|\bERROR\b",
    re.IGNORECASE,
)

# Impossible numeric values for clinical contexts
_IMPOSSIBLE_DAY = 10000  # No trial has 10000+ days
_IMPOSSIBLE_VISIT_COUNT = 200  # No single table has 200+ visits


class OutputValidator:
    """Hard validation gate for extracted table data."""

    def validate_table(self, table: ExtractedTable) -> ValidationResult:
        """
        Validate a single extracted table.

        Returns ValidationResult with errors/warnings.
        Does NOT raise — caller decides whether to reject or flag.
        """
        result = ValidationResult()

        # 1. Schema integrity checks
        self._check_schema_integrity(table, result)

        # 2. Cell value sanity checks
        self._check_cell_values(table, result)

        # 3. Structural consistency
        self._check_structural_consistency(table, result)

        # 4. Row consistency (VP2-3)
        self._check_row_consistency(table, result)

        # 5. Footnote chain validation (VP2-2)
        self._check_footnote_chain(table, result)

        # 6. Duplicate detection
        self._check_duplicates(table, result)

        if result.errors:
            result.valid = False

        return result

    def clean_table(self, table: ExtractedTable) -> ExtractedTable:
        """
        Clean a table by removing/fixing obviously malformed cells.

        This is the defensive layer that prevents NONE-type values
        from reaching downstream processing.
        """
        cleaned_cells: list[ExtractedCell] = []

        for cell in table.cells:
            cleaned = self._clean_cell(cell)
            if cleaned is not None:
                cleaned_cells.append(cleaned)

        return table.model_copy(update={"cells": cleaned_cells})

    def _check_schema_integrity(self, table: ExtractedTable, result: ValidationResult):
        """Verify the schema is internally consistent."""
        schema = table.schema_info

        if schema.num_rows == 0 and schema.num_cols == 0 and table.cells:
            result.warnings.append(
                f"Table {table.table_id}: Schema reports 0 rows/cols but has {len(table.cells)} cells"
            )

        if schema.num_cols > _IMPOSSIBLE_VISIT_COUNT:
            result.errors.append(
                f"Table {table.table_id}: Schema reports {schema.num_cols} columns — "
                f"likely hallucinated (max reasonable: {_IMPOSSIBLE_VISIT_COUNT})"
            )

        # Check for duplicate column headers
        if schema.column_headers:
            header_texts = [h.text for h in schema.column_headers]
            seen = set()
            dupes = set()
            for h in header_texts:
                if h in seen:
                    dupes.add(h)
                seen.add(h)
            if dupes:
                result.warnings.append(
                    f"Table {table.table_id}: Duplicate column headers: {dupes}"
                )

    def _check_cell_values(self, table: ExtractedTable, result: ValidationResult):
        """Check individual cell values for impossible/hallucinated content."""
        none_count = 0
        empty_marker_count = 0

        for cell in table.cells:
            # Check for NONE/NULL patterns in values
            if _NONE_PATTERNS.search(cell.raw_value):
                none_count += 1

            # Check for marker cells with suspiciously long text
            if cell.data_type == CellDataType.MARKER and len(cell.raw_value) > 20:
                result.warnings.append(
                    f"Cell ({cell.row},{cell.col}): MARKER type but long value "
                    f"'{cell.raw_value[:30]}...' — possibly misclassified"
                )

            # Check for impossible row/col indices
            if cell.row > 500 or cell.col > _IMPOSSIBLE_VISIT_COUNT:
                result.errors.append(
                    f"Cell ({cell.row},{cell.col}): Impossible coordinates — "
                    f"likely hallucinated"
                )

        if none_count > 0:
            pct = none_count / max(len(table.cells), 1) * 100
            msg = (
                f"Table {table.table_id}: {none_count} cells ({pct:.0f}%) contain "
                f"NONE/NULL patterns — possible hallucination"
            )
            if pct > 20:
                result.errors.append(msg)
            else:
                result.warnings.append(msg)

    def _check_structural_consistency(self, table: ExtractedTable, result: ValidationResult):
        """Check that the extracted cells are structurally consistent."""
        if not table.cells:
            return

        # Check for gaps in the grid
        rows_seen = set()
        cols_seen = set()
        for cell in table.cells:
            rows_seen.add(cell.row)
            cols_seen.add(cell.col)

        if rows_seen:
            max_row = max(rows_seen)
            expected_rows = set(range(max_row + 1))
            missing_rows = expected_rows - rows_seen
            if len(missing_rows) > max_row * 0.3:  # More than 30% rows missing
                result.warnings.append(
                    f"Table {table.table_id}: {len(missing_rows)} rows missing "
                    f"from extraction (out of {max_row + 1})"
                )

    def _check_duplicates(self, table: ExtractedTable, result: ValidationResult):
        """Check for duplicate cells at the same coordinates."""
        seen: set[tuple[int, int]] = set()
        dupes = 0
        for cell in table.cells:
            key = (cell.row, cell.col)
            if key in seen:
                dupes += 1
            seen.add(key)

        if dupes > 0:
            result.warnings.append(
                f"Table {table.table_id}: {dupes} duplicate cell coordinates found"
            )

    def _check_row_consistency(self, table: ExtractedTable, result: ValidationResult):
        """Check that each row has the same number of columns (VP2-3)."""
        if not table.cells:
            return
        from collections import Counter
        row_col_counts = Counter()
        for cell in table.cells:
            row_col_counts[cell.row] += 1

        col_counts = list(row_col_counts.values())
        if len(set(col_counts)) > 1:
            mode_count = Counter(col_counts).most_common(1)[0][0]
            anomalous = {r: cnt for r, cnt in row_col_counts.items() if cnt != mode_count}
            if anomalous:
                result.warnings.append(
                    f"Table {table.table_id}: Row consistency issue — "
                    f"{len(anomalous)} rows have different column counts "
                    f"(expected {mode_count}, anomalous: {anomalous})"
                )

    def _check_footnote_chain(self, table: ExtractedTable, result: ValidationResult):
        """Verify every footnote marker in cells has a definition (VP2-2)."""
        # Collect all markers referenced in cells
        cell_markers = set()
        for cell in table.cells:
            for m in cell.footnote_markers:
                cell_markers.add(m)

        # Collect all defined footnotes
        defined_markers = {fn.marker for fn in table.footnotes}

        # Find orphaned markers (in cells but no definition)
        orphaned = cell_markers - defined_markers
        if orphaned:
            result.warnings.append(
                f"Table {table.table_id}: Footnote markers {orphaned} found in cells "
                f"but no definition extracted"
            )

    def _clean_cell(self, cell: ExtractedCell) -> ExtractedCell | None:
        """
        Clean a single cell. Returns None to reject, or cleaned cell.
        """
        # Reject cells with impossible coordinates
        if cell.row > 500 or cell.col > _IMPOSSIBLE_VISIT_COUNT:
            return None

        # Clean NONE/NULL values → convert to EMPTY
        if _NONE_PATTERNS.search(cell.raw_value):
            return cell.model_copy(update={
                "raw_value": "",
                "data_type": CellDataType.EMPTY,
                "confidence": min(cell.confidence, 0.3),
            })

        # Clean superscript contamination in procedure names (col 0)
        if cell.col == 0 and cell.raw_value:
            cleaned_value, extra_markers = _strip_superscript_contamination(cell.raw_value)
            if cleaned_value != cell.raw_value:
                new_markers = list(cell.footnote_markers) + extra_markers
                return cell.model_copy(update={
                    "raw_value": cleaned_value,
                    "row_header": cleaned_value if cell.row_header == cell.raw_value else cell.row_header,
                    "footnote_markers": new_markers,
                })

        # Filter non-procedure noise from col 0 TEXT cells
        # The pipeline sometimes extracts amendment names, section references,
        # endpoints, abbreviations, and body text as "procedures."
        if cell.col == 0 and cell.data_type == CellDataType.TEXT:
            if _is_procedure_noise(cell.raw_value):
                return cell.model_copy(update={
                    "raw_value": "",
                    "data_type": CellDataType.EMPTY,
                    "confidence": 0.1,
                })

        return cell


# Procedure noise detection — rejects entries that are clearly not
# clinical procedures (amendment names, section references, endpoints,
# abbreviations, body text, table metadata).
_NOISE_PATTERNS = [
    re.compile(r"^Amendment \d+", re.IGNORECASE),
    re.compile(r"^Original Protocol", re.IGNORECASE),
    re.compile(r"^Section \d+", re.IGNORECASE),
    re.compile(r"^Sections? \d+\.\d+", re.IGNORECASE),
    re.compile(r"^Appendix \d+", re.IGNORECASE),
    re.compile(r"^Synopsis", re.IGNORECASE),
    re.compile(r"^Table \d+", re.IGNORECASE),
    re.compile(r"^Title Page", re.IGNORECASE),
    re.compile(r"^Header$", re.IGNORECASE),
    re.compile(r"^Abbreviation", re.IGNORECASE),
    re.compile(r"^Estimand", re.IGNORECASE),
    re.compile(r"^Objective", re.IGNORECASE),
    re.compile(r"^Primary endpoint", re.IGNORECASE),
    re.compile(r"^Secondary endpoint", re.IGNORECASE),
    re.compile(r"^Exploratory Objective", re.IGNORECASE),
    re.compile(r"^Long-term endpoint", re.IGNORECASE),
    re.compile(r"^To evaluate", re.IGNORECASE),
    re.compile(r"^To assess", re.IGNORECASE),
    re.compile(r"^To demonstrate", re.IGNORECASE),
    re.compile(r"^To conduct", re.IGNORECASE),
    re.compile(r"^To infer", re.IGNORECASE),
    re.compile(r"^Cases of", re.IGNORECASE),
    re.compile(r"^Regardless of evidence", re.IGNORECASE),
    re.compile(r"^Part [A-Z]:", re.IGNORECASE),
    re.compile(r"^Part [A-Z]\d?:", re.IGNORECASE),
    re.compile(r"^All participants", re.IGNORECASE),
    re.compile(r"^Blinded Participants", re.IGNORECASE),
    re.compile(r"^Unblinded Participants", re.IGNORECASE),
    re.compile(r"^Placebo participants", re.IGNORECASE),
    re.compile(r"^mRNA-\d+ participants", re.IGNORECASE),
    re.compile(r"^Participants who", re.IGNORECASE),
    re.compile(r"^Supplemental Schedule", re.IGNORECASE),
    re.compile(r"^Modified Supplemental", re.IGNORECASE),
    re.compile(r"^Section # and Name", re.IGNORECASE),
    re.compile(r"^Continue with original", re.IGNORECASE),
    re.compile(r"^Counselling the importance", re.IGNORECASE),
    re.compile(r"^True VE", re.IGNORECASE),
    re.compile(r"^Target VE", re.IGNORECASE),
    re.compile(r"^Header placeholder", re.IGNORECASE),
    re.compile(r"^\d+%$"),  # Standalone percentages like "60%"
]

# Short abbreviation noise — common non-procedure abbreviations
_ABBREVIATION_NOISE = {
    "cci", "psrt", "sae", "sap", "srr", "soe", "teae", "uloq", "usp",
    "ve", "who", "s", "s-2p", "mild", "moderate", "severe", "none",
    "header", "fold rise", "ia1 35%", "ia2 70%",
}


def _is_procedure_noise(value: str) -> bool:
    """Check if a col-0 value is noise rather than a clinical procedure."""
    v = value.strip()
    if not v:
        return False

    # Pattern-based noise
    for pat in _NOISE_PATTERNS:
        if pat.match(v):
            return True

    # Short abbreviation noise
    if v.lower() in _ABBREVIATION_NOISE:
        return True

    # Very long text (>150 chars) is body text, not a procedure name
    if len(v) > 150:
        return True

    # Section reference patterns: "Section 1.1 / 4.1.2 / ..."
    if v.startswith("Section ") and "/" in v:
        return True

    # "Vaccine efficacy of..." — endpoint description, not procedure
    if v.lower().startswith("vaccine efficacy"):
        return True

    return False


# Superscript contamination cleanup
_SUPERSCRIPT_MAP = {"ᵃ": "a", "ᵇ": "b", "ᶜ": "c", "ᵈ": "d",
                     "ᵉ": "e", "ᶠ": "f", "ᵍ": "g", "ʰ": "h"}

_CONTAMINATED_SUFFIXES = {
    "assessmente": "assessment",
    "assessmenta": "assessment",
    "assessmentd": "assessment",
    "appropriateb": "appropriate",
    "appropriated": "appropriate",
    "informationd": "information",
    "administrationf": "administration",
    "datesf": "dates",
    "resultsf": "results",
    "typingc": "typing",
    "typinge": "typing",
    "isolationc": "isolation",
    "isolatione": "isolation",
    "swab(s)c": "swab(s)",
}


def _strip_superscript_contamination(value: str) -> tuple[str, list[str]]:
    """Strip footnote superscripts that contaminate procedure names.

    Returns (cleaned_value, list_of_extracted_markers).
    """
    markers = []
    original = value

    # Strip Unicode superscripts
    for sup, plain in _SUPERSCRIPT_MAP.items():
        if value.endswith(sup):
            value = value[:-1]
            markers.append(plain)
            break

    # Check known contaminated endings
    val_lower = value.lower()
    for suffix, clean in _CONTAMINATED_SUFFIXES.items():
        if val_lower.endswith(suffix):
            idx = len(value) - len(suffix)
            marker_char = value[idx + len(clean):]
            value = value[:idx] + clean
            if marker_char:
                markers.append(marker_char.lower())
            break

    return value, markers
