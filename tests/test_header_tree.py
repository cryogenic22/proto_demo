"""
Tests for TreeThinker-style header tree builder.

Validates:
1. ColumnAddress dataclass — path, display, leaf
2. HeaderTreeBuilder — flat headers, multi-level with parent_col, inferred hierarchy
3. validate_tree — gap detection, overlap detection, span containment
4. Integration — real protocol header patterns (Pfizer, oncology, vaccine)
"""

import pytest

from src.models.schema import ColumnHeader, ColumnAddress
from src.pipeline.header_tree import HeaderTreeBuilder, validate_tree


# ---------------------------------------------------------------------------
# ColumnAddress unit tests
# ---------------------------------------------------------------------------

class TestColumnAddress:
    def test_create_address(self):
        addr = ColumnAddress(path=["Treatment", "Cycle 1", "Day 1"], col_index=2)
        assert addr.display == "Treatment > Cycle 1 > Day 1"
        assert addr.leaf == "Day 1"

    def test_single_level_path(self):
        addr = ColumnAddress(path=["Screening"], col_index=0)
        assert addr.display == "Screening"
        assert addr.leaf == "Screening"
        assert addr.level == 0
        assert addr.span == 1

    def test_empty_path(self):
        addr = ColumnAddress(path=[], col_index=0)
        assert addr.display == ""
        assert addr.leaf == ""

    def test_col_index_and_span(self):
        addr = ColumnAddress(path=["Treatment", "Cycle 1"], col_index=3, span=2, level=1)
        assert addr.col_index == 3
        assert addr.span == 2
        assert addr.level == 1


# ---------------------------------------------------------------------------
# HeaderTreeBuilder unit tests
# ---------------------------------------------------------------------------

