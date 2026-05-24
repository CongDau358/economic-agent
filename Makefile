# ── Economic Agent — Developer Makefile ───────────────────────────────────────
# Dùng: make <target>

PYTHON  ?= python
PIP     ?= pip
UVICORN ?= uvicorn
APP      = backend.main:app

.PHONY: help install dev test test-cov lint format typecheck \
        docker-up docker-down clean reset batch-predict schedule-ingest

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Economic Agent — Available commands:"
	@echo ""
	@echo "  make install          Cài tất cả dependencies"
	@echo "  make dev              Chạy server dev (auto-reload)"
	@echo "  make test             Chạy test suite"
	@echo "  make test-cov         Chạy tests + coverage report"
	@echo "  make lint             Kiểm tra code style (ruff)"
	@echo "  make format           Tự động format code (ruff)"
	@echo "  make typecheck        Kiểm tra type hints (mypy)"
	@echo "  make docker-up        Khởi động Docker (API + Redis + Frontend)"
	@echo "  make docker-down      Dừng Docker"
	@echo "  make batch-predict    Chạy batch predict với dữ liệu mẫu"
	@echo "  make schedule-ingest  Chạy ingestion pipeline một lần"
	@echo "  make clean            Xóa __pycache__, .pytest_cache"
	@echo "  make reset            Xóa toàn bộ data (vector store, raw, processed)"
	@echo ""

# ── Install ───────────────────────────────────────────────────────────────────
install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -r requirements.txt ruff mypy

# ── Dev server ────────────────────────────────────────────────────────────────
dev:
	$(UVICORN) $(APP) --reload --host 0.0.0.0 --port 8000

dev-log:
	LOG_LEVEL=debug $(UVICORN) $(APP) --reload --host 0.0.0.0 --port 8000

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v \
		--cov=backend \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-fail-under=60

test-fast:
	pytest tests/ -v -x --tb=short   # dừng ở lỗi đầu tiên

test-trend:
	pytest tests/test_trend_engine.py -v

test-services:
	pytest tests/test_services.py -v

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	ruff check backend/ tests/

format:
	ruff format backend/ tests/
	ruff check --fix backend/ tests/

typecheck:
	mypy backend/ --ignore-missing-imports --no-strict-optional

check: lint typecheck test  # chạy toàn bộ trước khi commit

# ── Docker ────────────────────────────────────────────────────────────────────
docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f api

docker-restart:
	docker compose restart api

# ── Pipelines ─────────────────────────────────────────────────────────────────
batch-predict:
	$(PYTHON) pipelines/batch_predict.py --sample

batch-predict-file:
	$(PYTHON) pipelines/batch_predict.py --input $(INPUT) --output data/batch_results

schedule-ingest:
	$(PYTHON) pipelines/schedule_ingest.py

schedule-ingest-cron:
	$(PYTHON) pipelines/schedule_ingest.py --scheduled --hours 6

# ── Utilities ─────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "✓ Cleaned"

reset: clean
	@echo "⚠ Xóa toàn bộ data. Tiếp tục? [y/N]" && read ans && [ "$$ans" = "y" ]
	rm -rf data/vector data/raw data/processed data/batch_results
	mkdir -p data/vector data/raw data/processed
	@echo "✓ Data reset"

# ── Env setup ─────────────────────────────────────────────────────────────────
env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ .env tạo từ .env.example — hãy điền OPENAI_API_KEY"; \
	else \
		echo ".env đã tồn tại"; \
	fi

# ── Security & Benchmarking ───────────────────────────────────────────────────
gen-key:
	$(PYTHON) scripts/generate_api_key.py

gen-keys:
	$(PYTHON) scripts/generate_api_key.py --count 3

benchmark:
	$(PYTHON) scripts/benchmark.py --requests 20 --concurrency 4

benchmark-predict:
	$(PYTHON) scripts/benchmark.py --endpoint predict --requests 30

