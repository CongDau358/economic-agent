from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .embedding.pipeline import EmbeddingBatchResult
from .storage.store import StoredRetrievalResult, VectorStorageSystem


@dataclass(frozen=True)
class RetrievalResult:
    text: str
    metadata: Dict[str, str]
    distance: float = 1.0
    chunk_id: str = ""


class VectorStoreService:
    def __init__(self, persist_directory: str) -> None:
        self._storage = VectorStorageSystem(persist_directory=persist_directory)

    def add_documents(self, records: List[Dict[str, str]]) -> EmbeddingBatchResult:
        return self._storage.upsert_chunks(records)

    def query(
        self,
        question: str,
        top_k: int = 4,
        *,
        company: Optional[str] = None,
        industry: Optional[str] = None,
        year: Optional[str] = None,
        source: Optional[str] = None,
        document_type: Optional[str] = None,
    ) -> List[RetrievalResult]:
        hits = self._storage.query(
            question,
            top_k=top_k,
            company=company,
            industry=industry,
            year=year,
            source=source,
            document_type=document_type,
        )
        return [
            RetrievalResult(
                text=item.text,
                metadata=item.metadata,
                distance=item.distance,
                chunk_id=item.chunk_id,
            )
            for item in hits
        ]

    def get_by_chunk_id(self, chunk_id: str) -> RetrievalResult | None:
        hit = self._storage.get_by_chunk_id(chunk_id)
        if hit is None:
            return None
        return RetrievalResult(
            text=hit.text,
            metadata=hit.metadata,
            distance=hit.distance,
            chunk_id=hit.chunk_id,
        )

    @property
    def embedding_model(self) -> str:
        return self._storage.embedding_model