class TestHeaderTreeBuilder:
    def test_flat_headers_single_level(self):
        """Single-level headers produce single-element paths."""
        headers = [
            ColumnHeader(col_index=0, text="Screening"),
            ColumnHeader(col_index=1, text="Day 1"),
        ]
        builder = HeaderTreeBuilder()
        addresses = builder.build_tree(headers)
        assert len(addresses) == 2
        assert addresses[0].path == ["Screening"]
        assert addresses[1].path == ["Day 1"]
        assert addresses[0].col_index == 0
        assert addresses[1].col_index == 1

    def test_multi_level_with_parent(self):
        """Headers with level and parent_col produce hierarchical paths."""
        headers = [
            ColumnHeader(col_index=0, text="Procedure", span=1, level=0),
            ColumnHeader(col_index=1, text="Treatment Period", span=5, level=0),
            ColumnHeader(col_index=1, text="Cycle 1", span=2, level=1, parent_col=1),
            ColumnHeader(col_index=1, text="Day 1", span=1, level=2, parent_col=1),
            ColumnHeader(col_index=2, text="Day 8", span=1, level=2, parent_col=1),
            ColumnHeader(col_index=3, text="Cycle 2", span=2, level=1, parent_col=1),
            ColumnHeader(col_index=3, text="Day 1", span=1, level=2, parent_col=3),
            ColumnHeader(col_index=4, text="Day 8", span=1, level=2, parent_col=3),
            ColumnHeader(col_index=5, text="End of Study", span=1, level=0),
        ]
        builder = HeaderTreeBuilder()
        addresses = builder.build_tree(headers)

        # Only leaf columns should appear as addresses
        leaf_indices = {a.col_index for a in addresses}
        assert 0 in leaf_indices   # Procedure
        assert 1 in leaf_indices   # Treatment Period > Cycle 1 > Day 1
        assert 2 in leaf_indices   # Treatment Period > Cycle 1 > Day 8
        assert 3 in leaf_indices   # Treatment Period > Cycle 2 > Day 1
        assert 4 in leaf_indices   # Treatment Period > Cycle 2 > Day 8
        assert 5 in leaf_indices   # End of Study

        day1 = next(a for a in addresses if a.col_index == 1)
        assert day1.path == ["Treatment Period", "Cycle 1", "Day 1"]
        assert day1.display == "Treatment Period > Cycle 1 > Day 1"

        day8_c1 = next(a for a in addresses if a.col_index == 2)
        assert day8_c1.path == ["Treatment Period", "Cycle 1", "Day 8"]

        day1_c2 = next(a for a in addresses if a.col_index == 3)
        assert day1_c2.path == ["Treatment Period", "Cycle 2", "Day 1"]

        eos = next(a for a in addresses if a.col_index == 5)
        assert eos.path == ["End of Study"]

    def test_two_level_headers(self):
        """Two-level headers (no grandchild level)."""
        headers = [
            ColumnHeader(col_index=0, text="Procedure", level=0),
            ColumnHeader(col_index=1, text="Screening", span=2, level=0),
            ColumnHeader(col_index=1, text="Visit 1", level=1, parent_col=1),
            ColumnHeader(col_index=2, text="Visit 2", level=1, parent_col=1),
            ColumnHeader(col_index=3, text="Follow-up", level=0),
        ]
        builder = HeaderTreeBuilder()
        addresses = builder.build_tree(headers)
        assert len(addresses) == 4  # Procedure, Visit 1, Visit 2, Follow-up

        v1 = next(a for a in addresses if a.col_index == 1)
        assert v1.path == ["Screening", "Visit 1"]

        v2 = next(a for a in addresses if a.col_index == 2)
        assert v2.path == ["Screening", "Visit 2"]

    def test_empty_headers(self):
        """Empty headers produce empty addresses."""
        builder = HeaderTreeBuilder()
        addresses = builder.build_tree([])
        assert addresses == []

    def test_all_level_zero(self):
        """All level-0 headers are treated as flat leaves."""
        headers = [
            ColumnHeader(col_index=0, text="A", level=0),
            ColumnHeader(col_index=1, text="B", level=0),
            ColumnHeader(col_index=2, text="C", level=0),
        ]
        builder = HeaderTreeBuilder()
        addresses = builder.build_tree(headers)
        assert len(addresses) == 3
        assert all(len(a.path) == 1 for a in addresses)

    def test_flatten_multi_level_inferred(self):
        """When parent_col is missing, infer hierarchy from spans and positions."""
        headers = [
            ColumnHeader(col_index=0, text="Procedure", span=1, level=0),
            ColumnHeader(col_index=1, text="Treatment Period", span=3, level=0),
            ColumnHeader(col_index=1, text="Day 1", span=1, level=1),
            ColumnHeader(col_index=2, text="Day 15", span=1, level=1),
            ColumnHeader(col_index=3, text="Day 29", span=1, level=1),
        ]
        builder = HeaderTreeBuilder()
        addresses = builder.flatten_multi_level(headers)

        assert len(addresses) == 4  # Procedure + 3 days
        day1 = next(a for a in addresses if a.col_index == 1)
        assert day1.path == ["Treatment Period", "Day 1"]


# ---------------------------------------------------------------------------
# Tree validation tests
# ---------------------------------------------------------------------------

class TestValidateTree:
    def test_valid_tree_no_errors(self):
        """A well-formed tree produces no errors."""
        addresses = [
            ColumnAddress(path=["A"], col_index=0),
            ColumnAddress(path=["B"], col_index=1),
            ColumnAddress(path=["C"], col_index=2),
        ]
        errors = validate_tree(addresses)
        assert len(errors) == 0

    def test_validate_tree_no_gaps(self):
        """Validation catches gaps in column indices."""
        addresses = [
            ColumnAddress(path=["A"], col_index=0),
            ColumnAddress(path=["C"], col_index=2),  # Gap at index 1
        ]
        errors = validate_tree(addresses)
        assert any("gap" in e.lower() for e in errors)

    def test_validate_tree_duplicate_col_index(self):
        """Validation catches duplicate column indices."""
        addresses = [
            ColumnAddress(path=["A"], col_index=0),
            ColumnAddress(path=["B"], col_index=0),  # Duplicate
        ]
        errors = validate_tree(addresses)
        assert any("duplicate" in e.lower() for e in errors)

    def test_validate_empty_tree(self):
        """Empty tree is valid."""
        errors = validate_tree([])
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# Integration tests — real protocol patterns
# ---------------------------------------------------------------------------

