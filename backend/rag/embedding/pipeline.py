from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Set

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from .constants import EMBEDDING_VERSION, MIN_EMBED_CHARS
from .model import resolve_embedding_model
from .normalizer import normalize_chunk_text, normalize_query_text


@dataclass
class EmbeddedRecord:
    chunk_id: str
    embedding_text: str
    display_text: str
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class EmbeddingBatchResult:
    embedded_count: int
    skipped_count: int
    duplicate_count: int
    model: str
    model_version: str


class EmbeddingPipeline:
    def __init__(self, persist_directory: str, collection_name: str = "economic_agent_docs") -> None:
        self.model_name, self._embeddings, self._dimension = resolve_embedding_model()
        self.model_version = EMBEDDING_VERSION
        self._store = Chroma(
            collection_name=collection_name,
            persist_directory=persist_directory,
            embedding_function=self._embeddings,
            collection_metadata={"hnsw:space": "cosine"},
        )
        self._seen_hashes: Set[str] = set()

    def _text_hash(self, embedding_text: str, chunk_id: str) -> str:
        payload = f"{self.model_name}:{self.model_version}:{chunk_id}:{embedding_text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def prepare_records(
        self, records: List[Dict[str, str]]
    ) -> tuple[List[EmbeddedRecord], int, int]:
        prepared: List[EmbeddedRecord] = []
        skipped = 0
        duplicate = 0
        for record in records:
            display_text = str(record.get("text", "")).strip()
            if len(display_text) < MIN_EMBED_CHARS:
                skipped += 1
                continue

            metadata = {k: str(v) for k, v in record.items() if k != "text"}
            embedding_text = normalize_chunk_text(display_text, metadata)
            if len(embedding_text) < MIN_EMBED_CHARS:
                skipped += 1
                continue

            chunk_id = metadata.get("chunk_id") or self._text_hash(embedding_text, display_text[:80])
            metadata["chunk_id"] = chunk_id
            metadata["text"] = display_text
            metadata["embedding_model"] = self.model_name
            metadata["embedding_version"] = self.model_version
            metadata["embedding_dimension"] = str(self._dimension)
            metadata["embedded_at"] = datetime.now(timezone.utc).isoformat()

            text_hash = self._text_hash(embedding_text, chunk_id)
            if text_hash in self._seen_hashes:
                duplicate += 1
                continue
            self._seen_hashes.add(text_hash)
            metadata["embedding_text_hash"] = text_hash

            prepared.append(
                EmbeddedRecord(
                    chunk_id=chunk_id,
                    embedding_text=embedding_text,
                    display_text=display_text,
                    metadata=metadata,
                )
            )
        return prepared, skipped, duplicate

    def embed_and_store(
        self,
        records: List[Dict[str, str]],
        *,
        max_retries: int = 2,
    ) -> EmbeddingBatchResult:
        prepared, skipped, duplicate = self.prepare_records(records)

        if not prepared:
            return EmbeddingBatchResult(
                embedded_count=0,
                skipped_count=len(records),
                duplicate_count=0,
                model=self.model_name,
                model_version=self.model_version,
            )

        ids = [item.chunk_id for item in prepared]
        texts = [item.embedding_text for item in prepared]
        metadatas = [item.metadata for item in prepared]

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                self._store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
                return EmbeddingBatchResult(
                    embedded_count=len(prepared),
                    skipped_count=skipped,
                    duplicate_count=duplicate,
                    model=self.model_name,
                    model_version=self.model_version,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < max_retries:
                    time.sleep(0.5 * (attempt + 1))
        if last_error:
            raise last_error
        return EmbeddingBatchResult(
            embedded_count=0,
            skipped_count=len(records),
            duplicate_count=0,
            model=self.model_name,
            model_version=self.model_version,
        )

    def query_normalized(self, question: str, top_k: int = 4) -> List[tuple[Document, float]]:
        normalized = normalize_query_text(question)
        return self._store.similarity_search_with_score(normalized, k=top_k)
