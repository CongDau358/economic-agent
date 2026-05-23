# Economic Agent — Deployment Guide

## Yêu cầu hệ thống

| Thành phần | Tối thiểu | Khuyến nghị |
|-----------|-----------|-------------|
| Python | 3.11+ | 3.11 |
| RAM | 2 GB | 4 GB |
| Disk | 5 GB | 20 GB |
| CPU | 2 core | 4 core |

---

## 1. Local Development

```bash
# Clone & setup
git clone https://github.com/cdauu000/economic-agent.git
cd economic-agent

# Xóa venv/ khỏi git tracking (nếu chưa)
git rm -r --cached venv/ 2>/dev/null || true

# Tạo virtualenv
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Cài dependencies
pip install -r requirements.txt

# Setup .env
make env                           # hoặc: cp .env.example .env
# → Điền OPENAI_API_KEY vào .env

# Kiểm tra config
python scripts/check_env.py

# Tạo API key
make gen-key

# Chạy server
make dev                           # http://localhost:8000
```

---

## 2. Docker (Recommended)

```bash
cp .env.example .env
# Điền OPENAI_API_KEY và API_KEYS vào .env

# Build và chạy toàn bộ stack (API + Redis + Frontend)
docker compose up --build

# Chỉ chạy API + Redis
docker compose up api redis

# Xem logs
docker compose logs -f api

# Dừng
docker compose down
```

**Services:**
- API: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- Redis: `localhost:6379`

---

## 3. Biến môi trường

### Bắt buộc
```bash
OPENAI_API_KEY=sk-...              # OpenAI API key
API_KEYS=key1,key2                 # API keys cho X-API-Key header
AUTH_ENABLED=true
```

### Tuỳ chọn nhưng khuyến nghị
```bash
# Market data (miễn phí)
FRED_API_KEY=...                   # https://fred.stlouisfed.org/docs/api/api_key.html

# Cache
REDIS_URL=redis://localhost:6379/0 # Để trống → in-memory cache
CACHE_TTL_SECONDS=3600

# Model config
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# RAG
RAG_TOP_K=5
RAG_SCORE_THRESHOLD=0.5
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200

# Trend engine weights (tổng = 1.0)
WEIGHT_FINANCIAL=0.5
WEIGHT_SENTIMENT=0.3
WEIGHT_MACRO=0.2

# Logging
LOG_LEVEL=info                     # debug|info|warning|error
```

---

## 4. Production Checklist

```
□ AUTH_ENABLED=true
□ API_KEYS được set với key đủ dài (dùng: make gen-key)
□ OPENAI_API_KEY được set
□ REDIS_URL được set (không dùng in-memory cho production)
□ LOG_LEVEL=info (không dùng debug)
□ venv/ không được commit vào git
□ .env không được commit vào git
□ data/ được backup định kỳ (chứa ChromaDB)
□ /health?deep=true trả status "ok"
□ Rate limiting đang hoạt động (rate_limiting: true trong /health)
```

---

## 5. API Key Management

```bash
# Tạo 1 key mới và tự động thêm vào .env
make gen-key

# Tạo 3 keys
make gen-keys

# Tạo key tuỳ chỉnh (không lưu vào .env)
python scripts/generate_api_key.py --count 2 --length 48 --no-save
```

Key format: `ea_<40 random chars>` (ví dụ: `ea_Kx9mN2pQrL...`)

---

## 6. Data Management

```bash
# Xem dung lượng data
du -sh data/

# Backup vector store
tar -czf backup_vector_$(date +%Y%m%d).tar.gz data/vector/

# Reset toàn bộ data (CẢNH BÁO: xóa hết documents)
make reset

# Xóa cache
python scripts/clear_cache.py
```

---

## 7. Monitoring

```bash
# Health check cơ bản
curl http://localhost:8000/health

# Deep health check (kiểm tra ChromaDB, Redis, disk)
curl http://localhost:8000/health?deep=true

# Usage metrics
curl -H "X-API-Key: your-key" http://localhost:8000/metrics

# Benchmark
make benchmark
python scripts/benchmark.py --url http://localhost:8000 \
  --api-key your-key --requests 50 --concurrency 5
```

---

## 8. Ingestion Pipelines

```bash
# Batch predict cho nhiều công ty
python pipelines/batch_predict.py --sample
python pipelines/batch_predict.py --input companies.json --format csv,json,excel

# Schedule ingestion định kỳ (chạy 1 lần)
python pipelines/schedule_ingest.py

# Schedule ingestion mỗi 6 giờ (cần: pip install apscheduler)
python pipelines/schedule_ingest.py --scheduled --hours 6
```

---

## 9. Testing

```bash
# Chạy toàn bộ tests
make test

# Với coverage report
make test-cov

# Chạy test nhóm cụ thể
make test-trend     # trend engine tests
make test-services  # service tests

# Test endpoint thủ công
API_BASE=http://localhost:8000 \
API_KEY=your-key \
python scripts/test_predict.py
```

---

## 10. GitHub Actions CI

CI tự động chạy khi push lên `main` hoặc `develop`:

1. **Lint** — ruff check + format check
2. **Type check** — mypy (warning only)
3. **Tests** — pytest trên Python 3.11 + 3.12, với Redis service
4. **Docker build** — verify image builds (không push)

Xem: `.github/workflows/ci.yml`