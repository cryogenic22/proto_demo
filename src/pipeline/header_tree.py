"""
Header Tree Builder — builds hierarchical column address paths from flat headers.

Takes the ColumnHeader list from structural analysis (which has level and parent_col
fields) and builds a proper tree structure where each leaf column has a full path
like ["Treatment Period", "Cycle 1", "Day 1"].

This is the TreeThinker-style approach: convert flat multi-level headers into
an explicit tree, then flatten back to ColumnAddress objects with full paths.

Backward compatible: if headers have no level/parent info, they produce
single-element paths (same as before).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from src.models.schema import ColumnAddress, ColumnHeader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal tree node
# ---------------------------------------------------------------------------

class _HeaderNode:
    """Internal tree node for building the header hierarchy."""

    def __init__(self, text: str, col_start: int, span: int, level: int):
        self.text = text
        self.col_start = col_start
        self.span = span
        self.level = level
        self.children: list[_HeaderNode] = []

    @property
    def col_end(self) -> int:
        return self.col_start + self.span - 1

    def contains(self, col_index: int) -> bool:
        return self.col_start <= col_index <= self.col_end


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class HeaderTreeBuilder:
    """Builds a hierarchical header tree from flat column headers.

    Takes the existing ColumnHeader list (which has level and parent_col)
    and builds a proper tree structure with full paths.
    """

    def build_tree(self, headers: list[ColumnHeader]) -> list[ColumnAddress]:
        """Convert flat headers with level/parent_col into ColumnAddress with full paths.

        Strategy:
        1. Group headers by level.
        2. Build parent-child relationships using parent_col and span containment.
        3. Walk the tree to produce one ColumnAddress per leaf column.

        If all headers are level 0 with span 1 (flat), each gets a single-element path.
        """
        if not headers:
            return []

        max_level = max(h.level for h in headers)

        # Fast path: all flat headers — no hierarchy to resolve
        if max_level == 0:
            return self._flat_addresses(headers)

        # Build the tree from headers grouped by level
        by_level: dict[int, list[ColumnHeader]] = defaultdict(list)
        for h in headers:
            by_level[h.level].append(h)

        # Build nodes for each level
        nodes_by_level: dict[int, list[_HeaderNode]] = {}
        for lvl in sorted(by_level.keys()):
            nodes_by_level[lvl] = [
                _HeaderNode(
                    text=h.text,
                    col_start=h.col_index,
                    span=h.span,
                    level=lvl,
                )
                for h in by_level[lvl]
            ]

        # Link children to parents.
        # Strategy: for each child header, find the parent at the level above
        # using parent_col (explicit) or span containment (fallback).
        for lvl in sorted(by_level.keys()):
            if lvl == 0:
                continue
            parent_lvl = lvl - 1
            parent_nodes = nodes_by_level.get(parent_lvl, [])
            for child_node in nodes_by_level[lvl]:
                child_header = next(
                    (h for h in by_level[lvl]
                     if h.col_index == child_node.col_start and h.text == child_node.text),
                    None,
                )
                parent = self._find_parent(
                    child_node, child_header, parent_nodes
                )
                if parent:
                    parent.children.append(child_node)

        # Walk the tree from level 0 roots, collecting leaf addresses
        roots = nodes_by_level.get(0, [])
        addresses: list[ColumnAddress] = []

        for root in roots:
            self._walk_tree(root, [], addresses)

        # Sort by col_index for deterministic output
        addresses.sort(key=lambda a: a.col_index)
        return addresses

    def flatten_multi_level(self, headers: list[ColumnHeader]) -> list[ColumnAddress]:
        """For headers that don't have parent_col info, infer hierarchy
        from span information and position.

        If a level-0 header has span > 1, all level-1 headers within its
        column range are its children.
        """
        if not headers:
            return []

        max_level = max(h.level for h in headers)
        if max_level == 0:
            return self._flat_addresses(headers)

        # Group by level
        by_level: dict[int, list[ColumnHeader]] = defaultdict(list)
        for h in headers:
            by_level[h.level].append(h)

        # Build nodes
        nodes_by_level: dict[int, list[_HeaderNode]] = {}
        for lvl in sorted(by_level.keys()):
            nodes_by_level[lvl] = [
                _HeaderNode(
                    text=h.text,
                    col_start=h.col_index,
                    span=h.span,
                    level=lvl,
                )
                for h in by_level[lvl]
            ]

        # Infer parent-child from span containment
        for lvl in sorted(by_level.keys()):
            if lvl == 0:
                continue
            parent_lvl = lvl - 1
            parent_nodes = nodes_by_level.get(parent_lvl, [])
            for child_node in nodes_by_level[lvl]:
                for pn in parent_nodes:
                    if pn.contains(child_node.col_start):
                        pn.children.append(child_node)
                        break

        # Walk from roots
        roots = nodes_by_level.get(0, [])
        addresses: list[ColumnAddress] = []
        for root in roots:
            self._walk_tree(root, [], addresses)

        addresses.sort(key=lambda a: a.col_index)
        return addresses

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _flat_addresses(headers: list[ColumnHeader]) -> list[ColumnAddress]:
        """Convert all-level-0 headers into single-element path ColumnAddresses."""
        return [
            ColumnAddress(
                path=[h.text],
                col_index=h.col_index,
                span=h.span,
                level=0,
            )
            for h in headers
        ]

    @staticmethod
    def _find_parent(
        child_node: _HeaderNode,
        child_header: ColumnHeader | None,
        parent_nodes: list[_HeaderNode],
    ) -> _HeaderNode | None:
        """Find the parent node for a child, using parent_col or span containment."""
        # Strategy 1: Use explicit parent_col from the ColumnHeader
        if child_header and child_header.parent_col is not None:
            for pn in parent_nodes:
                if pn.col_start == child_header.parent_col:
                    return pn
                # Also check if parent_col falls within parent's span
                if pn.contains(child_header.parent_col):
                    return pn

        # Strategy 2: Span containment — find the parent whose column range
        # contains the child's col_start
        for pn in parent_nodes:
            if pn.contains(child_node.col_start):
                return pn

        return None

    def _walk_tree(
        self,
        node: _HeaderNode,
        prefix: list[str],
        out: list[ColumnAddress],
    ) -> None:
        """Recursively walk the tree, emitting ColumnAddress for leaf nodes."""
        current_path = prefix + [node.text]

        if not node.children:
            # Leaf node — emit an address
            out.append(ColumnAddress(
                path=current_path,
                col_index=node.col_start,
                span=node.span,
                level=node.level,
            ))
        else:
            # Internal node — recurse into children
            for child in node.children:
                self._walk_tree(child, current_path, out)


# ---------------------------------------------------------------------------
# Tree validation
# ---------------------------------------------------------------------------

def validate_tree(addresses: list[ColumnAddress]) -> list[str]:
    """Check tree integrity.

    Returns a list of error strings (empty = valid tree).

    Checks:
    - Every col_index maps to exactly one leaf (no duplicates)
    - No gaps in col_index sequence
    - No overlapping addresses
    """
    if not addresses:
        return []

    errors: list[str] = []
    col_indices = [a.col_index for a in addresses]

    # Check for duplicates
    seen: dict[int, int] = {}
    for idx in col_indices:
        seen[idx] = seen.get(idx, 0) + 1
    for idx, count in seen.items():
        if count > 1:
            errors.append(
                f"Duplicate col_index {idx}: {count} addresses map to the same column"
            )

    # Check for gaps (only among unique indices)
    if col_indices:
        sorted_indices = sorted(set(col_indices))
        min_idx = sorted_indices[0]
        max_idx = sorted_indices[-1]
        expected = set(range(min_idx, max_idx + 1))
        actual = set(sorted_indices)
        gaps = expected - actual
        if gaps:
            errors.append(
                f"Gap in column indices: missing {sorted(gaps)}"
            )

    return errors


# ---------------------------------------------------------------------------
# VLM tree response parser
# ---------------------------------------------------------------------------

def parse_column_header_tree(tree_data: list[dict]) -> list[ColumnAddress]:
    """Parse a hierarchical column_header_tree from the VLM response.

    Expects the VLM to return a nested structure like:
    [
        {"text": "Treatment Period", "col_start": 2, "col_end": 7, "level": 0,
         "children": [
            {"text": "Cycle 1", "col_start": 2, "col_end": 4, "level": 1,
             "children": [
                {"text": "Day 1", "col_start": 2, "col_end": 2, "level": 2},
                {"text": "Day 8", "col_start": 3, "col_end": 3, "level": 2}
             ]}
         ]}
    ]
    """
    addresses: list[ColumnAddress] = []

    def _walk(node: dict, prefix: list[str]) -> None:
        text = node.get("text", "")
        col_start = node.get("col_start", 0)
        col_end = node.get("col_end", col_start)
        level = node.get("level", 0)
        children = node.get("children", [])
        current_path = prefix + [text]

        if not children:
            # Leaf: emit one address per column in the range
            for col_idx in range(col_start, col_end + 1):
                addresses.append(ColumnAddress(
                    path=current_path,
                    col_index=col_idx,
                    span=1,
                    level=level,
                ))
        else:
            for child in children:
                _walk(child, current_path)

    for root_node in tree_data:
        _walk(root_node, [])

    addresses.sort(key=lambda a: a.col_index)
    return addresses
