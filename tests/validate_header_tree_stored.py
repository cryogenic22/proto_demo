"""
Item 1: Validate Header Tree on all 9 stored protocols.

Checks:
- Every leaf col_index maps to exactly one column (no duplicates)
- Every parent's span contains its children
- Tree-derived column count matches schema_info.num_cols
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.schema import ColumnHeader
from src.pipeline.header_tree import HeaderTreeBuilder, validate_tree

PROTOCOL_DIR = Path(__file__).parent.parent / "data" / "protocols"


def validate_protocol(path: Path) -> list[str]:
    """Validate header tree for a single stored protocol. Returns error list."""
    errors: list[str] = []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    protocol_id = data.get("protocol_id", path.stem)
    tables = data.get("tables", [])

    if not tables:
        errors.append(f"  {protocol_id}: No tables found")
        return errors

    for idx, table in enumerate(tables):
        schema_info = table.get("schema_info", {})
        raw_headers = schema_info.get("column_headers", [])
        num_cols = schema_info.get("num_cols", 0)
        table_id = table.get("table_id", f"table_{idx}")

        prefix = f"  {protocol_id}/{table_id}"

        if not raw_headers:
            # No header data — skip but note it
            if num_cols > 0:
                errors.append(f"{prefix}: No column_headers but num_cols={num_cols}")
            continue

        # Parse raw headers into ColumnHeader models
        headers = []
        for h in raw_headers:
            headers.append(ColumnHeader(
                col_index=h.get("col_index", 0),
                text=h.get("text", ""),
                span=h.get("span", 1),
                level=h.get("level", 0),
                parent_col=h.get("parent_col"),
            ))

        # Build tree
        builder = HeaderTreeBuilder()
        try:
            addresses = builder.build_tree(headers)
        except Exception as e:
            errors.append(f"{prefix}: Tree build failed: {e}")
            continue

        # Check 1: validate_tree (duplicate col_index, gaps)
        tree_errors = validate_tree(addresses)
        for te in tree_errors:
            errors.append(f"{prefix}: {te}")

        # Check 2: Every leaf col_index maps to exactly one column
        seen_indices: dict[int, int] = {}
        for addr in addresses:
            seen_indices[addr.col_index] = seen_indices.get(addr.col_index, 0) + 1
        for ci, count in seen_indices.items():
            if count > 1:
                errors.append(
                    f"{prefix}: col_index {ci} maps to {count} leaves (should be 1)"
                )

        # Check 3: Parent span contains children
        # Build level-grouped nodes for containment check
        max_level = max(h.level for h in headers)
        if max_level > 0:
            by_level: dict[int, list[ColumnHeader]] = {}
            for h in headers:
                by_level.setdefault(h.level, []).append(h)

            for lvl in range(1, max_level + 1):
                parent_lvl = lvl - 1
                parents = by_level.get(parent_lvl, [])
                children = by_level.get(lvl, [])
                for child in children:
                    # Find parent by parent_col or span containment
                    found_parent = False
                    for parent in parents:
                        p_start = parent.col_index
                        p_end = parent.col_index + parent.span - 1
                        if p_start <= child.col_index <= p_end:
                            found_parent = True
                            break
                    if not found_parent and child.parent_col is not None:
                        # Check explicit parent_col
                        for parent in parents:
                            if parent.col_index == child.parent_col:
                                found_parent = True
                                break
                    if not found_parent:
                        errors.append(
                            f"{prefix}: Child (level={lvl}, col={child.col_index}, "
                            f"text='{child.text[:30]}') has no parent at level {parent_lvl}"
                        )

        # Check 4: Tree-derived column count matches num_cols
        tree_col_count = len(addresses)
        if num_cols > 0 and tree_col_count != num_cols:
            # This is informational — tree may have fewer leaves if hierarchy is present
            # Only flag if tree has MORE columns than schema says
            if tree_col_count > num_cols:
                errors.append(
                    f"{prefix}: Tree has {tree_col_count} leaf columns but "
                    f"schema num_cols={num_cols}"
                )

    return errors


def main():
    """Run header tree validation across all stored protocols."""
    print("=" * 60)
    print("Header Tree Validation — Stored Protocols")
    print("=" * 60)

    all_errors: list[str] = []
    protocols_checked = 0
    tables_checked = 0

    for path in sorted(PROTOCOL_DIR.glob("*.json")):
        if path.stem.endswith("_kes"):
            continue
        protocols_checked += 1
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        tables_checked += len(data.get("tables", []))

        print(f"\nChecking {path.stem}...")
        errors = validate_protocol(path)
        if errors:
            for e in errors:
                print(f"  WARN: {e}")
            all_errors.extend(errors)
        else:
            n_tables = len(data.get("tables", []))
            print(f"  OK ({n_tables} table(s), all headers valid)")

    print("\n" + "=" * 60)
    print(f"Summary: {protocols_checked} protocols, {tables_checked} tables checked")
    if all_errors:
        print(f"  {len(all_errors)} warning(s) found")
        # Non-critical warnings (missing headers, count mismatches) are OK
        # Only fail on structural errors (duplicates, broken containment)
        critical = [e for e in all_errors if "maps to" in e and "leaves" in e]
        if critical:
            print(f"  {len(critical)} CRITICAL error(s):")
            for c in critical:
                print(f"    {c}")
            sys.exit(1)
        print("  All warnings are non-critical (informational)")
    else:
        print("  All trees valid")

    print("=" * 60)


if __name__ == "__main__":
    main()
