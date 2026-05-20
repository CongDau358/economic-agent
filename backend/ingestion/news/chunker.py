from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..chunking.strategy import ChunkType, build_semantic_chunks
from .extractor import ExtractedArticle
from .sentiment import SentimentResult


@dataclass
class NewsChunk:
    text: str
    chunk_id: str
    chunk_index: int
    chunk_type: str
    publisher: str
    publication_date: str
    topic: str
    industry: str
    sentiment: str
    sentiment_score: float
    topics: List[str] = field(default_factory=list)


def build_chunks(
    article: ExtractedArticle,
    *,
    doc_id: str,
    industry: str,
    topics: List[str],
    sentiment: SentimentResult,
) -> List[NewsChunk]:
    body = article.body
    if article.title:
        body = f"{article.title}\n\n{body}".strip()

    primary_topic = topics[0] if topics else "general"
    header = (
        f"[NEWS | Publisher: {article.publisher} | Date: {article.publication_date} | "
        f"Topic: {primary_topic} | Industry: {industry} | Sentiment: {sentiment.label}]"
    )
    semantic = build_semantic_chunks(
        doc_id=doc_id,
        body=body,
        profile_name="news",
        context_header=header,
        source_hint=primary_topic,
    )

    result: List[NewsChunk] = []
    for item in semantic:
        chunk_type = (
            ChunkType.NEWS_EVENT.value
            if item.chunk_type == ChunkType.GENERAL
            else item.chunk_type.value
        )
        result.append(
            NewsChunk(
                text=item.text,
                chunk_id=item.chunk_id,
                chunk_index=item.chunk_index,
                chunk_type=chunk_type,
                publisher=article.publisher,
                publication_date=article.publication_date,
                topic=primary_topic,
                industry=industry,
                sentiment=sentiment.label,
                sentiment_score=sentiment.score,
                topics=topics,
            )
        )
    return result
