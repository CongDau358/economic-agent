from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Literal

LifecycleState = Literal["ingestion", "processing", "active", "review", "archived"]

ARCHIVE_YEAR_GAP = 5
REVIEW_YEAR_GAP = 3
NEWS_ARCHIVE_YEAR_GAP = 2

RANK_MULTIPLIER: Dict[LifecycleState, float] = {
    "ingestion": 0.0,
    "processing": 0.0,
    "active": 1.0,
    "review": 0.75,
    "archived": 0.45,
}


@dataclass(frozen=True)
class LifecycleDecision:
    state: LifecycleState
    rank_multiplier: float
    reason: str


def _current_year() -> int:
    return datetime.now(timezone.utc).year


def _parse_year(value: str) -> int | None:
    value = (value or "").strip()
    if not value.isdigit() or len(value) != 4:
        return None
    return int(value)


def resolve_lifecycle_state(metadata: Dict[str, str]) -> LifecycleDecision:
    explicit = str(metadata.get("lifecycle_state", "")).strip().lower()
    if explicit in RANK_MULTIPLIER:
        return LifecycleDecision(
            state=explicit,  # type: ignore[arg-type]
            rank_multiplier=RANK_MULTIPLIER[explicit],  # type: ignore[index]
            reason=f"explicit lifecycle_state={explicit}",
        )

    source = str(metadata.get("source", metadata.get("source_type", ""))).strip().lower()
    year = _parse_year(str(metadata.get("year", "")))
    now = _current_year()

    if year is None:
        return LifecycleDecision("active", RANK_MULTIPLIER["active"], "missing year defaults to active")

    age = now - year
    if source == "news" and age >= NEWS_ARCHIVE_YEAR_GAP:
        return LifecycleDecision("archived", RANK_MULTIPLIER["archived"], "news exceeded archive age threshold")
    if age >= ARCHIVE_YEAR_GAP:
        return LifecycleDecision("archived", RANK_MULTIPLIER["archived"], "document exceeded archive age threshold")
    if age >= REVIEW_YEAR_GAP:
        return LifecycleDecision("review", RANK_MULTIPLIER["review"], "document exceeded review age threshold")

    return LifecycleDecision("active", RANK_MULTIPLIER["active"], "within freshness window")


def stamp_lifecycle(
    metadata: Dict[str, str],
    state: LifecycleState,
    *,
    reason: str = "",
) -> Dict[str, str]:
    updated = dict(metadata)
    updated["lifecycle_state"] = state
    updated["lifecycle_updated_at"] = datetime.now(timezone.utc).isoformat()
    if reason:
        updated["lifecycle_reason"] = reason
    decision = resolve_lifecycle_state(updated)
    updated["retrieval_rank_multiplier"] = str(decision.rank_multiplier)
    return updated


def apply_ingestion_lifecycle(record: Dict[str, str]) -> Dict[str, str]:
    meta = stamp_lifecycle(dict(record), "ingestion", reason="document accepted for ingestion")
    if "text" in record:
        meta["text"] = record["text"]
    return meta


def apply_processing_lifecycle(record: Dict[str, str]) -> Dict[str, str]:
    meta = stamp_lifecycle(dict(record), "processing", reason="extraction chunking embedding in progress")
    if "text" in record:
        meta["text"] = record["text"]
    return meta


def apply_post_validation_lifecycle(record: Dict[str, str]) -> Dict[str, str]:
    meta = dict(record)
    decision = resolve_lifecycle_state(meta)
    state: LifecycleState = "active" if decision.state in {"active", "review"} else decision.state
    return stamp_lifecycle(meta, state, reason=decision.reason)


def apply_retrieval_lifecycle(metadata: Dict[str, str]) -> LifecycleDecision:
    return resolve_lifecycle_state(metadata)


def lifecycle_rank_multiplier(metadata: Dict[str, str]) -> float:
    explicit = metadata.get("retrieval_rank_multiplier")
    if explicit:
        try:
            return float(explicit)
        except ValueError:
            pass
    return resolve_lifecycle_state(metadata).rank_multiplier
