"""
scripts/benchmark.py
Benchmark nhanh các endpoint chính.

    python scripts/benchmark.py
    python scripts/benchmark.py --url http://localhost:8000 --requests 50
    python scripts/benchmark.py --endpoint predict --concurrency 5
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

import httpx


# ── Payloads ──────────────────────────────────────────────────────────────────

PREDICT_PAYLOAD = {
    "company": "Vinamilk",
    "financial_signals": ["revenue_up", "margin_stable", "eps_beat"],
    "sentiment_signals": ["analyst_upgrade", "positive_news"],
    "macro_signals": ["policy_support", "inflation_stable"],
}

ASK_PAYLOAD = {
    "question": "Rủi ro chính của công ty là gì?",
    "company": "Vinamilk",
    "retrieval_mode": "hybrid",
    "top_k": 4,
}

HEALTH_PAYLOAD = None


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class BenchResult:
    endpoint:     str
    n_requests:   int
    concurrency:  int
    latencies_ms: list[float] = field(default_factory=list)
    errors:       int = 0
    status_codes: list[int] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return self.n_requests - self.errors

    @property
    def p50(self) -> float:
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0

    @property
    def p95(self) -> float:
        if not self.latencies_ms:
            return 0
        s = sorted(self.latencies_ms)
        idx = int(len(s) * 0.95)
        return s[min(idx, len(s) - 1)]

    @property
    def p99(self) -> float:
        if not self.latencies_ms:
            return 0
        s = sorted(self.latencies_ms)
        idx = int(len(s) * 0.99)
        return s[min(idx, len(s) - 1)]

    @property
    def avg(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0

    @property
    def rps(self) -> float:
        total_s = sum(self.latencies_ms) / 1000
        return round(self.success_count / total_s, 2) if total_s > 0 else 0

    def print_summary(self) -> None:
        bar = "█" * min(40, int(self.p95 / 50))
        print(f"\n  Endpoint:    {self.endpoint}")
        print(f"  Requests:    {self.n_requests} ({self.concurrency} concurrent)")
        print(f"  Success:     {self.success_count}/{self.n_requests}")
        print(f"  Errors:      {self.errors}")
        print(f"  Latency p50: {self.p50:>8.1f} ms")
        print(f"  Latency p95: {self.p95:>8.1f} ms  {bar}")
        print(f"  Latency p99: {self.p99:>8.1f} ms")
        print(f"  Avg latency: {self.avg:>8.1f} ms")
        print(f"  RPS (est.):  {self.rps}")
        if self.errors > 0:
            codes = set(self.status_codes)
            print(f"  Status codes seen: {codes}")


# ── Runner ────────────────────────────────────────────────────────────────────

async def _single_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    payload: dict | None,
    result: BenchResult,
    sem: asyncio.Semaphore,
) -> None:
    async with sem:
        start = time.perf_counter()
        try:
            if method == "GET":
                r = await client.get(url)
            else:
                r = await client.post(url, json=payload)
            elapsed = (time.perf_counter() - start) * 1000
            result.latencies_ms.append(elapsed)
            result.status_codes.append(r.status_code)
            if r.status_code >= 400:
                result.errors += 1
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            result.latencies_ms.append(elapsed)
            result.errors += 1


async def benchmark(
    base_url: str,
    endpoint: str,
    n_requests: int,
    concurrency: int,
    api_key: str,
) -> BenchResult:
    configs = {
        "health":  ("GET",  "/health",  None),
        "predict": ("POST", "/predict", PREDICT_PAYLOAD),
        "ask":     ("POST", "/ask",     ASK_PAYLOAD),
    }
    if endpoint not in configs:
        raise ValueError(f"Unknown endpoint: {endpoint}. Choose: {list(configs)}")

    method, path, payload = configs[endpoint]
    url = base_url.rstrip("/") + path
    result = BenchResult(endpoint=f"{method} {path}", n_requests=n_requests, concurrency=concurrency)

    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        tasks = [
            _single_request(client, method, url, payload, result, sem)
            for _ in range(n_requests)
        ]
        print(f"  Running {n_requests} requests to {url}...", end="", flush=True)
        wall_start = time.perf_counter()
        await asyncio.gather(*tasks)
        wall_elapsed = time.perf_counter() - wall_start
        print(f" done in {wall_elapsed:.1f}s")

    return result


def main():
    parser = argparse.ArgumentParser(description="Benchmark Economic Agent API")
    parser.add_argument("--url",         default="http://localhost:8000")
    parser.add_argument("--api-key",     default="",         help="X-API-Key header")
    parser.add_argument("--requests",    type=int, default=20, help="Số requests (default: 20)")
    parser.add_argument("--concurrency", type=int, default=4,  help="Concurrent requests (default: 4)")
    parser.add_argument("--endpoint",    default="all",
                        help="health | predict | ask | all (default: all)")
    args = parser.parse_args()

    endpoints = ["health", "predict", "ask"] if args.endpoint == "all" else [args.endpoint]

    print(f"\n{'─'*55}")
    print(f"  Economic Agent Benchmark")
    print(f"  URL: {args.url}")
    print(f"  Requests: {args.requests}  Concurrency: {args.concurrency}")
    print(f"{'─'*55}")

    for ep in endpoints:
        result = asyncio.run(benchmark(
            args.url, ep, args.requests, args.concurrency, args.api_key,
        ))
        result.print_summary()

    print(f"\n{'─'*55}\n")


if __name__ == "__main__":
    main()