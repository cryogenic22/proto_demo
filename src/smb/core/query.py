"""
Semantic query engine for StructuredModel.

Provides convenience functions for common queries:
- Procedures at a visit
- Visit timeline
- Budget schedule export
- Procedure frequency analysis
"""

from __future__ import annotations

from typing import Any

from src.smb.core.model import StructuredModel


def get_procedures_at_visit(
    model: StructuredModel, visit_name: str
) -> list[dict[str, Any]]:
    """Get all procedures performed at a specific visit with mark types.

    Returns list of dicts:
        [{"procedure": str, "mark_type": str, "occurrence_count": int,
          "conditions": list, "footnotes": list, "confidence": str}]
    """
    visit = model.get_entity_by_name(visit_name, "Visit")
    if not visit:
        return []

    results = []
    # Find ScheduleEntries linked to this visit via HAS_SCHEDULE_ENTRY
    entry_rels = model.get_relationships(
        rel_type="HAS_SCHEDULE_ENTRY", source_id=visit.id
    )
    for rel in entry_rels:
        entry = model.get_entity_by_id(rel.target_entity_id)
        if not entry or entry.entity_type != "ScheduleEntry":
            continue

        # Find the procedure linked to this entry
        proc_rels = model.get_relationships(
            rel_type="FOR_PROCEDURE", source_id=entry.id
        )
        proc_name = "Unknown"
        for pr in proc_rels:
            proc = model.get_entity_by_id(pr.target_entity_id)
            if proc:
                proc_name = proc.name
                break

        results.append({
            "procedure": proc_name,
            "mark_type": entry.get_property("mark_type", "unknown"),
            "occurrence_count": entry.get_property("occurrence_count", 1),
            "total_occurrences": entry.get_property("total_occurrences", 1),
            "conditions": entry.get_property("conditions", []),
            "footnotes": entry.get_property("footnote_markers", []),
            "confidence": entry.confidence.value,
            "raw_mark": entry.get_property("raw_mark", ""),
            "cost_multiplier": entry.get_property("cost_multiplier", 1.0),
            "subset_fraction": entry.get_property("subset_fraction", 1.0),
        })

    return results


def get_visit_timeline(model: StructuredModel) -> list[dict[str, Any]]:
    """Get visits ordered by day number with metadata.

    Returns list of dicts:
        [{"visit_name": str, "day_number": int|None, "window_minus": int,
          "window_plus": int, "is_unscheduled": bool, "cycle": int|None,
          "procedure_count": int}]
    """
    visit_entities = model.get_entities("Visit")
    # Sort with None-safe key (day_number can be None)
    visits = sorted(
        visit_entities,
        key=lambda v: v.get_property("day_number") if v.get_property("day_number") is not None else 999999,
    )
    results = []

    for visit in visits:
        # Count how many schedule entries are linked to this visit
        entry_rels = model.get_relationships(
            rel_type="HAS_SCHEDULE_ENTRY", source_id=visit.id
        )
        proc_count = len(entry_rels)

        results.append({
            "visit_name": visit.name,
            "day_number": visit.get_property("day_number"),
            "window_minus": visit.get_property("window_minus", 0),
            "window_plus": visit.get_property("window_plus", 0),
            "window_unit": visit.get_property("window_unit", "DAYS"),
            "is_unscheduled": visit.get_property("is_unscheduled", False),
            "cycle": visit.get_property("cycle"),
            "procedure_count": proc_count,
        })

    return results


