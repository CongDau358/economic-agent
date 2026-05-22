"""
tests/test_trend_engine.py
Unit tests chi tiết cho TrendEngine.
"""

import pytest
from backend.trend_engine import (
    TrendEngine,
    FINANCIAL_SIGNALS,
    SENTIMENT_SIGNALS,
    MACRO_SIGNALS,
    _detect_conflict,
    _trend_label,
    _score_signals,
)


@pytest.fixture
def engine():
    return TrendEngine(weight_financial=0.5, weight_sentiment=0.3, weight_macro=0.2)


# ── Signal registry ───────────────────────────────────────────────────────────

def test_all_signal_registries_have_values():
    assert len(FINANCIAL_SIGNALS) >= 10
    assert len(SENTIMENT_SIGNALS) >= 10
    assert len(MACRO_SIGNALS) >= 10


def test_signal_scores_bounded():
    for sig, score in {**FINANCIAL_SIGNALS, **SENTIMENT_SIGNALS, **MACRO_SIGNALS}.items():
        assert -1.0 <= score <= 1.0, f"{sig} score={score} out of bounds"


# ── Core logic ────────────────────────────────────────────────────────────────

def test_trend_label_bullish():
    assert _trend_label(0.30) == "bullish"
    assert _trend_label(1.0) == "bullish"


def test_trend_label_bearish():
    assert _trend_label(-0.30) == "bearish"
    assert _trend_label(-1.0) == "bearish"


def test_trend_label_neutral():
    assert _trend_label(0.0) == "neutral"
    assert _trend_label(0.10) == "neutral"
    assert _trend_label(-0.10) == "neutral"


def test_score_signals_unknown_ignored():
    score, unknown = _score_signals(["revenue_up", "not_a_real_signal"], FINANCIAL_SIGNALS)
    assert "not_a_real_signal" in unknown
    assert isinstance(score, float)


def test_detect_conflict_true():
    assert _detect_conflict(["revenue_up", "revenue_down", "eps_beat", "eps_miss"])


def test_detect_conflict_false():
    assert not _detect_conflict(["revenue_up", "margin_stable", "eps_beat"])


# ── TrendEngine.analyze ───────────────────────────────────────────────────────

def test_analyze_insufficient_data_empty(engine):
    r = engine.analyze("X", [], [], [])
    assert r["status"] == "INSUFFICIENT_DATA"
    assert r["score"] is None


def test_analyze_insufficient_data_one_signal(engine):
    r = engine.analyze("X", ["revenue_up"], [], [])
    assert r["status"] == "INSUFFICIENT_DATA"


def test_analyze_ok_with_two_signals(engine):
    r = engine.analyze("X", ["revenue_up", "profit_up"], [], [])
    assert r["status"] == "OK"
    assert r["score"] is not None


def test_analyze_score_range(engine):
    r = engine.analyze(
        "Acme",
        ["revenue_up", "eps_beat", "margin_expansion"],
        ["positive_news"],
        ["gdp_growth"],
    )
    assert 0.0 <= r["score"] <= 1.0


def test_analyze_bullish(engine):
    r = engine.analyze(
        "Acme",
        ["revenue_up", "profit_up", "eps_beat", "guidance_raised"],
        ["analyst_upgrade", "positive_news"],
        ["policy_support", "gdp_growth", "interest_rate_down"],
    )
    assert r["trend"]["short_term"] == "bullish"
    assert r["score"] > 0.55


def test_analyze_bearish(engine):
    r = engine.analyze(
        "Acme",
        ["revenue_down", "profit_down", "eps_miss", "guidance_lowered"],
        ["analyst_downgrade", "negative_news"],
        ["geopolitical_risk", "interest_rate_high", "inflation_elevated"],
    )
    assert r["trend"]["short_term"] == "bearish"
    assert r["score"] < 0.45


def test_analyze_has_scenarios(engine):
    r = engine.analyze("A", ["revenue_up", "profit_up"], ["positive_news"], ["gdp_growth"])
    assert "scenarios" in r
    assert {"bull", "base", "bear"} == set(r["scenarios"].keys())
    assert r["scenarios"]["bull"] >= r["scenarios"]["base"] >= r["scenarios"]["bear"]


def test_analyze_conflict_warning(engine):
    r = engine.analyze(
        "A",
        ["revenue_up", "revenue_down", "eps_beat", "eps_miss"],
        ["positive_news"],
        ["gdp_growth"],
    )
    assert "conflicting_financial_signals" in r["risks"]
    assert any("mâu thuẫn" in w for w in r["warnings"])


def test_analyze_unknown_signals_warning(engine):
    r = engine.analyze(
        "A",
        ["revenue_up", "xyz_fake_signal"],
        ["positive_news"],
        ["gdp_growth"],
    )
    assert r["status"] == "OK"
    assert any("xyz_fake_signal" in w for w in r["warnings"])


def test_analyze_risks_opportunities_populated(engine):
    r = engine.analyze(
        "A",
        ["revenue_up", "profit_up"],
        ["negative_news", "analyst_downgrade"],
        ["gdp_growth", "geopolitical_risk"],
    )
    assert len(r["risks"]) > 0
    assert len(r["opportunities"]) > 0


def test_analyze_confidence_low_signal_count(engine):
    r = engine.analyze("A", ["revenue_up", "profit_up"], [], [])
    assert r["confidence"] < 0.75


def test_analyze_confidence_high_signal_count(engine):
    r = engine.analyze(
        "A",
        ["revenue_up", "profit_up", "eps_beat", "margin_expansion", "guidance_raised"],
        ["analyst_upgrade", "positive_news", "institutional_buying"],
        ["policy_support", "gdp_growth", "interest_rate_down"],
    )
    assert r["confidence"] >= 0.75


def test_analyze_custom_weights():
    engine_macro_heavy = TrendEngine(
        weight_financial=0.2,
        weight_sentiment=0.2,
        weight_macro=0.6,
    )
    engine_fin_heavy = TrendEngine(
        weight_financial=0.8,
        weight_sentiment=0.1,
        weight_macro=0.1,
    )
    signals = dict(
        company="A",
        financial_signals=["revenue_down"],
        sentiment_signals=["positive_news"],
        macro_signals=["gdp_growth", "policy_support", "interest_rate_down"],
    )
    r_macro = engine_macro_heavy.analyze(**signals)
    r_fin   = engine_fin_heavy.analyze(**signals)
    # macro-heavy weights benefitting from positive macro → higher score
    assert r_macro["score"] > r_fin["score"]


def test_analyze_short_vs_near_term_can_differ(engine):
    """Khi macro tệ nhưng tài chính tốt → short-term ≠ near-term có thể."""
    r = engine.analyze(
        "A",
        ["revenue_up", "profit_up", "eps_beat", "guidance_raised", "margin_expansion"],
        ["analyst_upgrade"],
        ["geopolitical_risk", "interest_rate_high", "inflation_elevated", "high_volatility"],
    )
    # Dù khác nhau hay không, cả 2 phải là valid label
    assert r["trend"]["short_term"]  in ("bullish", "bearish", "neutral")
    assert r["trend"]["near_term"]   in ("bullish", "bearish", "neutral")


def test_analyze_executive_summary_nonempty(engine):
    r = engine.analyze("VNM", ["revenue_up", "profit_up"], ["positive_news"], ["gdp_growth"])
    assert isinstance(r["executive_summary"], str)
    assert len(r["executive_summary"]) > 20


def test_analyze_assumptions_present(engine):
    r = engine.analyze("VNM", ["revenue_up", "profit_up"], ["positive_news"], ["gdp_growth"])
    assert len(r["assumptions"]) > 0