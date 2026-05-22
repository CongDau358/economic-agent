"""
tests/test_market_data.py
Unit tests cho market_data service (mock network calls).
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ── get_stock_info ────────────────────────────────────────────────────────────

class TestGetStockInfo:

    def test_returns_dict_with_ticker(self):
        mock_info = {
            "longName": "Vinamilk", "sector": "Consumer Staples",
            "marketCap": 5_000_000_000, "trailingPE": 18.5,
            "currentPrice": 75000, "currency": "VND",
        }
        with patch("yfinance.Ticker") as MockTicker:
            MockTicker.return_value.info = mock_info
            from backend.services.market_data import get_stock_info
            result = get_stock_info("VNM.HM")

        assert result["ticker"] == "VNM.HM"
        assert result["company_name"] == "Vinamilk"
        assert result["sector"] == "Consumer Staples"
        assert result["market_cap"] == 5_000_000_000

    def test_graceful_on_yfinance_error(self):
        with patch("yfinance.Ticker", side_effect=Exception("Network error")):
            from backend.services.market_data import get_stock_info
            result = get_stock_info("INVALID.XX")

        assert result["ticker"] == "INVALID.XX"
        assert "error" in result

    def test_missing_fields_return_none(self):
        with patch("yfinance.Ticker") as MockTicker:
            MockTicker.return_value.info = {}
            from backend.services.market_data import get_stock_info
            result = get_stock_info("X.XX")

        assert result["pe_ratio"] is None
        assert result["market_cap"] is None


# ── get_price_history ─────────────────────────────────────────────────────────

class TestGetPriceHistory:

    def test_returns_list_of_dicts(self):
        import pandas as pd
        mock_df = pd.DataFrame({
            "Date":   pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "Open":   [70000.0, 71000.0],
            "High":   [72000.0, 73000.0],
            "Low":    [69000.0, 70500.0],
            "Close":  [71500.0, 72000.0],
            "Volume": [1_000_000, 1_200_000],
        })
        with patch("yfinance.download", return_value=mock_df):
            from backend.services.market_data import get_price_history
            result = get_price_history("VNM.HM", period="1mo")

        assert isinstance(result, list)
        assert len(result) == 2
        assert {"date", "open", "high", "low", "close", "volume"} <= set(result[0].keys())

    def test_empty_dataframe_returns_empty_list(self):
        import pandas as pd
        with patch("yfinance.download", return_value=pd.DataFrame()):
            from backend.services.market_data import get_price_history
            result = get_price_history("X.XX")
        assert result == []

    def test_network_error_returns_empty_list(self):
        with patch("yfinance.download", side_effect=Exception("Timeout")):
            from backend.services.market_data import get_price_history
            result = get_price_history("X.XX")
        assert result == []


# ── get_macro_indicators ──────────────────────────────────────────────────────

class TestGetMacroIndicators:

    def test_no_fred_key_returns_warning(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "")
        from backend.config import get_settings
        get_settings.cache_clear()

        from backend.services.market_data import get_macro_indicators
        result = get_macro_indicators()
        assert "warning" in result

        get_settings.cache_clear()

    def test_with_fred_key_calls_api(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "test-key")
        from backend.config import get_settings
        get_settings.cache_clear()

        import pandas as pd
        mock_series = pd.Series([5.33, 5.25, 5.0],
                                index=pd.to_datetime(["2024-01-01","2024-02-01","2024-03-01"]))
        with patch("fredapi.Fred") as MockFred:
            MockFred.return_value.get_series.return_value = mock_series
            from backend.services.market_data import get_macro_indicators
            result = get_macro_indicators(["fed_funds_rate"])

        assert "fed_funds_rate" in result
        assert result["fed_funds_rate"]["latest"] == 5.0

        get_settings.cache_clear()

    def test_fredapi_not_installed_returns_error(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "test-key")
        from backend.config import get_settings
        get_settings.cache_clear()

        with patch.dict("sys.modules", {"fredapi": None}):
            from backend.services.market_data import get_macro_indicators
            result = get_macro_indicators()

        assert "error" in result or "warning" in result
        get_settings.cache_clear()


# ── build_market_context ──────────────────────────────────────────────────────

class TestBuildMarketContext:

    def test_with_ticker_includes_stock(self):
        with (
            patch("backend.services.market_data.get_stock_info",
                  return_value={"ticker": "VNM.HM", "price": 75000}),
            patch("backend.services.market_data.get_price_history",
                  return_value=[{"date": "2024-01-02", "close": 75000}]),
            patch("backend.services.market_data.get_macro_indicators",
                  return_value={"warning": "FRED_API_KEY not configured"}),
        ):
            from backend.services.market_data import build_market_context
            ctx = build_market_context("VNM.HM", include_macro=False)

        assert "stock" in ctx
        assert ctx["stock"]["ticker"] == "VNM.HM"

    def test_derived_macro_signals_generated(self):
        with (
            patch("backend.services.market_data.get_stock_info", return_value={}),
            patch("backend.services.market_data.get_price_history", return_value=[]),
            patch("backend.services.market_data.get_macro_indicators", return_value={
                "fed_funds_rate": {"latest": 5.5},
                "inflation_cpi":  {"latest": 3.2},
                "vix":            {"latest": 18.0},
            }),
        ):
            from backend.services.market_data import build_market_context
            ctx = build_market_context("VNM.HM", include_macro=True)

        signals = ctx.get("derived_macro_signals", [])
        assert "interest_rate_high" in signals   # rate > 4.0
        assert "inflation_elevated" in signals   # cpi > 3.0
        assert "low_volatility" in signals       # vix <= 25

    def test_no_ticker_skips_stock(self):
        with patch("backend.services.market_data.get_macro_indicators",
                   return_value={}):
            from backend.services.market_data import build_market_context
            ctx = build_market_context(ticker=None, include_macro=True)

        assert "stock" not in ctx
        assert "price_history_3m" not in ctx