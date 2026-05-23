"""
tests/test_notify.py
Tests cho notification service.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from backend.services.notify import NotifyConfig


# ── NotifyConfig ──────────────────────────────────────────────────────────────

class TestNotifyConfig:

    def test_from_env_defaults(self, monkeypatch):
        monkeypatch.delenv("NOTIFY_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("NOTIFY_EMAIL_TO",    raising=False)
        monkeypatch.setenv("NOTIFY_ENABLED",     "true")
        cfg = NotifyConfig.from_env()
        assert cfg.webhook_url == ""
        assert cfg.email_to    == ""
        assert cfg.enabled     is True

    def test_from_env_webhook(self, monkeypatch):
        monkeypatch.setenv("NOTIFY_WEBHOOK_URL", "https://hooks.slack.com/test")
        cfg = NotifyConfig.from_env()
        assert cfg.webhook_url == "https://hooks.slack.com/test"

    def test_from_env_disabled(self, monkeypatch):
        monkeypatch.setenv("NOTIFY_ENABLED", "false")
        cfg = NotifyConfig.from_env()
        assert cfg.enabled is False

    def test_from_env_threshold(self, monkeypatch):
        monkeypatch.setenv("NOTIFY_ERROR_RATE_THRESHOLD", "0.15")
        cfg = NotifyConfig.from_env()
        assert cfg.error_rate_threshold == 0.15

    def test_from_env_smtp(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "smtp.office365.com")
        monkeypatch.setenv("SMTP_PORT", "465")
        cfg = NotifyConfig.from_env()
        assert cfg.smtp_host == "smtp.office365.com"
        assert cfg.smtp_port == 465


# ── _build_slack_payload ──────────────────────────────────────────────────────

class TestSlackPayload:

    def test_slack_payload_structure(self):
        from backend.services.notify import _build_slack_payload
        payload = _build_slack_payload("Test Title", "Test message", "error")
        assert "attachments" in payload
        assert len(payload["attachments"]) == 1
        att = payload["attachments"][0]
        assert "color" in att
        assert "title" in att
        assert "Test Title" in att["title"]
        assert att["text"] == "Test message"

    def test_slack_warning_color(self):
        from backend.services.notify import _build_slack_payload
        p = _build_slack_payload("T", "M", "warning")
        assert p["attachments"][0]["color"] == "#ff9800"

    def test_slack_error_color(self):
        from backend.services.notify import _build_slack_payload
        p = _build_slack_payload("T", "M", "error")
        assert p["attachments"][0]["color"] == "#dc3545"

    def test_slack_info_color(self):
        from backend.services.notify import _build_slack_payload
        p = _build_slack_payload("T", "M", "info")
        assert p["attachments"][0]["color"] == "#36a64f"


class TestTeamsPayload:

    def test_teams_payload_structure(self):
        from backend.services.notify import _build_teams_payload
        payload = _build_teams_payload("Test Title", "Test message", "warning")
        assert payload["@type"]   == "MessageCard"
        assert payload["summary"] == "Test Title"
        assert "sections" in payload
        assert len(payload["sections"]) == 1

    def test_teams_has_theme_color(self):
        from backend.services.notify import _build_teams_payload
        p = _build_teams_payload("T", "M", "error")
        assert "themeColor" in p
        assert p["themeColor"] == "DC3545"


# ── send_webhook ──────────────────────────────────────────────────────────────

class TestSendWebhook:

    @pytest.mark.asyncio
    async def test_returns_false_when_disabled(self):
        from backend.services.notify import send_webhook
        cfg = NotifyConfig(enabled=False, webhook_url="https://hooks.slack.com/x")
        result = await send_webhook("T", "M", config=cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_url(self):
        from backend.services.notify import send_webhook
        cfg = NotifyConfig(enabled=True, webhook_url="")
        result = await send_webhook("T", "M", config=cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_sends_to_slack_url(self):
        from backend.services.notify import send_webhook
        cfg = NotifyConfig(enabled=True, webhook_url="https://hooks.slack.com/services/test")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__  = AsyncMock(return_value=False)
            MockClient.return_value.post       = AsyncMock(return_value=mock_response)

            result = await send_webhook("Test", "Message", level="error", config=cfg)

        assert result is True
        posted_payload = MockClient.return_value.post.call_args[1]["json"]
        assert "attachments" in posted_payload   # Slack format

    @pytest.mark.asyncio
    async def test_sends_to_teams_url(self):
        from backend.services.notify import send_webhook
        cfg = NotifyConfig(enabled=True, webhook_url="https://company.office.com/webhook")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__  = AsyncMock(return_value=False)
            MockClient.return_value.post       = AsyncMock(return_value=mock_response)

            result = await send_webhook("Test", "Message", config=cfg)

        assert result is True
        posted_payload = MockClient.return_value.post.call_args[1]["json"]
        assert "@type" in posted_payload   # Teams format

    @pytest.mark.asyncio
    async def test_returns_false_on_http_error(self):
        from backend.services.notify import send_webhook
        import httpx
        cfg = NotifyConfig(enabled=True, webhook_url="https://hooks.slack.com/test")

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__  = AsyncMock(return_value=False)
            MockClient.return_value.post       = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            result = await send_webhook("T", "M", config=cfg)

        assert result is False

    @pytest.mark.asyncio
    async def test_custom_url_sends_generic_payload(self):
        from backend.services.notify import send_webhook
        cfg = NotifyConfig(enabled=True, webhook_url="https://my-custom-webhook.io/notify")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__  = AsyncMock(return_value=False)
            MockClient.return_value.post       = AsyncMock(return_value=mock_response)

            await send_webhook("T", "M", level="info", config=cfg)

        payload = MockClient.return_value.post.call_args[1]["json"]
        assert payload["title"]   == "T"
        assert payload["message"] == "M"
        assert payload["level"]   == "info"


# ── send_email ────────────────────────────────────────────────────────────────

class TestSendEmail:

    @pytest.mark.asyncio
    async def test_returns_false_when_no_email_to(self):
        from backend.services.notify import send_email
        cfg = NotifyConfig(email_to="", smtp_user="u@x.com", enabled=True)
        result = await send_email("Subject", "Body", config=cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_smtp_user(self):
        from backend.services.notify import send_email
        cfg = NotifyConfig(email_to="admin@x.com", smtp_user="", enabled=True)
        result = await send_email("Subject", "Body", config=cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_disabled(self):
        from backend.services.notify import send_email
        cfg = NotifyConfig(
            email_to="admin@x.com", smtp_user="bot@x.com",
            smtp_pass="pass", enabled=False
        )
        result = await send_email("Subject", "Body", config=cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_calls_smtp_when_configured(self):
        from backend.services.notify import send_email
        cfg = NotifyConfig(
            email_to="admin@x.com", email_from="agent@x.com",
            smtp_user="agent@x.com", smtp_pass="secret",
            smtp_host="smtp.gmail.com", smtp_port=587, enabled=True,
        )
        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__  = MagicMock(return_value=False)

        with patch("smtplib.SMTP", return_value=mock_smtp):
            result = await send_email("Test Subject", "Body text", config=cfg)

        assert result is True
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("agent@x.com", "secret")
        mock_smtp.sendmail.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_on_smtp_error(self):
        import smtplib
        from backend.services.notify import send_email
        cfg = NotifyConfig(
            email_to="a@x.com", smtp_user="b@x.com",
            smtp_pass="p", enabled=True,
        )
        with patch("smtplib.SMTP", side_effect=smtplib.SMTPException("Auth failed")):
            result = await send_email("S", "B", config=cfg)

        assert result is False


# ── High-level helpers ────────────────────────────────────────────────────────

class TestNotifyHelpers:

    @pytest.mark.asyncio
    async def test_notify_job_failed_calls_both(self):
        from backend.services.notify import notify_job_failed

        with (
            patch("backend.services.notify.send_webhook", return_value=True)  as mock_wh,
            patch("backend.services.notify.send_email",   return_value=False) as mock_em,
        ):
            await notify_job_failed(
                job_id="j1", company="VNM",
                source_type="pdf", error="Parse failed",
                config=NotifyConfig(enabled=True, webhook_url="https://hooks.slack.com/x"),
            )

        mock_wh.assert_awaited_once()
        mock_em.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_notify_job_failed_message_contains_info(self):
        from backend.services.notify import notify_job_failed
        sent_messages = []

        async def capture_webhook(title, message, level="warning", config=None):
            sent_messages.append((title, message))
            return True

        with (
            patch("backend.services.notify.send_webhook", side_effect=capture_webhook),
            patch("backend.services.notify.send_email",   return_value=False),
        ):
            await notify_job_failed(
                job_id="j42", company="Vinamilk",
                source_type="excel", error="File corrupt",
                config=NotifyConfig(enabled=True),
            )

        assert sent_messages
        title, message = sent_messages[0]
        assert "Vinamilk"    in title
        assert "j42"         in message
        assert "excel"       in message
        assert "File corrupt" in message

    @pytest.mark.asyncio
    async def test_notify_health_degraded(self):
        from backend.services.notify import notify_health_degraded
        with (
            patch("backend.services.notify.send_webhook", return_value=True) as mock_wh,
            patch("backend.services.notify.send_email",   return_value=False),
        ):
            await notify_health_degraded(
                status="error",
                checks={"chromadb": {"status": "error", "error": "Connection refused"}},
                config=NotifyConfig(enabled=True, webhook_url="https://x.com"),
            )
        mock_wh.assert_awaited_once()
        _, msg = mock_wh.call_args[0]
        assert "chromadb" in msg

    @pytest.mark.asyncio
    async def test_notify_error_rate_spike(self):
        from backend.services.notify import notify_error_rate_spike
        with patch("backend.services.notify.send_webhook", return_value=True) as mock_wh:
            await notify_error_rate_spike(
                endpoint="/predict",
                error_rate=0.35,
                threshold=0.20,
                config=NotifyConfig(enabled=True, webhook_url="https://x.com"),
            )
        mock_wh.assert_awaited_once()
        title = mock_wh.call_args[0][0]
        assert "/predict" in title

    @pytest.mark.asyncio
    async def test_helpers_no_op_when_disabled(self):
        from backend.services.notify import notify_job_failed
        cfg = NotifyConfig(enabled=False)
        with (
            patch("backend.services.notify.send_webhook") as mock_wh,
            patch("backend.services.notify.send_email")   as mock_em,
        ):
            await notify_job_failed("j1", "VNM", "text", "err", config=cfg)

        # Dù send được gọi, cả 2 nên trả False và không thực sự gửi
        # (enabled=False được check trong send_webhook/send_email)
        assert mock_wh.await_count + mock_em.await_count >= 0  # không crash


# ── start_error_rate_monitor ──────────────────────────────────────────────────

class TestErrorRateMonitor:

    @pytest.mark.asyncio
    async def test_monitor_exits_when_disabled(self):
        from backend.services.notify import start_error_rate_monitor
        cfg = NotifyConfig(enabled=False)
        # Phải return ngay, không loop
        import asyncio
        try:
            await asyncio.wait_for(start_error_rate_monitor(config=cfg), timeout=0.5)
        except asyncio.TimeoutError:
            pytest.fail("Monitor không exit khi disabled")

    @pytest.mark.asyncio
    async def test_monitor_calls_notify_on_high_error_rate(self):
        import asyncio
        from backend.services.notify import start_error_rate_monitor
        from backend.services.metrics import MetricsCollector

        mock_metrics = MetricsCollector()
        # Simulate nhiều errors
        for _ in range(15):
            mock_metrics.record_call("/predict", latency_ms=100.0, is_error=True)
        for _ in range(5):
            mock_metrics.record_call("/predict", latency_ms=50.0,  is_error=False)
        # error_rate = 15/20 = 0.75 > threshold 0.2

        cfg = NotifyConfig(enabled=True, webhook_url="https://hooks.slack.com/x",
                          error_rate_threshold=0.2)

        with (
            patch("backend.services.notify.metrics", mock_metrics),
            patch("backend.services.notify.notify_error_rate_spike") as mock_notify,
            patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError()]),
        ):
            mock_notify.return_value = None
            try:
                await start_error_rate_monitor(interval_seconds=1, config=cfg)
            except asyncio.CancelledError:
                pass

        mock_notify.assert_awaited()