def get_budget_schedule(model: StructuredModel) -> list[dict[str, Any]]:
    """Get schedule entries formatted for budget calculator consumption.

    Returns list of dicts, one per procedure:
        [{"procedure": str, "canonical_name": str, "cpt_code": str,
          "category": str, "cost_tier": str, "visits_required": [str],
          "total_occurrences": int, "firm_occurrences": int,
          "conditional_occurrences": int, "is_phone_call": bool,
          "cost_multiplier": float, "subset_fraction": float,
          "avg_confidence": float, "source_pages": [int]}]
    """
    procedures = model.get_entities("Procedure")
    schedule: list[dict[str, Any]] = []

    for proc in procedures:
        # Find all ScheduleEntries for this procedure
        entry_rels = model.get_relationships(
            rel_type="FOR_PROCEDURE", target_id=proc.id
        )

        visits_required: list[str] = []
        total_occ = 0
        firm_occ = 0
        conditional_occ = 0
        confidences: list[float] = []
        source_pages: set[int] = set()
        is_phone = False
        cost_multiplier = 1.0
        subset_fraction = 1.0

        for rel in entry_rels:
            entry = model.get_entity_by_id(rel.source_entity_id)
            if not entry or entry.entity_type != "ScheduleEntry":
                continue

            mark_type = entry.get_property("mark_type", "unknown")
            occ = entry.get_property("total_occurrences", 1)

            # Find visit name
            visit_rels = model.get_relationships(
                rel_type="HAS_SCHEDULE_ENTRY", target_id=entry.id
            )
            for vr in visit_rels:
                visit = model.get_entity_by_id(vr.source_entity_id)
                if visit:
                    visits_required.append(visit.name)

            if mark_type == "firm":
                firm_occ += occ
            elif mark_type == "conditional":
                conditional_occ += occ
            elif mark_type == "span":
                firm_occ += occ
            elif mark_type == "excluded":
                continue
            else:
                firm_occ += occ

            total_occ += occ

            # Confidence mapping
            conf_map = {"high": 0.95, "medium": 0.85, "low": 0.7, "manual": 1.0}
            confidences.append(conf_map.get(entry.confidence.value, 0.85))

            # Provenance
            if entry.provenance.page_number is not None:
                source_pages.add(entry.provenance.page_number)

            # Phone call and cost modifiers (from inference)
            if entry.get_property("is_phone_call", False):
                is_phone = True
            entry_mult = entry.get_property("cost_multiplier", 1.0)
            if entry_mult != 1.0:
                cost_multiplier = entry_mult
            entry_frac = entry.get_property("subset_fraction", 1.0)
            if entry_frac != 1.0:
                subset_fraction = entry_frac

        if total_occ == 0:
            continue

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.85

        schedule.append({
            "procedure": proc.get_property("raw_name", proc.name),
            "canonical_name": proc.get_property("canonical_name", proc.name),
            "cpt_code": proc.get_property("cpt_code", ""),
            "category": proc.get_property("category", "Unknown"),
            "cost_tier": proc.get_property("cost_tier", "LOW"),
            "visits_required": sorted(set(visits_required)),
            "total_occurrences": total_occ,
            "firm_occurrences": firm_occ,
            "conditional_occurrences": conditional_occ,
            "is_phone_call": is_phone,
            "cost_multiplier": cost_multiplier,
            "subset_fraction": subset_fraction,
            "avg_confidence": round(avg_conf, 3),
            "source_pages": sorted(source_pages),
        })

    # Sort by category then procedure name
    schedule.sort(key=lambda s: (s["category"], s["canonical_name"]))
    return schedule


def get_procedure_frequency(
    model: StructuredModel, procedure_name: str
) -> dict[str, Any]:
    """Get frequency analysis for a specific procedure.

    Returns:
        {"procedure": str, "total_occurrences": int, "firm_count": int,
         "conditional_count": int, "visits": [{"visit": str, "mark_type": str,
         "occurrences": int}], "has_span": bool, "is_phone_call": bool}
    """
    proc = model.get_entity_by_name(procedure_name, "Procedure")
    if not proc:
        # Try case-insensitive search
        for e in model.get_entities("Procedure"):
            if e.name.lower() == procedure_name.lower():
                proc = e
                break
    if not proc:
        return {
            "procedure": procedure_name,
            "total_occurrences": 0,
            "firm_count": 0,
            "conditional_count": 0,
            "visits": [],
            "has_span": False,
            "is_phone_call": False,
        }

    entry_rels = model.get_relationships(
        rel_type="FOR_PROCEDURE", target_id=proc.id
    )

    visits: list[dict[str, Any]] = []
    total = 0
    firm = 0
    conditional = 0
    has_span = False
    is_phone = False

    for rel in entry_rels:
        entry = model.get_entity_by_id(rel.source_entity_id)
        if not entry or entry.entity_type != "ScheduleEntry":
            continue

        mark_type = entry.get_property("mark_type", "unknown")
        occ = entry.get_property("total_occurrences", 1)
        total += occ

        if mark_type == "firm":
            firm += occ
        elif mark_type == "conditional":
            conditional += occ
        elif mark_type == "span":
            firm += occ
            has_span = True

        if entry.get_property("is_phone_call", False):
            is_phone = True

        # Find visit name
        visit_rels = model.get_relationships(
            rel_type="HAS_SCHEDULE_ENTRY", target_id=entry.id
        )
        visit_name = "Unknown"
        for vr in visit_rels:
            v = model.get_entity_by_id(vr.source_entity_id)
            if v:
                visit_name = v.name
                break

        visits.append({
            "visit": visit_name,
            "mark_type": mark_type,
            "occurrences": occ,
            "raw_mark": entry.get_property("raw_mark", ""),
        })

    return {
        "procedure": proc.name,
        "total_occurrences": total,
        "firm_count": firm,
        "conditional_count": conditional,
        "visits": visits,
        "has_span": has_span,
        "is_phone_call": is_phone,
    }
