"""In-memory storage for SMB models — used for testing and standalone mode."""

from __future__ import annotations

from src.smb.core.model import StructuredModel
from src.smb.storage.base import SMBStore


class MemoryStore(SMBStore):
    """In-memory model storage. Data lost on process restart."""

    def __init__(self) -> None:
        self._models: dict[str, StructuredModel] = {}

    def save_model(self, model: StructuredModel) -> None:
        self._models[model.document_id] = model

    def load_model(self, document_id: str) -> StructuredModel | None:
        return self._models.get(document_id)

    def list_models(self) -> list[str]:
        return list(self._models.keys())

    def delete_model(self, document_id: str) -> bool:
        if document_id in self._models:
            del self._models[document_id]
            return True
        return False