test-all:
	pytest tests/ -v \
		--tb=short \
		--cov=backend \
		--cov-report=term-missing \
		--cov-report=html:htmlcov

# ── Health & monitoring ───────────────────────────────────────────────────────
health:
	curl -s http://localhost:8000/health | python -m json.tool

health-deep:
	curl -s "http://localhost:8000/health?deep=true" | python -m json.tool

test-health:
	pytest tests/test_health.py tests/test_config.py -v

test-config:
	pytest tests/test_config.py -v

# ── Admin ─────────────────────────────────────────────────────────────────────
admin-stats:
	curl -s -H "X-API-Key: $(KEY)" http://localhost:8000/admin/stats | python -m json.tool

admin-docs:
	curl -s -H "X-API-Key: $(KEY)" "http://localhost:8000/admin/documents?limit=10" | python -m json.tool

admin-clear-cache:
	curl -s -X DELETE -H "X-API-Key: $(KEY)" http://localhost:8000/admin/cache | python -m json.tool

admin-clear-jobs:
	curl -s -X DELETE -H "X-API-Key: $(KEY)" http://localhost:8000/admin/jobs | python -m json.tool

# ── Seed data ─────────────────────────────────────────────────────────────────
seed:
	$(PYTHON) scripts/seed_data.py

seed-company:
	$(PYTHON) scripts/seed_data.py --company $(COMPANY)

seed-list:
	$(PYTHON) scripts/seed_data.py --list

# ── Tests mới ─────────────────────────────────────────────────────────────────
test-admin:
	pytest tests/test_admin.py -v

test-pipelines:
	pytest tests/test_pipelines.py -v

test-notify:
	pytest tests/test_notify.py -v

# ── Search ────────────────────────────────────────────────────────────────────
search:
	curl -s -H "X-API-Key: $(KEY)" \
		"http://localhost:8000/search?q=$(Q)&top_k=5" | python -m json.tool

test-search:
	pytest tests/test_search.py -v

test-notify:
	pytest tests/test_notify.py -v

# ── Integration tests ─────────────────────────────────────────────────────────
test-integration:
	pytest tests/test_integration.py -v --tb=short

# ── Full test suite with all groups ──────────────────────────────────────────
test-all-groups:
	pytest tests/ -v --tb=short \
		--cov=backend \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-fail-under=60 \
		-p no:warnings

# ── Shell monitoring ─────────────────────────────────────────────────────────
monitor:
	API_URL=http://localhost:8000 API_KEY=$(KEY) \
		bash scripts/health_check.sh --deep

monitor-loop:
	API_URL=http://localhost:8000 API_KEY=$(KEY) \
		bash scripts/health_check.sh --deep --interval 60

# ── Frontend ─────────────────────────────────────────────────────────────────
frontend-dev:
	cd frontend && npm install && npm run dev

frontend-build:
	cd frontend && npm run build

# ── Key rotation ──────────────────────────────────────────────────────────────
rotate-key:
	$(PYTHON) scripts/rotate_api_key.py

rotate-key-safe:
	$(PYTHON) scripts/rotate_api_key.py --keep-old

list-keys:
	$(PYTHON) scripts/rotate_api_key.py --list

# ── Dev environment ───────────────────────────────────────────────────────────
dev-up:
	docker compose -f docker-compose.yml -f docker-compose.override.yml up --build

dev-down:
	docker compose -f docker-compose.yml -f docker-compose.override.yml down

# ── Install dev tools ─────────────────────────────────────────────────────────
install-dev:
	pip install -e ".[dev]"

security:
	bandit -r backend/ -x backend/ingestion,backend/rag,backend/retrieval,backend/orchestration,backend/memory --severity-level medium -f txt
	pip-audit -r requirements.txt

# ── Script tests ──────────────────────────────────────────────────────────────
test-scripts:
	pytest tests/test_scripts.py tests/test_rate_limiter.py -v

test-rate:
	pytest tests/test_rate_limiter.py -v