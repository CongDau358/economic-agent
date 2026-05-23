"""
backend/rag/retriever.py  (TẠO MỚI)

RAG Retriever theo AGENT.md:
- Metadata-constrained retrieval (filter theo company/sector)
- Rerank theo relevance + recency
- Score threshold gate
- INSUFFICIENT_DATA guard
- Citation map đầy đủ
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from typing import Any

log = logging.getLogger("economic_agent.rag")


class RAGRetriever:
    def __init__(self, top_k: int = 5):
        from backend.config import get_settings
        self.settings = get_settings()
        self.top_k = top_k
        self._collection = None
        self._embedder = None
        self._llm = None

    def _get_collection(self):
        if self._collection is None:
            import chromadb
            client = chromadb.PersistentClient(path=self.settings.chroma_persist_dir)
            self._collection = client.get_or_create_collection(
                self.settings.chroma_collection_name
            )
        return self._collection

    def _get_embedder(self):
        if self._embedder is None:
            from langchain_openai import OpenAIEmbeddings
            self._embedder = OpenAIEmbeddings(model=self.settings.openai_embedding_model)
        return self._embedder

    def _get_llm(self):
        if self._llm is None:
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(model=self.settings.openai_model, temperature=0.1)
        return self._llm

    def _retrieve(
        self,
        query: str,
        company: str | None = None,
        sector: str | None = None,
    ) -> list[dict]:
        collection = self._get_collection()
        embedder = self._get_embedder()

        query_emb = embedder.embed_query(query)

        # Build metadata filter
        where: dict | None = None
        if company and sector:
            where = {"$or": [{"company": company}, {"sector": sector}]}
        elif company:
            where = {"company": company}
        elif sector:
            where = {"sector": sector}

        results = collection.query(
            query_embeddings=[query_emb],
            n_results=self.top_k * 2,  # over-fetch for reranking
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        chunks = []
        for doc, meta, dist in zip(docs, metas, distances):
            similarity = 1 - dist  # convert distance to similarity
            if similarity < self.settings.rag_score_threshold:
                continue
            chunks.append({
                "text": doc,
                "source": meta.get("source", "unknown"),
                "company": meta.get("company", ""),
                "sector": meta.get("sector", ""),
                "ingested_at": meta.get("ingested_at", ""),
                "score": round(similarity, 4),
            })

        # Rerank: similarity * recency boost
        def recency_boost(ingested_at: str) -> float:
            try:
                dt = datetime.fromisoformat(ingested_at)
                days_old = (datetime.now(timezone.utc) - dt).days
                return max(0.7, 1.0 - days_old * 0.002)
            except Exception:
                return 0.9

        chunks.sort(
            key=lambda c: c["score"] * recency_boost(c["ingested_at"]),
            reverse=True,
        )
        return chunks[: self.top_k]

    def _build_prompt(self, question: str, chunks: list[dict]) -> str:
        context = "\n\n".join(
            f"[{i+1}] (source: {c['source']}, score: {c['score']})\n{c['text']}"
            for i, c in enumerate(chunks)
        )
        return f"""Bạn là Financial Intelligence Agent. Dựa HOÀN TOÀN vào các đoạn evidence dưới đây để trả lời câu hỏi.

EVIDENCE:
{context}

CÂU HỎI: {question}

YÊU CẦU:
- Chỉ dùng thông tin từ EVIDENCE, không tự bịa thêm facts
- Trích dẫn [số] cho mỗi claim quan trọng
- Nếu evidence không đủ, nói rõ INSUFFICIENT_DATA
- Không đưa ra lời khuyên đầu tư cụ thể

TRẢ LỜI:"""

    def ask(
        self,
        question: str,
        company: str | None = None,
        sector: str | None = None,
    ) -> dict[str, Any]:

        # ── 1. Retrieve ───────────────────────────────────────────────────────
        chunks = self._retrieve(question, company, sector)

        if not chunks:
            return {
                "status": "INSUFFICIENT_DATA",
                "answer": "Không tìm thấy evidence liên quan trong knowledge base. Vui lòng upload thêm dữ liệu.",
                "citations": [],
                "confidence": 0.0,
                "warnings": ["Không có document nào vượt score threshold"],
            }

        log.info("rag.retrieve", extra={"n_chunks": len(chunks), "company": company})

        # ── 2. Generate answer ────────────────────────────────────────────────
        prompt = self._build_prompt(question, chunks)
        llm = self._get_llm()
        answer = llm.invoke(prompt).content

        # ── 3. Confidence from retrieval quality ──────────────────────────────
        avg_score = sum(c["score"] for c in chunks) / len(chunks)
        confidence = round(min(0.95, avg_score * 1.1), 2)

        warnings = []
        if avg_score < 0.6:
            warnings.append("Chất lượng retrieval thấp — kết quả có thể không chính xác")
        if len(chunks) < 3:
            warnings.append("Ít hơn 3 evidence chunks — độ bao phủ có thể chưa đủ")

        return {
            "status": "OK",
            "question": question,
            "answer": answer,
            "citations": [
                {
                    "idx": i + 1,
                    "source": c["source"],
                    "company": c["company"],
                    "score": c["score"],
                    "snippet": c["text"][:200] + "..." if len(c["text"]) > 200 else c["text"],
                }
                for i, c in enumerate(chunks)
            ],
            "confidence": confidence,
            "warnings": warnings,
        }