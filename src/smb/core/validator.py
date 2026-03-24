"""
Validation engine — checks model consistency after inference.

Produces a ValidationReport with errors, warnings, and info messages.
Zero ProtoExtract imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.smb.core.model import StructuredModel


@dataclass
class ValidationReport:
    """Result of model validation."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "stats": self.stats,
        }


class ValidationEngine:
    """Runs validation checks on a StructuredModel."""

    def validate(self, model: StructuredModel) -> ValidationReport:
        """Run all validation checks. Returns a ValidationReport."""
        report = ValidationReport()

        self._check_entities_exist(model, report)
        self._check_visits_have_entries(model, report)
        self._check_no_unknown_marks(model, report)
        self._check_footnotes_resolved(model, report)
        self._compute_stats(model, report)

        # Store on model for downstream access
        model.validation_report = report.to_dict()

        return report

    def _check_entities_exist(
        self, model: StructuredModel, report: ValidationReport
    ) -> None:
        """Check that the model has the basic entity types."""
        visits = model.get_entities("Visit")
        procedures = model.get_entities("Procedure")
        entries = model.get_schedule_entries()

        if not visits:
            report.errors.append("No Visit entities found")
        if not procedures:
            report.errors.append("No Procedure entities found")
        if not entries:
            report.warnings.append(
                "No ScheduleEntry entities found — empty SoA?"
            )

    def _check_visits_have_entries(
        self, model: StructuredModel, report: ValidationReport
    ) -> None:
        """Check every Visit has at least 1 ScheduleEntry."""
        visits = model.get_entities("Visit")
        entries = model.get_schedule_entries()

        visit_ids_with_entries: set[str] = set()
        for e in entries:
            vid = e.get_property("visit_entity_id")
            if vid:
                visit_ids_with_entries.add(vid)

        for visit in visits:
            if visit.id not in visit_ids_with_entries:
                report.warnings.append(
                    f"Visit '{visit.name}' has no schedule entries"
                )

    def _check_no_unknown_marks(
        self, model: StructuredModel, report: ValidationReport
    ) -> None:
        """Check no ScheduleEntry has mark_type=unknown."""
        for entry in model.get_schedule_entries():
            mark = entry.get_property("mark_type", "")
            if mark == "unknown":
                report.errors.append(
                    f"ScheduleEntry '{entry.name}' has mark_type=unknown"
                )

    def _check_footnotes_resolved(
        self, model: StructuredModel, report: ValidationReport
    ) -> None:
        """Check all footnote_markers on ScheduleEntries are resolved."""
        footnote_markers_defined: set[str] = set()
        for fn in model.get_entities("Footnote"):
            marker = fn.get_property("footnote_marker")
            if marker:
                footnote_markers_defined.add(marker)

        for entry in model.get_schedule_entries():
            markers = entry.get_property("footnote_markers", [])
            for marker in markers:
                if marker not in footnote_markers_defined:
                    report.warnings.append(
                        f"ScheduleEntry '{entry.name}' references "
                        f"unresolved footnote marker '{marker}'"
                    )

    def _compute_stats(
        self, model: StructuredModel, report: ValidationReport
    ) -> None:
        """Add summary stats to the report."""
        visits = model.get_entities("Visit")
        procedures = model.get_entities("Procedure")
        entries = model.get_schedule_entries()

        report.stats = {
            "visits": len(visits),
            "procedures": len(procedures),
            "schedule_entries": len(entries),
            "firm_entries": len(model.get_firm_entries()),
            "conditional_entries": len(model.get_conditional_entries()),
            "footnotes": len(model.get_entities("Footnote")),
        }

        report.info.append(
            f"Model: {len(visits)} visits, {len(procedures)} procedures, "
            f"{len(entries)} schedule entries"
        )
