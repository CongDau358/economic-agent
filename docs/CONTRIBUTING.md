# Contributing to Economic Agent

## Setup

```bash
git clone https://github.com/cdauu000/economic-agent.git
cd economic-agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
make env         # tạo .env
make gen-key     # tạo API key
make dev         # chạy server
```

## Workflow

```
feature branch → PR → CI (lint + test) → merge vào develop → main
```

```bash
git checkout -b feature/ten-tinh-nang
# code...
make check       # lint + typecheck + test
git push origin feature/ten-tinh-nang
```

## Cấu trúc code

| Thư mục | Mục đích |
|---------|----------|
| `backend/` | FastAPI app, business logic |
| `backend/services/` | Các service tái sử dụng (cache, logger, metrics...) |
| `backend/ingestion/` | Ingestion pipelines (PDF, Excel, News, Text) |
| `backend/rag/` | Vector store, embedding pipeline |
| `backend/retrieval/` | Hybrid retrieval API |
| `backend/orchestration/` | RAG + LLM orchestration |
| `backend/memory/` | Document lifecycle management |
| `pipelines/` | Batch/scheduled scripts |
| `tests/` | Test suite |
| `scripts/` | Dev utilities |
| `docs/` | Documentation |

## Thêm signal mới vào TrendEngine

1. Mở `backend/trend_engine.py`
2. Thêm vào đúng registry (`FINANCIAL_SIGNALS`, `SENTIMENT_SIGNALS`, `MACRO_SIGNALS`)
3. Score: dương (+0.1 → +1.0) = bullish, âm (-0.1 → -1.0) = bearish
4. Thêm test vào `tests/test_trend_engine.py`

```python
# Ví dụ: thêm signal mới
FINANCIAL_SIGNALS: dict[str, float] = {
    ...
    "new_product_launch": +0.4,   # tín hiệu mới
    ...
}
```

## Thêm nguồn ingestion mới

1. Thêm extractor vào `backend/ingestion/`
2. Đăng ký trong `_sync_ingest()` ở `backend/main.py`
3. Thêm vào `source_type` validation whitelist
4. Viết test trong `tests/test_ingestion.py`

## Coding standards

```bash
make lint        # ruff check — phải pass trước khi commit
make format      # ruff format — tự động format
make typecheck   # mypy — warning only
```

- **Async**: dùng `async/await` cho endpoints, `asyncio.to_thread()` cho sync IO
- **Logging**: `log = get_logger(__name__)` — không dùng `print()` trong production code
- **Config**: đọc từ `get_settings()` — không hardcode config
- **Tests**: mỗi feature mới phải có tests, coverage target >= 60%
- **Docstrings**: function công khai phải có docstring

## Test

```bash
make test           # toàn bộ tests
make test-cov       # với coverage report
make test-trend     # chỉ trend engine
make test-services  # chỉ services

# Chạy 1 test cụ thể
pytest tests/test_trend_engine.py::TestTrendEngine::test_analyze_bullish -v
```

## Env vars mới

Khi thêm config mới:
1. Thêm vào `backend/config.py` với default hợp lý
2. Thêm vào `.env.example` với comment giải thích
3. Thêm vào `docs/DEPLOYMENT.md` bảng env vars
4. Thêm test vào `tests/test_config.py`

## Commit message

```
feat: thêm signal mới cho market_cap_growth
fix: sửa bug cache key collision khi ticker=None
refactor: tách health check thành service riêng
test: thêm tests cho WebSocket streaming
docs: cập nhật API.md với /admin endpoints
chore: nâng cấp pydantic-settings lên 2.6.0
```