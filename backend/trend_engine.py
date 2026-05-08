from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Dict, List


SIGNAL_SCORES: Dict[str, int] = {
    # Financial
    "revenue_up": 1,
    "profit_down": -1,
    "cost_up": -1,
    # Sentiment
    "positive_news": 1,
    "negative_news": -1,
    # Macro
    "interest_rate_down": 1,
    "policy_support": 1,
}


@dataclass(frozen=True)
class TrendResult:
    summary: str
    signals: Dict[str, List[str]]
    score: Dict[str, float]
    trend: str
    risks: List[str]
    opportunities: List[str]
    confidence: Dict[str, float | str]


def _score_signal(signal: str) -> int:
    return SIGNAL_SCORES.get(signal, 0)


def _avg_score(signals: List[str]) -> float:
    if not signals:
        return 0.0
    return float(mean(_score_signal(s) for s in signals))


def _infer_trend(total_score: float) -> str:
    if total_score > 0.15:
        return "UP"
    if total_score < -0.15:
        return "DOWN"
    return "NEUTRAL"


def _confidence(
    financial_signals: List[str],
    sentiment_signals: List[str],
    macro_signals: List[str],
    financial_avg: float,
    sentiment_avg: float,
    macro_avg: float,
) -> Dict[str, float | str]:
    dimensions_present = sum(
        1 for bucket in (financial_signals, sentiment_signals, macro_signals) if bucket
    )
    completeness = dimensions_present / 3.0

    directional_values = [financial_avg, sentiment_avg, macro_avg]
    non_zero = [x for x in directional_values if abs(x) > 1e-9]
    if not non_zero:
        consistency = 0.5
    else:
        positive = sum(1 for x in non_zero if x > 0)
        negative = sum(1 for x in non_zero if x < 0)
        consistency = max(positive, negative) / len(non_zero)

    confidence_value = max(0.0, min(1.0, (0.6 * completeness) + (0.4 * consistency)))

    if dimensions_present == 2:
        confidence_value = min(confidence_value, 0.55)
    elif dimensions_present <= 1:
        confidence_value = min(confidence_value, 0.35)

    reason = (
        f"completeness={completeness:.2f}, consistency={consistency:.2f}, "
        f"dimensions_present={dimensions_present}/3"
    )
    return {"value": round(confidence_value, 3), "reasoning": reason}


def predict_trend(
    financial_signals: List[str],
    sentiment_signals: List[str],
    macro_signals: List[str],
) -> TrendResult:
    financial_avg = _avg_score(financial_signals)
    sentiment_avg = _avg_score(sentiment_signals)
    macro_avg = _avg_score(macro_signals)

    weighted_total = (financial_avg * 0.5) + (sentiment_avg * 0.3) + (macro_avg * 0.2)
    trend = _infer_trend(weighted_total)

    confidence = _confidence(
        financial_signals=financial_signals,
        sentiment_signals=sentiment_signals,
        macro_signals=macro_signals,
        financial_avg=financial_avg,
        sentiment_avg=sentiment_avg,
        macro_avg=macro_avg,
    )

    risks: List[str] = []
    opportunities: List[str] = []

    for signal in financial_signals + sentiment_signals + macro_signals:
        score = _score_signal(signal)
        if score < 0:
            risks.append(signal)
        elif score > 0:
            opportunities.append(signal)

    if sum(1 for bucket in (financial_signals, sentiment_signals, macro_signals) if bucket) <= 1:
        trend = "INSUFFICIENT_DATA"

    summary = (
        "Deterministic trend inference based on weighted financial, sentiment, and macro signals."
    )

    return TrendResult(
        summary=summary,
        signals={
            "financial": financial_signals,
            "sentiment": sentiment_signals,
            "macro": macro_signals,
        },
        score={
            "financial": round(financial_avg, 3),
            "sentiment": round(sentiment_avg, 3),
            "macro": round(macro_avg, 3),
            "total": round(weighted_total, 3),
        },
        trend=trend,
        risks=sorted(set(risks)),
        opportunities=sorted(set(opportunities)),
        confidence=confidence,
    )
