"""
Item 2: Dry-run continuity stitcher on known multi-page tables.

For protocols that have multi-page SoA tables (P-14, Pfizer BNT162, P-09),
verifies that the stitcher doesn't reduce page counts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.schema import BoundingBox, TableRegion, TableType
from src.pipeline.table_stitcher import TableStitcher

PROTOCOL_DIR = Path(__file__).parent.parent / "data" / "protocols"

# Protocols known to have multi-page SoA tables
MULTI_PAGE_PROTOCOLS = [
    "p14",
    "p_14_690eb522",
    "pfizer_bnt162",
    "p09",
    "p01_brivaracetam",
    "p17_durvalumab_bb172274",
    "prot_0001_1_3a3bae33",
]


def validate_stitcher_for_protocol(proto_id: str) -> list[str]:
    """Run stitcher on a protocol's tables and verify page counts don't decrease."""
    errors: list[str] = []
    path = PROTOCOL_DIR / f"{proto_id}.json"
    if not path.exists():
        return [f"{proto_id}: Protocol file not found"]

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    tables = data.get("tables", [])
    if not tables:
        return [f"{proto_id}: No tables"]

    # Build TableRegion objects from stored data
    regions: list[TableRegion] = []
    for t in tables:
        pages = t.get("source_pages", [])
        if not pages:
            continue
        title = t.get("title", "")
        table_type_str = t.get("table_type", "SOA")
        try:
            tt = TableType(table_type_str)
        except ValueError:
            tt = TableType.OTHER
        regions.append(TableRegion(
            table_id=t.get("table_id", "unknown"),
            pages=pages,
            bounding_boxes=[
                BoundingBox(x0=0, y0=0, x1=100, y1=100, page=p) for p in pages
            ],
            table_type=tt,
            title=title,
            continuation_markers=[],
        ))

    if not regions:
        return [f"{proto_id}: No regions with pages"]

    # Record original page counts
    original_total_pages = sum(len(r.pages) for r in regions)
    original_region_count = len(regions)

    # Run stitcher (without PDF bytes — tests structural logic only)
    stitcher = TableStitcher()
    merged = stitcher.stitch(regions)

    # Check: total page coverage should not decrease
    merged_total_pages = sum(len(r.pages) for r in merged)
    merged_all_pages = set()
    for r in merged:
        merged_all_pages.update(r.pages)

    original_all_pages = set()
    for r in regions:
        original_all_pages.update(r.pages)

    if merged_all_pages != original_all_pages:
        lost = original_all_pages - merged_all_pages
        gained = merged_all_pages - original_all_pages
        if lost:
            errors.append(
                f"{proto_id}: Stitcher LOST pages {sorted(lost)}! "
                f"Original={sorted(original_all_pages)}, "
                f"Merged={sorted(merged_all_pages)}"
            )
        if gained:
            errors.append(
                f"{proto_id}: Stitcher gained unexpected pages {sorted(gained)}"
            )

    # Check: page counts should not decrease
    if merged_total_pages < original_total_pages:
        errors.append(
            f"{proto_id}: Total page refs decreased "
            f"({original_total_pages} -> {merged_total_pages})"
        )

    return errors


def main():
    print("=" * 60)
    print("Stitcher Dry-Run — Multi-Page Table Validation")
    print("=" * 60)

    all_errors: list[str] = []

    for proto_id in MULTI_PAGE_PROTOCOLS:
        path = PROTOCOL_DIR / f"{proto_id}.json"
        if not path.exists():
            print(f"\n{proto_id}: SKIPPED (not found)")
            continue

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        tables = data.get("tables", [])
        multi_page = [t for t in tables if len(t.get("source_pages", [])) > 1]

        print(f"\n{proto_id}: {len(tables)} tables, {len(multi_page)} multi-page")
        errors = validate_stitcher_for_protocol(proto_id)
        if errors:
            for e in errors:
                print(f"  FAIL: {e}")
            all_errors.extend(errors)
        else:
            regions_before = len(tables)
            # Re-run to report merged count
            regions_list = []
            for t in tables:
                pages = t.get("source_pages", [])
                if pages:
                    regions_list.append(TableRegion(
                        table_id=t.get("table_id", ""),
                        pages=pages,
                        bounding_boxes=[BoundingBox(x0=0, y0=0, x1=100, y1=100, page=p) for p in pages],
                        table_type=TableType.SOA,
                        title=t.get("title", ""),
                        continuation_markers=[],
                    ))
            merged = TableStitcher().stitch(regions_list)
            all_pages = set()
            for r in regions_list:
                all_pages.update(r.pages)
            print(f"  OK: {regions_before} -> {len(merged)} regions, "
                  f"{len(all_pages)} unique pages preserved")

    print("\n" + "=" * 60)
    if all_errors:
        print(f"FAILED: {len(all_errors)} error(s)")
        sys.exit(1)
    else:
        print("All stitcher validations passed")
    print("=" * 60)


if __name__ == "__main__":
    main()
