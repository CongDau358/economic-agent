"""
pipelines/schedule_ingest.py  (TẠO MỚI)

Chạy ingestion định kỳ từ danh sách URL tin tức / file.
Dùng APScheduler hoặc chạy thủ công: python pipelines/schedule_ingest.py

Thêm vào requirements.txt:
    apscheduler==3.10.4
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Cho phép import backend từ root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ingestion.ingestor import ingest
from backend.services.logger import setup_logging

setup_logging(level="INFO")
log = logging.getLogger("pipelines.schedule")


# ── Danh sách nguồn cần cập nhật định kỳ ─────────────────────────────────────
WATCH_SOURCES: list[dict] = [
    {
        "source_type": "url",
        "company": "Vinamilk",
        "sector": "Consumer Staples",
        "url": "https://www.vinamilk.com.vn/vi/tin-tuc",
    },
    {
        "source_type": "url",
        "company": "VinGroup",
        "sector": "Real Estate",
        "url": "https://www.vingroup.net/tin-tuc-su-kien",
    },
    # Thêm nguồn khác vào đây
]


def run_all() -> None:
    log.info("pipeline.start", extra={"n_sources": len(WATCH_SOURCES)})
    success, failed = 0, 0
    for src in WATCH_SOURCES:
        try:
            result = ingest(**src)
            log.info(
                "pipeline.done",
                extra={"company": src["company"], "chunks": result["chunks_upserted"]},
            )
            success += 1
        except Exception as exc:
            log.error("pipeline.failed", extra={"company": src.get("company"), "error": str(exc)})
            failed += 1

    log.info("pipeline.summary", extra={"success": success, "failed": failed})


def run_scheduled(interval_hours: int = 6) -> None:
    """Chạy theo lịch — yêu cầu: pip install apscheduler"""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
    except ImportError:
        log.error("Cần cài: pip install apscheduler")
        return

    scheduler = BlockingScheduler()
    scheduler.add_job(run_all, "interval", hours=interval_hours)
    log.info("scheduler.start", extra={"interval_hours": interval_hours})
    run_all()  # chạy ngay lần đầu
    scheduler.start()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--scheduled", action="store_true", help="Chạy theo lịch định kỳ")
    parser.add_argument("--hours", type=int, default=6, help="Khoảng cách giữa các lần chạy (giờ)")
    args = parser.parse_args()

    if args.scheduled:
        run_scheduled(args.hours)
    else:
        run_all()