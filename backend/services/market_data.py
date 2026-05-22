"""
backend/services/market_data.py
Fetches real-time and historical market / macro data.

Providers:
  - Yahoo Finance (yfinance) — free, no key required
  - FRED (Federal Reserve) — free with API key (fredapi)
  - Alpha Vantage — free tier (25 req/day) with API key

Install:
    pip install yfinance fredapi
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger("economic_agent.market_data")


# ── Yahoo Finance ─────────────────────────────────────────────────────────────

def get_stock_info(ticker: str) -> dict[str, Any]:
    """
    Return key financial metrics for a stock ticker.
    Example: get_stock_info("VNM.HM")  # Vinamilk on HoSE
    """
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "ticker": ticker,
            "company_name": info.get("longName", ticker),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "eps": info.get("trailingEps"),
            "revenue_growth": info.get("revenueGrowth"),
            "profit_margins": info.get("profitMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange", ""),
        }
    except Exception as exc:
        logger.warning("yfinance error for %s: %s", ticker, exc)
        return {"ticker": ticker, "error": str(exc)}


def get_price_history(
    ticker: str, period: str = "3mo", interval: str = "1d"
) -> list[dict]:
    """
    Return OHLCV price history.
    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
    """
    try:
        import yfinance as yf
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if df.empty:
            return []
        df = df.reset_index()
        return [
            {
                "date": str(row["Date"])[:10],
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
            }
            for _, row in df.iterrows()
        ]
    except Exception as exc:
        logger.warning("price history error for %s: %s", ticker, exc)
        return []


def get_sector_performance(sector_etfs: dict[str, str] | None = None) -> dict[str, Any]:
    """
    Compare YTD performance across sector ETFs.
    Default set covers US sectors; override with Vietnam-specific tickers.
    """
    if sector_etfs is None:
        sector_etfs = {
            "Technology": "XLK",
            "Financials": "XLF",
            "Healthcare": "XLV",
            "Energy": "XLE",
            "Consumer Disc.": "XLY",
            "Consumer Staples": "XLP",
            "Industrials": "XLI",
            "Materials": "XLB",
            "Utilities": "XLU",
            "Real Estate": "XLRE",
        }
    try:
        import yfinance as yf
        result = {}
        for sector, etf in sector_etfs.items():
            ticker = yf.Ticker(etf)
            hist = ticker.history(period="ytd")
            if len(hist) >= 2:
                ytd_return = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
                result[sector] = round(ytd_return, 2)
        return result
    except Exception as exc:
        logger.warning("sector performance error: %s", exc)
        return {}


# ── FRED Macro Data ───────────────────────────────────────────────────────────

FRED_SERIES = {
    "gdp_growth": "A191RL1Q225SBEA",     # Real GDP growth QoQ
    "inflation_cpi": "CPIAUCSL",          # CPI (YoY %)
    "unemployment": "UNRATE",             # Unemployment rate
    "fed_funds_rate": "FEDFUNDS",         # Fed funds rate
    "10y_treasury": "DGS10",              # 10-year treasury yield
    "vix": "VIXCLS",                      # VIX volatility index
    "usd_index": "DTWEXBGS",             # USD broad index
    "credit_spread_hy": "BAMLH0A0HYM2",  # HY credit spread
}


def get_macro_indicators(
    series_ids: list[str] | None = None,
    lookback_months: int = 6,
) -> dict[str, Any]:
    """
    Fetch macro indicators from FRED.
    Requires FRED_API_KEY in .env (free at https://fred.stlouisfed.org/docs/api/api_key.html).
    Falls back gracefully if key is missing.
    """
    from backend.config import get_settings
    settings = get_settings()

    if not settings.fred_api_key:
        logger.info("FRED_API_KEY not set — skipping macro fetch")
        return {"warning": "FRED_API_KEY not configured"}

    try:
        from fredapi import Fred
        fred = Fred(api_key=settings.fred_api_key)

        if series_ids is None:
            series_ids = list(FRED_SERIES.keys())

        start = (datetime.now() - timedelta(days=lookback_months * 31)).strftime(
            "%Y-%m-%d"
        )
        result = {}
        for name in series_ids:
            fred_id = FRED_SERIES.get(name, name)
            try:
                series = fred.get_series(fred_id, observation_start=start)
                latest = series.dropna().iloc[-1] if not series.empty else None
                result[name] = {
                    "latest": round(float(latest), 4) if latest is not None else None,
                    "series_id": fred_id,
                    "as_of": str(series.dropna().index[-1])[:10] if not series.empty else None,
                }
            except Exception as e:
                result[name] = {"error": str(e), "series_id": fred_id}
        return result
    except ImportError:
        logger.warning("fredapi not installed — run: pip install fredapi")
        return {"error": "fredapi not installed"}
    except Exception as exc:
        logger.warning("FRED error: %s", exc)
        return {"error": str(exc)}


# ── Aggregated market context for /predict ───────────────────────────────────

def build_market_context(
    ticker: str | None = None,
    include_macro: bool = True,
) -> dict[str, Any]:
    """
    Build a unified market context dict to enrich trend analysis.
    This is what gets passed to the trend engine as additional signals.
    """
    context: dict[str, Any] = {}

    if ticker:
        context["stock"] = get_stock_info(ticker)
        context["price_history_3m"] = get_price_history(ticker, period="3mo")

    if include_macro:
        context["macro"] = get_macro_indicators()

    # Auto-derive macro signals from fetched data
    macro_signals: list[str] = []
    macro = context.get("macro", {})

    if isinstance(macro.get("fed_funds_rate"), dict):
        rate = macro["fed_funds_rate"].get("latest")
        if rate is not None:
            macro_signals.append("interest_rate_high" if rate > 4.0 else "interest_rate_low")

    if isinstance(macro.get("inflation_cpi"), dict):
        cpi = macro["inflation_cpi"].get("latest")
        if cpi is not None:
            macro_signals.append("inflation_elevated" if cpi > 3.0 else "inflation_stable")

    if isinstance(macro.get("vix"), dict):
        vix = macro["vix"].get("latest")
        if vix is not None:
            macro_signals.append("high_volatility" if vix > 25 else "low_volatility")

    context["derived_macro_signals"] = macro_signals
    return context