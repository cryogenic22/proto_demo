"""Tests for KEStore singleton behaviour."""

from src.persistence.ke_store import create_ke_store, reset_ke_store


class TestKEStoreSingleton:
    def setup_method(self):
        reset_ke_store()

    def teardown_method(self):
        reset_ke_store()

    def test_singleton_returns_same_instance(self):
        """Two consecutive calls must return the identical object."""
        store_a = create_ke_store()
        store_b = create_ke_store()
        assert store_a is store_b

    def test_reset_clears_instance(self):
        """After reset, a new instance must be created."""
        store_a = create_ke_store()
        reset_ke_store()
        store_b = create_ke_store()
        assert store_a is not store_b
