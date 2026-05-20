from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

ConfidenceBand = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]

# Higher = more trusted (aligned with source-priority-rules.md)
SOURCE_TRUST: Dict[str, float] = {
    "pdf": 1.0,
    "excel": 0.95,
    "text": 0.75,
    "news": 0.6,
    "unknown": 0.4,
}

MIN_CHUNKS_FOR_ANSWER = 1
MIN_CHUNKS_FOR_STRATEGIC = 2
MIN_TRUST_FOR_STRATEGIC = 0.6
LOW_CONFIDENCE_THRESHOLD = 0.45
HIGH_CONFIDENCE_THRESHOLD = 0.70
MAX_DISTANCE_FOR_RELEVANCE = 1.25


@dataclass(frozen=True)
class GovernedChunk:
    text: str
    metadata: Dict[str, str]
    relevance_score: float
    trust_score: float
    combined_score: float


@dataclass
class RetrievalAssessment:
    status: Literal["OK", "INSUFFICIENT_DATA", "LOW_CONFIDENCE"]
    chunk_count: int
    trusted_chunk_count: int
    warnings: List[str] = field(default_factory=list)
    confidence_value: float = 0.0
    confidence_band: ConfidenceBand = "INSUFFICIENT"
    confidence_reasoning: str = ""


def source_trust(source_type: str) -> float:
    return SOURCE_TRUST.get((source_type or "unknown").strip().lower(), SOURCE_TRUST["unknown"])


def _normalize_distance(distance: float) -> float:
    """Map vector distance to a 0–1 relevance score (higher is better)."""
    return max(0.0, min(1.0, 1.0 - (distance / max(MAX_DISTANCE_FOR_RELEVANCE, 1e-6))))


def _text_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())[:500]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def rerank_and_deduplicate(
    contexts: List[Dict[str, str]],
    distances: Optional[List[float]] = None,
) -> List[GovernedChunk]:
    """Rerank by blended relevance + trust; drop duplicates and weak relevance."""
    governed: List[GovernedChunk] = []
    seen: set[str] = set()

    for idx, ctx in enumerate(contexts):
        text = (ctx.get("text") or "").strip()
        if not text:
            continue
        fp = _text_fingerprint(text)
        if fp in seen:
            continue
        seen.add(fp)

        st = source_trust(str(ctx.get("source_type", "unknown")))
        rel = _normalize_distance(distances[idx]) if distances and idx < len(distances) else 0.55
        if rel < 0.2:
            continue

        from ..memory.lifecycle import lifecycle_rank_multiplier

        lifecycle_mult = lifecycle_rank_multiplier({k: str(v) for k, v in ctx.items()})
        combined = round(((0.55 * rel) + (0.45 * st)) * lifecycle_mult, 4)
        governed.append(
            GovernedChunk(
                text=text,
                metadata={k: str(v) for k, v in ctx.items() if k != "text"},
                relevance_score=round(rel, 4),
                trust_score=st,
                combined_score=combined,
            )
        )

    governed.sort(key=lambda c: c.combined_score, reverse=True)
    return governed


def _is_strategic_question(question: str) -> bool:
    q = question.lower()
    markers = (
        "risk",
        "opportunity",
        "outlook",
        "forecast",
        "trend",
        "strategy",
        "recommend",
        "should",
        "rủi ro",
        "cơ hội",
        "xu hướng",
        "dự báo",
    )
    return any(m in q for m in markers)


def assess_retrieval(
    question: str,
    governed: List[GovernedChunk],
) -> RetrievalAssessment:
    warnings: List[str] = []
    trusted = [c for c in governed if c.trust_score >= MIN_TRUST_FOR_STRATEGIC]
    count = len(governed)

    if count < MIN_CHUNKS_FOR_ANSWER:
        return RetrievalAssessment(
            status="INSUFFICIENT_DATA",
            chunk_count=count,
            trusted_chunk_count=len(trusted),
            warnings=["No relevant retrieved chunks met the minimum evidence threshold."],
            confidence_value=0.25,
            confidence_band="INSUFFICIENT",
            confidence_reasoning="Retrieval returned no usable evidence for this question.",
        )

    strategic = _is_strategic_question(question)
    if strategic and count < MIN_CHUNKS_FOR_STRATEGIC:
        warnings.append(
            "Strategic question requires at least 2 supporting chunks; only "
            f"{count} chunk(s) available."
        )
    if strategic and len(trusted) < 1:
        warnings.append(
            "No medium- or high-trust sources in retrieval set; prefer uploading official reports."
        )

    avg_rel = sum(c.relevance_score for c in governed) / count
    avg_trust = sum(c.trust_score for c in governed) / count
    avg_combined = sum(c.combined_score for c in governed) / count

    confidence_value = round(min(1.0, (0.5 * avg_combined) + (0.3 * avg_rel) + (0.2 * avg_trust)), 3)

    if strategic and (count < MIN_CHUNKS_FOR_STRATEGIC or len(trusted) < 1):
        confidence_value = min(confidence_value, 0.4)

    if avg_trust <= MIN_TRUST_FOR_STRATEGIC:
        warnings.append(
            "Retrieval is dominated by low-trust sources; treat conclusions as preliminary."
        )

    if confidence_value < LOW_CONFIDENCE_THRESHOLD:
        band: ConfidenceBand = "LOW"
        status: Literal["OK", "INSUFFICIENT_DATA", "LOW_CONFIDENCE"] = "LOW_CONFIDENCE"
        warnings.append(
            "Low-confidence retrieval: financial claims must be limited to cited evidence only."
        )
    elif confidence_value >= HIGH_CONFIDENCE_THRESHOLD:
        band = "HIGH"
        status = "OK"
    else:
        band = "MEDIUM"
        status = "OK"

    if strategic and count < MIN_CHUNKS_FOR_STRATEGIC:
        return RetrievalAssessment(
            status="INSUFFICIENT_DATA",
            chunk_count=count,
            trusted_chunk_count=len(trusted),
            warnings=warnings,
            confidence_value=min(confidence_value, 0.35),
            confidence_band="INSUFFICIENT",
            confidence_reasoning=(
                "Insufficient evidence for strategic claims; need more supporting chunks."
            ),
        )

    return RetrievalAssessment(
        status=status,
        chunk_count=count,
        trusted_chunk_count=len(trusted),
        warnings=warnings,
        confidence_value=confidence_value,
        confidence_band=band,
        confidence_reasoning=(
            f"Retrieval quality based on {count} chunk(s), "
            f"avg relevance {avg_rel:.2f}, avg trust {avg_trust:.2f}."
        ),
    )


def governed_to_context_dicts(governed: List[GovernedChunk]) -> List[Dict[str, str]]:
    return [{"text": c.text, **c.metadata} for c in governed]


def apply_retrieval_governance(
    question: str,
    contexts: List[Dict[str, str]],
    distances: Optional[List[float]] = None,
) -> Tuple[List[Dict[str, str]], RetrievalAssessment]:
    governed = rerank_and_deduplicate(contexts, distances)
    assessment = assess_retrieval(question, governed)
    return governed_to_context_dicts(governed), assessment
