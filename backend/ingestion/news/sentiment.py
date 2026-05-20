from __future__ import annotations

from dataclasses import dataclass

from .constants import NEGATIVE_TERMS, POSITIVE_TERMS


@dataclass
class SentimentResult:
    label: str
    score: float


def analyze_sentiment(text: str) -> SentimentResult:
    lower = text.lower()
    pos = sum(1 for term in POSITIVE_TERMS if term in lower)
    neg = sum(1 for term in NEGATIVE_TERMS if term in lower)
    total = pos + neg
    if total == 0:
        return SentimentResult(label="neutral", score=0.0)
    score = round((pos - neg) / max(total, 1), 3)
    if score >= 0.2:
        return SentimentResult(label="positive", score=min(1.0, score))
    if score <= -0.2:
        return SentimentResult(label="negative", score=max(-1.0, score))
    return SentimentResult(label="neutral", score=score)
