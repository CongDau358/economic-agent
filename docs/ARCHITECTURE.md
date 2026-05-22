# Changelog

## [1.1.0] — Upgrade

### Added
- `backend/config.py` — Pydantic Settings, tất cả config từ `.env`
- `backend/auth.py` — `X-API-Key` middleware, `AccessLogMiddleware`
- `backend/models.py` — Shared Pydantic response models
- `backend/exception_handlers.py` — Global 422/4xx/500 handler, JSON chuẩn
- `backend/services/cache.py` — In-memory cache + Redis, decorator `@cached`
- `backend/services/job_store.py` — Job tracking với `create/update/get/list/cleanup`
- `backend/services/logger.py` — JSON logs (production) + colored console (dev)
- `backend/services/market_data.py` — yfinance (stock) + FRED (macro indicators)
- `backend/services/metrics.py` — Usage metrics: calls, latency, error rate, cache hit rate
- `backend/services/rate_limiter.py` — slowapi: 10/30/20 req/min cho upload/predict/ask
- `GET /jobs` — List tất cả jobs với filter `company`, `status`, `limit`
- `GET /jobs/{job_id}` — Job detail
- `GET /metrics` — Usage metrics endpoint
- `WS /ws/analyze` — WebSocket streaming real-time analysis
- `Makefile` — `make dev/test/lint/docker-up/batch-predict/clean/reset`
- `docs/API.md` — API reference đầy đủ
- `docs/ARCHITECTURE.md` — Kiến trúc hệ thống
- `scripts/check_env.py` — Kiểm tra `.env` trước khi chạy
- `scripts/clear_cache.py` — Xóa cache
- `scripts/test_predict.py` — Test nhanh endpoint
- `pipelines/schedule_ingest.py` — Cron ingestion định kỳ
- `pipelines/batch_predict.py` — Batch scoring nhiều công ty, export CSV+JSON
- `pytest.ini`, `tests/conftest.py` — Test infrastructure
- `tests/test_trend_engine.py` — 22 test cases cho TrendEngine
- `tests/test_services.py` — Tests cho cache/job_store/logger/rate_limiter
- `tests/test_market_data.py` — Tests cho market data (mocked)
- `tests/test_ingestion.py` — Tests cho ingestion pipeline (mocked)
- `tests/test_metrics.py` — Tests cho MetricsCollector
- `.github/workflows/ci.yml` — CI: lint + test (3.11/3.12) + docker build
- `Dockerfile` (multi-stage) + `docker-compose.yml` (API + Redis + Frontend)
- `.gitignore` — loại `venv/`, `data/`, `.env`

### Changed
- `backend/main.py` — Tích hợp auth, CORS, rate limiting, background tasks,
  job store, cache, metrics, WebSocket, lifespan handler, `/metrics` endpoint
- `backend/trend_engine.py` — Signal registry đầy đủ (54 signals), short/near-term
  trend, scenario analysis, conflict detection, confidence penalties,
  INSUFFICIENT_DATA guard, `predict_trend()` backward-compat wrapper
- `POST /upload` — Async (BackgroundTasks), không block, trả `job_id` ngay
- `POST /predict` — Cache + market data enrichment + ticker support
- `POST /ask` — Cache 30 phút, chạy trong thread
- `GET /health` — Thêm jobs stats, rate_limiting, cache info
- `requirements.txt` — Thêm `python-docx`, `pydantic-settings`, `yfinance`,
  `fredapi`, `httpx`, `redis[asyncio]`, `slowapi`, `apscheduler`, `pytest-*`

### Fixed
- `venv/` bị commit vào git → thêm `.gitignore`
- `python-docx` thiếu trong `requirements.txt` dù Word ingestion đã được mô tả
- `.env.example` không hiển thị trong viewer → cung cấp dạng `.txt`

## [1.0.0] — Initial Release

- FastAPI backend: `/health`, `/upload`, `/predict`, `/ask`
- ChromaDB vector store
- PDF, Excel, News, Text ingestion pipelines
- Hybrid retrieval (dense + sparse)
- Prompt orchestration pipeline
- Deterministic trend scoring
- AGENT.md spec