class TestTreeIntegration:
    def test_real_protocol_headers_flat(self):
        """Parse actual protocol column headers into tree — flat Pfizer-style."""
        headers = [
            ColumnHeader(col_index=0, text="Procedure", level=0),
            ColumnHeader(col_index=1, text="Screening", level=0),
            ColumnHeader(col_index=2, text="Day 1", level=0),
            ColumnHeader(col_index=3, text="Day 29", level=0),
            ColumnHeader(col_index=4, text="Day 57", level=0),
            ColumnHeader(col_index=5, text="End of Study", level=0),
        ]
        builder = HeaderTreeBuilder()
        addresses = builder.build_tree(headers)
        assert len(addresses) == 6
        assert all(len(a.path) == 1 for a in addresses)  # Single level

    def test_oncology_cycle_headers(self):
        """Oncology protocol with Treatment > Cycle > Day hierarchy."""
        headers = [
            ColumnHeader(col_index=0, text="Assessment", level=0),
            ColumnHeader(col_index=1, text="Screening", level=0),
            ColumnHeader(col_index=2, text="Treatment", span=4, level=0),
            ColumnHeader(col_index=2, text="Cycle 1", span=2, level=1, parent_col=2),
            ColumnHeader(col_index=2, text="Day 1", level=2, parent_col=2),
            ColumnHeader(col_index=3, text="Day 15", level=2, parent_col=2),
            ColumnHeader(col_index=4, text="Cycle 2", span=2, level=1, parent_col=2),
            ColumnHeader(col_index=4, text="Day 1", level=2, parent_col=4),
            ColumnHeader(col_index=5, text="Day 15", level=2, parent_col=4),
            ColumnHeader(col_index=6, text="End of Treatment", level=0),
            ColumnHeader(col_index=7, text="Follow-up", level=0),
        ]
        builder = HeaderTreeBuilder()
        addresses = builder.build_tree(headers)

        # Should have 8 leaf addresses
        assert len(addresses) == 8

        c1d1 = next(a for a in addresses if a.col_index == 2)
        assert c1d1.path == ["Treatment", "Cycle 1", "Day 1"]

        c2d15 = next(a for a in addresses if a.col_index == 5)
        assert c2d15.path == ["Treatment", "Cycle 2", "Day 15"]

    def test_vaccine_period_headers(self):
        """Vaccine protocol with Vaccination Period > Visit hierarchy."""
        headers = [
            ColumnHeader(col_index=0, text="Procedure", level=0),
            ColumnHeader(col_index=1, text="Vaccination Period", span=3, level=0),
            ColumnHeader(col_index=1, text="Visit 1 (Day 1)", level=1, parent_col=1),
            ColumnHeader(col_index=2, text="Visit 2 (Day 29)", level=1, parent_col=1),
            ColumnHeader(col_index=3, text="Visit 3 (Day 57)", level=1, parent_col=1),
            ColumnHeader(col_index=4, text="Follow-up Period", span=2, level=0),
            ColumnHeader(col_index=4, text="Visit 4 (Day 85)", level=1, parent_col=4),
            ColumnHeader(col_index=5, text="Visit 5 (Day 365)", level=1, parent_col=4),
        ]
        builder = HeaderTreeBuilder()
        addresses = builder.build_tree(headers)

        assert len(addresses) == 6  # Procedure + 5 visits

        v1 = next(a for a in addresses if a.col_index == 1)
        assert v1.path == ["Vaccination Period", "Visit 1 (Day 1)"]

        v4 = next(a for a in addresses if a.col_index == 4)
        assert v4.path == ["Follow-up Period", "Visit 4 (Day 85)"]

    def test_backward_compat_no_tree_data(self):
        """Headers with no level/parent info still work (backward compatibility)."""
        headers = [
            ColumnHeader(col_index=0, text="Procedure"),
            ColumnHeader(col_index=1, text="Screening"),
            ColumnHeader(col_index=2, text="Baseline"),
        ]
        builder = HeaderTreeBuilder()
        addresses = builder.build_tree(headers)
        assert len(addresses) == 3
        assert all(len(a.path) == 1 for a in addresses)
        assert all(a.span == 1 for a in addresses)
