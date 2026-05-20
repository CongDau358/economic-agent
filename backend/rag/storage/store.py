from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from langchain_core.documents import Document

from ..embedding.pipeline import EmbeddingBatchResult, EmbeddingPipeline
from .metadata import (
    build_chroma_filter,
    normalize_storage_metadata,
    validate_storage_metadata,
)


@dataclass(frozen=True)
class StorageStats:
    collection_name: str
    persist_directory: str
    embedding_model: str


@dataclass(frozen=True)
class StoredRetrievalResult:
    text: str
    metadata: Dict[str, str]
    distance: float
    chunk_id: str


class VectorStorageSystem:
    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "economic_agent_docs",
    ) -> None:
        os.makedirs(persist_directory, exist_ok=True)
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._pipeline = EmbeddingPipeline(
            persist_directory=persist_directory,
            collection_name=collection_name,
        )

    @property
    def embedding_model(self) -> str:
        return self._pipeline.model_name

    def _prepare_for_storage(self, records: List[Dict[str, str]]) -> List[Dict[str, str]]:
        prepared: List[Dict[str, str]] = []
        for record in records:
            meta = normalize_storage_metadata(record)
            errors = validate_storage_metadata(meta)
            if errors:
                continue
            prepared.append(meta)
        return prepared

    def upsert_chunks(self, records: List[Dict[str, str]]) -> EmbeddingBatchResult:
        storage_records = self._prepare_for_storage(records)
        if not storage_records:
            return EmbeddingBatchResult(
                embedded_count=0,
                skipped_count=len(records),
                duplicate_count=0,
                model=self._pipeline.model_name,
                model_version=self._pipeline.model_version,
            )

        existing_ids: set[str] = set()
        try:
            existing = self._pipeline._store._collection.get(ids=[r["chunk_id"] for r in storage_records])  # noqa: SLF001
            existing_ids = set(existing.get("ids") or [])
        except Exception:
            existing_ids = set()

        if existing_ids:
            try:
                self._pipeline._store._collection.delete(ids=list(existing_ids))  # noqa: SLF001
            except Exception:
                pass

        return self._pipeline.embed_and_store(storage_records)

    def query(
        self,
        question: str,
        *,
        top_k: int = 4,
        company: str | None = None,
        industry: str | None = None,
        year: str | None = None,
        source: str | None = None,
        document_type: str | None = None,
        fetch_k: int | None = None,
    ) -> List[StoredRetrievalResult]:
        search_k = fetch_k or max(top_k * 3, top_k)
        filter_clause = build_chroma_filter(
            company=company,
            industry=industry,
            year=year,
            source=source,
            document_type=document_type,
        )

        if filter_clause:
            pairs = self._query_with_filter(question, filter_clause, top_k=search_k)
        else:
            pairs = self._pipeline.query_normalized(question, top_k=search_k)

        results: List[StoredRetrievalResult] = []
        for doc, score in pairs:
            metadata = {k: str(v) for k, v in doc.metadata.items()}
            if company and metadata.get("company") != company:
                continue
            if industry and metadata.get("industry") != industry:
                continue
            if year and metadata.get("year") != year:
                continue
            if source and metadata.get("source") != source:
                continue
            if document_type and metadata.get("document_type") != document_type:
                continue
            results.append(
                StoredRetrievalResult(
                    text=str(metadata.get("text") or doc.page_content),
                    metadata=metadata,
                    distance=float(score),
                    chunk_id=str(metadata.get("chunk_id", "")),
                )
            )
            if len(results) >= top_k:
                break

        if not results and filter_clause:
            pairs = self._pipeline.query_normalized(question, top_k=top_k)
            for doc, score in pairs:
                metadata = {k: str(v) for k, v in doc.metadata.items()}
                results.append(
                    StoredRetrievalResult(
                        text=str(metadata.get("text") or doc.page_content),
                        metadata=metadata,
                        distance=float(score),
                        chunk_id=str(metadata.get("chunk_id", "")),
                    )
                )
        return results[:top_k]

    def _query_with_filter(
        self,
        question: str,
        filter_clause: Dict[str, object],
        *,
        top_k: int,
    ) -> List[tuple[Document, float]]:
        from ..embedding.normalizer import normalize_query_text

        normalized = normalize_query_text(question)
        try:
            return self._pipeline._store.similarity_search_with_score(  # type: ignore[return-value]
                normalized,
                k=top_k,
                filter=filter_clause,
            )
        except Exception:
            return self._pipeline.query_normalized(question, top_k=top_k)

    def get_by_chunk_id(self, chunk_id: str) -> StoredRetrievalResult | None:
        try:
            data = self._pipeline._store._collection.get(ids=[chunk_id], include=["metadatas", "documents"])  # noqa: SLF001
            ids = data.get("ids") or []
            if not ids:
                return None
            metadata = {k: str(v) for k, v in (data.get("metadatas") or [{}])[0].items()}
            text = str((data.get("documents") or [""])[0] or metadata.get("text", ""))
            return StoredRetrievalResult(
                text=text,
                metadata=metadata,
                distance=0.0,
                chunk_id=chunk_id,
            )
        except Exception:
            return None

    def stats(self) -> StorageStats:
        return StorageStats(
            collection_name=self.collection_name,
            persist_directory=self.persist_directory,
            embedding_model=self._pipeline.model_name,
        )
