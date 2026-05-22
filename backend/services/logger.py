"""
backend/services/logger.py
Structured JSON logging for production; colored console logging for development.

Usage:
    from backend.services.logger import setup_logging, get_logger
    
    setup_logging()   # Call once at startup in main.py
    log = get_logger(__name__)
    log.info("prediction.done", company="Acme", score=0.78, confidence=0.85)
"""

import logging
import logging.config
import sys
from typing import Any


# ── JSON formatter (production) ───────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """Outputs each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        import json, traceback, datetime

        log = {
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Extra fields set via log.info("msg", extra={"company": "Acme"})
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs", "message",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName", "exc_info", "exc_text",
            }:
                log[key] = value

        if record.exc_info:
            log["exception"] = traceback.format_exception(*record.exc_info)

        return json.dumps(log, default=str)


# ── Colored formatter (development) ──────────────────────────────────────────

COLORS = {
    "DEBUG": "\033[36m",    # cyan
    "INFO": "\033[32m",     # green
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",    # red
    "CRITICAL": "\033[35m", # magenta
}
RESET = "\033[0m"


class ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname:8s}{RESET}"
        return super().format(record)


# ── Setup ─────────────────────────────────────────────────────────────────────

def setup_logging(
    level: str = "INFO",
    json_logs: bool = False,
    log_file: str | None = None,
) -> None:
    """
    Configure root logger. Call once at application startup.
    
    Args:
        level:     Minimum log level (DEBUG / INFO / WARNING / ERROR).
        json_logs: True → JSON lines (for production / log aggregators).
                   False → human-readable colored output (for dev).
        log_file:  Optional path to write logs to a file in addition to stdout.
    """
    handlers: dict[str, Any] = {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json" if json_logs else "colored",
        }
    }

    if log_file:
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": log_file,
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "formatter": "json",
        }

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {"()": JSONFormatter},
                "colored": {
                    "()": ColorFormatter,
                    "format": "%(asctime)s %(levelname)s %(name)s  %(message)s",
                    "datefmt": "%H:%M:%S",
                },
            },
            "handlers": handlers,
            "loggers": {
                # Silence noisy third-party libs
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
                "chromadb": {"level": "WARNING"},
                "openai": {"level": "WARNING"},
                "uvicorn.access": {"level": "WARNING"},  # handled by AccessLogMiddleware
            },
            "root": {
                "level": level.upper(),
                "handlers": list(handlers.keys()),
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper — import this instead of `logging.getLogger`."""
    return logging.getLogger(name)