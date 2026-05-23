"""
backend/services/notify.py  (TẠO MỚI)

Notification service — gửi alert khi:
  - Job ingestion thất bại
  - Error rate vượt ngưỡng
  - Health check degraded/error

Hỗ trợ:
  - Webhook (Slack, Discord, Teams, custom)
  - Email (SMTP)

Cấu hình trong .env:
    NOTIFY_WEBHOOK_URL=https://hooks.slack.com/services/...
    NOTIFY_EMAIL_TO=admin@company.com
    NOTIFY_EMAIL_FROM=agent@company.com
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=...
    SMTP_PASS=...
    NOTIFY_ERROR_RATE_THRESHOLD=0.2   # alert khi >20% errors
"""

from __future__ import annotations

import asyncio
import smtplib
import os
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx

from .logger import get_logger

log = get_logger("economic_agent.notify")


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class NotifyConfig:
    webhook_url:            str   = ""
    email_to:               str   = ""
    email_from:             str   = ""
    smtp_host:              str   = "smtp.gmail.com"
    smtp_port:              int   = 587
    smtp_user:              str   = ""
    smtp_pass:              str   = ""
    error_rate_threshold:   float = 0.2    # 20%
    enabled:                bool  = True

    @classmethod
    def from_env(cls) -> "NotifyConfig":
        return cls(
            webhook_url=os.getenv("NOTIFY_WEBHOOK_URL", ""),
            email_to=os.getenv("NOTIFY_EMAIL_TO", ""),
            email_from=os.getenv("NOTIFY_EMAIL_FROM", ""),
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_pass=os.getenv("SMTP_PASS", ""),
            error_rate_threshold=float(os.getenv("NOTIFY_ERROR_RATE_THRESHOLD", "0.2")),
            enabled=os.getenv("NOTIFY_ENABLED", "true").lower() == "true",
        )


# ── Payload builder ───────────────────────────────────────────────────────────

def _build_slack_payload(title: str, message: str, level: str = "warning") -> dict:
    color = {"info": "#36a64f", "warning": "#ff9800", "error": "#dc3545"}.get(level, "#6366f1")
    return {
        "attachments": [{
            "color": color,
            "title": f"[Economic Agent] {title}",
            "text":  message,
            "footer": "Economic Agent v1.1.0",
        }]
    }


def _build_teams_payload(title: str, message: str, level: str = "warning") -> dict:
    return {
        "@type":    "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary":  title,
        "themeColor": {"warning": "FF9800", "error": "DC3545"}.get(level, "6366F1"),
        "sections": [{
            "activityTitle": f"[Economic Agent] {title}",
            "activityText":  message,
        }],
    }


# ── Webhook ───────────────────────────────────────────────────────────────────

async def send_webhook(
    title:   str,
    message: str,
    level:   str = "warning",
    config:  NotifyConfig | None = None,
) -> bool:
    cfg = config or NotifyConfig.from_env()
    if not cfg.enabled or not cfg.webhook_url:
        return False

    # Auto-detect Slack vs Teams vs custom
    if "slack.com" in cfg.webhook_url or "hooks.slack" in cfg.webhook_url:
        payload = _build_slack_payload(title, message, level)
    elif "office.com" in cfg.webhook_url or "microsoft" in cfg.webhook_url:
        payload = _build_teams_payload(title, message, level)
    else:
        payload = {"title": title, "message": message, "level": level}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(cfg.webhook_url, json=payload)
            r.raise_for_status()
            log.info("notify.webhook.sent", extra={"title": title, "level": level})
            return True
    except Exception as exc:
        log.warning("notify.webhook.failed", extra={"error": str(exc)})
        return False


# ── Email (SMTP) ──────────────────────────────────────────────────────────────

async def send_email(
    subject: str,
    body:    str,
    config:  NotifyConfig | None = None,
) -> bool:
    cfg = config or NotifyConfig.from_env()
    if not cfg.enabled or not cfg.email_to or not cfg.smtp_user:
        return False

    def _send():
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Economic Agent] {subject}"
        msg["From"]    = cfg.email_from or cfg.smtp_user
        msg["To"]      = cfg.email_to
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(cfg.smtp_user, cfg.smtp_pass)
            smtp.sendmail(cfg.smtp_user, cfg.email_to, msg.as_string())

    try:
        await asyncio.to_thread(_send)
        log.info("notify.email.sent", extra={"to": cfg.email_to, "subject": subject})
        return True
    except Exception as exc:
        log.warning("notify.email.failed", extra={"error": str(exc)})
        return False


# ── High-level helpers ────────────────────────────────────────────────────────

async def notify_job_failed(
    job_id:      str,
    company:     str,
    source_type: str,
    error:       str,
    config:      NotifyConfig | None = None,
) -> None:
    """Gọi sau khi job ingestion thất bại."""
    title   = f"Ingestion Job Failed — {company}"
    message = (
        f"Job ID:      {job_id}\n"
        f"Company:     {company}\n"
        f"Source type: {source_type}\n"
        f"Error:       {error}"
    )
    await asyncio.gather(
        send_webhook(title, message, level="error", config=config),
        send_email(title, message, config=config),
        return_exceptions=True,
    )


async def notify_health_degraded(
    status: str,
    checks: dict[str, Any],
    config: NotifyConfig | None = None,
) -> None:
    """Gọi khi /health?deep=true trả degraded hoặc error."""
    failed = [
        f"  • {name}: {info.get('error', info.get('status'))}"
        for name, info in checks.items()
        if info.get("status") in ("error", "warning")
    ]
    title   = f"Health Check {status.upper()}"
    message = "Các dependency có vấn đề:\n" + "\n".join(failed)
    await asyncio.gather(
        send_webhook(title, message, level=status, config=config),
        send_email(title, message, config=config),
        return_exceptions=True,
    )


async def notify_error_rate_spike(
    endpoint:   str,
    error_rate: float,
    threshold:  float,
    config:     NotifyConfig | None = None,
) -> None:
    """Gọi khi error rate vượt ngưỡng."""
    title   = f"High Error Rate — {endpoint}"
    message = (
        f"Endpoint:   {endpoint}\n"
        f"Error rate: {error_rate:.1%}\n"
        f"Threshold:  {threshold:.1%}"
    )
    await send_webhook(title, message, level="error", config=config)


# ── Background monitor ────────────────────────────────────────────────────────

async def start_error_rate_monitor(
    interval_seconds: int = 300,
    config:           NotifyConfig | None = None,
) -> None:
    """
    Chạy trong background, kiểm tra error rate định kỳ.
    Thêm vào lifespan trong main.py:

        asyncio.create_task(start_error_rate_monitor())
    """
    cfg = config or NotifyConfig.from_env()
    if not cfg.enabled:
        return

    from .metrics import metrics as m
    while True:
        await asyncio.sleep(interval_seconds)
        summary = m.summary()
        for endpoint, stats in summary.get("endpoints", {}).items():
            rate = stats.get("error_rate", 0)
            if rate > cfg.error_rate_threshold and stats.get("calls", 0) >= 10:
                await notify_error_rate_spike(endpoint, rate, cfg.error_rate_threshold, cfg)