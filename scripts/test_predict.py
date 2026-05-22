"""
scripts/test_predict.py
Test nhanh /predict endpoint.

    python scripts/test_predict.py
"""

import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests

BASE = os.getenv("API_BASE", "http://localhost:8000")
KEY  = os.getenv("API_KEY", "")

payload = {
    "company": "Vinamilk",
    "ticker": "VNM.HM",
    "financial_signals": ["revenue_up", "margin_stable", "eps_beat"],
    "sentiment_signals": ["analyst_upgrade", "positive_news"],
    "macro_signals": ["policy_support", "inflation_stable"],
    "enrich_with_market_data": False,
}

r = requests.post(f"{BASE}/predict", json=payload, headers={"X-API-Key": KEY})
print(f"Status: {r.status_code}")
print(json.dumps(r.json(), ensure_ascii=False, indent=2))