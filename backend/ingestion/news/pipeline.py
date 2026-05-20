from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .chunker import NewsChunk, build_chunks
from .extractor import extract_from_text, extract_from_url
from .sentiment import SentimentResult, analyze_sentiment
from .topics import detect_topics


@dataclass
class NewsPipelineResult:
    content_type: str
    publisher: str
    publication_date: str
    topic: str
    industry: str
    sentiment: str
    sentiment_score: float
    topics: List[str] = field(default_factory=list)
    chunks: List[Dict[str, str]] = field(default_factory=list)


def _chunks_to_records(
    chunks: List[NewsChunk],
    *,
    company: str,
    sector: str,
    raw_ref: str,
    processed_file: str,
    doc_id: str,
    content_type: str,
) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for chunk in chunks:
        records.append(
            {
                "text": chunk.text,
                "chunk_id": chunk.chunk_id,
                "doc_id": doc_id,
                "company": company,
                "sector": sector,
                "source_type": "news",
                "content_type": content_type,
                "chunk_type": chunk.chunk_type,
                "publisher": chunk.publisher,
                "publication_date": chunk.publication_date,
                "topic": chunk.topic,
                "topics": ",".join(chunk.topics),
                "industry": chunk.industry,
                "sentiment": chunk.sentiment,
                "sentiment_score": str(chunk.sentiment_score),
                "reliability": "medium",
                "raw_ref": raw_ref,
                "processed_file": processed_file,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return records


def process_news_article(
    *,
    company: str,
    sector: str,
    raw_ref: str,
    processed_file: str,
    doc_id: str | None = None,
    url: str = "",
    text: str = "",
    publisher: str = "",
) -> NewsPipelineResult:
    resolved_doc_id = doc_id or processed_file
    if url.strip():
        article = extract_from_url(url.strip())
        raw_ref = raw_ref or url.strip()
    elif text.strip():
        article = extract_from_text(
            text.strip(),
            publisher=publisher.strip() or "social",
        )
        raw_ref = raw_ref or "inline_news"
    else:
        return NewsPipelineResult(
            content_type="unknown",
            publisher="unknown",
            publication_date="",
            topic="general",
            industry=sector,
            sentiment="neutral",
            sentiment_score=0.0,
        )

    industry = sector.strip() or "unknown"
    combined = f"{article.title}\n{article.body}"
    topics = detect_topics(combined, industry=industry)
    sentiment = analyze_sentiment(combined)
    news_chunks = build_chunks(
        article,
        doc_id=resolved_doc_id,
        industry=industry,
        topics=topics,
        sentiment=sentiment,
    )
    records = _chunks_to_records(
        news_chunks,
        company=company,
        sector=sector,
        raw_ref=raw_ref,
        processed_file=processed_file,
        doc_id=resolved_doc_id,
        content_type=article.content_type,
    )

    return NewsPipelineResult(
        content_type=article.content_type,
        publisher=article.publisher,
        publication_date=article.publication_date,
        topic=topics[0],
        industry=industry,
        sentiment=sentiment.label,
        sentiment_score=sentiment.score,
        topics=topics,
        chunks=records,
    )
