"""
Protocol Bridge — converts PipelineOutput dicts to Protocol objects.

Bridges the extraction pipeline (which produces PipelineOutput) and the
knowledge-element store (which persists Protocol objects).
"""

from __future__ import annotations

import hashlib
import logging
import re

from src.models.protocol import Protocol, ProtocolMetadata, SectionNode

logger = logging.getLogger(__name__)


def _slug(text: str) -> str:
    """Convert a filename to a URL-safe slug."""
    name = re.sub(r"\.[^.]+$", "", text)  # strip extension
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return name or "unknown"


def _protocol_id_from(filename: str) -> str:
    """Generate a stable protocol_id from the filename hash + slug."""
    slug = _slug(filename)
    digest = hashlib.sha256(filename.encode()).hexdigest()[:8]
    return f"{slug}_{digest}"


def _parse_sections(pdf_bytes: bytes, filename: str) -> list[SectionNode]:
    """Parse sections with content_html from the PDF.

    Returns a hierarchical list of SectionNode objects with content
    populated via get_section_formatted().
    """
    try:
        from src.pipeline.section_parser import SectionParser

        parser = SectionParser()
        sections = parser.parse(pdf_bytes, filename=filename)
        flat = parser._flatten(sections)

        # Convert to SectionNode objects with content_html
        nodes: list[SectionNode] = []
        node_map: dict[str, SectionNode] = {}

        for s in flat:
            # Extract formatted HTML content (limit to avoid huge payloads)
            content_html = ""
            try:
                content_html = parser.get_section_formatted(
                    pdf_bytes, s, output="html", include_subsections=False
                )
                # Truncate very large sections to keep storage manageable
                if len(content_html) > 50000:
                    content_html = content_html[:50000] + "\n<!-- truncated -->"
            except Exception:
                pass

            node = SectionNode(
                number=s.number,
                title=s.title,
                page=s.page,
                end_page=s.end_page,
                level=s.level,
                content_html=content_html,
                children=[],
            )
            node_map[s.number] = node

            # Build hierarchy — add to parent if it exists
            if "." in s.number:
                parent_num = ".".join(s.number.split(".")[:-1])
                parent = node_map.get(parent_num)
                if parent:
                    parent.children.append(node)
                    continue
            nodes.append(node)

        logger.info(f"Parsed {len(flat)} sections ({len(nodes)} top-level) with content_html")
        return nodes

    except Exception as e:
        logger.warning(f"Section parsing failed: {e}")
        return []


def _build_budget_lines(result_json: dict) -> list[dict]:
    """Build budget line items from extraction results."""
    budget_lines = []
    seen_procs = set()

    for table in result_json.get("tables", []):
        for proc in table.get("procedures", []):
            canonical = proc.get("canonical_name", proc.get("raw_name", ""))
            if canonical.lower() in seen_procs:
                continue
            seen_procs.add(canonical.lower())

            # Count visits where this procedure appears
            raw_name = proc.get("raw_name", "")
            visit_count = 0
            for cell in table.get("cells", []):
                if (cell.get("row_header", "").strip().lower()[:30] == raw_name.strip().lower()[:30]
                        and cell.get("data_type") in ("MARKER", "CONDITIONAL")
                        and cell.get("raw_value", "").strip()):
                    visit_count += 1

            budget_lines.append({
                "procedure": raw_name,
                "canonical_name": canonical,
                "cpt_code": proc.get("code", ""),
                "category": proc.get("category", ""),
                "cost_tier": proc.get("estimated_cost_tier", "LOW"),
                "visits_required": visit_count,
                "total_occurrences": visit_count,
                "estimated_unit_cost": None,
                "avg_confidence": proc.get("confidence", 0.85),
                "notes": "",
            })

    return budget_lines


def _build_quality_summary(result_json: dict) -> dict:
    """Build quality summary metrics from extraction results."""
    total_cells = 0
    review_items = 0
    marker_cells = 0
    text_cells = 0

    for table in result_json.get("tables", []):
        cells = table.get("cells", [])
        total_cells += len(cells)
        for cell in cells:
            if cell.get("confidence", 1.0) < 0.85:
                review_items += 1
            if cell.get("data_type") == "MARKER":
                marker_cells += 1
            elif cell.get("data_type") == "TEXT":
                text_cells += 1

    return {
        "total_cells": total_cells,
        "review_items": review_items,
        "correction_rate": review_items / max(total_cells, 1),
        "marker_cells": marker_cells,
        "text_cells": text_cells,
        "vision_verified": 0,
    }


def pipeline_output_to_protocol(
    result_json: dict,
    filename: str,
    pdf_bytes: bytes = b"",
) -> Protocol:
    """Convert a serialized PipelineOutput dict to a Protocol.

    Args:
        result_json: Serialized PipelineOutput (from model_dump_json()).
        filename: Original uploaded filename.
        pdf_bytes: Raw PDF bytes for section parsing (optional).

    Returns:
        A valid Protocol object ready for persistence.
    """
    protocol_id = _protocol_id_from(filename)

    # Parse sections with content_html from PDF
    sections = []
    if pdf_bytes:
        sections = _parse_sections(pdf_bytes, filename)

    # Build budget lines from extraction
    budget_lines = _build_budget_lines(result_json)

    # Build quality summary
    quality_summary = _build_quality_summary(result_json)

    return Protocol(
        protocol_id=protocol_id,
        document_name=result_json.get("document_name", filename),
        document_hash=result_json.get("document_hash", ""),
        total_pages=result_json.get("total_pages", 0),
        metadata=ProtocolMetadata(),
        sections=sections,
        tables=result_json.get("tables", []),
        procedures=result_json.get("procedures", []),
        budget_lines=budget_lines,
        quality_summary=quality_summary,
        pipeline_version=result_json.get("pipeline_version", "0.1.0"),
    )
