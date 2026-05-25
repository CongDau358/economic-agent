"""
backend/trend_engine.py  (NÂNG CẤP)

Thêm so với bản gốc:
- Signal registry đầy đủ với trọng số chi tiết
- Short-term (1-3 tháng) + Near-term (3-6 tháng) trend
- Penalty factors theo AGENT.md (conflict, low coverage)
- Scenario analysis (bull / base / bear)
- Confidence warnings khi evidence mâu thuẫn
- INSUFFICIENT_DATA guard
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# ── Signal registries ─────────────────────────────────────────────────────────

FINANCIAL_SIGNALS: dict[str, float] = {
    # Bullish
    "revenue_up": +0.8,
    "margin_expansion": +0.7,
    "profit_up": +0.8,
    "eps_beat": +0.7,
    "cash_flow_positive": +0.6,
    "debt_reduction": +0.5,
    "dividend_increase": +0.4,
    "buyback": +0.3,
    "guidance_raised": +0.8,
    "market_share_gain": +0.6,
    # Bearish
    "revenue_down": -0.8,
    "margin_compression": -0.7,
    "profit_down": -0.8,
    "eps_miss": -0.7,
    "cash_burn": -0.6,
    "debt_increase": -0.5,
    "dividend_cut": -0.6,
    "guidance_lowered": -0.8,
    "impairment": -0.5,
    # Neutral / mixed
    "cost_up": -0.3,
    "cost_down": +0.3,
    "margin_stable": 0.0,
    "revenue_stable": 0.0,
}

SENTIMENT_SIGNALS: dict[str, float] = {
    "positive_news": +0.6,
    "analyst_upgrade": +0.7,
    "insider_buying": +0.5,
    "institutional_buying": +0.4,
    "media_positive": +0.4,
    "negative_news": -0.6,
    "analyst_downgrade": -0.7,
    "insider_selling": -0.4,
    "short_interest_high": -0.5,
    "media_negative": -0.4,
    "regulatory_concern": -0.6,
    "litigation_risk": -0.5,
    "management_change": -0.2,
    "management_positive": +0.3,
    "esg_positive": +0.2,
    "esg_negative": -0.3,
}

MACRO_SIGNALS: dict[str, float] = {
    "policy_support": +0.6,
    "interest_rate_down": +0.5,
    "interest_rate_stable": +0.1,
    "interest_rate_high": -0.4,
    "inflation_stable": +0.3,
    "inflation_elevated": -0.4,
    "gdp_growth": +0.5,
    "gdp_contraction": -0.6,
    "credit_easing": +0.4,
    "credit_tightening": -0.4,
    "fx_favorable": +0.3,
    "fx_headwind": -0.3,
    "commodity_cost_up": -0.3,
    "commodity_cost_down": +0.3,
    "sector_tailwind": +0.4,
    "sector_headwind": -0.4,
    "low_volatility": +0.2,
    "high_volatility": -0.3,
    "geopolitical_risk": -0.4,
}


def _score_signals(signals: list[str], registry: dict[str, float]) -> tuple[float, list[str]]:
    """Return (raw_score, unknown_signals)."""
    total = 0.0
    unknown = []
    for s in signals:
        if s in registry:
            total += registry[s]
        else:
            unknown.append(s)
    # Clip [-1, 1]
    return max(-1.0, min(1.0, total / max(len(registry) * 0.3, 1))), unknown


def _trend_label(score: float) -> str:
    if score >= 0.25:
        return "bullish"
    if score <= -0.25:
        return "bearish"
    return "neutral"


def _confidence_from_signals(n_signals: int, has_conflict: bool) -> float:
    base = min(0.95, 0.4 + n_signals * 0.08)
    if has_conflict:
        base -= 0.15
    return round(max(0.1, base), 2)


def _detect_conflict(fin_signals: list[str]) -> bool:
    """Check for contradictory financial signals."""
    bullish = {"revenue_up", "profit_up", "eps_beat", "guidance_raised"}
    bearish = {"revenue_down", "profit_down", "eps_miss", "guidance_lowered"}
    has_bull = any(s in bullish for s in fin_signals)
    has_bear = any(s in bearish for s in fin_signals)
    return has_bull and has_bear


@dataclass
class TrendEngine:
    weight_financial: float = 0.5
    weight_sentiment: float = 0.3
    weight_macro: float = 0.2

    def analyze(
        self,
        company: str,
        financial_signals: list[str],
        sentiment_signals: list[str],
        macro_signals: list[str],
        extra_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        all_signals = financial_signals + sentiment_signals + macro_signals

        # ── INSUFFICIENT_DATA guard ───────────────────────────────────────────
        if len(all_signals) < 2:
            return {
                "company": company,
                "status": "INSUFFICIENT_DATA",
                "message": "Cần ít nhất 2 tín hiệu để phân tích. Vui lòng upload thêm dữ liệu.",
                "score": None,
                "trend": None,
                "confidence": 0.0,
            }

        fin_score, fin_unknown = _score_signals(financial_signals, FINANCIAL_SIGNALS)
        sent_score, sent_unknown = _score_signals(sentiment_signals, SENTIMENT_SIGNALS)
        macro_score, macro_unknown = _score_signals(macro_signals, MACRO_SIGNALS)

        composite = (
            fin_score * self.weight_financial
            + sent_score * self.weight_sentiment
            + macro_score * self.weight_macro
        )

        has_conflict = _detect_conflict(financial_signals)
        confidence = _confidence_from_signals(len(all_signals), has_conflict)

        # Normalise score to [0, 1]
        score_01 = round((composite + 1) / 2, 3)

        # ── Short-term vs Near-term ───────────────────────────────────────────
        st_trend = _trend_label(composite)
        # Near-term dampened by macro weight
        nt_composite = composite * 0.7 + macro_score * 0.3
        nt_trend = _trend_label(nt_composite)

        # ── Risks & Opportunities ─────────────────────────────────────────────
        risks: list[str] = []
        opportunities: list[str] = []

        negative_fin = [s for s in financial_signals if FINANCIAL_SIGNALS.get(s, 0) < -0.4]
        positive_fin = [s for s in financial_signals if FINANCIAL_SIGNALS.get(s, 0) > 0.4]
        negative_macro = [s for s in macro_signals if MACRO_SIGNALS.get(s, 0) < -0.3]
        positive_macro = [s for s in macro_signals if MACRO_SIGNALS.get(s, 0) > 0.3]

        risks.extend(negative_fin)
        risks.extend(negative_macro)
        if has_conflict:
            risks.append("conflicting_financial_signals")
        opportunities.extend(positive_fin)
        opportunities.extend(positive_macro)

        # ── Scenario analysis ────────────────────────────────────────────────
        scenarios = {
            "bull": round(min(1.0, score_01 + 0.12), 3),
            "base": score_01,
            "bear": round(max(0.0, score_01 - 0.15), 3),
        }

        # ── Executive summary ────────────────────────────────────────────────
        trend_vn = {"bullish": "tăng trưởng", "bearish": "suy giảm", "neutral": "trung tính"}
        summary = (
            f"{company} cho thấy xu hướng {trend_vn.get(st_trend, st_trend)} "
            f"ngắn hạn (điểm {score_01:.2f}/1.0, confidence {confidence:.0%}). "
        )
        if has_conflict:
            summary += "Lưu ý: có tín hiệu tài chính mâu thuẫn nhau. "
        if nt_trend != st_trend:
            summary += f"Trung hạn có thể chuyển sang {trend_vn.get(nt_trend, nt_trend)}."

        # ── Warnings ────────────────────────────────────────────────────────
        warnings: list[str] = []
        if has_conflict:
            warnings.append("Phát hiện tín hiệu tài chính mâu thuẫn — confidence bị giảm")
        if fin_unknown:
            warnings.append(f"Tín hiệu tài chính không nhận dạng được: {fin_unknown}")
        if len(all_signals) < 5:
            warnings.append("Số lượng tín hiệu thấp — kết quả có thể chưa đủ độ tin cậy")

        return {
            "company": company,
            "status": "OK",
            "score": score_01,
            "trend": {
                "short_term": st_trend,       # 1-3 tháng
                "near_term": nt_trend,        # 3-6 tháng
            },
            "confidence": confidence,
            "executive_summary": summary,
            "financial_signals": {
                "score": round(fin_score, 3),
                "inputs": financial_signals,
            },
            "sentiment_signals": {
                "score": round(sent_score, 3),
                "inputs": sentiment_signals,
            },
            "macro_signals": {
                "score": round(macro_score, 3),
                "inputs": macro_signals,
            },
            "scenarios": scenarios,
            "risks": risks,
            "opportunities": opportunities,
            "assumptions": [
                "Trọng số: Tài chính 50%, Sentiment 30%, Vĩ mô 20%",
                "Không phải lời khuyên đầu tư",
                "Dựa trên dữ liệu tại thời điểm phân tích",
            ],
            "warnings": warnings,
        }


# ── Backward compatibility ─────────────────────────────────────────────────────
# Bản gốc dùng predict_trend() — giữ lại để không break các import cũ.

from dataclasses import dataclass as _dc

@_dc
class _TrendResult:
    summary:      str
    signals:      dict
    score:        float | None
    trend:        str | None
    risks:        list
    opportunities: list
    confidence:   float


_default_engine = TrendEngine()


def predict_trend(
    financial_signals: list[str],
    sentiment_signals: list[str],
    macro_signals: list[str],
    company: str = "Unknown",
) -> _TrendResult:
    """
    Backward-compat wrapper — bản cũ dùng hàm này.
    Gọi nội bộ TrendEngine.analyze() rồi map về _TrendResult.
    """
    result = _default_engine.analyze(
        company=company,
        financial_signals=financial_signals,
        sentiment_signals=sentiment_signals,
        macro_signals=macro_signals,
    )
    trend_val = result.get("trend") or {}
    return _TrendResult(
        summary=result.get("executive_summary", ""),
        signals={
            "financial": result.get("financial_signals", {}),
            "sentiment": result.get("sentiment_signals", {}),
            "macro":     result.get("macro_signals", {}),
        },
        score=result.get("score"),
        trend=trend_val.get("short_term") if isinstance(trend_val, dict) else trend_val,
        risks=result.get("risks", []),
        opportunities=result.get("opportunities", []),
        confidence=result.get("confidence", 0.0),
    )