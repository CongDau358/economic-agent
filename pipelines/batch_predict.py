"""
pipelines/batch_predict.py  (CẬP NHẬT)

Chạy /predict cho nhiều công ty từ file JSON/CSV.
Output: CSV + JSON + Excel qua export service.

    python pipelines/batch_predict.py --sample
    python pipelines/batch_predict.py --input companies.json --output data/batch_results
    python pipelines/batch_predict.py --input companies.json --format csv,json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.trend_engine import TrendEngine
from backend.services.export import export_predictions
from backend.services.logger import get_logger, setup_logging

setup_logging()
log = get_logger("pipelines.batch_predict")


SAMPLE_INPUT = [
    {
        "company": "Vinamilk",
        "ticker": "VNM.HM",
        "financial_signals": ["revenue_up", "margin_stable", "eps_beat"],
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
    {
        "company": "VinGroup",
        "ticker": "VIC.HM",
        "financial_signals": ["revenue_up", "debt_increase"],
        "sentiment_signals": ["media_positive", "analyst_downgrade"],
        "macro_signals": ["interest_rate_high", "sector_tailwind"],
    },
    {
        "company": "Hoa Phat Group",
        "ticker": "HPG.HM",
        "financial_signals": ["revenue_down", "margin_compression"],
        "sentiment_signals": ["negative_news"],
        "macro_signals": ["commodity_cost_up", "gdp_growth"],
    },
]


def run_batch(
    companies: list[dict],
    output_dir: Path,
    formats: list[str],
) -> list[dict]:
    engine  = TrendEngine()
    results = []

    log.info("batch.start", extra={"n": len(companies)})

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
                "company":    company,
                "score":      result.get("score"),
                "short_term": (result.get("trend") or {}).get("short_term"),
                "status":     result.get("status"),
            })
        except Exception as exc:
            log.error("batch.failed", extra={"company": company, "error": str(exc)})
            results.append({
                "company": company,
                "ticker":  item.get("ticker", ""),
                "status":  "ERROR",
                "error":   str(exc),
                "score":   None,
                "trend":   None,
                "confidence": 0.0,
                "risks":   [],
                "opportunities": [],
                "executive_summary": "",
            })

    # Export
    paths = export_predictions(results, output_dir, formats=formats)
    log.info("batch.complete", extra={"n": len(results), "paths": paths})

    print(f"\n{'─'*55}")
    print(f"  Batch Predict — {len(results)} công ty")
    print(f"{'─'*55}")
    for fmt, path in paths.items():
        print(f"  {fmt.upper():6s}: {path}")

    # Summary table
    print(f"\n  {'Company':<20} {'Score':>6}  {'Trend':<10}  Status")
    print(f"  {'─'*20}  {'─'*6}  {'─'*10}  {'─'*16}")
    for r in results:
        trend = r.get("trend") or {}
        st    = trend.get("short_term", "N/A") if isinstance(trend, dict) else "N/A"
        score = f"{r['score']:.3f}" if r.get("score") is not None else "  N/A"
        print(f"  {r['company']:<20} {score:>6}  {st:<10}  {r.get('status','')}")
    print(f"{'─'*55}\n")

    return results


def main():
    parser = argparse.ArgumentParser(description="Batch predict for multiple companies")
    parser.add_argument("--input",   help="File JSON danh sách công ty")
    parser.add_argument("--output",  default="data/batch_results", help="Thư mục output")
    parser.add_argument("--format",  default="csv,json,excel",
                        help="Formats xuất (csv,json,excel)")
    parser.add_argument("--sample",  action="store_true", help="Dùng dữ liệu mẫu")
    args = parser.parse_args()

    if args.sample or not args.input:
        companies = SAMPLE_INPUT
        print("Chạy với dữ liệu mẫu...")
    else:
        companies = json.loads(Path(args.input).read_text(encoding="utf-8"))

    formats = [f.strip() for f in args.format.split(",")]
    run_batch(companies, Path(args.output), formats)


if __name__ == "__main__":
    main()