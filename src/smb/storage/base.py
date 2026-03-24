"""Abstract storage interface for SMB models."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.smb.core.model import StructuredModel


class SMBStore(ABC):
    """Abstract storage backend for structured models."""

    @abstractmethod
    def save_model(self, model: StructuredModel) -> None:
        """Persist a structured model."""

    @abstractmethod
    def load_model(self, document_id: str) -> StructuredModel | None:
        """Load a structured model by document ID."""

    @abstractmethod
    def list_models(self) -> list[str]:
        """List all stored document IDs."""

    @abstractmethod
    def delete_model(self, document_id: str) -> bool:
        """Delete a stored model. Returns True if found and deleted."""
