"""
tests/test_websocket.py
Tests cho WebSocket /ws/analyze endpoint.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def ws_client(mock_heavy_services):
    from backend.main import app
    return TestClient(app)


# ── Connection ────────────────────────────────────────────────────────────────

class TestWebSocketConnect:

    def test_connect_and_receive_done(self, ws_client, mocker):
        """Kết nối thành công, nhận đủ status → result → done."""
        from backend.main import orchestrator, trend_engine

        mock_rag = MagicMock()
        mocker.patch.object(orchestrator, "run", return_value=mock_rag)
        mocker.patch.object(orchestrator, "to_response_dict", return_value={
            "answer": "Mock answer", "citations": [], "confidence": 0.8,
        })
        mocker.patch.object(trend_engine, "analyze", return_value={
            "company": "Vinamilk", "status": "OK", "score": 0.72,
            "trend": {"short_term": "bullish", "near_term": "bullish"},
            "confidence": 0.87, "risks": [], "opportunities": [],
            "executive_summary": "Tăng trưởng tốt.", "warnings": [],
            "scenarios": {"bull": 0.84, "base": 0.72, "bear": 0.57},
            "financial_signals": {"score": 0.6, "inputs": []},
            "sentiment_signals": {"score": 0.4, "inputs": []},
            "macro_signals":     {"score": 0.3, "inputs": []},
            "assumptions": [],
        })

        with ws_client.websocket_connect("/ws/analyze") as ws:
            ws.send_json({"company": "Vinamilk", "question": "Phân tích rủi ro?"})
            messages = []
            for _ in range(10):
                try:
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["type"] in ("done", "error"):
                        break
                except Exception:
                    break

        types = [m["type"] for m in messages]
        assert "status" in types
        assert "result" in types
        assert "done" in types

    def test_result_contains_expected_keys(self, ws_client, mocker):
        from backend.main import orchestrator, trend_engine

        mocker.patch.object(orchestrator, "run", return_value=MagicMock())
        mocker.patch.object(orchestrator, "to_response_dict", return_value={
            "answer": "Test", "citations": [{"source": "doc.pdf"}], "confidence": 0.9,
        })
        mocker.patch.object(trend_engine, "analyze", return_value={
            "company": "VCB", "status": "OK", "score": 0.65,
            "trend": {"short_term": "neutral", "near_term": "neutral"},
            "confidence": 0.75, "risks": [], "opportunities": [],
            "executive_summary": "", "warnings": [], "scenarios": {},
            "financial_signals": {"score": 0, "inputs": []},
            "sentiment_signals": {"score": 0, "inputs": []},
            "macro_signals":     {"score": 0, "inputs": []},
            "assumptions": [],
        })

        with ws_client.websocket_connect("/ws/analyze") as ws:
            ws.send_json({"company": "VCB"})
            result_msg = None
            for _ in range(10):
                try:
                    msg = ws.receive_json()
                    if msg["type"] == "result":
                        result_msg = msg
                    if msg["type"] in ("done", "error"):
                        break
                except Exception:
                    break

        assert result_msg is not None
        data = result_msg["data"]
        assert "company" in data
        assert "rag"     in data
        assert "trend"   in data
        assert "market"  in data

    def test_with_ticker_triggers_market_data(self, ws_client, mocker):
        from backend.main import orchestrator, trend_engine

        mocker.patch.object(orchestrator, "run", return_value=MagicMock())
        mocker.patch.object(orchestrator, "to_response_dict", return_value={
            "answer": "OK", "citations": [], "confidence": 0.8,
        })
        mocker.patch.object(trend_engine, "analyze", return_value={
            "company": "VNM", "status": "OK", "score": 0.7,
            "trend": {"short_term": "bullish", "near_term": "bullish"},
            "confidence": 0.8, "risks": [], "opportunities": [],
            "executive_summary": "", "warnings": [], "scenarios": {},
            "financial_signals": {"score": 0, "inputs": []},
            "sentiment_signals": {"score": 0, "inputs": []},
            "macro_signals":     {"score": 0, "inputs": []},
            "assumptions": [],
        })

        mock_market = patch(
            "backend.services.market_data.build_market_context",
            return_value={"stock": {"ticker": "VNM.HM", "price": 75000},
                          "derived_macro_signals": ["inflation_stable"]},
        )

        with mock_market:
            with ws_client.websocket_connect("/ws/analyze") as ws:
                ws.send_json({"company": "Vinamilk", "ticker": "VNM.HM"})
                messages = []
                for _ in range(10):
                    try:
                        msg = ws.receive_json()
                        messages.append(msg)
                        if msg["type"] in ("done", "error"):
                            break
                    except Exception:
                        break

        status_msgs = [m["msg"] for m in messages if m["type"] == "status"]
        # Phải có ít nhất 1 status về market data
        assert any("VNM.HM" in msg or "thị trường" in msg for msg in status_msgs)

    def test_empty_company_still_connects(self, ws_client, mocker):
        from backend.main import orchestrator, trend_engine

        mocker.patch.object(orchestrator, "run", return_value=MagicMock())
        mocker.patch.object(orchestrator, "to_response_dict", return_value={
            "answer": "No company specified.", "citations": [], "confidence": 0.5,
        })
        mocker.patch.object(trend_engine, "analyze", return_value={
            "company": "", "status": "INSUFFICIENT_DATA",
            "message": "Cần ít nhất 2 tín hiệu.",
            "score": None, "trend": None, "confidence": 0.0,
        })

        with ws_client.websocket_connect("/ws/analyze") as ws:
            ws.send_json({})  # không có company
            done = False
            for _ in range(10):
                try:
                    msg = ws.receive_json()
                    if msg["type"] in ("done", "error", "result"):
                        done = True
                        break
                except Exception:
                    break
        assert done

    def test_market_data_failure_sends_warning_status(self, ws_client, mocker):
        from backend.main import orchestrator, trend_engine

        mocker.patch.object(orchestrator, "run", return_value=MagicMock())
        mocker.patch.object(orchestrator, "to_response_dict", return_value={
            "answer": "OK", "citations": [], "confidence": 0.8,
        })
        mocker.patch.object(trend_engine, "analyze", return_value={
            "company": "X", "status": "OK", "score": 0.6,
            "trend": {"short_term": "neutral", "near_term": "neutral"},
            "confidence": 0.7, "risks": [], "opportunities": [],
            "executive_summary": "", "warnings": [], "scenarios": {},
            "financial_signals": {"score": 0, "inputs": []},
            "sentiment_signals": {"score": 0, "inputs": []},
            "macro_signals":     {"score": 0, "inputs": []},
            "assumptions": [],
        })

        with patch(
            "backend.services.market_data.build_market_context",
            side_effect=Exception("API timeout"),
        ):
            with ws_client.websocket_connect("/ws/analyze") as ws:
                ws.send_json({"company": "X", "ticker": "X.XX"})
                messages = []
                for _ in range(10):
                    try:
                        msg = ws.receive_json()
                        messages.append(msg)
                        if msg["type"] in ("done", "error"):
                            break
                    except Exception:
                        break

        # Phải có status warning về market data failure
        status_msgs = [m.get("msg", "") for m in messages if m["type"] == "status"]
        assert any("⚠" in msg for msg in status_msgs)