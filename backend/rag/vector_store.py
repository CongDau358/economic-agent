from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List

from langchain_community.embeddings import FakeEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document


@dataclass(frozen=True)
class RetrievalResult:
    text: str
    metadata: Dict[str, str]


class VectorStoreService:
    def __init__(self, persist_directory: str) -> None:
        os.makedirs(persist_directory, exist_ok=True)
        self._store = Chroma(
            collection_name="economic_agent_docs",
            persist_directory=persist_directory,
            embedding_function=FakeEmbeddings(size=256),
        )

    def add_documents(self, records: List[Dict[str, str]]) -> None:
        docs = [
            Document(page_content=r["text"], metadata={k: v for k, v in r.items() if k != "text"})
            for r in records
        ]
        if docs:
            self._store.add_documents(docs)

    def query(self, question: str, top_k: int = 4) -> List[RetrievalResult]:
        docs = self._store.similarity_search(question, k=top_k)
        return [
            RetrievalResult(text=d.page_content, metadata={k: str(v) for k, v in d.metadata.items()})
            for d in docs
        ]
