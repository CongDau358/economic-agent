"""
tests/test_pipelines.py
Tests cho batch_predict và schedule_ingest pipelines.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ── batch_predict ─────────────────────────────────────────────────────────────

class TestBatchPredict:

    COMPANIES = [
        {
            "company": "Vinamilk", "ticker": "VNM.HM",
            "financial_signals": ["revenue_up", "eps_beat"],
            "sentiment_signals": ["positive_news"],
            "macro_signals": ["policy_support"],
        },
        {
            "company": "VCB", "ticker": "VCB.HM",
            "financial_signals": ["profit_up", "guidance_raised"],
            "sentiment_signals": ["analyst_upgrade"],
            "macro_signals": ["interest_rate_stable"],
        },
    ]

    def test_run_batch_returns_results(self, tmp_path):
        from pipelines.batch_predict import run_batch
        results = run_batch(self.COMPANIES, tmp_path, formats=["json"])
        assert len(results) == 2
        assert all("company" in r for r in results)

    def test_run_batch_creates_json_file(self, tmp_path):
        from pipelines.batch_predict import run_batch
        run_batch(self.COMPANIES, tmp_path, formats=["json"])
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == 1

    def test_run_batch_creates_csv_file(self, tmp_path):
        from pipelines.batch_predict import run_batch
        run_batch(self.COMPANIES, tmp_path, formats=["csv"])
        csv_files = list(tmp_path.glob("*.csv"))
        assert len(csv_files) == 1

    def test_run_batch_creates_excel_file(self, tmp_path):
        from pipelines.batch_predict import run_batch
        run_batch(self.COMPANIES, tmp_path, formats=["excel"])
        xlsx_files = list(tmp_path.glob("*.xlsx"))
        assert len(xlsx_files) == 1

    def test_run_batch_all_formats(self, tmp_path):
        from pipelines.batch_predict import run_batch
        run_batch(self.COMPANIES, tmp_path, formats=["csv", "json", "excel"])
        assert len(list(tmp_path.glob("*.json"))) == 1
        assert len(list(tmp_path.glob("*.csv")))  == 1
        assert len(list(tmp_path.glob("*.xlsx"))) == 1

    def test_run_batch_result_has_score(self, tmp_path):
        from pipelines.batch_predict import run_batch
        results = run_batch(self.COMPANIES, tmp_path, formats=["json"])
        for r in results:
            if r.get("status") == "OK":
                assert r.get("score") is not None
                assert 0.0 <= r["score"] <= 1.0

    def test_run_batch_result_has_trend(self, tmp_path):
        from pipelines.batch_predict import run_batch
        results = run_batch(self.COMPANIES, tmp_path, formats=["json"])
        for r in results:
            if r.get("status") == "OK":
                assert "trend" in r
                assert "short_term" in (r["trend"] or {})

    def test_run_batch_handles_error_gracefully(self, tmp_path):
        """Nếu 1 company lỗi, các company còn lại vẫn được xử lý."""
        from pipelines.batch_predict import run_batch
        from backend.trend_engine import TrendEngine

        call_count = 0
        original_analyze = TrendEngine.analyze

        def flaky_analyze(self, company, **kwargs):
            nonlocal call_count
            call_count += 1
            if company == "Vinamilk":
                raise RuntimeError("Simulated error")
            return original_analyze(self, company, **kwargs)

        with patch.object(TrendEngine, "analyze", flaky_analyze):
            results = run_batch(self.COMPANIES, tmp_path, formats=["json"])

        assert len(results) == 2
        vnm = next(r for r in results if r["company"] == "Vinamilk")
        vcb = next(r for r in results if r["company"] == "VCB")
        assert vnm["status"] == "ERROR"
        assert vcb["status"] in ("OK", "INSUFFICIENT_DATA")

    def test_run_batch_sample_input(self, tmp_path):
        """Sample input từ SAMPLE_INPUT có thể chạy được."""
        from pipelines.batch_predict import SAMPLE_INPUT, run_batch
        results = run_batch(SAMPLE_INPUT, tmp_path, formats=["json"])
        assert len(results) == len(SAMPLE_INPUT)

    def test_run_batch_json_content_valid(self, tmp_path):
        from pipelines.batch_predict import run_batch
        run_batch(self.COMPANIES, tmp_path, formats=["json"])
        json_file = list(tmp_path.glob("*.json"))[0]
        content = json.loads(json_file.read_text(encoding="utf-8"))
        assert isinstance(content, list)
        assert len(content) == len(self.COMPANIES)

    def test_run_batch_ticker_preserved(self, tmp_path):
        from pipelines.batch_predict import run_batch
        results = run_batch(self.COMPANIES, tmp_path, formats=["json"])
        vnm = next(r for r in results if r["company"] == "Vinamilk")
        assert vnm.get("ticker") == "VNM.HM"

    def test_run_batch_empty_list(self, tmp_path):
        from pipelines.batch_predict import run_batch
        results = run_batch([], tmp_path, formats=["json"])
        assert results == []


# ── schedule_ingest ───────────────────────────────────────────────────────────

class TestScheduleIngest:

    def test_run_all_success(self):
        from pipelines.schedule_ingest import run_all, WATCH_SOURCES

        with patch("pipelines.schedule_ingest.ingest") as mock_ingest:
            mock_ingest.return_value = {"chunks_upserted": 10, "company": "Test"}
            run_all()

        assert mock_ingest.call_count == len(WATCH_SOURCES)

    def test_run_all_handles_failure_gracefully(self):
        """Nếu 1 source lỗi, các source còn lại vẫn được xử lý."""
        from pipelines.schedule_ingest import run_all, WATCH_SOURCES

        call_count = 0
        def sometimes_fail(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Network error")
            return {"chunks_upserted": 5}

        with patch("pipelines.schedule_ingest.ingest", side_effect=sometimes_fail):
            run_all()  # không raise exception

        assert call_count == len(WATCH_SOURCES)

    def test_watch_sources_have_required_fields(self):
        from pipelines.schedule_ingest import WATCH_SOURCES
        for src in WATCH_SOURCES:
            assert "source_type" in src
            assert "company"     in src
            assert "sector"      in src

    def test_watch_sources_url_type_have_url(self):
        from pipelines.schedule_ingest import WATCH_SOURCES
        for src in WATCH_SOURCES:
            if src["source_type"] == "url":
                assert "url" in src
                assert src["url"].startswith("http")

    def test_run_all_calls_ingest_with_correct_args(self):
        from pipelines.schedule_ingest import run_all, WATCH_SOURCES

        captured_calls = []
        def capture_ingest(**kwargs):
            captured_calls.append(kwargs)
            return {"chunks_upserted": 3}

        with patch("pipelines.schedule_ingest.ingest", side_effect=capture_ingest):
            run_all()

        assert len(captured_calls) == len(WATCH_SOURCES)
        for call in captured_calls:
            assert "company"     in call
            assert "sector"      in call
            assert "source_type" in call


# ── export_predictions integration ───────────────────────────────────────────

class TestExportIntegration:
    """Integration giữa batch_predict và export service."""

    def test_batch_predict_and_export_roundtrip(self, tmp_path):
        """Chạy batch predict → export → đọc lại CSV, verify data."""
        import csv
        from pipelines.batch_predict import run_batch

        companies = [
            {
                "company": "TestCo", "ticker": "TC.XX",
                "financial_signals": ["revenue_up", "profit_up"],
                "sentiment_signals": ["positive_news"],
                "macro_signals": ["gdp_growth"],
            }
        ]
        run_batch(companies, tmp_path, formats=["csv"])
        csv_files = list(tmp_path.glob("*.csv"))
        assert csv_files

        rows = list(csv.DictReader(
            open(csv_files[0], encoding="utf-8-sig")
        ))
        assert len(rows) == 1
        assert rows[0]["company"] == "TestCo"
        assert rows[0]["ticker"]  == "TC.XX"

    def test_batch_predict_excel_readable(self, tmp_path):
        """Excel output có thể đọc bằng openpyxl."""
        import openpyxl
        from io import BytesIO
        from pipelines.batch_predict import run_batch

        companies = [{
            "company": "TestCo", "ticker": "",
            "financial_signals": ["revenue_up", "eps_beat"],
            "sentiment_signals": [],
            "macro_signals": ["gdp_growth"],
        }]
        run_batch(companies, tmp_path, formats=["excel"])
        xlsx_files = list(tmp_path.glob("*.xlsx"))
        assert xlsx_files

        wb = openpyxl.load_workbook(xlsx_files[0])
        ws = wb.active
        assert ws.max_row >= 2  # header + ít nhất 1 data row