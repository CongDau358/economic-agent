"""
pipelines/batch_predict.py  (TẠO MỚI)

Chạy /predict cho nhiều công ty từ file JSON/CSV.
Output: CSV kết quả + JSON chi tiết.

Dùng:
    python pipelines/batch_predict.py --input companies.json --output results/
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.trend_engine import TrendEngine
from backend.services.logger import setup_logging

setup_logging()

import logging
log = logging.getLogger("pipelines.batch_predict")


SAMPLE_INPUT = [
    {
        "company": "Vinamilk",
        "ticker": "VNM.HM",
        "financial_signals": ["revenue_up", "margin_stable", "dividend_increase"],
        "sentiment_signals": ["analyst_upgrade", "positive_news"],
        "macro_signals": ["policy_support", "inflation_stable"],
    },
    {
        "company": "Vietcombank",
        "ticker": "VCB.HM",
        "financial_signals": ["profit_up", "eps_beat", "guidance_raised"],
        "sentiment_signals": ["institutional_buying"],
        "macro_signals": ["interest_rate_stable", "credit_easing"],
    },
]


def run_batch(companies: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    engine = TrendEngine()
    results = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    for item in companies:
        company = item.get("company", "Unknown")
        try:
            result = engine.analyze(
                company=company,
                financial_signals=item.get("financial_signals", []),
                sentiment_signals=item.get("sentiment_signals", []),
                macro_signals=item.get("macro_signals", []),
            )
            result["ticker"] = item.get("ticker", "")
            results.append(result)
            log.info("batch.predict", extra={
                "company": company,
                "score": result.get("score"),
                "trend": result.get("trend", {}).get("short_term"),
            })
        except Exception as exc:
            log.error("batch.failed", extra={"company": company, "error": str(exc)})
            results.append({"company": company, "status": "ERROR", "error": str(exc)})

    # JSON chi tiết
    json_path = output_dir / f"batch_{ts}.json"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    # CSV tóm tắt
    csv_path = output_dir / f"batch_{ts}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["company", "ticker", "score", "short_term", "near_term", "confidence", "status"])
        for r in results:
            trend = r.get("trend") or {}
            writer.writerow([
                r.get("company"),
                r.get("ticker", ""),
                r.get("score", ""),
                trend.get("short_term", "") if isinstance(trend, dict) else "",
                trend.get("near_term", "") if isinstance(trend, dict) else "",
                r.get("confidence", ""),
                r.get("status", ""),
            ])

    log.info("batch.complete", extra={"json": str(json_path), "csv": str(csv_path), "n": len(results)})
    print(f"\n✓ JSON: {json_path}\n✓ CSV:  {csv_path}\n✓ {len(results)} công ty đã xử lý")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="File JSON chứa danh sách công ty")
    parser.add_argument("--output", default="data/batch_results", help="Thư mục output")
    parser.add_argument("--sample", action="store_true", help="Chạy với dữ liệu mẫu")
    args = parser.parse_args()

    if args.sample or not args.input:
        companies = SAMPLE_INPUT
        print("Chạy với dữ liệu mẫu...")
    else:
        companies = json.loads(Path(args.input).read_text(encoding="utf-8"))

    run_batch(companies, Path(args.output))